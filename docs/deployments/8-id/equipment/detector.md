# Detector

*The coherent-scattering area detectors, the flight path, and the beam-position monitors. First cut; PVs read from the beamline config, carried confirm.*

XPCS detection is three fast area detectors on a translation stage, downstream of an evacuated flight path with a beam stop, plus the beam-position monitors that normalize intensity. They are modelled in the detection stage of the [descriptor](../inventory.md). The detectors reuse the `Camera` Family and the beam stop the `BeamStop` Family; the flight path binds a loose `FlightPath` Family; the beam-position monitors bind a loose `BeamPositionMonitor` Family, held for gate-review.

## Detector chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Eiger4M` | `Camera` | Eiger 4M coherent-scattering detector (`DET-1`) |
| `Lambda2M` | `Camera` | Lambda 2M detector (`DET-1`) |
| `Rigaku3M` | `Camera` | Rigaku 3M high-frame-rate detector (`DET-1`) |
| `DetectorStage` | `LinearStage` | Aerotech detector positioning stage |
| `FlightPath` | `FlightPath` (loose) | evacuated flight path carrying the scattered beam (`XPCS-2`) |
| `BeamStop` | `BeamStop` | flight-tube beam stop |
| `TetrAMM_QUAD1` | `BeamPositionMonitor` | TetrAMM picoammeter / position monitor, four channels (`BPM-1`) |

## Families

Reused from the catalog: `Camera` (the three detectors), `LinearStage` (the detector stage), and `BeamStop`. The beam-position monitors bind a loose `BeamPositionMonitor` Family, held for gate-review even though 8-ID is the second independent beamline to use it (see [Model](../model.md#loose-families-held-for-gate-review)). The flight path stays a loose `FlightPath` Family (single beamline). The detector models are `DET-1`; the flight-path geometry is `XPCS-2`. See [Inventory](../inventory.md) for the Asset tree.
