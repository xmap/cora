# The beamline

*The part of XFP CORA models today, as areas you can jump to: the white-beam optics and dose-delivery gating, the solution sample stages and delivery pump, and the flux / dose monitors, plus the controls. First cut.*

XFP (X-ray Footprinting of Biological Materials) is the NSLS-II dose-delivery beamline at sector 17-BM, a Case Western Reserve University partner beamline. It irradiates a biological macromolecule in solution with an intense white / pink beam to footprint it via hydroxyl radicals; the structural readout is done offline by mass spectrometry. Its PV zones run `FE:C17B` (the front-end white-beam slit), `XF:17BM-OP` / `XF:17BMA-OP` (the optics: the bendable mirror, the beamline slits), `XF:17BMA-EPS` / `-PPS` / `-CT` (the shutters), `XF:17BM-BI` (the flux and beam-position monitors), and `XF:17BMA-ES:1` / `ES:2` (the footprinting endstations: the filter wheel, the sample stages, the pumps) (`ENC-1`). 17-BM is a bending-magnet, white / pink beam source, with no monochromator in the footprinting path (`SRC-1`, `WHITE-1`).

Unlike every other beamline in the fleet, the stations here do not end in a detector that records a measurement. They end in a **dose** delivered to a sample, and a **dose record**; the structural readout is offline (see [Detector](detector.md)). Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that conditions the white beam, sets the dose rate, and gates the timed dose; the [Sample](sample.md) that flows or positions the solution sample in the beam; and the [Detector](detector.md), which here is the flux / dose monitoring (no imaging detector). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the storage-ring machine state read through a loose `StorageRing` (`MACHINE-1`), the bendable front-end mirror (`OPT-1`), the white-beam and defining slits (`OPT-2`), the eight-position Al filter wheel that sets the dose rate (`ATTN-1`), and the dose-delivery gating, the personnel and timed shutters (`PSS-1`, `DOSE-1`) and the delay-generator dose timer that fires the millisecond Uniblitz fast shutter (`DOSE-1`).
- [Sample](sample.md): the capillary-flow sample stage (`SAMPLE-1`), the high-throughput plate and shutterless HTFly stages (`HT-1`), and the sample-delivery pump (the graduated catalog `FlowController`, presents Regulator, `FLOW-1`). The fraction collector, the pure-Python 96-well plate addressing, and the solution Subject are the sample-custody seam (`FC-1`, `HT-1`, `SUBJECT-1`).
- [Detector](detector.md): the QuadEM flux monitor and the Sydor beam-position monitor that measure the delivered dose (`DET-1`, `DIAG-1`). There is no scattering, area, or imaging detector: the footprinting structural readout is offline mass spectrometry (`READOUT-1`).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, the dose-delivery timing, the sample-custody seam, and the offline-readout seam (the run produces a footprinted sample plus a dose record; the mass spec is downstream). The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum for the white-beam optics), plus the footprinting consumables (buffers, radical scavengers, the flow medium) as Supply; carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the remaining loose families and the graduated catalog `FlowController` (earned on the i22 / 7-BM / LIX / XFP rule-of-three).
