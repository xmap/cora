# Inventory

*The CORA Asset model for I03: the planned device tree, the dodal-derived control handles, and what still needs confirming.*

I03 is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i03/beamline.yaml) descriptor that the Source page renders from.

As at I22, the **control handles are known**: dodal records the real EPICS PV prefixes (`BL03I` beamline root, `SR03I` insertion). Devices bind to catalog [Families](../../catalog/families.md) where one fits. No vendor Model is bound: dodal names hardware (Dectris Eiger, Oxford Cryosystems, the sample robot) but none is procured into the CORA catalog.

## The Asset tree

Root Asset `I03` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`. Bold families are loose design-intent names not in the catalog (they render as plain text). `Goniometer` is **not** bold: I03 graduates it into the catalog (see [Model](model.md)). PV prefixes are the dodal dry facts, carried `confirm`.

| Asset | Family | Control handle (dodal) | Notes |
| --- | --- | --- | --- |
| `I03` | (root) | | bound to the Diamond Site |
| `Undulator` | InsertionDevice | `SR03I-MO-SERVC-01:` | MX source; gap-to-energy lookup, harmonic ~3 |
| `StorageRing` | **StorageRing** | | machine-level, observe-only ring state; loose, reused from I22 |
| `DCM` | Monochromator | `BL03I-MO-DCM-01:` | double-crystal mono, Si(111); energy/wavelength virtual axes |
| `VFM` | Mirror | `BL03I-OP-VFM-01:` | focusing mirror; selectable coatings + 22-channel bimorph bend |
| `DiamondFilter` | Filter | `BL03I-MO-FLTR-01:Y` | CVD diamond filter paddle |
| `Attenuator` | Filter | `BL03I-EA-ATTN-01:` | binary absorber-foil attenuator; Filter Family covers it |
| `CollimationTable` | Table | `BL03I-MO-TABLE-01` | collimation support table |
| `BeamStop` | BeamStop | `BL03I-MO-BS-01:` | on-axis beamstop (positioned) |
| `ApertureScatterguard` | Aperture | `BL03I-MO-MAPT-01:` / `BL03I-MO-SCAT-01:` | coordinated aperture + scatterguard; Aperture Family |
| `HutchShutter` | Shutter | `BL03I` (PSS-interlocked) | hutch safety shutter |
| `SampleShutter` | Shutter | `BL03I-EA-SHTR-01:` | fast sample shutter (Zebra-driven) |
| `QBPM` | **Diagnostic** | `BL03I-DI-QBPM-01:` | quadrant BPM; presents Sensor; loose, reuses 2-BM's Diagnostic family |
| `Flux` | **FluxMonitor** | `BL03I-MO-FLUX-01:` | flux readout; presents Sensor; loose, reused from I22 |
| `IPin` | **FluxMonitor** | `BL03I-EA-PIN-01:` | ion-chamber pin diode; presents Sensor; loose |
| `XBPMFeedback` | (deferred) | `BL03I-EA-FDBK-01:` | beam-position feedback loop; modelling deferred |
| `Goniometer` | Goniometer | `BL03I-MO-SGON-01:` | the Smargon; graduated the Goniometer Family (catalog) |
| `LowerGonio` | LinearStage | `BL03I-MO-GONP-01:` | lower goniometer x/y/z base |
| `Robot` | (Positioner, deferred) | `BL03I-MO-ROBOT-01:` | sample-changing robot; one Positioner Asset + Subject + Clearance (19-BM shape), not a new Family |
| `Backlight` | **Backlight** | `BL03I` | sample illumination; new loose family |
| `Cryostream` | TemperatureController | `BL03I-EA-CSTRM-01:` | Oxford cryostream; settable actuator; loose, reused from I22 |
| `Thawer` | TemperatureController | `BL03I-EA-THAW-01` | sample thawer; settable actuator; loose |
| `Eiger` | Camera | `BL03I-EA-EIGER-01:` | Dectris Eiger area detector (Detector Role) |
| `DetectorMotion` | LinearStage | `BL03I-MO-DET-01:` | detector translation; integrated shutter |
| `FluorescenceDetector` | (Sensor, deferred) | `BL03I-EA-FLU-01:` | retractable fluorescence detector; presents Sensor; loose |
| `Zebra` | TimingController | `BL03I-EA-ZEBRA-01:` | FPGA trigger fan-out |
| `Panda` | TimingController | `BL03I-EA-PANDA-01:` | PandABox timing + HDF capture |

Reused catalog Families (no new Family needed): `InsertionDevice`, `Monochromator`, `Mirror`, `Filter`, `Table`, `BeamStop`, `Aperture`, `Shutter`, `Camera`, `LinearStage`, `TimingController`. **One new catalog Family graduated:** `Goniometer` (the Smargon, the first canonical goniometer). Loose families reused from siblings: `StorageRing`, `FluxMonitor` (from I22) and `Diagnostic` (from 2-BM, the family behind its BeamPositionMonitor device). `TemperatureController` (the cryostream and thawer) was loose here too but has since graduated to a catalog Family (presenting the `Regulator` Role) on the i11 rule-of-three. Only `Backlight` is genuinely new and loose (an illumination affordance no Family carries). The robot and the fluorescence detector present existing Roles (Positioner, Sensor) and are carried with their shape deferred rather than minting a Family, mirroring how 19-BM and 32-ID handle the sample-exchange arm.

## Pending confirmations

Every value below is reverse-engineered from dodal or inferred, awaiting the beamline team or a Diamond source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which hutch each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Undulator energy range and gap-to-energy curve | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Optic internal settings (coatings, bimorph, d-spacing, thermal) | `DCM`, `VFM` | `unknown-pending-confirmation` | (OPT-1) |
| Storage-ring state modelling boundary | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Diagnostics Sensor modelling and beam-center | `QBPM`, `Flux`, `IPin` | `unknown-pending-confirmation` | (DIAG-1) |
| XBPM feedback loop: modelled construct vs floor | `XBPMFeedback` | `unknown-pending-confirmation` | (FEEDBACK-1) |
| Goniometer per-axis decomposition and centre-of-rotation calibration | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Robot Asset, Clearance gate, and Subject custody lifecycle | `Robot` | `unknown-pending-confirmation` | (ROBOT-1) |
| Settable-actuator command path for the sample environment | `Cryostream`, `Thawer` | `unknown-pending-confirmation` | (ENV-1) |
| Eiger threshold/beam-center and fluorescence/backlight modelling | `Eiger`, `FluorescenceDetector`, `Backlight` | `unknown-pending-confirmation` | (DET-1) |
| MX Capabilities and Methods in scope | techniques | `unknown-pending-confirmation` | (TECH-1) |
| Hardware identity (serial numbers, asset tags) | all devices | `unknown-pending-confirmation` | (ID-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1, the energy-change seam ENERGY-1, the endstation Assembly ASSEMBLY-1, and the triggering binding TRIG-1) are on [Open questions](questions.md) without a placeholder here.
