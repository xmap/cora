# Nanotomography station

*The nanotomography endstation: the rotation axis and fine sample positioner at the elliptical-mirror nanofocus. First cut, from papers, handles carried confirm.*

The nanotomography station sits at the focus of the elliptical focusing mirrors, where the demagnified source reaches roughly 100 to 120 nm. A sample on the rotation axis is illuminated by the diverging cone beam; rotating it through projections while a downstream detector records gives a tomogram, and moving it along the cone sets the magnification (see the [cone-beam magnification axis](detector.md)).

## Devices

| Asset | Family | Note |
| --- | --- | --- |
| `SampleRotary` | RotaryStage | The tomographic rotation axis, the scannable driven during a tomogram and the master clock for hardware-triggered acquisition. Model, encoder resolution, and max speed are not in public sources (STAGE-1). |
| `SampleTripod` | LinearStage | The fine three-axis sample positioner (the piezo "tripod" in the software paper): sample centring and alignment. The axis set is a per-Asset setting; model and travel pending (STAGE-2). |

## Acquisition

A tomogram is acquired by the beamline's custom `mgn-routines` tomogram script (launched from a `mgn-control-guis` dialog), which drives the rotation axis and the detector over EPICS while the [TATU trigger](controls.md) hardware-synchronises the projection exposures to the rotation. CORA's edge would conduct this sequence over the EPICS floor (see [Controls](controls.md) and [Model](../model.md#the-control-seam-a-custom-epics-application-layer)). The concrete rotation ranges, speeds, and projection counts are not modelled yet; they join with the acquisition recipes (see [Techniques](../techniques.md#not-modelled-yet)).

The whole station is carried `confirm`: the device families are inferred from the published papers, but no handles, encoders, or vendor models are public (STAGE-1, STAGE-2). See [Open questions](../questions.md#sample-stations).
