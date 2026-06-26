# Detector

*The Eiger, the beamstops, the sample backlight, and the hardware triggers, across both experiment hutches. Design-phase; values are reverse-engineered from dodal, carried `confirm`.*

i19's detection side is the chemical-crystallography counterpart of the MX shape: one Eiger area detector that records the single-crystal diffraction pattern, a beamstop in each experiment hutch, a sample backlight for on-axis viewing, and the FPGA timing boxes that fan out the hardware triggers. The detector itself lives in EH2 with the four-circle; a beamstop and a trigger box sit in each of EH1 and EH2 (which hutch holds what is an Enclosure question, ENC-1). They are modelled in the detection stage of the [descriptor](../inventory.md).

## The detection devices

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `Detector` | `Camera` | Detector | `BL19I-EA-EIGER-01:` | the Eiger area detector, the single-crystal diffraction science detector (EH2) (DET-1) |
| `BeamstopEH1` | `BeamStop` | Positioner | `BL19I-RS-ABSB-01:` | the EH1 beamstop, with homing (DET-1) |
| `BeamstopEH2` | `BeamStop` | Positioner | `BL19I-OP-ABSB-02:` | the EH2 beamstop, with homing (DET-1) |
| `Backlight` | `Backlight` (loose) | Positioner | `BL19I-EA-IOC-12:` | sample backlight, in / out illumination for OAV centring (EH2); held under review (DET-1) |
| `TriggerControllerEH1` | `TimingController` | Sequencer | `BL19I-EA-ZEBRA-02:` | the EH1 Zebra (DET-1) |
| `TriggerControllerEH2` | `TimingController` | Sequencer | `BL19I-EA-ZEBRA-03:` | the EH2 Zebra (DET-1) |
| `TriggerSequencer` | `TimingController` | Sequencer | `BL19I-EA-PANDA-01:` | the EH2 PandA (DET-1) |

The 2theta detector arm and the reciprocal-space pseudo-axis are not detection Assets: they ride the Newport kappa four-circle on the sample side. See [Beamline](../beamline.md) for the source walk and [Sample](sample.md) for the four-circle and its arm.

## How each maps onto CORA

- **The Eiger reuses `Camera`.** A pixel-array area detector is the Camera Family presenting the Detector Role, the same shape i03's Eiger and the imaging pilots use; here it records the single-crystal diffraction pattern from the four-circle in EH2. The photon-counting specifics (threshold energy) and the beam center are calibration dodal does not carry (DET-1).
- **Both beamstops reuse `BeamStop`.** Each experiment hutch carries one beamstop ahead of the detector path; the homing behaviour is a Positioner affordance on the same mount, not a separate Family. The two are distinct Assets because they are distinct devices in distinct hutches (ENC-1), not a Family split. Their in-position calibration is to confirm (DET-1).
- **The triggers reuse `TimingController`.** Each hutch has a Zebra; EH2 adds a PandA. All three bind the `TimingController` Family, the same one the 2-BM Timing device and i03's / I22's Zebra and PandA boxes use, confirming that "timing-generation is a first-class device" generalizes across APS and Diamond. The PandA-versus-Zebra distinction is a bound-Model difference on one Family, not two Families (DET-1); which box drives which acquisition is a Method concern, not an Asset one.
- **The backlight presents the Positioner Role, carried loose.** The in / out illumination for OAV centring has no existing Family with an illumination affordance, so it binds the loose `Backlight` family that i03 introduced. This is the 4th sighting (after i03 / i24 / fmx); the family is held under review and is earned to the catalog only on a confirmed rule-of-three, so i19 carries it loose for now (DET-1).

Pin-tip recognition for OAV centring is a Method behaviour over the on-axis viewer and backlight, not a device; the viewing cameras themselves are on the sample side.

## Why no new family

The detection side coins nothing. The Eiger is `Camera` reuse; both beamstops are `BeamStop` reuse; all three trigger boxes are `TimingController` reuse with the PandA / Zebra split living in a bound Model rather than in a new Family. The backlight reuses the loose `Backlight` family rather than minting a fresh one, and stays held pending a rule-of-three (DET-1). No new Family is earned on the detector side and nothing graduates; the catalog is unchanged.

See [Families](../../../catalog/families.md) for the bound Families, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the modelling decisions, and the [Diamond Site](../../diamond/index.md#the-techniques-adapted-here) for where i19's detection sits among the fleet's diffraction beamlines.
