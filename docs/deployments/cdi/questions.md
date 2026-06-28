# Open questions

*What CORA needs the CDI team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/cdi-profile-collection`](https://github.com/NSLS2/cdi-profile-collection) profile collection and the [`NSLS2/cditools`](https://github.com/NSLS2/cditools) device library): the EPICS PVs are read from them, but vendor identities, physical positions, and the timing configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU18 undulator period, gap range, and harmonic usage. The device (`SR:C09-ID:G1{IVU18:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the photon-shutter PVs. Neither is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Whether the 09IDB branch zone (`Slt:DM3`, the quadrant BPM) is a distinct access-gated enclosure or part of the optics hutch. | Two enclosures (9-ID-A optics, 9-ID-C endstation); 09IDB folded into the optics zone. | The Enclosure boundaries. |
| MACHINE-1 | Nice-to-have | The storage-ring state CDI reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs beyond `ring_current` pending. | The machine-state observation. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The Si DCM cryo detail and full range (the Si(111) reflection and `d = 3.1287 A` are read from the Energy model), and the DMM multilayer coating and bandpass. Both monochromators (`Mono:HDCM`, `Mono:DMM`) are in source. | Two Monochromator Assets, Si(111) recorded, other settings blank. | The Monochromator settings. |
| KB-1 | Blocks-go-live | The KB mirror focal size, coating / stripe, and working distance; whether both VKB and HKB are always installed. | A `Mirror` Asset (the KB pair); focus geometry blank. | The KB nanofocus spec. |
| ENERGY-1 | Nice-to-have | Whether incident energy is ever scanned as the measurement, and the true energy range (the `5-15 keV` bounds are marked `TODO: CHECK` in source). | Fixed-energy imaging; the range left provisional. | The energy Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | Which endstation tower (`TDMS:T1` / `TDMS:T2`) carries the sample versus the detector, the sample-to-detector distance that sets the q-range, and the full `Gon:1` goniometer axis set. Some tower axes are read-only pending commissioning in source. | Two `LinearStage` towers and a `Goniometer`; roles and distance deferred. | The endstation geometry. |
| DET-1 | Blocks-go-live | Which detector (Eiger2 / Merlin) is primary for which technique, the foil materials / thicknesses, and whether a direct-beam beamstop is installed (none is in source). | Both Cameras; Eiger2 primary; no beamstop modelled. | The detector roster and beamstop. |
| CAM-1 | Nice-to-have | Which diagnostic cameras (the BCU inline camera, the sample camera, the optics-module Prosilicas) are live. | The inline and sample cameras modelled; others noted. | The diagnostic-camera set. |
| DIAG-1 | Nice-to-have | The foil-monitor channel map and the quadrant / diamond BPM channels (the diamond BPM was repurposed from ion-chamber use in source). | Read-only flux and beam-position probes; channel maps blank. | The `FluxMonitor` and `BeamPositionMonitor` bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Blocks-go-live | The exposure-gating chain. The profile collection exposes no trigger box (no Zebra / PandA startup file, no shutter PVs); the Eiger2 and Merlin carry internal and external trigger modes. How is a coherent-imaging exposure gated and synchronized with the scan? | Detector-internal triggering; no floor trigger box modelled. | The triggering chain. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs behind the EPICS motor records. | One `MotionController` family bound (`EndstationMotionController`), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the coherent-imaging Methods (forward CDI, ptychography, Bragg CDI) enter CORA's catalog, or stay deferred? This is the same owner-scope decision 8-ID opened. | Methods deferred (rendered unlinked), no Practice recorded. | The coherent-imaging Method scope. |
