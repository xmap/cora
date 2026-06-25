# Detector

*The coherent-scattering area detectors, the WAXS detector, the beam stop, and the beam-position monitors. First cut; PVs read from the beamline config, carried confirm.*

9-ID detection is coherent area detectors for the small-angle pattern (a Pilatus and an Eiger on a translation stage), a wide-angle detector on a pedestal for GIWAXS, the beam stop that blocks the direct beam, and the beam-position monitors that diagnose and normalize the beam. They are modelled in the detection stage of the [descriptor](../inventory.md).

The detectors reuse the `Camera` Family, the stage `LinearStage`, and the beam stop the catalog `BeamStop` Family. The TetrAMM and the two XBPMs bind a loose `BeamPositionMonitor` Family that 4-ID and 8-ID also use, held for gate-review.

## Detector chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Pilatus1M` | `Camera` | Pilatus 1M coherent-scattering detector (`DET-1`) |
| `EigerDetector` | `Camera` | Eiger coherent-scattering detector; prefix a guess pending `CTRL-1` (`DET-1`) |
| `DetectorStage` | `LinearStage` | Eiger positioning stage (`eiger_x` / `eiger_y`) |
| `WAXSDetector` | `Camera` | wide-angle (GIWAXS) detector on its pedestal (`DET-1`) |
| `BeamStop` | `BeamStop` | direct-beam stop and its carriage |
| `TetrAMM` | `BeamPositionMonitor` (loose) | TetrAMM picoammeter / position monitor, four channels (`BPM-1`) |
| `XBPM_1` / `XBPM_2` | `BeamPositionMonitor` (loose) | X-ray beam-position monitors (`xpbm1` / `xpbm2`) (`BPM-1`) |

## Families

Reused from the catalog: `Camera` (the Pilatus, Eiger, and WAXS detectors), `LinearStage` (the detector stage), and `BeamStop`. The beam-position monitors bind a loose `BeamPositionMonitor` Family, held for gate-review even though 9-ID is a further independent beamline to use it: the Sensor fold-vs-promote question is open (`DIAG-1` / `FLUX-1`; see [Model](../model.md#loose-families-held-for-gate-review)). Whether each monitor is a true position monitor or an intensity (I0) normalizer is `BPM-1`; the detector models are `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
