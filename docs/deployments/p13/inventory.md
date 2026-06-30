# Inventory

*The CORA Asset model for the operational core of P13 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics hutch (the KB focusing-mirror motions, the energy axis, the beam diagnostics) and the experiment hutch (the EMBLMiniDiff diffractometer, its centring stage, the aperture / beamstop / objective / illumination, the Eiger and Pilatus detectors, the flux and XRF detectors). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p13/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P13, CORA's first EMBL Hamburg beamline, **coins no new Family and changes nothing in the catalog**: it is a reuse-and-reinforce MX deployment, reusing the MX Families graduated at i03 and exercised across the MX fleet. The control handles are read from the public MXCuBE config (Exporter addresses for the microdiff motions, TINE channels for the detector / energy / beam services); no vendor Models are bound. Because EMBL publishes the MXCuBE config, the experiment hutch resolves into a real `Goniometer` rather than the grouped banks the sparser DESY OnlineXML forced at P11 (`MX-1`).

## The Asset tree

Root Asset `P13` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P13` | `Unit` | (root) | - | bound to the PETRA III Site; operated by EMBL Hamburg (SEAM-1) |
| `KBMirrorStage` | `Device` | LinearStage | p13-oh | KB focusing-mirror pitch / roll motions, grouped (OPT-1, GROUP-1) |
| `BeamEnergy` | `Device` | PseudoAxis | p13-oh | photon-energy virtual axis (TINEEnergy); mono motions not labelled (ENERGY-1, OPT-1) |
| `BeamDiagnostics` | `Device` | FluxMonitor | p13-oh | beam-conditioning-unit intensity / centring diagnostics, grouped (DIAG-1) |
| `Diffractometer` | `Device` | Goniometer | p13-eh | EMBLMiniDiff microdiffractometer; omega / kappa / centring axes (MX-1) |
| `MDCentringStage` | `Device` | LinearStage | p13-eh | diffractometer vertical centring axis + coupled motions (MX-1) |
| `BeamAperture` | `Device` | Aperture | p13-eh | beam-defining aperture on the microdiff; size table pending (OPT-1) |
| `Beamstop` | `Device` | BeamStop | p13-eh | microdiff beamstop; direct-beam stop |
| `SampleObjective` | `Device` | Objective | p13-eh | on-axis sample-viewing zoom objective (OAV-1) |
| `SampleIllumination` | `Device` | Backlight | p13-eh | microdiff sample illumination; Backlight affordance (DET-1) |
| `EigerDetector` | `Device` | Camera | p13-eh | Dectris Eiger 16M area detector; primary MX detector (DET-1) |
| `PilatusDetector` | `Device` | Camera | p13-eh | Dectris Pilatus 6M area detector; alternative MX detector (DET-1) |
| `DetectorDistance` | `Device` | PseudoAxis | p13-eh | detector-distance + resolution virtual axes (DET-1) |
| `FluxMonitor` | `Device` | FluxMonitor | p13-eh | pin-diode flux monitor; incident-flux normalization (DIAG-1) |
| `OnAxisCamera` | `Device` | Camera | p13-eh | on-axis / sample-changer viewing cameras; handle pending (OAV-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | p13-eh | energy-dispersive XRF detector; edge scanning (DET-1) |

Families reused from the catalog: `LinearStage`, `PseudoAxis`, `FluxMonitor`, `Goniometer`, `Aperture`, `BeamStop`, `Objective`, `Camera`, `EnergyDispersiveSpectrometer`, plus the loose `Backlight` (sample-illumination affordance, held for graduation, `DET-1`). No new family is coined and nothing graduates. The automated sample changer is MXCuBE bookkeeping, a deferred sample-exchange Procedure, not a device (`ROBOT-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `ExporterMotionController` | MotionController | Exporter_microdiff | microdiff Exporter host; diffractometer + beam-defining motions (CTRL-1) |
| `TINEMotionController` | MotionController | TINE_embl | TINE floor; KB mirrors, energy, detector distance, flux / XRF (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (inferred optics / experiment split) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator source (absent from the config) | `P13` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (monochromator, KB mirrors) | `KBMirrorStage`, `BeamEnergy` | `unknown-pending-confirmation` | (OPT-1) |
| The energy / monochromator coupling | `BeamEnergy` | `unknown-pending-confirmation` | (ENERGY-1) |
| The goniometer geometry (kappa range, axis offsets) | `Diffractometer` | `unknown-pending-confirmation` | (MX-1) |
| The aperture-size table | `BeamAperture` | `unknown-pending-confirmation` | (OPT-1) |
| The OAV objective / on-axis camera handle | `SampleObjective`, `OnAxisCamera` | `unknown-pending-confirmation` | (OAV-1) |
| The cryostream service and handles | the sample environment | `unknown-pending-confirmation` | (CRYO-1) |
| The detector models, ROI modes, and geometry | `EigerDetector`, `PilatusDetector`, `DetectorDistance` | `unknown-pending-confirmation` | (DET-1) |
| The beam-diagnostic service split | `BeamDiagnostics`, `FluxMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| The automated sample changer | the experiment hutch | `unknown-pending-confirmation` | (ROBOT-1) |
| The Exporter / TINE handle freshness vs the live beamline | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The EMBL / DESY operator and safety boundary | the governance | `unknown-pending-confirmation` | (GOV-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
