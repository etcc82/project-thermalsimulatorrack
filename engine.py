"""
coolrack engine - eight liquid-cooled servers sharing one coolant loop.

This file is ONLY the physics. It knows nothing about web pages or drawing.
server.py runs it and streams its state; index.html draws that state.

The loop:

    CDU reservoir --supply--> 8 cold plates in parallel --return--> heat
    exchanger (dumps heat into facility water) --> back to the reservoir

Each server is the same cold plate model as sim.py. What is new is that they
share coolant: if the loop runs warm, every server runs warm.

All numbers are sensible ballparks, not measurements from real hardware.
"""

import math
import threading

WATER_HEAT_CAPACITY = 4180.0  # J per kg per degree C

IDLE_POWER = 150.0  # W, server doing nothing
JOB_POWER = 1000.0  # W, server running a job flat out
THROTTLE_AT = 90.0  # C, chip protects itself above this by halving power
THROTTLE_CLEAR = 80.0  # C, and returns to full power below this


class Server:
    """One GPU with a cold plate. Same maths as ColdPlate in sim.py."""

    def __init__(self, number, start_temp):
        self.number = number
        self.chip_temp = start_temp
        self.outlet_temp = start_temp
        self.job = False
        self.blocked = False
        self.throttled = False
        self.power = IDLE_POWER
        self.flow = 0.0
        self.thermal_mass = 200.0  # J per C

    @property
    def resistance(self):
        # A blocked cold plate transfers heat worse as well as passing less flow.
        return 0.030 if self.blocked else 0.020

    @property
    def openness(self):
        # Share of flow this server takes. A blocked plate lets less through.
        return 0.3 if self.blocked else 1.0

    def step(self, inlet_temp, flow, dt):
        self.flow = flow
        demand = JOB_POWER if self.job else IDLE_POWER

        # The chip protects itself if it gets too hot (with a gap so it
        # does not flicker on and off).
        if self.chip_temp > THROTTLE_AT:
            self.throttled = True
        elif self.chip_temp < THROTTLE_CLEAR:
            self.throttled = False
        self.power = demand * 0.5 if self.throttled else demand

        if flow > 1e-6:
            carry = flow * WATER_HEAT_CAPACITY  # watts carried per degree of rise
            # How much of the chip-to-coolant gap the coolant closes on its way
            # across the plate: nearly all of it when flow is slow, less when
            # it rushes through. It can never exceed 1, so coolant can never
            # leave hotter than the chip. (sim.py used a simpler formula that
            # is fine at normal flow but breaks this rule at very low flow.)
            pickup = 1 - math.exp(-1 / (self.resistance * carry))
            heat_removed = carry * pickup * (self.chip_temp - inlet_temp)
            self.outlet_temp = inlet_temp + pickup * (self.chip_temp - inlet_temp)
        else:
            heat_removed = 0.0  # no flow, no heat leaves
            self.outlet_temp = self.chip_temp

        self.chip_temp += (self.power - heat_removed) * dt / self.thermal_mass
        return heat_removed


class PumpController:
    """Feedback control: measure, compare with the target, adjust.

    This is a PI controller, the workhorse of real cooling plant:
      P (proportional) reacts to how far off target we are right now.
      I (integral) builds up while we stay off target, and removes the
        last bit of error that P alone would leave behind.

    It can only react AFTER the temperature has moved. That lateness is
    the weakness a predictive controller is meant to fix.
    """

    KP = 0.03  # pump speed per degree C of error
    KI = 0.012  # pump speed per degree C of error, per second
    MIN_SPEED = 0.1
    MAX_SPEED = 1.0

    def __init__(self):
        self.integral = 0.0

    def start_from(self, current_speed, measured, target):
        # Begin from where the pump already is, so switching on is smooth.
        self.integral = current_speed - self.KP * (measured - target)

    def update(self, measured, target, dt):
        error = measured - target  # positive means too hot, so pump harder
        wanted = self.KP * error + self.integral
        # Only let the integral build while the pump can still respond.
        # Otherwise it keeps growing at full speed and takes ages to unwind.
        if not (wanted >= self.MAX_SPEED and error > 0) and not (wanted <= self.MIN_SPEED and error < 0):
            self.integral += self.KI * error * dt
        return max(self.MIN_SPEED, min(self.MAX_SPEED, self.KP * error + self.integral))


class Rack:
    """Eight servers, one pump, one heat exchanger."""

    NOMINAL_FLOW = 0.200  # kg/s for the whole rack (0.025 per server)
    RESERVOIR_MASS = 10.0  # kg of coolant in the loop
    FACILITY_TEMP = 25.0  # C, the building's water supply
    EXCHANGER_EFFECTIVENESS = 0.8  # 1.0 would cool coolant all the way to 25 C
    PUMP_RATED_POWER = 150.0  # W of electricity at full speed
    PUMP_RAMP = 0.15  # a real pump cannot change speed instantly: max change per second

    def __init__(self, servers=8):
        self.lock = threading.Lock()
        self.server_count = servers
        self.reset()

    def reset(self):
        self.time = 0.0
        self.supply_temp = self.FACILITY_TEMP + 1.0
        self.return_temp = self.supply_temp
        self.pump_speed = 1.0  # 0..1, what the operator asks for
        self.pump_failed = False
        self.auto = False  # False = operator sets pump speed by hand
        self.target = 60.0  # C, what the controller holds the hottest chip at
        self.controller = PumpController()
        self.heat_rejected = 0.0
        self.servers = [Server(i + 1, self.supply_temp) for i in range(self.server_count)]
        self.events = []
        self.log("Rack started")

    def log(self, message):
        self.events.append({"t": round(self.time, 1), "msg": message})
        self.events = self.events[-12:]

    @property
    def total_flow(self):
        health = 0.4 if self.pump_failed else 1.0
        return self.NOMINAL_FLOW * self.pump_speed * health

    @property
    def hottest(self):
        return max(s.chip_temp for s in self.servers)

    @property
    def pump_power(self):
        # Pump electricity rises with the cube of speed: half speed costs
        # about an eighth of the power. This is why slowing down saves so much.
        return self.PUMP_RATED_POWER * self.pump_speed ** 3

    def step(self, dt):
        if self.auto:
            wanted = self.controller.update(self.hottest, self.target, dt)
            limit = self.PUMP_RAMP * dt
            self.pump_speed += max(-limit, min(limit, wanted - self.pump_speed))

        flow = self.total_flow
        total_openness = sum(s.openness for s in self.servers)

        # Every server draws from the same supply temperature.
        mixed = 0.0
        for s in self.servers:
            share = flow * s.openness / total_openness
            s.step(self.supply_temp, share, dt)
            mixed += share * s.outlet_temp

        if flow > 1e-6:
            # Return water is all the outlets mixed together.
            self.return_temp = mixed / flow
            # The heat exchanger cools it part of the way to facility temperature.
            drop = self.EXCHANGER_EFFECTIVENESS * (self.return_temp - self.FACILITY_TEMP)
            self.heat_rejected = flow * WATER_HEAT_CAPACITY * drop
            cooled = self.return_temp - drop
            # Cooled water flows into the reservoir and nudges its temperature.
            self.supply_temp += flow * (cooled - self.supply_temp) * dt / self.RESERVOIR_MASS
        else:
            self.heat_rejected = 0.0

        self.time += dt

    # ----- things the operator can do -------------------------------------

    def set_job(self, target, on):
        for s in self.servers:
            if target == "all" or s.number == target:
                s.job = on
        who = "all servers" if target == "all" else "server %s" % target
        self.log("Job %s on %s" % ("started" if on else "stopped", who))

    def set_blocked(self, number, on):
        for s in self.servers:
            if s.number == number:
                s.blocked = on
        self.log("Cold plate %s on server %s" % ("blocked" if on else "cleared", number))

    def set_pump_failed(self, on):
        self.pump_failed = on
        self.log("Pump failure: flow down to 40%" if on else "Pump repaired")

    def set_pump_speed(self, value):
        if not self.auto:  # in automatic, the controller owns the pump
            self.pump_speed = max(0.1, min(1.0, float(value)))

    def set_auto(self, on):
        self.auto = on
        if on:
            self.controller.start_from(self.pump_speed, self.hottest, self.target)
        self.log("Automatic control on, holding %d C" % self.target if on else "Manual control")

    def set_target(self, value):
        self.target = max(45.0, min(80.0, float(value)))

    # ----- what the outside world sees ------------------------------------

    def snapshot(self):
        return {
            "time": round(self.time, 1),
            "supply": round(self.supply_temp, 2),
            "return": round(self.return_temp, 2),
            "facility": self.FACILITY_TEMP,
            "flow": round(self.total_flow, 4),
            "nominal_flow": self.NOMINAL_FLOW,
            "pump_speed": self.pump_speed,
            "pump_failed": self.pump_failed,
            "pump_power": round(self.pump_power, 1),
            "auto": self.auto,
            "target": self.target,
            "it_power": round(sum(s.power for s in self.servers)),
            "heat_rejected": round(self.heat_rejected),
            "throttle_at": THROTTLE_AT,
            "servers": [
                {
                    "n": s.number,
                    "chip": round(s.chip_temp, 1),
                    "out": round(s.outlet_temp, 1),
                    "power": round(s.power),
                    "flow": round(s.flow, 4),
                    "job": s.job,
                    "blocked": s.blocked,
                    "throttled": s.throttled,
                }
                for s in self.servers
            ],
            "events": list(self.events),
        }
