# Notes

## Techniques

*What CORA would run at PDF: high-energy total-scattering and powder-diffraction techniques, each a [Catalog](../../catalog/methods.md) Method. PDF is the twin of [XPD](../xpd/notes.md#techniques) and follows its deferral exactly, after Diamond [i11](../i11/notes.md#techniques) and [i15-1](../i15-1/notes.md#techniques).*

PDF's techniques are high-energy total scattering and powder diffraction: a high-energy beam through a powder or capillary sample onto a large area detector, with the sample-to-detector distance setting the accessible Q. These Methods are new to CORA's imaging- and spectroscopy-heritage catalog. As at XPD, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / PDF | `total_scattering` | rapid-acquisition pair distribution function: a near and a far detector distance merged to high Q (DIST-1); Method not yet in catalog, shared with i15-1 and XPD |
| Powder diffraction | `powder_diffraction` | the same high-energy beam and detector for Rietveld-quality powder patterns; Method not yet in catalog, shared with i11 and XPD |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, monochromator, mirror, and slit tuning; reuses the existing Method |

Both techniques need the [sample spinner and environment](sample.md) and the [area detectors](detector.md); the exposure is gated by the fast shutter, with the two-distance merge sequenced in software (DIST-1).

### Why the Methods stay deferred

Diamond i11 (powder diffraction) and i15-1 (total scattering / PDF) opened the question of whether these Methods enter CORA's catalog (TECH-1), and `main` deliberately left them pending: the concrete acquisition recipes (energies, distances, exposures, the near / far merge) join as the deployment approaches the point where CORA drives the beamline. PDF reinforces both Methods at a second NSLS-II endstation without coining either, the same earn-the-abstraction discipline XPD follows. Because the defining Methods are not in the catalog, PDF records **no Practice** in the [NSLS-II Site](../nsls2/index.md), exactly as XPD records none; the binding lands when the Method does.

The PDF reduction itself (the azimuthal integration of the detector frames and the Fourier transform of the structure function into the pair distribution function G(r)) is `ComputePort` work, not a beamline Method: the beamline takes the frames, CORA's compute leg turns them into the result.

## Governance

*Who may act at PDF and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A PDF beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may change the incident energy, move a detector tower to a new distance, set a sample-environment temperature ramp, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### In-situ and high-throughput runs

A variable-temperature total-scattering series or a high-throughput sample queue can run long and unattended, which is where CORA's trust shape earns its keep: the engine holds the temperature ramp and the acquisition while the trust boundary bounds what may change mid-series and who may intervene. If an autonomous Agent were added to steer acquisition (choose the next temperature point, decide when the pattern statistics are sufficient, trigger a PDF reduction to check the result), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's PDF content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at PDF |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [the stage pages](source.md) (`EnergyAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (28-ID-1-A optics, 28-ID-1-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring its twin [XPD](../xpd/notes.md#model) and the other reverse-engineered deployments. Left out on purpose:

- **No new Family.** PDF is a reuse-and-reinforce deployment: the flat-panel and pixel detectors bind `Camera`, the photodiode `FluxMonitor`, the thermal cluster `TemperatureController`, the side-bounce mono `Monochromator`, the focusing mirror `Mirror`, the spinner `Goniometer`, the slits `Slit`, the fast shutter `Shutter`, the beamstops `BeamStop`, the detector and sample-environment stages `LinearStage`, the master energy a `PseudoAxis`. Nothing graduates and the catalog is unchanged.
- **The held loose family.** The `StorageRing` current readback is a loose supply observation (machine state), never an Asset Family.
- **No new Capability or Method.** Total scattering / PDF and powder diffraction sit on the deferred `total_scattering` / `powder_diffraction` Methods Diamond i11 and i15-1 left pending (`TECH-1`); PDF reinforces them at a second NSLS-II endstation without coining either, and records no Practice until they land. The PDF reduction (azimuthal integration and the Fourier transform to G(r)) is `ComputePort` work, not a Method.
- **The gas-handling and humidity rig.** Present in the profile collection but carried deferred (`ENV-1`): a design-phase scaffold models the thermal environment that is settled (`TemperatureController`) and defers the in-situ gas / humidity actuators until they earn modelling, the same discipline the other deployments follow.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the PDF team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/pdf-profile-collection`](https://github.com/NSLS2/pdf-profile-collection) profile collection and the [`NSLS2/pdftools`](https://github.com/NSLS2/pdftools) device library): the EPICS PVs are read from them, but vendor identities, physical positions, and the detector geometry are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 28-ID source identity and parameters. No source PV is in the profile collection; CORA infers the shared 28-ID damping wiggler from facility knowledge. | An insertion device, the shared damping wiggler, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the fast and photon shutters are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| MACHINE-1 | Nice-to-have | The storage-ring state PDF reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs beyond `ring_current` pending. | The machine-state observation. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Nice-to-have | The side-bounce monochromator crystal cut, reflection, and energy range. The device (`Mono:SBM`) is confirmed. | A single high-energy Laue `Monochromator` Asset; cut and range blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Is PDF always fixed-energy per experiment, or does any routine scan energy as the measurement? | Fixed-energy; energy scan deferred. | The energy Capability decision. |

### Sample and environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full spinner and analyzer goniohead axis set, and whether the sample orientation warrants a `Goniometer` plus an Assembly (the i11 precedent). | A `Goniometer` spinner; the analyzer noted, the Assembly deferred. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | Which thermal units are live (the cs800 cryostream make, the Lakeshore cryostat, the Linkam furnace) and their ranges. | One thermal-environment `TemperatureController` Asset; units blank. | The sample-environment roster. |
| ENV-1 | Nice-to-have | The gas-handling and humidity rig (flow valves, residual-gas analyzer, humidity) is present in source but not modelled. Does it warrant a settable actuator Asset (the loose `FlowController` family)? | Deferred; the thermal cluster is modelled, the gas / humidity rig noted. | The in-situ environment modelling. |

### Detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which detectors are live (the two PerkinElmer panels, the Pilatus) and which serves which role. | Both Cameras; PerkinElmer primary; Pilatus alongside. | The detector roster. |
| DIST-1 | Blocks-go-live | The two-detector / two-distance geometry: the near and far distances, which tower is static vs moving, and how the panels merge for the PDF Q-range (the `TwoDetectors` plan). | Two `LinearStage` towers; the merge deferred. | The detector geometry and Q-range. |
| DIAG-1 | Nice-to-have | The background-photodiode / flux channel detail. | A read-only `FluxMonitor` probe; channel map blank. | The FluxMonitor binding. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs behind the EPICS motor records. | One `MotionController` family bound (`EndstationMotionController`), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the total-scattering and powder-diffraction Methods enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i11 / i15-1 and XPD opened. | Methods deferred (rendered unlinked), no Practice recorded. | The powder / PDF Method scope. |
