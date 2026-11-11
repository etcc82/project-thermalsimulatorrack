"""
Checks that the engine obeys the physics. Run:  python3 test_engine.py

The big one is energy balance: once things settle, heat leaving through the
heat exchanger must equal the electrical power going in. If it does not,
the model is creating or destroying energy and cannot be trusted.
"""

import math

from engine import Rack, WATER_HEAT_CAPACITY


def settle(rack, seconds=1500, dt=0.05):
    for _ in range(int(seconds / dt)):
        rack.step(dt)


def test_energy_balance():
    rack = Rack()
    rack.set_job("all", True)
    settle(rack)
    snap = rack.snapshot()
    assert abs(snap["heat_rejected"] - snap["it_power"]) < 5, snap
    print("energy balance ok: %d W in, %d W out" % (snap["it_power"], snap["heat_rejected"]))


def test_matches_hand_calculation():
    rack = Rack()
    rack.set_job("all", True)
    settle(rack)
    flow = rack.total_flow
    rise = 8000 / (flow * WATER_HEAT_CAPACITY)
    # supply = return - 0.8 * (return - 25), with return = supply + rise
    supply = (0.2 * rise + 20) / 0.8
    carry = 0.025 * WATER_HEAT_CAPACITY
    chip = supply + 1000 / (carry * (1 - math.exp(-1 / (0.020 * carry))))
    assert abs(rack.supply_temp - supply) < 0.05, (rack.supply_temp, supply)
    assert abs(rack.servers[0].chip_temp - chip) < 0.05, (rack.servers[0].chip_temp, chip)
    print("hand calculation ok: supply %.1f C, chip %.1f C" % (supply, chip))


def test_blocked_plate_runs_hotter_and_warms_nobody_else_much():
    rack = Rack()
    rack.set_job("all", True)
    settle(rack)
    before = rack.servers[1].chip_temp
    rack.set_blocked(1, True)
    settle(rack)
    assert rack.servers[0].chip_temp > before + 10
    assert rack.servers[1].chip_temp < before  # others get a little more flow
    print("blocked plate ok: server 1 at %.1f C, server 2 at %.1f C" % (
        rack.servers[0].chip_temp, rack.servers[1].chip_temp))


def test_pump_failure_plus_blockage_throttles():
    rack = Rack()
    rack.set_job("all", True)
    rack.set_blocked(1, True)
    rack.set_pump_failed(True)
    hit = False
    for _ in range(int(600 / 0.05)):
        rack.step(0.05)
        hit = hit or rack.servers[0].throttled
    assert hit
    assert max(s.chip_temp for s in rack.servers) < 95
    print("throttle ok: protection engaged, hottest chip stayed under 95 C")


def test_coolant_never_leaves_hotter_than_the_chip():
    # Heat only flows from hot to cold, so this must hold at any flow.
    rack = Rack()
    rack.set_job("all", True)
    rack.set_pump_speed(0.1)
    for _ in range(int(300 / 0.05)):
        rack.step(0.05)
        for s in rack.servers:
            assert s.outlet_temp <= s.chip_temp + 1e-9
    print("second law ok: coolant never left hotter than the chip, even at 10% flow")


def test_controller_holds_target_and_saves_pump_power():
    rack = Rack()
    rack.set_auto(True)
    rack.set_job("all", True)
    settle(rack, 600)
    assert abs(rack.hottest - rack.target) < 0.3, rack.hottest
    assert rack.pump_power < 0.25 * rack.PUMP_RATED_POWER
    print("controller ok: holds %.1f C at %d%% speed, pump using %.0f W of %.0f W" % (
        rack.hottest, rack.pump_speed * 100, rack.pump_power, rack.PUMP_RATED_POWER))


def test_controller_recovers_after_being_maxed_out():
    # A blocked plate pins the pump at 100% and it still cannot reach target.
    # When the blockage clears, it must come back down promptly (no wind-up).
    rack = Rack()
    rack.set_auto(True)
    rack.set_job("all", True)
    rack.set_blocked(3, True)
    settle(rack, 300)
    assert rack.pump_speed > 0.99 and rack.hottest > rack.target + 5
    rack.set_blocked(3, False)
    settle(rack, 120)
    assert abs(rack.hottest - rack.target) < 1.5, rack.hottest
    print("recovery ok: back to %.1f C two minutes after the blockage cleared" % rack.hottest)


if __name__ == "__main__":
    test_coolant_never_leaves_hotter_than_the_chip()
    test_controller_holds_target_and_saves_pump_power()
    test_controller_recovers_after_being_maxed_out()
    test_energy_balance()
    test_matches_hand_calculation()
    test_blocked_plate_runs_hotter_and_warms_nobody_else_much()
    test_pump_failure_plus_blockage_throttles()
    print("all checks passed")
