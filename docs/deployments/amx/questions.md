# Open questions

*What CORA needs the AMX team to confirm. This model is reverse-engineered from public open source (the `NSLS2/amx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries): the EPICS PVs are read from the `startup/*.py` device classes, but the goniometer / robot / detector vendor identities, the crystal cut, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The IVU21 undulator period, gap range, and gap-to-energy curve. The device (`SR:C17-ID:G1{IVU21:1}`) is in source; the parameters are not. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| TOPO-1 | Nice-to-have | AMX (17-ID-1) shares the IVU21 undulator and the 17-ID straight with FMX (17-ID-2, which uses IVU21:2). Is the straight canted (two beams), and is one root Unit per branch the right model? | One root Unit feeding the 17-ID-1 branch (the FMX / CSX canted precedent); FMX is the sibling branch. | The sector topology and the FMX relationship. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the front-end / photon shutter PVs (not in the profile collection; the front end is shared with FMX). | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The vertical DCM crystal cut, d-spacing, and energy range. The monochromator (`Mono:DCM`) and its axes are in source. | One Monochromator Asset, crystal settings blank. | The Monochromator settings. |
| KB-1 | Nice-to-have | The tandem-deflection and KB mirror coatings and calibration. The mirrors (`Mir:TDM`, `Mir:KBH/KBV`) are in source. | The mirror internals are per-Asset settings on the existing Mirror Family. | The focusing-optic settings. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer axis decomposition (single omega + GX / GY / GZ centring + PY / PZ pin fine) and the centre-of-rotation calibration. The stack (`Gon:1`) is in source. | A `Goniometer` Asset (catalog Family, graduated on the i03 Smargon); per-axis decomposition to confirm. | The goniometer model. |
| ROBOT-1 | Blocks-go-live | The EMBL sample-changing robot model, the dewar / puck layout, the exchange workflow, and the Subject custody lifecycle. The robot (`EMBL`) and Governor are in source. | One Positioner-presenting `Robot` Asset (not a new Family); the autonomous loop is a Procedure + a Subject custody thread, gated by a Clearance. | The robot model and the autonomous-loop modelling. |
| DET-1 | Blocks-go-live | The Eiger model and beam centre (not exposed in the profile collection), and the Mercury fluorescence detector element count and ROI map. | An Eiger (`Camera`, PV pending) and a Mercury (`EnergyDispersiveSpectrometer`); model / ROIs to confirm. | The detector roster. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the four-quadrant BPMs) and the `BeamPositionMonitor` sensor fold-vs-promote hold. | Read-only beam-position (loose `BeamPositionMonitor`) probes; channel map blank. | The BeamPositionMonitor bindings. |
| CRYO-1 | Nice-to-have | The sample cryo-cooling (cold-gas cryostream), not exposed in the profile collection. | Sample cooling deferred; a `TemperatureController` when its PV is supplied. | The sample-environment Assets. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the goniometer vector controller is a PowerBrick; the profile's vector PV is misconfigured to the FMX prefix). | Family bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) enter CORA's catalog, or stay pending? AMX is the third consumer (after i03, FMX). | The three Methods reused pending; coining awaits a conduct-path (an MX integration scenario), not the sighting count (the energy_scan discipline). | The MX Method scope. |
