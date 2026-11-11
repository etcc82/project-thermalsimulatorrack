"""
coolrack - step 1: one GPU, one cold plate, one stream of coolant.

Run it:   python sim.py
Output:   step1.png (chip and coolant temperatures over time)

The whole model is two ideas:

1. Heat flows from the hot chip into the cooler liquid. How easily it flows
   is set by a "thermal resistance" R (degrees C per watt). Lower R = better
   cold plate.

2. The liquid warms up as it carries heat away:
       heat (W) = flow (kg/s) x heat capacity (J/kg.C) x temperature rise (C)

Everything else is bookkeeping.
"""

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

WATER_HEAT_CAPACITY = 4180.0  # J per kg per degree C


@dataclass
class ColdPlate:
    """One GPU with a cold plate bolted on top.

    These numbers are sensible ballparks, not measurements from real hardware.
    """

    resistance: float = 0.020  # C per W, chip -> liquid
    thermal_mass: float = 200.0  # J per C, how much heat the metal soaks up
    chip_temp: float = 30.0  # C, starting temperature

    def step(self, power_w: float, inlet_temp: float, flow_kg_s: float, dt: float):
        """Advance the model by dt seconds. Returns (heat_removed_w, outlet_temp)."""
        carry = flow_kg_s * WATER_HEAT_CAPACITY  # watts carried per degree of rise

        # The liquid warms as it crosses the plate, so the chip "sees" the
        # average liquid temperature. Solving for heat removed gives the line
        # below. This shortcut is fine at normal flow; engine.py uses the
        # fuller version that also behaves at very low flow.
        heat_removed = (self.chip_temp - inlet_temp) / (self.resistance + 1 / (2 * carry))

        outlet_temp = inlet_temp + heat_removed / carry

        # Whatever heat is not removed warms the chip up (or cools it, if negative).
        self.chip_temp += (power_w - heat_removed) * dt / self.thermal_mass
        return heat_removed, outlet_temp


def workload(t: float) -> float:
    """GPU power draw in watts at time t (seconds). A job starts at 60s."""
    if t < 60:
        return 150.0  # idle
    if t < 240:
        return 1000.0  # training job running flat out
    return 300.0  # light inference


def run(flow_kg_s, seconds=360, dt=0.1, inlet_temp=30.0):
    """Simulate one scenario. flow_kg_s is a function of time."""
    plate = ColdPlate(chip_temp=inlet_temp)
    times, chip, outlet, power = [], [], [], []
    for i in range(int(seconds / dt)):
        t = i * dt
        p = workload(t)
        _, out = plate.step(p, inlet_temp, flow_kg_s(t), dt)
        times.append(t)
        chip.append(plate.chip_temp)
        outlet.append(out)
        power.append(p)
    return times, chip, outlet, power


def healthy_flow(t):
    return 0.025  # kg/s, about 1.5 litres a minute


def failing_pump(t):
    # Pump loses 60% of its flow at t=150s, mid-job.
    return 0.025 if t < 150 else 0.010


if __name__ == "__main__":
    t, chip_ok, out_ok, power = run(healthy_flow)
    _, chip_bad, out_bad, _ = run(failing_pump)

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

    top.plot(t, power, color="#444")
    top.set_ylabel("GPU power (W)")
    top.set_title("One GPU on one cold plate")

    bottom.plot(t, chip_ok, label="Chip, healthy pump", color="#1f77b4")
    bottom.plot(t, out_ok, label="Coolant out, healthy pump", color="#1f77b4", linestyle="--")
    bottom.plot(t, chip_bad, label="Chip, pump fails at 150s", color="#d62728")
    bottom.plot(t, out_bad, label="Coolant out, pump fails", color="#d62728", linestyle="--")
    bottom.axvline(150, color="#d62728", alpha=0.3)
    bottom.set_ylabel("Temperature (C)")
    bottom.set_xlabel("Time (s)")
    bottom.legend(fontsize=8)
    bottom.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig("step1.png", dpi=150)

    print(f"Healthy pump, peak chip temp:  {max(chip_ok):.1f} C")
    print(f"Failing pump, peak chip temp:  {max(chip_bad):.1f} C")
    print(f"Healthy pump, peak coolant out: {max(out_ok):.1f} C")
    print("Saved step1.png")
