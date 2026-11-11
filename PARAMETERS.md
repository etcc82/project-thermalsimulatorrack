# Hardware parameters and where they come from

The target hardware is the **NVIDIA GB200 NVL72** rack. This file records every
number the model uses or will use, the document it came from, and how far it
can be trusted.

Status as of 11 November 2026: research only. `engine.py` still runs on
placeholder values and has not been re-parameterised to these figures yet.

**How these were gathered.** Values were extracted from the linked documents by
an automated reader. Before any figure is quoted outside this repo, open the
document and confirm it by eye.

The file is in four tiers, strongest first: primary documents, a consistency
check, estimates derived from third-party data, and what is still missing.

## 1. From primary documents

### The rack

| Parameter | Value | Source |
|---|---|---|
| Rack power | "approximately 120kW" | NVIDIA DGX GB Rack Scale Systems User Guide, 17 Sep 2026 |
| Rack TDP (HPE build) | 132 kW | HPE QuickSpecs a50009224enw, version 5, 20 Jul 2026 |
| Peak electrical design power (HPE build) | "approximately 192 kW" (1.5 × TDP) | same |
| Heat to liquid / to air (HPE build) | 115 kW / 17 kW | HPE product page (not in the QuickSpecs) |
| Compute trays | 18, each 1RU | NVIDIA guide; HPE QuickSpecs |
| NVLink switch trays | 9, each 1RU | NVIDIA guide; HPE QuickSpecs |
| Per compute tray | 2 Grace CPUs, 4 Blackwell GPUs | NVIDIA guide; HPE QuickSpecs |
| Liquid cooled | CPUs and GPUs in compute trays, via rack manifolds and cold plates | NVIDIA guide; HPE QuickSpecs |
| Air cooled | Networking and storage in compute trays; power shelves | NVIDIA guide |
| Switch tray cooling | Not stated in either document | |
| Power shelves | 8 × 33 kW (NVIDIA); 6, max 8, × 33 kW (HPE) | NVIDIA guide; HPE QuickSpecs |
| Rack | 48U; liquid manifold 44U, top-feed or bottom-feed kits | HPE QuickSpecs |
| Weight, fully loaded | 3245 lb (about 1472 kg) | HPE QuickSpecs |
| Row CDU offered | Vertiv XDU1350, liquid-to-liquid, "rated for 1.3 MW", max 8 racks (162.5 kW per rack) | HPE QuickSpecs |
| Maximum liquid inlet temperature | 45 °C | QCT QoolRack Stand-alone paper (undated) |
| Maximum liquid return temperature | 65 °C | same |
| Coolant flow | "up to 130 LPM per rack" | same |

### A published operating point for this rack

From the nVent RackChiller CDU800 specification (nVent-SPEC-01468, 2025),
reference point for **5 GB200 NVL72 racks**:

| Parameter | Value | Per rack |
|---|---|---|
| Cooling capacity | 575 kW | 115 kW |
| Secondary (rack side) flow | 690 LPM, 1.2 LPM/kW | 138 LPM |
| Secondary fluid | PG25 | |
| Secondary supply / return | 45 °C / 57.4 °C | rise of 12.4 °C |
| Approach temperature difference | 4 K | |
| Primary (facility) fluid | Water, 985 LPM, supplied at 41 °C | |
| CDU secondary fluid volume | 100 L | |
| CDU power consumption | 22.2 kW (whole unit, 800 kW class) | |

This is the best validation target found so far: a complete, self-consistent
set of flow, temperature and heat for the exact rack.

### A single-rack CDU

Vertiv CoolChip CDU 121, datasheet SL-71348 (R01/26):

| Parameter | Value |
|---|---|
| Nominal cooling capacity | 121 kW at 4 °C approach |
| Nominal secondary flow | 120 l/min at 1.15 bar |
| Fluid | Water or PG-25 with inhibitors |
| Secondary circuit volume | 7.2 L |
| Primary circuit volume | 3.4 L |
| Secondary temperature control | within ±1 °C |
| Nominal power consumption | 875 W (AC), 860 W (DC) |
| Size | 4U, in-rack |

## 2. Consistency check

Heat = mass flow × heat capacity × temperature rise. Using textbook
approximations for PG25 near 51 °C (density 1008 kg/m³, heat capacity
3960 J/kg·K):

| Published point | Heat the equation gives | Published heat | Difference |
|---|---|---|---|
| nVent: 690 LPM, 45 → 57.4 °C | 569 kW | 575 kW | 1.0% low |

The published numbers obey the physics to within the accuracy of the fluid
properties. The same equation explains why sources quote different flows:

| Heat | Flow | Implied rise |
|---|---|---|
| 115 kW | 138 LPM (nVent) | 12.4 °C |
| 115 kW | 130 LPM (QCT) | 13.3 °C |
| 121 kW | 120 l/min (Vertiv) | 15.2 °C |
| 115 kW | 86 LPM | 20 °C (the full 45 → 65 °C envelope) |

They are different design points on one curve, not disagreements.

## 3. Estimates derived from third-party data

Nothing in this section comes from NVIDIA. Each item says what it rests on.

### Cold plate thermal resistance

Basis: ToneCooling's GB200-compatible kit (TC-BZP-GB200-01A), one kit per
superchip (two GPU plates and one Grace CPU plate on one manifold).

| Vendor figure | Value |
|---|---|
| Heat load | 1,200 W + 1,200 W + 300 W = 2,700 W |
| Flow | 2.5 L/min, pure water |
| Inlet | 25 ± 2 °C |
| Cold plate surface | "below 43 °C" |
| Pressure drop | 35 ± 5 kPa |

Two different resistances come out of this, and they must not be mixed up:

| Quantity | At 25 °C inlet | Across the ±2 °C inlet tolerance |
|---|---|---|
| Surface to **inlet** coolant: (43 − 25) / 2700 | 0.0067 K/W | 0.0059 to 0.0074 K/W |
| Plate resistance as `engine.py` uses it | 0.0029 K/W | 0.0016 to 0.0038 K/W |

Why they differ: at 2,700 W and 2.5 L/min the water itself warms by 15.5 °C,
leaving at about 40.5 °C. Most of the 18 °C between inlet and surface is the
coolant heating up, not resistance in the plate. `engine.py` models coolant
warming separately, so feeding it 0.0067 would count that warming twice. The
engine value is the one to use.

Limits of this estimate:

- "Below 43 °C" is a ceiling, so these are upper bounds on resistance.
- The result is very sensitive to the inlet tolerance (see the range), because
  the surface sits only about 2.5 °C above the outlet water.
- It is the cold plate **surface**, not the chip junction. The resistance from
  junction to plate (the chip package and thermal paste) is unknown, so the
  model can report plate surface temperature, not GPU temperature.
- The page does not say whether the figures are measured or design targets,
  and its own component table lists about 500 W per GPU against the 1,200 W
  plate rating without reconciling them. Treat as low confidence.
- It is per superchip kit (2 GPUs + 1 CPU), in pure water, not PG25.

### How the 115 kW of liquid heat divides

| Assumption | GPUs + CPUs | Share of 115 kW | Unaccounted |
|---|---|---|---|
| GPUs at 1,000 W, CPU plates at 300 W | 82.8 kW | 72% | 32.2 kW |
| GPUs at 1,200 W, CPU plates at 300 W | 97.2 kW | 85% | 17.8 kW |

So GPU and CPU cold plates account for roughly 72 to 85% of the liquid heat.
Between 18 and 32 kW goes somewhere else on the liquid loop, most plausibly the
nine NVLink switch trays, but no primary document confirms that they are liquid
cooled or gives their power. A separate trade article puts each compute node at
5.4 to 5.7 kW (97 to 103 kW for 18), which sits at the top of this range.

### Flow per superchip

| Basis | Flow |
|---|---|
| Vendor kit rating (ToneCooling) | 2.5 L/min |
| Whole-rack flow shared across 36 superchips: 138 / 36 | 3.8 L/min |

The second figure is an upper bound: it assumes every litre goes through the
compute cold plates. At 2.5 L/min, 36 kits take 90 LPM, leaving 48 LPM of the
138 for anything else on the loop.

## 4. Unconfirmed claims from trade articles

| Claim | Value | Note |
|---|---|---|
| GPU power | 1,000 W or 1,200 W | Sources differ; no NVIDIA figure found |
| NVLink switch trays liquid cooled | Yes | Several articles say so; neither primary document states it |
| Flow "around 2 litres per second" | 120 LPM | Attributed to NVIDIA or suppliers, no document named |
| Junction temperature held below 75 °C | | One article, citing an NVIDIA URL that could not be confirmed |
| Inlet 20 to 25 °C, 80 LPM, 1.5 bar max drop | | Same article; conflicts with the 45 °C figures above |

## 5. Not found

- **GPU temperature limits** (throttle and shutdown thresholds). Not in NVIDIA's
  guide, HPE's QuickSpecs or the cold plate vendor's page. No value should be
  assumed. The 90 °C throttle point currently in `engine.py` is a placeholder
  and must be labelled as one wherever results are shown.
- **Junction-to-plate resistance**, needed to turn plate temperature into GPU
  temperature.
- **Switch tray cooling and power.**
- **Rack pressure drop** from a primary source. The manifold layout is known
  (44U, top or bottom feed); the pressure figures are not.
- **Thermal mass** of cold plates and trays (sets how fast temperatures move).
  Could be estimated later from copper mass and coolant volume.
- **CDU pump curves** (flow against pressure, power against speed).

## 6. What changes in the model

1. 18 compute trays in place of 8 servers, two superchip kits per tray.
2. 115 kW to liquid. The 17 kW to air is outside the model and should be stated.
3. PG25 coolant in place of water (lower heat capacity, slightly denser).
4. Supply at 45 °C, not 25 to 30 °C. This is warm-water cooling: every
   temperature in the model moves up by about 15 to 20 °C.
5. Plate resistance of about 0.003 K/W per superchip kit, labelled as an
   estimate, with 0.0016 to 0.0038 K/W as the range to test across.
6. An extra heat load of 18 to 32 kW on the loop that is not GPU or CPU.
7. Validation test: at 115 kW and 138 LPM with 45 °C supply, the model's return
   temperature must come out at 57.4 °C.
8. Report cold plate surface temperature, not GPU temperature, until a
   junction-to-plate figure is found.

## Sources

- NVIDIA DGX GB Rack Scale Systems User Guide: https://docs.nvidia.com/dgx/dgxgb200-user-guide/dgxgb200-user-guide.pdf
- HPE QuickSpecs a50009224enw: https://www.hpe.com/psnow/doc/a50009224enw.pdf
- HPE, NVIDIA GB200 NVL72 by HPE: https://buy.hpe.com/us/en/compute/rack-scale-system/nvidia-nvl-system/nvidia-gb200-nvl72-by-hpe/p/1014890104
- QCT QoolRack Stand-alone paper: https://blog.qct.io/wp-content/uploads/2025/04/QCT-Qoolrack-Stand-Alone_Advanced-Liquid-Cooling-for-NVIDIA-GB200-NVL72-Systems.pdf
- nVent RackChiller CDU800 specification: https://origin-nvent.nvent.com/sites/default/files/acquiadam/assets/HOFFMAN-SPEC-01468-RackChillerCDU800-EN.pdf
- Vertiv CoolChip CDU 121 datasheet: https://www.vertiv.com/4932ce/globalassets/shared/vertiv-coolchip-cdu-100_datasheet_en.pdf
- ToneCooling GB200 cold plate kit: https://tonecooling.com/nvidia-gb200-nvl72-cooling-requirements/
