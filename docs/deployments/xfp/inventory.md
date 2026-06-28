# Inventory

*The CORA Asset model for the operational core of XFP modelled today: the planned device tree and what still needs confirming.*

This cut models the XF:17BM white-beam optics, the dose-delivery gating, and the XF:17BMA-ES:1 / ES:2 footprinting endstations; the fraction collector, the 96-well plate addressing, the temperature diagnostics, the intermittently-connected stages, and the monochromatic XAS endstation (ES:3) are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/xfp/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. XFP coins **no new Family**: the dose-delivery and sample devices reuse the existing `Mirror` / `Slit` / `Filter` / `Shutter` / `TimingController` / `LinearStage` / `FluxMonitor` vocabulary, and the one reuse worth naming is the sample-delivery pump, which binds the catalog `FlowController` Family (graduated; presents Regulator), with XFP its fourth consumer (see [Model](model.md#the-flowcontroller-rule-of-three)). The genuinely-new parts, the dose-as-experiment-variable, the solution Subject, and the offline mass-spec readout, land on the Method, the Subject, and the seam, not on devices. Notably there is **no Detector-role imaging device**: the readout is offline. Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `XFP` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `XFP` | `Unit` | (root) | - | bound to the NSLS-II Site; 17-BM |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring current, observe-only, `SR:OPS-BI{DCCT:1}` (MACHINE-1, SRC-1) |
| `FrontEndMirror` | `Device` | Mirror | xfp-optics | bendable white-beam mirror, `XF:17BM-OP{Mir:1}` (OPT-1) |
| `WhiteBeamSlit` | `Device` | Slit | xfp-optics | front-end white-beam slit, `FE:C17B-OP{Slt:1}` (OPT-2) |
| `DefiningSlit` | `Device` | Slit | xfp-optics | ADC defining slit (its gap sets the HTFly exposure), `XF:17BMA-OP{Slt:ADC}` (OPT-2, HT-1) |
| `FilterWheel` | `Device` | Filter | xfp-optics | eight-position Al filter wheel (dose rate), `XF:17BMA-ES:1{Fltr:1}` (ATTN-1) |
| `PhotonShutter` | `Device` | Shutter | xfp-optics | PPS front-end photon shutter, `XF:17BM-PPS{Sh:FE}` (PSS-1) |
| `DoseShutter` | `Device` | Shutter | xfp-optics | EPS timed-exposure pre-shutter, `XF:17BMA-EPS{Sh:1}` (DOSE-1) |
| `DoseTimer` | `Device` | TimingController | xfp-optics | DG535 delay generator firing the ms Uniblitz fast shutter, `XF:17BMA-ES:2{DG:1}` (DOSE-1) |
| `CapillaryFlowStage` | `Device` | LinearStage | xfp-endstation | capillary-flow sample stage (x / y), `XF:17BMA-ES:1{Stg:5}` (SAMPLE-1) |
| `HighThroughputStage` | `Device` | LinearStage | xfp-endstation | 96-well plate stage (x / y); well addressing is a Procedure, no robot (HT-1) |
| `HtFlyStage` | `Device` | LinearStage | xfp-endstation | shutterless HTFly stage (velocity = exposure), `XF:17BMA-ES:2{HTFly:1}` (HT-1, DOSE-1) |
| `DeliveryPump` | `Device` | FlowController | xfp-endstation | sample-delivery syringe pump, `XF:17BMA-ES:1{Pmp:02}`; binds the graduated `FlowController` (presents Regulator), XFP its fourth consumer (FLOW-1) |
| `FluxMonitor` | `Device` | FluxMonitor | xfp-endstation | QuadEM electrometer, incident flux + time-series = dose, `XF:17BM-BI{EM:1}` (DET-1, DOSE-1) |
| `BeamPositionMonitor` | `Device` | BeamPositionMonitor (loose) | xfp-endstation | Sydor 4-channel position + sum-flux monitor, `XF:17BM-BI{EM:BPM1}` (DIAG-1) |

Families reused from the catalog: `Mirror`, `Slit`, `Filter`, `Shutter`, `TimingController`, `LinearStage`, `FluxMonitor`, and `FlowController` (the delivery pump; graduated on the i22 / 7-BM / LIX / XFP rule-of-three, presents Regulator). Loose families reused from siblings: `StorageRing` (supply), `BeamPositionMonitor` (held under review, DIAG-1). No new family is coined here; the delivery pump reuses the graduated catalog `FlowController`. There is no Detector-role imaging device: the readout is offline (READOUT-1).

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-endstation hutch grouping | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Bending-magnet source | the source | `unknown-pending-confirmation` | (SRC-1) |
| White vs pink vs mono in the footprinting path | the beam conditioning | `unknown-pending-confirmation` | (WHITE-1) |
| Control handles (EPICS PVs) and data plane | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Front-end mirror coating and bend | `FrontEndMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Attenuator chain (filter wheel, z-attenuator, pinholes) | `FilterWheel` | `unknown-pending-confirmation` | (ATTN-1) |
| Dose-delivery chain and flux-to-dose calibration | `DoseShutter`, `DoseTimer`, `FluxMonitor` | `unknown-pending-confirmation` | (DOSE-1) |
| Capillary-flow sample stage | `CapillaryFlowStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| High-throughput plate + HTFly + well addressing | `HighThroughputStage`, `HtFlyStage` | `unknown-pending-confirmation` | (HT-1) |
| Delivery-pump Family | `DeliveryPump` | `unknown-pending-confirmation` | (FLOW-1) |
| Fraction collector and aliquot custody | the sample handling | `unknown-pending-confirmation` | (FC-1) |
| The solution Subject | the sample | `unknown-pending-confirmation` | (SUBJECT-1) |
| Temperature / bias diagnostics | the diagnostics | `unknown-pending-confirmation` | (TEMP-1) |
| Flux / dose-monitor channel map | `FluxMonitor` | `unknown-pending-confirmation` | (DET-1) |
| Beam-position-monitor position-vs-intensity split | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Offline mass-spec readout hand-off | the readout | `unknown-pending-confirmation` | (READOUT-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
