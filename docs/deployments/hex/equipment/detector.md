# Detector

*The Kinetix sCMOS imaging cameras and their scintillator-lens table, the Phantom Veo high-speed camera, the PerkinElmer flat panel for angle-dispersive diffraction, the GeRM germanium strip detector for energy-dispersive diffraction, and the detector / optics positioning that switches technique. Reverse-engineered from `NSLS2/hex-profile-collection` (`startup/*.py`) and `NSLS2/hextools`; the endstation detector PVs are read from the profile collection, carried confirm.*

HEX's detection side is where its multi-technique character lives: one endstation hosts imaging / tomography, energy-dispersive diffraction (EDXD), and angle-dispersive diffraction (ADXD), and the detectors and optics are moved into the beam remotely per technique. Every device on this side binds an existing catalog Family, and the technique switch is a positioning leg over existing devices, so this page coins nothing.

## Detection chain

| Device | Family | PV | Role |
| --- | --- | --- | --- |
| `ImagingCamera` | `Camera` | `XF:27ID1-BI{Kinetix-Det:N}` | the Teledyne Photometrics Kinetix sCMOS cameras (kinetix1 default, kinetix3 alternate) for imaging and tomography (`DET-3`) |
| `ImagingScintillator` | `Scintillator` | the imaging scintillator-lens table | converts the X-ray image for the sCMOS cameras; magnification positions "2 & 4 mm", "20 & 40 mm", "Dual cam" (`DET-3`) |
| `HighSpeedCamera` | `Camera` | the Phantom Veo | high-speed / time-resolved radiography (`DET-3`) |
| `FlatPanelDetector` | `Camera` | `XF:27ID1-ES{PE-Det:1}` | the PerkinElmer XRD1621 amorphous-silicon flat panel; inferred angle-dispersive / powder-diffraction (ADXD) detector (`DET-1`) |
| `EnergyDispersiveDetector` | `EnergyDispersiveSpectrometer` | `XF:27ID1-ES{GeRM-Det:1}` | the GeRM germanium strip detector for energy-dispersive diffraction (EDXD) (`DET-2`) |
| `DetectorStage` | `LinearStage` | the detector / optics positioning | moves the chosen detector or optic into the beam per technique (`TECH-1`, `DET-1`) |

The chain reads outward from the sample. For imaging and tomography, the X-ray image lands on a scintillator on the `ImagingScintillator` table (selectable magnifications behind the "2 & 4 mm", "20 & 40 mm", and "Dual cam" positions), and the visible image is read by the Kinetix `ImagingCamera`; for fast or in-situ work the `HighSpeedCamera` (Phantom Veo) records time-resolved radiography. For monochromatic angle-dispersive diffraction the `FlatPanelDetector` (the PerkinElmer flat panel) records the 2D powder pattern. For energy-dispersive diffraction the `EnergyDispersiveDetector` (the GeRM germanium strip detector) records a per-channel energy spectrum from a defined gauge volume inside the sample. Which detector is in the beam is set by the `DetectorStage` positioning.

## The energy-dispersive detector reuses an earned family

The `EnergyDispersiveDetector` is the GeRM germanium strip detector, and it is a different shape from the area cameras: it resolves photon energy per event to give a spectrum, from which diffraction peaks are fit at fixed scattering angle (the energy-dispersive geometry). That shape is already in the catalog. The `EnergyDispersiveSpectrometer` Family was earned by the APS 2-ID fluorescence detector and the 7-BM germanium energy-dispersive-diffraction detector; its definition presents the `Sensor` Role (a scalar or short-vector Reading per point, distinct from the `Camera` 2D Frame) and explicitly spans the silicon-drift and germanium variants. HEX's GeRM detector is the **third consumer** of that Family, with the channel count, energy resolution, and gauge-volume dimensions carried as per-Asset settings (`DET-2`). It is controlled through the beamline's Phoebus GUI with `caput` thresholds and the `edxd_viewer` tool; those handles are observed, not modelled (`CTRL-1`).

## Multi-technique by positioning, not a new instrument

The structurally distinct thing on the detection side is that imaging, EDXD, and ADXD all live in the one endstation and are selected during an experiment by moving detectors and optics into the beam remotely. CORA models this as a positioning action, not a fused mega-detector: the `DetectorStage` (a `LinearStage`) moves the chosen detector or optic into place, and CORA conducts that positioning over the `ControlPort` ahead of the technique's acquisition (see [Controls](controls.md)). So the technique switch coins no device and no Capability; it is a Practice-level sequence (`TECH-1`).

| Technique | Detector in the beam | Family |
| --- | --- | --- |
| imaging / tomography | `ImagingCamera` + `ImagingScintillator` | `Camera` + `Scintillator` |
| time-resolved radiography | `HighSpeedCamera` | `Camera` |
| energy-dispersive diffraction (EDXD) | `EnergyDispersiveDetector` | `EnergyDispersiveSpectrometer` |
| angle-dispersive diffraction (ADXD) | `FlatPanelDetector` | `Camera` |

## Why no new detector family

The detection side reinforces the catalog rather than extending it. The Kinetix and Phantom cameras and the PerkinElmer flat panel reuse `Camera`; the imaging scintillator-lens table reuses `Scintillator`; the detector / optics positioning reuses `LinearStage`; and the GeRM strip detector reuses the existing `EnergyDispersiveSpectrometer` Family as its third consumer (`DET-2`). HEX's imaging and tomography overlap the fleet heavily (the 2-BM pilot, the NSLS-II FXI), and its diffraction reuses the pending energy-dispersive (7-BM) and powder (i11) Methods. That side is reinforcement, not novelty. What is distinct here is that several one-technique detectors share one endstation and are selected by positioning (`TECH-1`).

## Families

Reused from the catalog: `Camera` (the Kinetix and Phantom cameras and the PerkinElmer flat panel), `Scintillator` (the imaging table), `LinearStage` (the detector / optics positioning), and `EnergyDispersiveSpectrometer` (the GeRM strip detector, the third consumer). New families: none; nothing graduates and the catalog is unchanged. The PerkinElmer model and its ADXD role are `DET-1`; the GeRM channel count, resolution, and gauge volume are `DET-2`; the Kinetix default and the scintillator / lens set are `DET-3`. See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family decisions, and [beamline.md](../beamline.md) for the source walk.
