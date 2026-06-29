# Inventory

*The CORA Asset model for the operational core of P01 modelled today: the planned device tree and what still needs confirming.*

This cut models the two optics hutches (the undulator, the double-crystal monochromator, the deflection mirrors, the front-end and secondary slits, the diamond monitor, the RIXS pre-optic) and the three experiment hutches (EH1 nuclear resonant scattering, EH2 diffraction, EH3 RIXS). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p01/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P01, CORA's first PETRA III beamline, **coins no new Family and changes nothing in the catalog**: it reuses the optics / motion Families graduated across the fleet. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P01` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P01` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p01-oh1 | undulator source, 2.5-80 keV; gap / taper virtual axes, period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p01-oh1 | double-crystal monochromator; crystal cut pending (MONO-1) |
| `Mirror1` | `Device` | Mirror | p01-oh1 | first deflection / harmonic-rejection mirror; coating pending (OPT-1) |
| `Mirror2` | `Device` | Mirror | p01-oh1 | second deflection mirror; coating pending (OPT-1) |
| `FrontEndSlit1` | `Device` | Slit | p01-oh1 | first front-end definition slit (OPT-1) |
| `FrontEndSlit2` | `Device` | Slit | p01-oh1 | second front-end definition slit (OPT-1) |
| `SecondarySlit` | `Device` | Slit | p01-oh2 | secondary defining slit (OPT-1) |
| `DiamondMonitor` | `Device` | FluxMonitor | p01-oh2 | diamond beam-position / flux monitor; role pending (OPT-1) |
| `RIXSPreOptic` | `Device` | LinearStage | p01-oh2 | RIXS pre-optic translation; optic kind pending (OPT-1) |
| `HighResMono400` | `Device` | Monochromator | p01-eh1 | high-resolution mono, 400 channel-cut + piezo fine axes (NRS-1) |
| `HighResMono1064` | `Device` | Monochromator | p01-eh1 | high-resolution mono, 1064 channel-cut + piezo fine axes (NRS-1) |
| `HighResMono3D` | `Device` | Monochromator | p01-eh1 | high-resolution mono, 3-bounce 'd' configuration (NRS-1) |
| `HighResMono3W` | `Device` | Monochromator | p01-eh1 | high-resolution mono, 3-bounce 'w' configuration (NRS-1) |
| `HighResMonoEnergy` | `Device` | PseudoAxis | p01-eh1 | virtual energy axes coupling the HRM theta motions (NRS-1) |
| `CompoundRefractiveLens` | `Device` | Transfocator | p01-eh1 | CRL focusing assembly; lens count / material pending (OPT-1) |
| `BeamDefiningSlit` | `Device` | Slit | p01-eh1 | EH1 beam-defining JJ slit |
| `BeamPositionMonitor` | `Device` | FluxMonitor | p01-eh1 | EH1 beam-position monitor stage; role candidate (DIAG-1) |
| `IonChamber` | `Device` | FluxMonitor | p01-eh1 | EH1 ion-chamber stage, flux normalization (DIAG-1) |
| `SampleTable` | `Device` | Table | p01-eh1 | EH1 sample / instrument table |
| `Goniometer` | `Device` | Goniometer | p01-eh2 | EH2 sample-orientation circle (theta / two-theta); not the composed Diffractometer Assembly (DIFF-1) |
| `SampleStage` (EH2) | `Device` | LinearStage | p01-eh2 | EH2 sample positioning / centring (x / y / tilt) |
| `DefiningSlit` | `Device` | Slit | p01-eh2 | EH2 beam-defining JJ slit |
| `DetectorSlit` (EH2) | `Device` | Slit | p01-eh2 | EH2 detector / receiving slit |
| `DetectorTable` | `Device` | Table | p01-eh2 | EH2 detector table |
| `DetectorStage` (EH2) | `Device` | LinearStage | p01-eh2 | EH2 detector positioning stage; detector device pending (DET-1) |
| `KBMirrorHorizontal` | `Device` | Mirror | p01-eh3 | horizontal-focusing KB mirror; bend radius pending (OPT-1) |
| `KBMirrorVertical` | `Device` | Mirror | p01-eh3 | vertical-focusing KB mirror; bend radius pending (OPT-1) |
| `SampleStage` (EH3) | `Device` | LinearStage | p01-eh3 | EH3 RIXS sample stage (x / y / b / rot / tilt) (SAMPLE-1) |
| `DetectorSlit` (EH3) | `Device` | Slit | p01-eh3 | EH3 detector / receiving slit |
| `InstrumentTable` | `Device` | Table | p01-eh3 | EH3 spectrometer table (virtual x / y over jacks) |
| `DetectorStage` (EH3) | `Device` | LinearStage | p01-eh3 | EH3 main detector positioning stage; detector device pending (DET-1) |
| `SecondaryDetectorStage` | `Device` | LinearStage | p01-eh3 | EH3 secondary detector arm; role pending (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `FluxMonitor`, `LinearStage`, `PseudoAxis`, `Transfocator`, `Table`, `Goniometer`. No new family is coined and nothing graduates. The detector devices (the NRS avalanche photodiode, the RIXS and diffraction detectors) are named but not bound, because the OnlineXML carries their positioning stages, not the detector device servers (`DET-1`).

## Cross-cutting controllers

The motion-controller classes, related to the devices sideways by `controller_id`, not nested in the beam-path tree:

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 stepper controllers, the dominant P01 motor class (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | generic Tango motor controllers (DCM, virtual axes) (CTRL-1) |
| `VirtualMotorExecutors` | MotionController | Tango_vmexecutor | Sardana virtual-motor executors (coupled energy / slit axes) (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (two optics, three experiment) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Which HRM is in beam per isotope / resolution | the four `HighResMono*` | `unknown-pending-confirmation` | (NRS-1) |
| The mirror coatings / stripes and KB bend radii | `Mirror1`, `Mirror2`, `KBMirrorHorizontal`, `KBMirrorVertical` | `unknown-pending-confirmation` | (OPT-1) |
| The CRL lens count and material | `CompoundRefractiveLens` | `unknown-pending-confirmation` | (OPT-1) |
| The EH2 goniometer full circle count and detector arm | `Goniometer` | `unknown-pending-confirmation` | (DIFF-1) |
| The EH3 RIXS sample-stage / environment detail | `SampleStage` (EH3) | `unknown-pending-confirmation` | (SAMPLE-1) |
| The detector models per endstation | the `DetectorStage` Assets | `unknown-pending-confirmation` | (DET-1) |
| The diagnostics handles and roles | `BeamPositionMonitor`, `IonChamber`, `DiamondMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
