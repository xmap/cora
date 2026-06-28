# Open questions

*What CORA needs the PDF team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/pdf-profile-collection`](https://github.com/NSLS2/pdf-profile-collection) profile collection and the [`NSLS2/pdftools`](https://github.com/NSLS2/pdftools) device library): the EPICS PVs are read from them, but vendor identities, physical positions, and the detector geometry are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 28-ID source identity and parameters. No source PV is in the profile collection; CORA infers the shared 28-ID damping wiggler from facility knowledge. | An insertion device, the shared damping wiggler, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the fast and photon shutters are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| MACHINE-1 | Nice-to-have | The storage-ring state PDF reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs beyond `ring_current` pending. | The machine-state observation. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Nice-to-have | The side-bounce monochromator crystal cut, reflection, and energy range. The device (`Mono:SBM`) is confirmed. | A single high-energy Laue `Monochromator` Asset; cut and range blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Is PDF always fixed-energy per experiment, or does any routine scan energy as the measurement? | Fixed-energy; energy scan deferred. | The energy Capability decision. |

## Sample and environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full spinner and analyzer goniohead axis set, and whether the sample orientation warrants a `Goniometer` plus an Assembly (the i11 precedent). | A `Goniometer` spinner; the analyzer noted, the Assembly deferred. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | Which thermal units are live (the cs800 cryostream make, the Lakeshore cryostat, the Linkam furnace) and their ranges. | One thermal-environment `TemperatureController` Asset; units blank. | The sample-environment roster. |
| ENV-1 | Nice-to-have | The gas-handling and humidity rig (flow valves, residual-gas analyzer, humidity) is present in source but not modelled. Does it warrant a settable actuator Asset (the loose `FlowController` family)? | Deferred; the thermal cluster is modelled, the gas / humidity rig noted. | The in-situ environment modelling. |

## Detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which detectors are live (the two PerkinElmer panels, the Pilatus) and which serves which role. | Both Cameras; PerkinElmer primary; Pilatus alongside. | The detector roster. |
| DIST-1 | Blocks-go-live | The two-detector / two-distance geometry: the near and far distances, which tower is static vs moving, and how the panels merge for the PDF Q-range (the `TwoDetectors` plan). | Two `LinearStage` towers; the merge deferred. | The detector geometry and Q-range. |
| DIAG-1 | Nice-to-have | The background-photodiode / flux channel detail. | A read-only `FluxMonitor` probe; channel map blank. | The FluxMonitor binding. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs behind the EPICS motor records. | One `MotionController` family bound (`EndstationMotionController`), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the total-scattering and powder-diffraction Methods enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i11 / i15-1 and XPD opened. | Methods deferred (rendered unlinked), no Practice recorded. | The powder / PDF Method scope. |
