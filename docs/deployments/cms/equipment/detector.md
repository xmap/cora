# Detector

*The SAXS / WAXS / MAXS area detectors, the detector translations and telescoping flight path, the beamstop, the flux monitors, the beam-position monitor, and the specular reflectivity mechanism. Reverse-engineered from `NSLS2/cms-profile-collection` (`startup/*.py`); PVs read from the profile collection, carried confirm.*

CMS's measurement is the scattering pattern on a Pilatus area detector, read at the small-, wide-, or medium-angle position down a telescoping flight path. The same detector face also carries specular X-ray reflectivity, with no extra hardware: the reflected beam is tracked across the fixed Pilatus by a software region as the sample angle is stepped. Every device on the detection side binds an existing catalog Family, and reflectivity is a Method over them, so this page coins nothing.

## Detection chain

| Device | Family | PV | Role |
| --- | --- | --- | --- |
| `SaxsDetector` | `Camera` | `XF:11BMB-ES{Det:PIL2M}` | Pilatus 2M, small-angle (SAXS); also the detector for specular reflectivity (`DET-1`, `XR-1`) |
| `WaxsDetector` | `Camera` | `XF:11BMB-ES{Det:PIL800K}` | Pilatus 800K, wide-angle (WAXS) (`DET-1`) |
| `MaxsDetector` | `Camera` | `XF:11BMB-ES{Det:PIL800K2}` | a second Pilatus 800K at the medium-angle position; one 800K head is powered at a time per configuration (`DET-1`) |
| `DetectorStage` | `LinearStage` | the SAXS / WAXS / MAXS detector translations and the telescoping flight path | sets the sample-to-detector distance and hence the accessible angle; distances are calibration (`DET-1`) |
| `Beamstop` | `BeamStop` | `XF:11BMB-ES{BS:SAXS}` | blocks the SAXS direct beam (`DET-1`) |
| `EndstationFluxMonitor` | `FluxMonitor` | ion chamber `IM:3` + BIM4 scintillation counter `IM:4` + endstation electrometer `IM:2` | incident-flux measurement at the endstation for normalization (`DET-1`) |
| `BeamPositionMonitor` | `BeamPositionMonitor` (loose) | `XF:11BMB-BI{BPM:1}` | BIM5 four-quadrant diamond-diode beam-position monitor (`DIAG-1`) |

The chain reads outward from the sample. The Pilatus area detector records the scattering pattern; the detector stage translates it along the telescoping flight path to set the sample-to-detector distance, which is what selects the angular range a run covers. The beamstop blocks the direct beam off the SAXS detector face. The endstation flux monitors read the incident flux as a scalar for normalization, drawing on the ion chamber, the BIM4 scintillation counter, and the endstation electrometer together. The diamond-diode beam-position monitor reads the four-quadrant beam position for diagnostics.

CMS carries three Pilatus heads across the small-, wide-, and medium-angle positions, but only one 800K head is powered at a time per configuration (`DET-1`): the WAXS and MAXS positions share that constraint, so the active geometry is a setting on the configuration rather than three independent live cameras. Detector distances are calibration values, carried as settings on the stage and not invented here (`DET-1`).

## Specular reflectivity without a two-theta arm

Specular X-ray reflectivity (XR) is the one genuinely distinct measurement on the detection side, and it is realized with no new hardware. There is no physical two-theta detector arm and no point detector. The area detector stays fixed, and the "two-theta" is synthetic: a software region-of-interest slides across the fixed Pilatus face to where the reflected beam lands as the sample theta (the `sth` axis on the `SampleGoniometer`, see [Sample](sample.md)) is stepped. The specular intensity for each step is the integrated counts inside that tracked region; the reflectivity curve is built by stepping `sth` and reading the moving region across the stationary detector (`XR-1`).

This means XR composes only devices that already exist for scattering:

| Role in XR | Device | Family |
| --- | --- | --- |
| the swept angle | `SampleGoniometer` `sth` | `Goniometer` |
| the detected signal | `SaxsDetector` read over a tracked region | `Camera` |
| incident normalization | `EndstationFluxMonitor` | `FluxMonitor` |

No device is coined, no two-theta arm is modelled, and no point detector is added (`XR-1`). The reflectivity Method is shared with i10, its soft X-ray RASOR sibling; CMS is the second consumer of that Method, the first to realize it on a hard X-ray area detector by sliding a region across the fixed Pilatus rather than swinging a detector (`XR-1`, `TECH-1`). The integrated-region readout and the `sth` step list are calibration and run settings, carried not invented.

## Why no new detector family

The detection side reinforces the catalog rather than extending it. The three Pilatus heads reuse `Camera`; the detector translations and flight path reuse `LinearStage`; the SAXS beamstop reuses `BeamStop`; the endstation flux monitors reuse `FluxMonitor`. The only loose binding is the `BeamPositionMonitor` Family for the BIM5 diamond-diode BPM, and that Family is already held under review across the fleet (4-ID, 8-ID, 9-ID) pending the sensor fold-versus-promote decision; CMS adds a sighting, not a new Family (`DIAG-1`).

XR adds no detector family either, because it is a Method over the same `Goniometer` + `Camera` + `FluxMonitor` vocabulary, not a device. CMS's SAXS / WAXS / MAXS scattering overlaps the fleet heavily: it is the direct NSLS-II twin of [SMI](../../smi/equipment/detector.md) and shares its science axis with Diamond I22 and APS 9-ID / 12-ID-E, reusing the same Camera / Goniometer / Slit / BeamStop / FluxMonitor vocabulary with zero new families. That scattering side is reinforcement, not novelty. What is distinct here is the hard X-ray reflectivity Method realized with no new hardware (`XR-1`), and CMS standing up as a further NSLS-II beamline re-testing the Site and Federation kernel.

## Families

Reused from the catalog: `Camera` (the three Pilatus heads), `LinearStage` (the detector translations and telescoping flight path), `BeamStop` (the SAXS beamstop), and `FluxMonitor` (the endstation ion chamber, scintillation counter, and electrometer). Loose and held under review: `BeamPositionMonitor` (the BIM5 diamond-diode BPM, `DIAG-1`). New families: none; nothing graduates and the catalog is unchanged. Specular reflectivity is the `reflectivity` Method over `Goniometer` + `Camera` + `FluxMonitor`, the second consumer after i10 (`XR-1`, `TECH-1`). The one-800K-at-a-time configuration and the detector-distance calibration are `DET-1`. See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family decisions, and [beamline.md](../beamline.md) for the source walk.
