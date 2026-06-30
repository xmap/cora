# Sample

*The tomographic sample stack: the rotary stage and the sample-centring stages. First cut.*

The 8.3.2 sample stack is where the specimen is rotated and positioned in the beam for micro-tomography. It is a reverse-engineered first cut: the stage structure is read from the DXchange / DXfile HDF5 data record (the `sample_motor_stack` group), but the stage models, axis sets, and live BCS handles are not public, carried `confirm` (`SAMPLE-1`, `CTRL-1`).

## The stage stack

- **`SampleRotary`** (`RotaryStage`): the tomographic rotation stage. For continuous-rotation tomography it is the master clock that triggers the camera (`TRIG-1`). The data record's `sample_motor_stack` exposes `axis1pos`, `axis2pos`, and `axis5pos`; which axis is the rotation is pending (`ROT-1`).
- **`SamplePositioning`** (`LinearStage`): the sample-centring stage that brings the specimen onto the centre of rotation. The data record exposes `sample_x` and `sample_y`; the full axis set is pending (`SAMPLE-1`).

These reuse the imaging Families the fleet already carries (the 2-BM pilot, the NSLS-II FXI design, and the ALBA FAXTOR design): a rotary stage and a sample-centring linear stage. 8.3.2 coins no new Family.

## Not modelled yet

The exact axis travels, resolutions, and vendor models for the sample stack are not published and are carried pending (`SAMPLE-1`). Which of the `axisNpos` channels is the tomographic rotation is the key open question (`ROT-1`), and the triggering and synchronization scheme that ties the rotary master clock to the camera is likewise pending (`TRIG-1`). They land when 8.3.2 staff confirm the endstation configuration. The [2-BM sample tower](../../2-bm/equipment/sample_tower.md) shows the shape a fully-modelled tomography endstation carries.
