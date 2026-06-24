# Detector

*Several detector modalities, not one camera path. Design-phase; values are taken from the 7-BM docs or inferred.*

The single biggest detector-side difference from the 2-BM micro-CT pilot is that 7-BM runs several detector modalities, chosen per technique. They are modelled in the detection stage of the [descriptor](../inventory.md). Two of them present the **Sensor** Role (a scalar or short-vector Reading, not a 2D frame), which the 2-BM camera path never needed.

## The modalities

| Device | Family | Role | Notes (from the 7-BM docs) |
| --- | --- | --- | --- |
| `Scintillator` | `Scintillator` | (part of the imaging path) | scintillator crystal for indirect x-ray imaging; cracks under prolonged white beam |
| `TomographyCamera` | `Camera` | Detector | area camera coupled to the scintillator through visible optics, for tomography and radiographic imaging |
| `HighSpeedCamera` | `Camera` | Detector | high-speed movie camera (Photron Nova S16 in the docs); chopper-gated movie bursts |
| `Photodiode` | `Photodiode` (loose) | Sensor | PIN diode for time-resolved radiography; a scalar intensity Reading |
| `EnergyDispersiveSpectrometer` | `EnergyDispersiveSpectrometer` | Sensor | germanium energy-dispersive detector; a per-photon energy spectrum |

## How each maps onto CORA

- **Tomography (camera).** The scintillator-plus-visible-optics-plus-area-camera path is the same shape as 2-BM. It reuses the `Scintillator` and `Camera` Families and the Detector Role, and could later compose the cross-facility `Microscope` Assembly. No new shape.
- **High-speed imaging (movie camera).** Still a `Camera` presenting the Detector Role. What is new is the acquisition: short movie bursts, one per chopper opening, hardware-gated by the DG645 timing chain and optionally ring-synced at 271 kHz. That is a new acquisition Method and a Run / Dataset question (is one burst one Run, the N-sequence set one Campaign, and how are top-up-blanked frames represented), not a new detector Family (HSI-1).
- **Radiography (point photodiode).** A PIN photodiode reads transmitted intensity as a scalar time series, read out through a high-speed digitizer (ADQ14) or oscilloscope plus the DataGrabber program. The Role is settled (Sensor); the digitizer, scope, and DataGrabber stay on the floor. What is open is the detector Family and whether one trace is one Dataset (RAD-1).
- **Energy-dispersive diffraction (germanium detector).** A germanium detector records the energy of each absorbed photon, an MCA spectrum transformed to scattering vector by Bragg's Law. It presents the Sensor Role (a short-vector Reading) and binds the catalog `EnergyDispersiveSpectrometer` Family (graduated once 2-ID and 7-BM shared it). What is open is whether it is the same physical detector as the fluorescence MCA (DET-1).

## Families

The imaging path reuses `Scintillator` and `Camera`. The energy-dispersive detector binds the catalog `EnergyDispersiveSpectrometer` Family (graduated once 2-ID and 7-BM shared it), the first to fill the Sensor Role with a science detector. The `Photodiode` point detector is still a loose family presenting the existing Sensor Role, rendered as plain text; whether it is earned into the catalog or stays a deployment-local Sensor device is settled when staff confirm it and the naming review weighs in. This is the same loose-binding pattern 2-BM uses for its uncatalogued `Diagnostic` and `BeamPositionMonitor` Sensor devices.

The detector data units, the energy-dispersive detector identity, and the camera models are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
