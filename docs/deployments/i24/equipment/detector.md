# Detector

*The Eiger and the commissioning Jungfrau, the detector translation, and the Zebra timing that gates the chip raster. Design-phase; values are reverse-engineered from dodal or inferred.*

i24's detection is the serial-crystallography shape: one large area detector on a translation, plus a Zebra timing controller that hardware-gates the per-window exposure as the fixed-target chip is rastered across the beam. There is no rotation here, so the detector takes one diffraction snapshot per addressable chip window rather than a continuous sweep. The devices are modelled in the detection stage of the [descriptor](../inventory.md).

## The detectors

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `EigerDetector` | `Camera` | Detector | `BL24I-EA-EIGER-01:CAM:` | Eiger area detector, the production serial-collection detector |
| `JungfrauDetector` | `Camera` | Detector | `BL24I-EA-JFRAU-01:` | a Jungfrau area detector, carried as commissioning |
| `DetectorStage` | `LinearStage` | Positioner | `BL24I-MO-DET-01:` | detector translation (Y / Z); sets the detector distance / position |
| `Timing` | `TimingController` | (Controller) | `BL24I-EA-ZEBRA-01:` | Zebra FPGA timing that TTL-gates the per-window exposure during the chip raster |

## How each maps onto CORA

- **The Eiger reuses `Camera`.** A pixel-array area detector is the Camera Family presenting the Detector Role, the same shape the imaging pilots and I03 use; the photon-counting specifics and the beam-centre are calibration dodal does not carry (DET-1). dodal exposes a DetectorBeamCenter helper at this handle, but the full detector configuration and beam-centre stay open (DET-1).
- **The Jungfrau is carried as commissioning.** It reuses `Camera` (Detector Role) as well, but dodal carries it as a CommissioningJungfrauDetector, so CORA models the Eiger path as primary and the Jungfrau as the second detector pending (DET-1).
- **The detector motion is a Positioner.** The translation stage reuses `LinearStage`; it sets the detector distance / position along Y / Z. The axis roles are calibration to confirm (OPT-2).
- **The Zebra is the `TimingController`.** It hardware-sequences the chip-raster collection, TTL-gating the detector and the fast sample shutter so one diffraction snapshot is taken per addressable chip window. The detailed trigger graph, the per-window dwell, and the raster pattern are the serial-collection seam CORA's edge drives, not a device property, and are carried as the open SSX-1.

## Families

The Eiger and the Jungfrau reuse `Camera`; the detector motion reuses `LinearStage`; the Zebra reuses `TimingController`. No new Family is earned on the detector side, which is the families-only outcome i24 carries across the whole descriptor. See [Inventory](../inventory.md) for the Asset tree, [Open questions](../questions.md) for the detector configuration and serial timing still to confirm, and the [Family catalog](../../../catalog/families.md) for the shared definitions.
