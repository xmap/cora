# Fleet recurrence: MAX IV

Cross-fleet device-class frequency across the MAX IV beamlines surveyed under `research/maxiv/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

MAX IV is a Tango + Sardana facility with a partial public device source: only the `contrast` DAQ framework (`maxiv-science/contrast`) carries per-Asset Tango topology, and only for two beamlines (NanoMAX, CoSAXS). This file is filled by hand from those per-beamline `facts.md` device inventories; there is no extractor for the contrast idiom.

!!! warning "Count physical beamlines, not repos"
    Only two MAX IV beamlines are Tier-2-buildable from public source (NanoMAX, CoSAXS); SoftiMAX (contrast scaffold, too thin), BioMAX (controller code, not topology), and the rest (firewalled / staff-only) are not folded here. So the maximum MAX IV recurrence count is 2. NanoMAX has two endstations (diffraction + imaging) in one config; that is one beamline, one data point (a device appearing in both endstations counts once).

## Beamlines folded in so far

| Beamline | Port | Science | Source commit | Note |
| --- | --- | --- | --- | --- |
| NanoMAX | B303A | hard X-ray nanoprobe (ptychography, nano-XRF, nano-diffraction, nano-imaging) | `8e787ac` | NOT yet a deployment; this pass. Two endstations (diffraction B303A-E02 + imaging B303A-E01) sharing one optics train |

CoSAXS (B310A) is the one remaining buildable MAX IV beamline, not yet folded in; its counts will move when its pass lands.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. From NanoMAX alone so far:

| Family | Beamlines | Status |
| --- | --- | --- |
| Mirror | 1 (nanomax) | graduated |
| Monochromator | 1 (nanomax) | graduated |
| Slit | 1 (nanomax) | graduated |
| InsertionDevice | 1 (nanomax) | graduated |
| Filter | 1 (nanomax) | graduated |
| LinearStage | 1 (nanomax) | graduated |
| Goniometer | 1 (nanomax) | graduated |
| PseudoAxis | 1 (nanomax) | graduated |
| Camera | 1 (nanomax) | graduated |
| EnergyDispersiveSpectrometer | 1 (nanomax) | graduated |
| FluxMonitor | 1 (nanomax) | graduated |
| TimingController | 1 (nanomax) | graduated (binding confirm; PandaBox vs GenericProbe) |
| BeamPositionMonitor | 1 (nanomax) | loose (DIAG-1) |

Every Family NanoMAX binds is a graduated catalog entry (plus the loose BeamPositionMonitor held under DIAG-1); NanoMAX coins nothing.

## Device classes by beamline count

The raw `contrast` constructor classes seen in source, before mapping to a CORA Family. These are contrast-framework device classes (not Tango device-server classes); the underlying hardware vendor is encoded in the class.

| Source class | Beamlines |
| --- | --- |
| `TangoMotor` | 1 (nanomax) |
| `SmaractLinearMotor` / `SmaractRotationMotor` | 1 (nanomax) |
| `SmaractLinearMotor_MCS2` / `SmaractRotationMotor_MCS2` | 1 (nanomax) |
| `E727Motor` (PI piezo) | 1 (nanomax) |
| `LC400Motor` (nPoint) | 1 (nanomax) |
| `PiezoLegsMotor` | 1 (nanomax) |
| `DacMotor` (NI-DAC) | 1 (nanomax) |
| `EigerTango` | 1 (nanomax) |
| `Pilatus3` | 1 (nanomax) |
| `Xspress3` | 1 (nanomax) |
| `AlbaEM` | 1 (nanomax) |
| `PandaBox` / `PandaBoxPCAP` | 1 (nanomax) |

## Graduation shortlist (the actionable output)

From NanoMAX alone, **nothing clears a rule-of-three that is not already graduated.** Watches to carry into the CoSAXS pass:

| Candidate Family | Distinct beamlines | Discriminator | Blocker / note |
| --- | --- | --- | --- |
| TimingController (PandaBox) | 1 (nanomax) | fast-scan / fly-scan trigger + encoder capture | already graduated; PandaBox binding confirm (vs GenericProbe). PandaBox is expected at CoSAXS too (a MAX IV / Tango-facility staple), a reinforcement watch. |
| BeamPositionMonitor | 1 (nanomax) + fleet-wide | beam-centroid position monitor | LOOSE, held fleet-wide under `DIAG-1`; do not coin |

One paragraph: NanoMAX, mined as data, earns CORA no new Family. It is the first MAX IV beamline and the first on the contrast DAQ idiom (vs ESRF Beacon YAML, NSLS-II bluesky, APS bits), but every device binds an already-graduated family. Its modelling value is twofold: it is the first MAX IV / Tango-Sardana-floor device pass (validating the survey's "partial-buildable" verdict and the contrast-as-source approach), and it is a two-endstation nanoprobe (ptychography / nano-imaging) on CORA's imaging ladder. The cross-MAX-IV recurrence signal will only become meaningful once CoSAXS is folded in (the second and last buildable beamline); expect Slit, Mirror, Camera, FluxMonitor, and PandaBox/TimingController to reach 2 there.
