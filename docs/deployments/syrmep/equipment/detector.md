# Detector

*How SYRMEP converts and records the transmitted beam: a scintillator and area cameras on a long sample-to-detector propagation rail. First cut, reverse-engineered.*

SYRMEP's detector station is built for propagation-based phase contrast: the long sample-to-detector rail lets the beam propagate before it is recorded, turning phase gradients into measurable intensity. The scintillator converts X-rays to visible light, which the area camera records.

## The propagation rail

`PropagationRail` binds the catalog [`LinearStage`](../../../catalog/families.md): the sample-to-detector distance (3-160 cm), the phase-contrast propagation axis, not a focus stage (the 2-BM `CameraZ` precedent). The two-axis detector rail handles are pending (`DET-2`).

## The scintillator and cameras

`Scintillator` binds [`Scintillator`](../../../catalog/families.md): the screen that converts the transmitted X-rays to visible light (published configurations cite a GGG:Eu screen; the routine screen type and thickness are `DET-3`).

SYRMEP runs more than one area detector, each binding [`Camera`](../../../catalog/families.md):

- `TomographyCamera`: a 16-bit sCMOS (2048x2048 px, effective pixel 0.9-5.7 um via selectable optics; published configs name a Hamamatsu Orca Flash).
- `CCDCamera`: a 12/16-bit CCD (4008x2672 px, 4.5 um pixel, PSF ~13 um).
- `PhotonCountingCamera`: the XC Hydra photon-counting detector (Direct Conversion AB), used for large-specimen and helical CT (J. Synchrotron Rad. 2023); its pixel size is `DET-4`.

Which camera is the default routine-tomography detector, and its pixel size and field of view, is pending (`DET-1`).

## Pending

| Value to confirm | Applies to | Tracking |
| --- | --- | --- |
| The default routine-tomography camera, pixel size, and field of view | `TomographyCamera` / `CCDCamera` | `DET-1` |
| The propagation rail and two-axis detector rail handles | `PropagationRail` | `DET-2` |
| The routine scintillator screen type and thickness | `Scintillator` | `DET-3` |
| The XC Hydra photon-counting detector pixel size and when it is used | `PhotonCountingCamera` | `DET-4` |
