# Detector

*The flat-panel and pixel area detectors, the two detector towers, the beamstops, and the flux monitor. PVs verified against `startup/80-areadetector2.py`, `81-pilatus.py`, `72-two-detector.py`, `11-motors.py`, `10-machine.py`.*

PDF's measurement is the total-scattering pattern on a large area detector. To reach the high Q a pair distribution function needs, the detector sits close to the sample; a near panel and a far panel are merged across two distances to cover the full range. This two-distance, two-detector geometry is the shape that distinguishes PDF from its twin XPD.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `AreaDetector` | Camera | `XF:28ID1-ES{Det:PE1}` | PerkinElmer flat panel, primary PDF detector |
| `PixelDetector` | Camera | `XF:28ID1-ES{Det:Pilatus}` | Pilatus photon-counting pixel detector |
| `DetectorStage1` | LinearStage | `XF:28ID1B-ES{Det:1}` | first detector tower (static distance) |
| `DetectorStage2` | LinearStage | `XF:28ID1B-ES{Det:2}` | second detector tower (moving distance) |
| `BeamStop` | BeamStop | `XF:28ID1B-ES{BS:1}` | direct-beam stop |
| `FluxMonitor` | FluxMonitor | `XF:28ID1B-OP{Det:1-Det:2}` | background photodiode (I0) |

## Two detectors, two distances

The `AreaDetector` is a PerkinElmer flat panel (a second panel sits alongside), the primary total-scattering / powder detector; the `PixelDetector` is a Pilatus photon-counting detector with an energy-thresholded readout, used for high-Q or low-background frames. Both reuse `Camera`, the flat-panel precedent XPD already carries.

The `DetectorStage1` and `DetectorStage2` are the two detector towers (`Det_1` and `Det_2`, each X / Y / Z). The Z axis sets the sample-to-detector distance and hence the accessible Q. PDF carries two towers so a near and a far panel can be merged into one wide-Q dataset: one panel stays static while the other steps in and out of the beam, the explicit two-detector acquisition the `TwoDetectors` plan sequences. Which tower is static versus moving, and how the panels merge, are DIST-1. Each `BeamStop` (`BStop1`, with `BStop2` and a table-mounted stop alongside) blocks the direct beam ahead of its panel.

## Reuse, not new vocabulary

This is the reinforcement point of PDF as a CORA exercise: a high-energy total-scattering beamline with flat-panel and pixel detectors, two distance towers, and beamstops that needs **no new Family**. The detectors reuse `Camera`, the `FluxMonitor` photodiode reuses the graduated flux Family (#353), and the beamstops reuse `BeamStop`. The total-scattering detector chain is the same shape its twin [XPD](../../xpd/equipment/detector.md) carries; PDF adds the second physical detector tower for the simultaneous near / far merge, but the families are unchanged.
