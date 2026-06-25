# Operations

*How CORA would get ready and measure at FXI, and the supplies a run draws on. This is CORA's runbook design, not a transcription of the beamline's current operating procedure.*

Operations ties together the procedures, recipes, enclosures, and cautions into the act of running a measurement under CORA.

## The runbook

- [Procedures](procedures.md): staff-run sequences (energy-lookup calibration, rotation-center finding, focus alignment) that produce the Calibrations a scan needs.
- [Recipes](recipes.md): deployment-bound step sequences (energy setting, dark/flat capture, element-edge XANES) that expand into Procedures.
- [Enclosures](enclosures.md): the two hutch permits, optics hutch `18-IDA` and experiment hutch `18-IDB`.
- [Cautions](cautions.md): the quirks to know (cross-wired zone-plate / Bertrand-lens Y axes, flaky shutter, Zebra overflow, camera staging timeout).

A typical fly-tomography run, as CORA would conduct it: confirm the hutch permit and the energy-lookup Calibration; set the energy (the [energy-setting recipe](recipes.md)); capture dark and flat references; arm the position-trigger against the rotary; run the continuous-rotation fly scan; reconstruct. The staging is CORA's Conductor, acting over the EPICS floor through the ControlPort; see [Controls](equipment/controls.md#the-seam-cora-and-the-floor).

## Supplies

Continuously-available resources a run draws on. Facility-scope supplies are owned by the [NSLS-II Site](../nsls2/index.md); the beamline draws on them.

| Supply | Kind | How observed |
| --- | --- | --- |
| Photon beam | PhotonBeam | storage-ring current (`SR:*`, Site-scope) |
| Cooling water | CoolingWater | beamline cooling loop |
| Vacuum | Vacuum | `XF:18IDB-UT{V...}` gate/cryo valves |
| Liquid nitrogen | LiquidNitrogen | DCM crystal cooling (`XF:18IDA-UT` Cryo:1 levels/flow; valves V4/V5) |
| Power | Power | beamline power |

The data a run produces is recorded as a CORA Dataset (CORA's own data of record); the raw frames land on the facility filestore and are moved into that Dataset over CORA's `TransferPort` (the transfer leg). See [Experiment > Datasets](experiment.md#datasets).
