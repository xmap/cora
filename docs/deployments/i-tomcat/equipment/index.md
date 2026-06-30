# The beamline

*The I-TOMCAT beamline as areas you can jump to: the three stations the beam passes through, plus the controls that drive them and the resources they draw on. Modelling exercise.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stations**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what comes through. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (the undulator front end and the conditioning optics, shared with S-TOMCAT) and the I-TOMCAT experiment hutch (the endstation and the detector suite).

The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right. So the list reads as one row of peers, but the first three share an axis the last two cross.

## Stations

- [Source](../beamline.md): the shared beam delivery. The U15 undulator feeds a double-crystal multilayer monochromator (8-50 keV, 8-30 keV recommended until the HTSU10 upgrade), a CVD diamond window, the filter batteries and a focusing mirror, then the safety shutter.
- [Sample](sample.md): the I-TOMCAT endstation (ES2, ~33 m from source), an air-bearing rotation stage carrying sample positioning and a continuous-rotation slip ring, plus a sample-side fast shutter. The maximum field of view is about 1.5 x 1.5 mm2.
- [Detector](detector.md): a visible-light microscope (interchangeable objectives over a scintillator) coupling the X-ray image to a high-speed camera suite, including the PSI in-house GigaFRoST continuous-streaming camera.

## Shared

- [Controls](controls.md): the SLS EPICS floor and the BEC scan/orchestration layer, and where CORA's edge would replace it.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page yet in this modelling exercise.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, target Models, and pending confirmations). The hutch PSS permit signals are SLS facility signals, not public (see [Open questions](../questions.md)).
