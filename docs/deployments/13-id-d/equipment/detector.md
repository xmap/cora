# Detector

*The Eiger2 area detector and its table plus 2theta arm, the ion chambers and the DAC photodiode, the XGLab Dante MCA, and the fibre sample illumination at 13-ID-D. Scaffold; device-to-PV reconstruction from the GSECARS EPICS support tree, carried at medium confidence.*

13-ID-D measures monochromatic powder and single-crystal X-ray diffraction off a sample held in a diamond anvil cell. The detection side reads the scattered beam on an area detector, monitors the incident and transmitted flux through ion chambers and a photodiode, and carries a fluorescence MCA alongside. Every device here reuses a catalog [Family](../../../catalog/families.md): the novelty of this beamline is the high-pressure sample environment (the new loose `PressureCell` family, see [Sample](sample.md)), not anything on the detection axis. The cell's in-situ pressure and temperature metrology detector, the LightField spectrometer, is a [Sample](sample.md)-side device, not a detection-chain detector; it reads the cell, not the diffracted beam.

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `AreaDetector` | `Camera` | the Eiger2 X 9M area detector (`13EIG2_9M:`), the primary diffraction detector; the Pilatus 1M CdTe and Si units (`13PIL1MCdTe:`, `13PIL1MSi:`) are alternative area detectors exchanged onto the same role (`DET-1`) |
| `DetectorStage` | `LinearStage` + `TiltStage` | the detector table and 2theta arm; the table translates and the arm tilts. The 2theta swing transform would bind a `PseudoAxis`, but its prefix was seen only in a Galil test template, so the binding is deferred, not invented (`DET-1`) |
| `FluxMonitor` | `FluxMonitor` | the ion chambers over a USB-CTR multi-channel scaler (`13IDD:scaler1`) and the DAC photodiode (`13IDD:Photodiode`), for incident and transmitted flux (`DET-1`) |
| `FluorescenceDetector` | `EnergyDispersiveSpectrometer` | the XGLab Dante MCA (`13IDD_Dante1:`), an energy-dispersive fluorescence detector (`DET-1`) |
| `SampleIllumination` | `Backlight` | the fibre sample illumination (`13IDD:US_IllumOnOff`), a loose `Backlight` (`DET-1`) |

The chain reads outward from the sample. The diffracted beam lands on the Eiger2 X 9M area detector, which reads out per pixel; the Pilatus 1M CdTe and Si units are alternative area detectors that take the same role when a different sensor or energy range is wanted, so they bind the same `Camera` Family and differ as a per-Asset setting (`DET-1`). The detector table carries the detector and translates it, while the 2theta arm tilts it to set the scattering angle; the arm's table translation and tilt are catalog axes (`LinearStage`, `TiltStage`), and the 2theta swing as a single derived angle would bind a `PseudoAxis`, deferred because its prefix appears only in a Galil test template (`DET-1`). The ion chambers, counted over the USB-CTR multi-channel scaler, and the DAC photodiode monitor the incident and transmitted flux for normalization (`DET-1`). The XGLab Dante MCA collects energy-dispersive fluorescence alongside the diffraction (`DET-1`), and the fibre illumination lights the sample for visual alignment (`DET-1`).

## Why no new detector family

The detection axis tempts no new device class. The Eiger2 and the Pilatus units are conventional area detectors and bind the catalog `Camera`, reusing the existing scattering anatomy; which sensor sits in the beam (Eiger2 X 9M, Pilatus 1M CdTe, or Pilatus 1M Si) is a per-Asset setting on the one detector role, not a new Family per model (`DET-1`).

The flux side, the ion chambers over the scaler and the DAC photodiode, binds the catalog `FluxMonitor`, the same shape every other APS flux monitor carries; these are current-integrating monitors read for normalization, and role is a Method concern, not a Family difference (`DET-1`).

The fluorescence MCA is the one device that could read as a candidate for a coined family, so the reuse argument is worth making explicitly. The XGLab Dante is an energy-dispersive fluorescence detector, the same anatomy as the multi-element fluorescence detectors at 2-ID and 7-BM, and it binds the same catalog `EnergyDispersiveSpectrometer` they already use. This is precedent reuse, not novelty: a new vendor for an existing detector shape earns no new Family (`DET-1`).

The detector table and 2theta arm decompose into ordinary translation and tilt axes (`LinearStage`, `TiltStage`); the 2theta swing as a derived angle is a `PseudoAxis` transform held back rather than invented, because the only prefix seen for it was a Galil test template (`DET-1`). The fibre illumination is a plain loose `Backlight`. None of these is a new device class.

The net result is zero new families on the detection axis. The one new family this deployment coins, the loose `PressureCell`, sits on the [Sample](sample.md) side for the high-pressure cell, and the entire diffraction spine, detection included, is catalog reuse (see [Model](../model.md)).

## Families

Reused from the catalog: `Camera` (the Eiger2 X 9M and the Pilatus 1M CdTe and Si area detectors), `FluxMonitor` (the ion chambers over the USB-CTR scaler and the DAC photodiode), `EnergyDispersiveSpectrometer` (the XGLab Dante MCA, the 2-ID / 7-BM precedent), `LinearStage` and `TiltStage` (the detector table and 2theta arm), and the loose `Backlight` (the fibre sample illumination). No new family is coined on the detection axis, and nothing graduates; the catalog is unchanged. The open detail is the device-to-PV reconstruction, rougher here because the source is the EPICS-native GSECARS support tree rather than a Python device roster (`DET-1`), and the deferred 2theta `PseudoAxis` binding (`DET-1`). See [Inventory](../inventory.md) for the Asset tree and [Model](../model.md) for the no-new-family argument across the whole instrument.
