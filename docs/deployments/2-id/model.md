# Model

*The developer's index into where 2-ID content lives, how EAA fits the seam, and the record of what is deliberately deferred. Design-phase.*

2-ID is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, characterizes the seam with the EAA tooling the scaffold is mined from, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/2-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-id/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface, shared with 2-BM; `2-ID` added to its beamline list, with a pending scanning-fluorescence Practice and a pending beamline scientist |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | no new Family added; the source reuses existing Families, and the new device classes (`ZonePlate`, the fluorescence detector) are bound to loose Family strings pending registration |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; `scanning_fluorescence_microscopy` is named but not coined (see below) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 2-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## How EAA fits

This scaffold is mined from the [Experiment Automation Agents (EAA)](https://github.com/AdvancedPhotonSource/EAA) APS-microprobe integration (`packages/eaa-imaging/.../tool/imaging/aps_mic`) and its [2-ID-D launcher](https://github.com/AdvancedPhotonSource/eaa_driver_scripts_aps_2idd). EAA is read as data about the beamline, not copied as a design. CORA does not add a "confirm the EAA tool" row anywhere; it dissolves EAA into three things it already models:

- **Conductor replaces the orchestration.** EAA's `scan_control` runs the autofocus loop (acquire a 2D map, take a line scan, register it, step the `zp_z` focus axis, minimise the spot width) and submits the `fly2d` / `step1d` rasters over the EPICS scanRecord. That set-then-measure-until-criterion sequencing is what CORA's Conductor takes over: CORA owns the [Run lifecycle](../../architecture/modules/run/index.md) (start, hold, abort, close), the durable scan state, and the stopping governance. EAA fuses policy and sequencing in one loop; CORA draws the seam through the middle.
- **EPICS stays floor.** The EPICS scanRecord and sscan IOC, the motor PVs, the hardware-triggered raster, and the downstream `XRF-Maps` fitting are the floor and the compute edge. CORA observes and conducts over them; it never replaces them.
- **EAA registers as an Agent.** EAA's tactical decide loops (the LLM agent loop and the deterministic Bayesian-optimization parameter tuner) register as an external [Agent](../../architecture/modules/agent/index.md). Each proposed move and objective value becomes a Decision, with the LLM route recorded through the inference-recorder provenance path. EAA's own per-tool default-deny gate (operator confirmation required, motion and beam disabled by default) is exactly the interpose point CORA's permit and clearance adjudication occupies.

The net is regime-2 for CORA's runtime model: a CORA-conducted, multi-step compute-and-move Run, with an external agent proposing inside the loop. That is the shape the edge-runtime work anticipates, surfacing here as a concrete first consumer rather than a hypothetical.

## Deliberately not here yet

These are the parts of 2-ID this scaffold leaves out on purpose. Each is a CORA scope or naming decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](questions.md).

- **The sister experiment hutch and the hutch roster.** The descriptor models one root Unit Asset `2-ID` with one experiment hutch (`2-ID-D`). Whether the sector adds a sister station (a 2-ID-E-class hutch) as a second hutch sub-tree, and where the shared optics sit, is held until `TOPO-1` resolves the roster. The root identity and `facility_code` binding do not migrate when it does: adding a hutch adds Component sub-trees, it does not re-home the root. This mirrors the 32-ID scaffold modelling only 32-ID-C and deferring 32-ID-B.

- **Coining the scanning-fluorescence Method.** `scanning_fluorescence_microscopy` is a new modality (point-raster XRF, mechanistically unlike full-field projection). A design-phase scaffold coins no Method, so it is named and rendered unlinked, carried as a pending Practice (`METHOD-1`). It is earned into the catalog when a confirmed scenario uses it and a naming review accepts the name.

- **The fluorescence-detector Family name.** The energy-dispersive detector is bound to a loose Family string (`EnergyDispersiveSpectrometer`). The eventual catalog Family name is a naming-review decision that must avoid the reserved `Detector` Role noun (a detector is the Role an Asset plays, not its Family); `EnergyDispersiveSpectrometer` is the working placeholder, not a committed name.

- **Scanning fluorescence tomography as a Plan, not a Method.** A rotation over a sequence of XRF maps is a Plan setpoint over the scanning-XRF Method, the same way laminography is a tomography Plan at a tilt setpoint at 2-BM. It is not a separate Method, and it waits on a confirmed rotation axis (`ENV-1`).

- **Micro-XANES and ptychography.** Named by world-facts but absent from EAA's `aps_mic` code path; ptychography also needs a coherent-diffraction detector this scaffold does not model. Modelling either now would be invention.

- **Integration scenarios and vendor Models.** No `test_2id_*.py` registers 2-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real, and hard-registering a simulation-mined, pre-confirmation beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
