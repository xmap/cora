# Sample

*The endstation sample side: the capillary-flow, high-throughput, and HTFly sample stages, and the sample-delivery pump, plus where the fraction collector, the 96-well plate, and the solution Subject sit. First cut; PVs read from the `NSLS2/xfp-profile-collection` startup files, carried confirm.*

XFP's sample side delivers a biological macromolecule in solution into the white beam to be footprinted, then captures the irradiated aliquot for offline analysis. Like [LIX](../../lix/index.md), the specimen is a liquid, not a solid mount, and the delivery is fluidic. What is distinctive here is that the "result" of placing the sample in the beam is not a measurement but a **delivered dose**, and the sample itself, now footprinted, is carried off the beamline to a mass spectrometer (see [Detector](detector.md) and [Controls](controls.md)). The hardware is modelled in the sample stage of the [descriptor](../inventory.md); the custody chain is described here and in [Controls](controls.md).

## The sample side at a glance

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `CapillaryFlowStage` | `LinearStage` | `XF:17BMA-ES:1{Stg:5-Ax:X}` | places a flowing solution capillary in the beam (x / y, 100 mm travel) (`SAMPLE-1`) |
| `HighThroughputStage` | `LinearStage` | `XF:17BMA-ES:2{Stg:7-Ax:X}` | positions a 96-well plate (x / y, 200 mm travel); the well addressing is a Procedure, no robot (`HT-1`) |
| `HtFlyStage` | `LinearStage` | `XF:17BMA-ES:2{HTFly:1-Ax:X}` | sweeps a fly-cell row through the beam; the velocity sets the exposure (dose) (`HT-1`, `DOSE-1`) |
| `DeliveryPump` | `FlowController` (loose) | `XF:17BMA-ES:1{Pmp:02}` | the syringe pump flowing solution through the capillary / flow cell during irradiation (`FLOW-1`) |

## Delivering the sample to the beam

XFP runs several sample-delivery modes, each with its own stage, and all reuse the catalog `LinearStage` Family.

The **capillary-flow mode** uses the `CapillaryFlowStage` to place a flowing solution capillary at the beam. A solution sample is pushed through the capillary by the delivery pump so that fresh, un-irradiated material is continuously presented, and the timed dose shutter (see [Source](../beamline.md)) gates the exposure (`SAMPLE-1`).

The **high-throughput mode** uses the `HighThroughputStage` to position a 96-well plate, exposing one well at a time. The **HTFly mode** is shutterless: the `HtFlyStage` sweeps a fly-cell row through the defining slit at a set velocity, so the exposure time, and therefore the dose, is the slit gap divided by the stage velocity rather than a shutter opening (`HT-1`, `DOSE-1`). All three are plain translation stages; the dose-timing for HTFly lives in the Procedure, not in a special device.

## The fluidic delivery: the pump

The `DeliveryPump` flows the solution sample through the capillary or flow cell during irradiation. It is a settable flow / pump actuator (an M50 syringe pump with rate / volume setpoints and a run command, driving the dose-response / fraction-collection mode; a second PHD2000 infusion pump drives the capillary-flow / time-resolved mode), exactly the anatomy of the existing loose `FlowController` Family that i22, 7-BM, and LIX already use. So the pump **reuses** `FlowController`; it coins nothing. XFP is its **fourth** consumer, reinforcing the rule-of-three that [LIX](../../lix/model.md#the-flowcontroller-rule-of-three) already fired (see [Model](../model.md#the-flowcontroller-rule-of-three)).

## The Subject and the sample-custody seam

The deepest part of XFP's sample side is not a device. The **Subject** is a biological macromolecule (a protein or nucleic acid) in a buffer; the run irradiates it and produces a **footprinted aliquot**, which is the output that matters. Two pieces of the custody chain are deliberately modelled as the seam plus the Subject / Procedure shape, not as device Families:

| Part of the chain | How CORA models it | Why |
| --- | --- | --- |
| The fraction collector | the sample-custody seam (`FC-1`) | a PV-bound aliquot-routing actuator (a collect / waste valve, a tube index, a fill pattern) that captures footprinted aliquots into tubes; no existing Family fits an aliquot-router cleanly, so it is carried in the custody seam, not coined at n=1 |
| The 96-well plate addressing | a Procedure + a Subject custody thread (`HT-1`) | the plate is addressed alpha-numerically (8 columns x 12 rows) by pure Python plus a coordinate table, with no robot, no sample-changer, and no PV; moving to a well is a move on the `HighThroughputStage`, the i03 / MX3 / LIX custody-as-Procedure precedent (XFP at the no-robot end) |
| The footprinted aliquot | a Subject carried to offline MS (`SUBJECT-1`, `READOUT-1`) | the run's output is the irradiated sample plus a dose record; the structural analysis (mass spec) is downstream, off the beamline |

These aggregates are not instantiated in this descriptor-and-docs cut; they are the shape the deployment will take, recorded so the reader knows where the footprinting experiment's identity lives: the Subject (which macromolecule, which buffer), the Supply (buffers, radical scavengers, the flow medium), and the Procedure (the dose program plus the aliquot collection), with the dose record as the system of record.

## Sample environment

The only sample-environment readouts in the profile collection are temperature / bias diagnostics (an SR630 thermocouple monitor and the Sydor bias controller), used as alignment-flux proxies rather than as a controlled sample environment; they are read-only and deferred (`TEMP-1`).

## Why no new Family here

The sample stages all reuse the catalog `LinearStage`. The one fluidic device, the delivery pump, reuses the existing loose `FlowController` Family rather than coining a new one. The fraction collector, the 96-well plate, and the solution sample are deliberately not coined as device Families: they are the sample-custody and offline-readout seam, which is where a dose-delivery beamline's novelty belongs (`FC-1`, `HT-1`, `SUBJECT-1`, `READOUT-1`). Nothing here graduates and the catalog is unchanged.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family-reuse rationale and the FlowController rule-of-three, and [the source walk](../beamline.md) for the PVs as read from the profile collection.
