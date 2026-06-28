# Microtomography station

*The microtomography endstation: the large-field-of-view rotation axis and sample positioner. First cut, from papers, handles carried confirm.*

The microtomography station works the same cone-beam geometry as the nanotomography station at coarser resolution and a much larger field of view (the two stations together span roughly 120 nm to 55 um resolution and roughly 150 um to 85 mm field of view). The sample sits further along the cone, so the magnification is lower and the illuminated field wider, suited to larger specimens and faster, time-resolved (4D) tomography.

## Devices

| Asset | Family | Note |
| --- | --- | --- |
| `MicroSampleRotary` | RotaryStage | The microtomography rotation axis, the master clock for the micro-station triggered acquisition. Model and handle pending (STAGE-3). |
| `MicroSampleStage` | LinearStage | The microtomography sample positioner. Axis set, travel, model, and handles pending (STAGE-3). |

## Acquisition

Acquisition follows the same pattern as the [nanotomography station](nanotomography.md): a `mgn-routines` tomogram script drives the rotation and detector over EPICS with the [TATU trigger](controls.md) hardware-synchronising the projections. The micro station's faster, wider-field operation is where MOGNO's 4D time-resolved tomography lives, though the specific continuous-rotation and streaming modes are not asserted here without a source (see [Techniques](../techniques.md#a-familiar-technique-on-a-third-facility)).

The micro-station devices are modelled at Family granularity only: the public sources describe the station qualitatively, so the stage models and handles are open questions (STAGE-3). See [Open questions](../questions.md#sample-stations).
