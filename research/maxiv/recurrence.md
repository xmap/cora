# Fleet recurrence: MAX IV

Cross-fleet device-class frequency across the MAX IV beamlines surveyed under `research/maxiv/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

MAX IV is a Tango + Sardana facility with a partial public device source: only the `contrast` DAQ framework (`maxiv-science/contrast`) carries per-Asset Tango topology, and only for two beamlines (NanoMAX, CoSAXS). This file is filled by hand from those per-beamline `facts.md` device inventories; there is no extractor for the contrast idiom.

!!! warning "Count physical beamlines, not repos"
    Only two MAX IV beamlines are Tier-2-buildable from public source (NanoMAX, CoSAXS); SoftiMAX (contrast scaffold, too thin), BioMAX (controller code, not topology), and the rest (firewalled / staff-only) are not folded here. So the maximum MAX IV recurrence count is 2, and this file now covers BOTH, i.e. the complete public-buildable MAX IV set. NanoMAX has two endstations (diffraction + imaging) in one config; that is one beamline, one data point (a device appearing in both endstations counts once).

## Beamlines folded in so far

| Beamline | Port | Science | Source commit | Note |
| --- | --- | --- | --- | --- |
| NanoMAX | B303A | hard X-ray nanoprobe (ptychography, nano-XRF, nano-diffraction, nano-imaging) | `8e787ac` | NOT yet a deployment. Two endstations (diffraction B303A-E02 + imaging B303A-E01) sharing one optics train |
| CoSAXS | B310A | coherent / small-angle X-ray scattering (SAXS / WAXS) | `8e787ac` | NOT yet a deployment; this pass. Single station (B310A-E) on a coherent SAXS optics train; long SAXS detector in a flight tube |

This is the complete public-buildable MAX IV set (both contrast beamlines with a per-Asset topology). No further MAX IV beamline is Tier-2-buildable from public source.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. Across both buildable beamlines:

| Family | Beamlines | Status |
| --- | --- | --- |
| Mirror | 2 (nanomax, cosaxs) | graduated |
| Slit | 2 (nanomax, cosaxs) | graduated |
| InsertionDevice | 2 (nanomax, cosaxs) | graduated |
| Filter | 2 (nanomax, cosaxs) | graduated |
| LinearStage | 2 (nanomax, cosaxs) | graduated |
| PseudoAxis | 2 (nanomax, cosaxs) | graduated |
| Camera | 2 (nanomax, cosaxs) | graduated |
| FluxMonitor | 2 (nanomax, cosaxs) | graduated |
| TimingController | 2 (nanomax, cosaxs) | graduated (binding confirm; PandaBox vs GenericProbe) |
| Monochromator | 1 (nanomax) | graduated (CoSAXS has only an energy pseudo, no separate mono device in contrast; MONO-1) |
| Goniometer | 1 (nanomax) | graduated |
| EnergyDispersiveSpectrometer | 1 (nanomax) | graduated |
| BeamPositionMonitor | 1 (nanomax) | loose (DIAG-1) |

Every Family both beamlines bind is a graduated catalog entry (plus the loose BeamPositionMonitor at NanoMAX, held under DIAG-1); neither coins anything.

## Device classes by beamline count

The raw `contrast` constructor classes seen in source, before mapping to a CORA Family. These are contrast-framework device classes (not Tango device-server classes); the underlying hardware vendor is encoded in the class.

| Source class | Beamlines |
| --- | --- |
| `TangoMotor` | 2 (nanomax, cosaxs) |
| `SmaractLinearMotor_MCS2` / `SmaractRotationMotor_MCS2` | 2 (nanomax, cosaxs) |
| `EigerTango` | 2 (nanomax, cosaxs) |
| `AlbaEM` | 2 (nanomax, cosaxs) |
| `PandaBox` | 2 (nanomax, cosaxs) |
| `SmaractLinearMotor` / `SmaractRotationMotor` | 1 (nanomax) |
| `E727Motor` (PI piezo) | 1 (nanomax) |
| `LC400Motor` (nPoint) | 1 (nanomax) |
| `PiezoLegsMotor` | 1 (nanomax) |
| `DacMotor` (NI-DAC) | 1 (nanomax) |
| `Pilatus3` | 1 (nanomax) |
| `Xspress3` | 1 (nanomax) |
| `PandaBoxPCAP` | 1 (nanomax) |

The shared classes (`TangoMotor`, `SmaractLinearMotor_MCS2`, `EigerTango`, `AlbaEM`, `PandaBox`) are the MAX IV / contrast staples; they appear at both beamlines but each maps to an already-graduated Family, so the recurrence reinforces rather than coins.

## Graduation shortlist (the actionable output)

Across the complete public-buildable MAX IV set (both beamlines), **nothing clears a rule-of-three that is not already graduated.** The two-beamline count is the ceiling for MAX IV public source, so no MAX IV-internal rule-of-three is even reachable. Watches:

| Candidate Family | Distinct beamlines | Discriminator | Blocker / note |
| --- | --- | --- | --- |
| TimingController (PandaBox) | 2 (nanomax, cosaxs) | fast-scan / fly-scan trigger + encoder capture | already graduated; PandaBox is the MAX IV fly-scan staple at both beamlines. Still a binding-confirm (PandaBox presents TimingController vs a bare GenericProbe), NOT a new coin. Reinforces the fleet-wide fly-scan-timing signal (NSLS-II Zebra, MAX IV PandaBox). |
| BeamPositionMonitor | 1 (nanomax) + fleet-wide | beam-centroid position monitor | LOOSE, held fleet-wide under `DIAG-1`; do not coin |

One paragraph: the complete public-buildable MAX IV set (NanoMAX + CoSAXS), mined as data, earns CORA no new Family. Both are on the contrast DAQ idiom (the first such passes, vs ESRF Beacon YAML / NSLS-II bluesky / APS bits), and every device binds an already-graduated family; nine families reach two MAX IV beamlines (Mirror, Slit, InsertionDevice, Filter, LinearStage, PseudoAxis, Camera, FluxMonitor, TimingController), but two is the public ceiling here so no MAX IV-internal rule-of-three is reachable. The set's value is not catalog enrichment but (1) validating CORA's ControlPort over a Tango + Sardana + contrast floor at two real beamlines, and (2) covering two distinct techniques on the imaging / coherence ladder (NanoMAX nanoprobe + ptychography, CoSAXS coherent SAXS). The CORA-relevant tomography lines at MAX IV (ForMAX, TomoWISE) remain staff-question deployments with no public device source; this recurrence will not grow further from public source.
