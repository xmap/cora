# Open questions

*What CORA needs the CHX team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/chx-profile-collection`](https://github.com/NSLS2/chx-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector/timing configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU20 undulator period, gap range, and harmonic usage. The device (`SR:C11-ID:G1{IVU20:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:11ID-PPS{Sh:FE}`, `XF:11IDA-PPS{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The Si DCM cryo detail and full range (the Si(111) cut and harmonic 5 are read from the production `move_E` routine), and the DMM multilayer coating and bandpass. Both monochromators (`Mono:DCM`, `Mono:DMM`) are in source. | Two Monochromator Assets, Si(111) cut recorded, other settings blank. | The Monochromator settings. |
| CRL-1 | Blocks-go-live | The FOE transfocator (`XF:11IDA-OP{Lens:`) lens material and lenslet count. Its catalog home is settled: it binds the graduated `Transfocator` CRL Family; only the per-Asset lens spec is open. (The endstation kinoform lenses `k1`/`k2`, `XF:11IDB-OP{Lens:1` / `{Lens:2`, are a distinct refractive optic, not a compound-lens transfocator; they are named but not modelled as devices, and whether they earn their own Family is a separate future question, not part of CRL-1.) | The transfocator binds the graduated `Transfocator` Family; lens material and count left blank. | The transfocator lens spec. |
| GI-1 | Nice-to-have | Is grazing-incidence scattering (GISAXS) a live routine, and does the `Mir:GI` mirror steer the beam for it? | A `Mirror` Asset; GISAXS noted as a technique. | The GISAXS geometry. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full diffractometer axis set behind the `SamplePositioner` pseudomotor, and whether the goniometric axes warrant a `Goniometer` plus a Diffractometer Assembly (the 8-ID precedent). | A `LinearStage` sample stack, rotation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which Eiger (4M / 1M / 500K) is the primary XPCS detector vs the spare set, whether a separate along-beam stage sets the sample-to-detector distance (the `Det:SAXS` motor is transverse X/Y only), and the Xspress3 element count. | Eiger 4M primary; all Cameras; no distance stage modelled. | The detector roster and q-range. |
| CAM-1 | Nice-to-have | Which beam-viewing cameras (the Prosilica x-ray-eyes, the PointGrey, the OAV) are live. | The OAV modelled as a Camera; others noted. | The beam-viewing camera set. |
| DIAG-1 | Nice-to-have | The scaler flux channel map (which channel is I0) and the BPM / AH401B electrometer channels. | Read-only flux and beam-position probes; channel maps blank. | The FluxCounter and BeamPositionMonitor bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Blocks-go-live | The XPCS exposure-gating chain: how the Zebra, the delay generator (`delaygen:DG0:`), and the fast shutter co-time the Eiger frame triggers, and their vendor identities. | One `TimingController` (Zebra) gating the fast shutter and frames; chain detail blank. | The triggering chain. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| ENERGY-1 | Nice-to-have | Is CHX always fixed-energy, or does anomalous XPCS scan energy as the measurement (the `energy_scan` Capability the catalog anticipates, shared with BMM)? | Fixed-energy; energy_scan deferred (the BMM question). | The energy Capability decision. |
| TECH-1 | Blocks-go-live | Do the XPCS and small-angle-scattering Methods enter CORA's catalog, or stay deferred? This is the same owner-scope decision 8-ID opened. | Methods deferred (rendered unlinked), no Practice recorded. | The coherent-scattering Method scope. |
