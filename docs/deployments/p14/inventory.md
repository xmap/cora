# Inventory

*The CORA Asset model for the operational core of P14 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics hutch (the KB focusing-mirror motions, the focusing mirror, the CRL transfocator, the beam-defining slits, the energy axis, the beam diagnostics), EH1 (the EMBLMiniDiff diffractometer, the aperture / beamstop / objective / illumination, the three Eiger detectors, the flux / XRF detectors, the X-ray imaging camera), and EH2 (the EMBLBSD diffractometer, the Pilatus 2M, the EH2 table and beam-defining optics). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p14/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P14, CORA's second EMBL Hamburg beamline, **coins no new Family and changes nothing in the catalog**: it is a reuse-and-reinforce MX deployment, reusing the MX Families graduated at i03 and exercised across the MX fleet (including its sibling P13). The control handles are read from the public MXCuBE configs (Exporter addresses for the microdiff motions, TINE channels for the detector / energy / beam services); no vendor Models are bound. Two experiment hutches share one source / optics chain (`EH-1`); some EH2 axes are published as `MotorMockup` and flagged (`MOCK-1`).

## The Asset tree

Root Asset `P14` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P14` | `Unit` | (root) | - | bound to the PETRA III Site; operated by EMBL Hamburg (SEAM-1) |
| `KBMirrorStage` | `Device` | LinearStage | p14-oh | KB focusing-mirror pitch / roll motions, grouped (OPT-1, GROUP-1) |
| `FocusingMirror` | `Device` | Mirror | p14-oh | KB beam-focusing optic; coating / substrate not in config (OPT-1) |
| `CompoundRefractiveLens` | `Device` | Transfocator | p14-oh | CRL transfocator, shared with EH2; lens count / material pending (OPT-1) |
| `BeamDefiningSlits` | `Device` | Slit | p14-oh | beam-defining slit boxes on the P14Atto group, grouped (OPT-1, GROUP-1) |
| `BeamEnergy` | `Device` | PseudoAxis | p14-oh | photon-energy virtual axis (TINEEnergy), shared by both hutches (ENERGY-1, OPT-1) |
| `BeamDiagnostics` | `Device` | FluxMonitor | p14-oh | beam intensity / centring diagnostics, grouped (DIAG-1) |
| `DiffractometerEH1` | `Device` | Goniometer | p14-eh1 | EH1 EMBLMiniDiff microdiffractometer; omega / kappa / centring axes (MX-1) |
| `BeamApertureEH1` | `Device` | Aperture | p14-eh1 | EH1 beam-defining aperture; size table pending (OPT-1) |
| `BeamstopEH1` | `Device` | BeamStop | p14-eh1 | EH1 microdiff beamstop; direct-beam stop |
| `SampleObjectiveEH1` | `Device` | Objective | p14-eh1 | EH1 on-axis sample-viewing zoom objective (OAV-1) |
| `SampleIlluminationEH1` | `Device` | Backlight | p14-eh1 | EH1 microdiff sample illumination; Backlight affordance (DET-1) |
| `DiffractometerEH2` | `Device` | Goniometer | p14-eh2 | EH2 EMBLBSD diffractometer; some axes MotorMockup (MX-1, MOCK-1) |
| `BeamApertureEH2` | `Device` | Aperture | p14-eh2 | EH2 beam-defining aperture; size table pending (OPT-1) |
| `BeamstopEH2` | `Device` | BeamStop | p14-eh2 | EH2 beamstop; direct-beam stop |
| `SampleObjectiveEH2` | `Device` | Objective | p14-eh2 | EH2 on-axis sample-viewing zoom objective (OAV-1) |
| `SampleIlluminationEH2` | `Device` | Backlight | p14-eh2 | EH2 sample illumination; Backlight affordance (DET-1) |
| `ExperimentTableEH2` | `Device` | LinearStage | p14-eh2 | EH2 experiment-table hor / ver positioning; handle pending (TABLE-1, MOCK-1) |
| `EigerDetector` | `Device` | Camera | p14-eh1 | Dectris Eiger 16M silicon area detector; primary MX detector (DET-1) |
| `EigerCdTe16MDetector` | `Device` | Camera | p14-eh1 | Dectris Eiger 16M CdTe; high-energy MX detector variant (DET-1) |
| `EigerCdTe4MDetector` | `Device` | Camera | p14-eh1 | Dectris Eiger 4M CdTe; smaller high-energy MX detector (DET-1) |
| `PilatusDetectorEH2` | `Device` | Camera | p14-eh2 | Dectris Pilatus 2M area detector; EH2 MX detector (DET-1) |
| `DetectorDistance` | `Device` | PseudoAxis | p14-eh1 | detector-distance + resolution virtual axes; EH2 carries its own pair (DET-1) |
| `FluxMonitor` | `Device` | FluxMonitor | p14-eh1 | pin-diode flux monitor; incident-flux normalization (DIAG-1) |
| `OnAxisCamera` | `Device` | Camera | p14-eh1 | EH1 on-axis / sample-changer viewing cameras; handle pending (OAV-1) |
| `XrayImagingCamera` | `Device` | Camera | p14-eh1 | EH1 X-ray imaging camera; centring imaging, handle pending (IMG-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | p14-eh1 | energy-dispersive XRF detector; edge scanning (DET-1) |

Families reused from the catalog: `LinearStage`, `Mirror`, `Transfocator`, `Slit`, `PseudoAxis`, `FluxMonitor`, `Goniometer`, `Aperture`, `BeamStop`, `Objective`, `Camera`, `EnergyDispersiveSpectrometer`, plus the loose `Backlight` (sample-illumination affordance, held for graduation, `DET-1`). No new family is coined and nothing graduates. The automated sample changer is MXCuBE bookkeeping, a deferred sample-exchange Procedure, not a device (`ROBOT-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `ExporterMotionController` | MotionController | Exporter_microdiff | microdiff Exporter hosts (p14md301 / p14md302 / pe2bsd01); diffractometers + beam-defining motions (CTRL-1) |
| `TINEMotionController` | MotionController | TINE_embl | TINE floor; KB mirrors, CRL, energy, detector distance, flux / XRF (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (one optics hutch, two experiment hutches) | the enclosures | `unknown-pending-confirmation` | (ENC-1) (EH-1) |
| The undulator source (absent from the config) | `P14` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (monochromator, KB mirrors, CRL, slits) | `KBMirrorStage`, `FocusingMirror`, `CompoundRefractiveLens`, `BeamDefiningSlits` | `unknown-pending-confirmation` | (OPT-1) |
| The energy / monochromator coupling | `BeamEnergy` | `unknown-pending-confirmation` | (ENERGY-1) |
| The goniometer geometries (both endstations) | `DiffractometerEH1`, `DiffractometerEH2` | `unknown-pending-confirmation` | (MX-1) |
| The EH2 mockup axes (live vs simulated) | `DiffractometerEH2`, `ExperimentTableEH2` | `unknown-pending-confirmation` | (MOCK-1) |
| The EH2 table control handle | `ExperimentTableEH2` | `unknown-pending-confirmation` | (TABLE-1) |
| The aperture-size tables | `BeamApertureEH1`, `BeamApertureEH2` | `unknown-pending-confirmation` | (OPT-1) |
| The OAV objective / on-axis camera handles | `SampleObjectiveEH1`, `SampleObjectiveEH2`, `OnAxisCamera` | `unknown-pending-confirmation` | (OAV-1) |
| The X-ray imaging camera handle | `XrayImagingCamera` | `unknown-pending-confirmation` | (IMG-1) |
| The cryostream service and handles | the sample environments | `unknown-pending-confirmation` | (CRYO-1) |
| The detector models, ROI modes, and geometry | the `Eiger*` / `Pilatus*` / `DetectorDistance` Assets | `unknown-pending-confirmation` | (DET-1) |
| The beam-diagnostic service split | `BeamDiagnostics`, `FluxMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| The automated sample changer | the experiment hutches | `unknown-pending-confirmation` | (ROBOT-1) |
| The Exporter / TINE handle freshness vs the live beamline | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The EMBL / DESY operator and safety boundary | the governance | `unknown-pending-confirmation` | (GOV-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
