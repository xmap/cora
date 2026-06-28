# Inventory

*The CORA Asset model for the operational core of ID32 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared soft X-ray optics, the RIXS spectrometer endstation, and the XMCD high-field-magnet endstation. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id32/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. ID32, CORA's first ESRF deployment, **coins no new Family and changes nothing in the catalog**: the APPLE-II undulators reuse `InsertionDevice` and the polarization is a `PseudoAxis` (the i06 / i10 precedent), and the three loose families ID32 pushes to a rule-of-three (`SpectrometerArm`, `Magnet`, `PolarizationAnalyzer`) are held, their graduations deferred to dedicated gated PRs (see [Model](model.md#loose-families-held-at-the-rule-of-three)). Control handles are filled from the BLISS Beacon config (Tango / IcePAP / BLISS addresses); no vendor Models are bound.

## The Asset tree

Root Asset `ID32` (`tier = Unit`, `facility_code = esrf`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `ID32` | `Unit` | (root) | - | bound to the ESRF Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | ESRF-EBS ring state, observe-only (MACHINE-1) |
| `Undulator` | `Device` | InsertionDevice | id32-optics | two APPLE-II undulators (HU70a + HU70c), `id/master/id32` (gaps hu70ag / hu70cg, phases hu70ap / hu70cp) (SRC-1) |
| `Polarization` | `Device` | PseudoAxis | id32-optics | polarization axis over the APPLE-II phase (BLISS PolarizationPolicy: horizontal / vertical / linear) (POL-1) |
| `BeamEnergy` | `Device` | PseudoAxis | id32-optics | incident-energy axis (BLISS `energy` calc over `energy_pgm` + both undulators) (MONO-1) |
| `Monochromator` | `Device` | GratingMonochromator | id32-optics | soft X-ray PGM (BLISS `pgm`; gratings XMCD_300 / XMCD_900 / RIXS_800 / RIXS_1600) (MONO-1) |
| `FocusingMirror` | `Device` | Mirror | id32-optics | soft X-ray focusing mirrors; absent from the public BLISS config, deferred (OPT-1) |
| `BeamSlit` | `Device` | Slit | id32-optics | primary / secondary / mono beam-defining slits (BLISS `slits`, hgap / hoffset; IcePAP iceid321) (OPT-2) |
| `Diffractometer` | `Device` | Goniometer | id32-rixs | 4-circle sample diffractometer (DiffE4CH, E4CH) (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | id32-rixs | reciprocal-space (hkl) axis over the diffractometer (DIFF-2) |
| `RixsSpectrometerArm` | `Device` | SpectrometerArm (loose) | id32-rixs | ~5 m dispersive RIXS arm (rixs_spectro, IcePAP iceid324); held at rule-of-three (RIXS-1) |
| `Polarimeter` | `Device` | PolarizationAnalyzer (loose) | id32-rixs | scattered-beam polarimeter on the RIXS arm (iceid324 thpol/...); 3rd consumer, held (POL-2) |
| `RixsDetector` | `Device` | Camera | id32-rixs | Andor CCD, `id32/limaccds/andor_1` (DET-1) |
| `Magnet` | `Device` | Magnet (loose) | id32-xmcd | 9 T / 4 T XMCD split-coil magnet, `id32/cryogenic_magnet_ps/xmcd1`; 3rd consumer, held (MAG-1) |
| `SampleTemperatureController` | `Device` | TemperatureController | id32-xmcd | VTI sample LakeShore 336, `id32/regulation/ls336_hfm` (TEMP-1) |
| `CryostatDiagnostics` | `Device` | TemperatureController | id32-xmcd | coil / shield diagnostics LakeShore 340, `id32/regulation/ls340_hfm` (TEMP-1) |
| `XesSpectrometerArm` | `Device` | SpectrometerArm (loose) | id32-xmcd | XES Rowland arm (xes_spectro, IcePAP iceid329); the 2nd arm completing the rule-of-three, held (RIXS-1) |
| `XesDetector` | `Device` | Camera | id32-xmcd | Andor CCD, `id32/limaccds/andor_2` (DET-1) |
| `SampleStage` | `Device` | LinearStage | id32-xmcd | XMCD sample stage in the magnet bore (SAMPLE-1) |

Families reused from the catalog: `InsertionDevice`, `PseudoAxis`, `GratingMonochromator`, `Mirror`, `Slit`, `Goniometer`, `Camera`, `TemperatureController`, `LinearStage`. Loose families reused from siblings: `StorageRing` (supply), `SpectrometerArm` (SIX; held at rule-of-three, RIXS-1), `Magnet` (4-ID / i10-1; held, MAG-1), `PolarizationAnalyzer` (4-ID / i10; held, POL-2). No new family is coined and nothing graduates (the three graduations are deferred to dedicated PRs).

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the endstations | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| APPLE-II period and segments | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (Tango / IcePAP / BLISS) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| ESRF PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Polarization domain and conversion rule | `Polarization` | `unknown-pending-confirmation` | (POL-1) |
| PGM gratings, cff, energy range | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and handles | `FocusingMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis map | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Diffractometer circle roles and Assembly | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space partition rule | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| SpectrometerArm geometry and graduation | `RixsSpectrometerArm`, `XesSpectrometerArm` | `unknown-pending-confirmation` | (RIXS-1) |
| Polarimeter family at n=3 | `Polarimeter` | `unknown-pending-confirmation` | (POL-2) |
| Magnet fields, ramp, cryogens, graduation | `Magnet` | `unknown-pending-confirmation` | (MAG-1) |
| LakeShore sensor / loop maps | `SampleTemperatureController`, `CryostatDiagnostics` | `unknown-pending-confirmation` | (TEMP-1) |
| Andor CCD configurations | `RixsDetector`, `XesDetector` | `unknown-pending-confirmation` | (DET-1) |
| XMCD sample-stage axes | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Vacuum extent and liquid-helium supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
