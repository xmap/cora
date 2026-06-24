# Inventory

*The CORA Asset model for the part of 2-ID modelled today: the 2-ID-D microprobe hutch as a planned device tree, and what still needs confirming.*

This scaffold models the 2-ID-D scanning fluorescence microprobe hutch; the sister station and the rest of the sector are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-id/beamline.yaml) descriptor that the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) where one fits. The probe-forming zone plate (`ZonePlate`) and the energy-dispersive fluorescence detector (`EnergyDispersiveSpectrometer`) bind to loose Family strings, rendered as plain text: they are device classes not yet earned into the catalog, and no Asset is registered yet to earn them. No vendor Models are bound and no control handles are filled, because parts are not catalogued and PV names are not published (the EAA launcher is a simulation).

## The Asset tree

Root Asset `2-ID` (`tier = Unit`, `facility_code = aps`); the modelled 2-ID-D hutch devices nest below by `parent_id`. The sister experiment hutch and the shared optics-hutch detail are not in this tree (deferred, `TOPO-1`). The undulator and monochromator are the upstream source the hutch draws on.

| Asset | Tier | Family | Design spec / note |
| --- | --- | --- | --- |
| `2-ID` | `Unit` | (root) | bound to the APS Site; Sector 2 microprobe beamline, 2-ID-D hutch modelled |
| `Undulator` | `Device` | InsertionDevice | Sector 2 undulator source, upstream and shared |
| `Monochromator` | `Device` | Monochromator | double-crystal monochromator assumed; upstream optics, energy unconfirmed |
| `ZonePlate` | `Device` | ZonePlate (loose) | probe-forming Fresnel zone plate in 2-ID-D; `zp_z` focus axis driven by EAA autofocus |
| `SamplePositioning` | `Device` | LinearStage | sample-scanning raster stack in 2-ID-D; `samy` and `samz` evidenced |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer (loose) | energy-dispersive XRF detector in 2-ID-D; records a spectrum per scan point |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `LinearStage`. Bound to loose Family strings (not yet in the catalog): `ZonePlate`, `EnergyDispersiveSpectrometer`. These are earned into the catalog only when a confirmed device registers and a naming review accepts the name; that does not happen in a design-phase scaffold. The detector Family name in particular must avoid the reserved `Detector` Role noun (see [Model](model.md#deliberately-not-here-yet)).

## Pending confirmations

Every value below is an inference from the EAA corpus or a world-fact awaiting the 2-ID team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch roster, optics-hutch location, and root topology (one vs more hutches; post-APS-U layout) | the root, the optics, the hutches | `unknown-pending-confirmation` | (TOPO-1) |
| Control handles (EPICS PVs, drive crates, IOC hosts) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| 2-ID-D hutch PSS permit signal | the enclosure | `unknown-pending-confirmation` | (PSS-1) |
| Undulator device type, period, and gap | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Front-end and beam-defining optics (mask, window, slits), undescribed by EAA | the source stage | `unknown-pending-confirmation` | (SRC-2) |
| Monochromator presence, crystal, energy range, and axes | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Zone-plate parameters and the order-sorting aperture | `ZonePlate` | `unknown-pending-confirmation` | (OPTICS-1) |
| Sample-scanning axis complement (horizontal scan axis, coarse vs fine piezo) | `SamplePositioning` | `unknown-pending-confirmation` | (AXIS-1) |
| Fluorescence detector model, element channels, and segmentation | `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| Detection readout chain (preamplifier, EPICS scalers, I0 flux monitors) | the detection electronics | `unknown-pending-confirmation` | (DET-2) |
| Sample environment (any in-situ stage, and whether a rotation axis exists) | the sample stage | `unknown-pending-confirmation` | (ENV-1) |
| Endstation supplies (cooling, sample-environment gases) | `resources` | `unknown-pending-confirmation` | (SUP-1) |
