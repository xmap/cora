# Operations

*The runbook for getting ready and measuring at FXI, and the supplies a run draws on. Reverse-engineered from the profile collection.*

Operations ties together the procedures, recipes, enclosures, and cautions into the act of running a measurement.

## The runbook

- [Procedures](procedures.md): staff-run sequences (energy-lookup calibration, rotation-center finding, focus alignment) that produce the Calibrations a scan needs.
- [Recipes](recipes.md): deployment-bound step sequences (energy_setting, dark/flat capture, element-edge XANES) that expand into Procedures.
- [Enclosures](enclosures.md): the two hutch permits, optics hutch `18-IDA` and experiment hutch `18-IDB`.
- [Cautions](cautions.md): the quirks to know (cross-wired ZP/Bertrand Y axes, flaky shutter, Zebra overflow, camera staging timeout).

A typical fly-tomography run: confirm the hutch permit and the energy-lookup Calibration; set energy via the `energy_setting` recipe; capture dark and flat references; arm the Zebra against the rotary; run the continuous-rotation fly scan; reconstruct (Reckoner / TomoPy). The staging ceremony is the Conductor's, over the `ControlPort`; see [Controls](equipment/controls.md#the-seam-cora-and-the-epics-floor).

## Supplies

Continuously-available resources a run draws on. Facility-scope supplies are owned by the [NSLS-II Site](../nsls2/index.md); the beamline draws on them.

| Supply | Kind | How observed |
| --- | --- | --- |
| Photon beam | PhotonBeam | storage-ring current (`SR:*`, Site-scope) |
| Cooling water | CoolingWater | beamline cooling loop |
| Vacuum | Vacuum | `XF:18IDB-UT{V...}` gate/cryo valves |
| Liquid nitrogen | LiquidNitrogen | DCM crystal cooling (`XF:18IDA-UT` Cryo:1 levels/flow; valves V4/V5) |
| Power | Power | beamline power |

Datasets land in Tiled (`tiled.nsls2.bnl.gov`, catalog `fxi`) under `/nsls2/data/fxi-new/...`; CORA references the Tiled resource as the Dataset source-of-record but does not own the archive. Dataset checksum/integrity is not in the resource docs (DATA-1).
