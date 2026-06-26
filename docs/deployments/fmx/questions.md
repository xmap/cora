# Open questions

*What CORA needs the FMX team to confirm. This model is reverse-engineered from public open source (the `NSLS2/fmx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries): the EPICS PVs are read from the `startup/*.py` device classes, but the goniometer / robot / detector vendor identities, the crystal cut, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The IVU21 undulator period, gap range, and gap-to-energy curve. The device (`SR:C17-ID:G1{IVU21:2}`) is in source; the parameters are not. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| TOPO-1 | Nice-to-have | FMX (17-ID-2) shares the IVU21 undulator and the 17-ID straight with AMX (17-ID-1). Is the straight canted (two beams), and is one root Unit per branch the right model? | One root Unit feeding the 17-ID-2 branch (the CSX / 32-ID canted precedent); AMX is the sibling branch. | The sector topology and the AMX relationship. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:17ID-PPS:FAMX{Sh:FE}`, `XF:17IDA-PPS:FMX{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HDCM crystal cut, d-spacing, and energy range. The monochromator (`Mono:DCM`) and its axes are in source. | One Monochromator Asset, crystal settings blank. | The Monochromator settings. |
| KB-1 | Nice-to-have | The HFM and KB mirror coatings, the bimorph calibration, and the CRL transfocator lens count and focal configuration. The mirrors (`Mir:HFM`, `Mir:KBH/KBV`) and the CRL (`CRL:`) are in source. | The mirror / CRL internals are per-Asset settings on the existing Mirror / Transfocator Families. | The focusing-optic settings. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer axis decomposition (single omega + GX / GY / GZ centring + PY / PZ pin + PI fine) and the centre-of-rotation calibration. The stack (`Gon:1`) is in source. | A `Goniometer` Asset (catalog Family, graduated on the i03 Smargon); per-axis decomposition to confirm. | The goniometer model. |
| ROBOT-1 | Blocks-go-live | The sample-changing robot model, the dewar / puck layout, the exchange workflow, and the Subject custody lifecycle. The Governor state machine (`Gov:Robot`) and the dewar interlock (`DewarSwitch`) are in source. | One Positioner-presenting `Robot` Asset (not a new Family); the autonomous loop is a Procedure + a Subject custody thread, gated by a Clearance. | The robot model and the autonomous-loop modelling. |
| DET-1 | Blocks-go-live | The Eiger model and beam centre, and the Mercury fluorescence detector element count and ROI map. The Eiger (`Det:Eig16M`) and the Mercury (`Det:Mer`) are in source. | An Eiger 16M (`Camera`) and a Mercury (`EnergyDispersiveSpectrometer`); model / ROIs to confirm. | The detector roster. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the Prosilica BPM cameras, the sector XBPM) and the `BeamPositionMonitor` sensor fold-vs-promote hold. | Read-only beam-position (loose `BeamPositionMonitor`) probes; channel map blank. | The BeamPositionMonitor bindings. |
| CRYO-1 | Nice-to-have | The sample cryo-cooling (cold-gas cryostream) and the annealer / thaw-air actuator. The annealer (`Wago:`) is in source; the cryostream IOC is not. | Sample cooling deferred; the annealer named, the cryostream a `TemperatureController` when its PV is supplied. | The sample-environment Assets. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the PowerBrick / PPMAC vector controller `Gon:1-Vec` / `MC17:Sender`, the Zebra `Zeb:3`, and the EPICS motor records). | Families bound (MotionController, TimingController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) enter CORA's catalog, or stay pending? FMX is the second consumer after i03. | The three Methods reused pending (no mechanical promotion for Methods; the energy_scan deferral discipline); no new Method coined. | The MX Method scope. |
| SERIAL-1 | Nice-to-have | The fixed-target chip-scanner serial-crystallography mode (the Oxford chip raster, a PPMAC on-the-fly motion). Is it modelled, and does it reuse the `serial_crystallography` Method (i24 / LCLS-MFX)? | Deferred; FMX's primary mode is rotation MX, the chip-scanner mode is named here. | The serial-mode Assets and Method. |
