# Sample

*The fast-tomography experiment endstation: the rotary stage, the sample positioning and table, and the fast shutter. First cut.*

The FAXTOR experiment endstation (`faxtor-experiment`) is where the specimen is rotated and positioned in the beam for fast tomography. It is a reverse-engineered first cut from ALBA's public facility pages; the stage models and axis sets are not published, carried `confirm` (`SAMPLE-1`).

## The stage stack

- **`SampleTable`** (`Table`): the support table carrying the endstation stages; degrees of freedom pending (`SAMPLE-1`).
- **`Rotary`** (`RotaryStage`): the tomographic rotation stage. FAXTOR runs continuous-rotation tomography up to 20 Hz, so the rotary is the master clock that triggers the camera (`TRIG-1`).
- **`SamplePositioning`** (`LinearStage`): the sample centring stage that brings the specimen onto the centre of rotation; axis set pending (`SAMPLE-1`).
- **`FastShutter`** (`Shutter`): the sample-side fast shutter that limits dose between projections; model pending (`SAMPLE-1`).

These reuse the imaging Families the fleet already carries (the 2-BM pilot and the MAX IV TomoWISE design): a rotary stage, a sample-centring linear stage, a support table, and a fast shutter. FAXTOR coins no new Family.

## Not modelled yet

The exact axis travels, resolutions, and vendor models for the endstation stages are not published and are carried pending (`SAMPLE-1`). The triggering and synchronization scheme that ties the rotary master clock to the camera is likewise pending (`TRIG-1`). They land when ALBA staff confirm the endstation configuration. The [2-BM sample tower](../../2-bm/equipment/sample_tower.md) shows the shape a fully-modelled tomography endstation carries.
