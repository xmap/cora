# Model

*The developer's index into where LCLS-MFX content lives, and the architectural gap register this exercise produced. Design-phase.*

MFX is a documentation-and-descriptor scaffold: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, then records the gaps the exercise found.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/lcls-mfx/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lcls-mfx/beamline.yaml) | the device walk, with the `pcdshub`-derived EPICS PV prefixes; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/slac/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/slac/site.yaml) | the SLAC facility surface; MFX is its only beamline, with XFEL practices carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | **no Family graduated.** MFX reuses catalog Families and carries loose families (`FluxMonitor`, `Diagnostic`, `Transfocator`, `Laser` reused; `EmissionSpectrometer` new and loose) |
| Catalog Capability / Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; serial crystallography, pump-probe, and emission-spectroscopy Methods are deferred (the catalog tomography Methods do not fit an XFEL) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound; `pcdshub` names hardware (Dectris, Rayonix, the von Hamos) but no part is procured |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers MFX Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md), including the pump-probe laser Clearance |

## The headline: the families fold, the gaps are architectural

I03 graduated a device Family (Goniometer). MFX graduates none, and that is the finding. Of MFX's full device set, exactly one type has no CORA Family, the von Hamos emission spectrometer, carried as a single new loose family (`EmissionSpectrometer`, SPEC-1). Everything else reuses an existing Family: the offset mirrors fold into `Mirror`, the solid-Si attenuators into `Filter`, the JAWS into `Slit`, the pulse picker into `Shutter` (PULSE-1), the profile imagers into `Scintillator` + `Camera`, the intensity-position monitors into `FluxMonitor` + `Diagnostic`, the channel-cut into `Monochromator`, the lens stacks into the loose `Transfocator`, the EventSequencer into `TimingController`, the pump-probe laser into the loose `Laser` (the 4-ID precedent), and the area detector into `Camera`. Each fold was reviewed against coining a synonym and rejected.

So the device taxonomy generalizes from storage rings to an XFEL almost untouched. What does not generalize is the **acquisition ontology**. That is the product of this exercise, recorded next.

## Deliberately not here yet (the architectural gap register)

These are the parts of MFX this scaffold leaves out on purpose. Unlike the open questions (facts the LCLS team owns), each of these is a CORA scope decision: a shape the model does not yet have, with the seam it would extend named. None is built speculatively; an XFEL is the trigger that would justify the work.

- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The load-bearing gap. CORA's acquisition is a single-detector poll-to-Done loop (`apps/api/src/cora/operation/acquisitions.py`) plus a sub-Hz scalar observation logbook with no pulse-ID key (`apps/api/src/cora/run/aggregates/run/entries.py`). An XFEL collects a free-running stream of per-shot frames correlated by fiducial at beam rate. The Run-as-provenance-envelope survives and the per-shot data plane lives in `psana` (CORA references a `Dataset`, as it does for reconstructions via `ComputePort`), but representing a DAQ run as an actuation is a new event-stream axis. Its shape is sketched as a forward-looking design note in CORA's design memory (gated, not built).
- **Beam-synchronous event-code timing (TIMING-1).** The EventSequencer plays a sequence of `[beam_code, delta_beam, delta_fiducial, burst_count]` lines that gate acquisition at beam rate. CORA's `TimingController` Family carries the device, but "acquire on event-code N at rate R, burst B" has no typed parameter home; today it would be opaque setpoints.
- **Femtosecond pump-probe synchronization (LASER-1).** The optical laser and the FEL are two synchronized timing domains (the `lxt_ttc` SyncAxis holds a ~50 fs deadband; the timetool corrects residual jitter). CORA's `PartitionRule` is single-domain spatial math; a cross-timing-domain synchronization is a relationship it cannot express. The laser device itself folds (loose `Laser`, 4-ID precedent); the sync is the gap.
- **One switched FEL source feeding co-equal instruments (TOPO-1).** One linac and undulator line serve many instruments, beam routed one at a time by the transport mirrors. CORA models each beamline as a root Unit owning its source; a shared, switched source feeding co-equal Units has no home except the `Supply("PhotonBeam")` seam, and the routing state ("which instrument has beam now") is new.
- **Attenuator transmission solver (ATT-1).** The solid-Si attenuators solve a foil combination for a requested transmission, energy-dependent (the `AttBase` solver). CORA's `Filter` covers the discrete selection; the solve is the deferred `Attenuable` + `SolverReference` leg (`apps/api/src/cora/operation/_partition_rule_eval.py` defers SolverReference evaluation). MFX, with the transfocator focus solver (CRL-1), is the rule-of-three trigger.
- **Computed device-state to path-transmission lightpath (LIGHTPATH-1).** `pcdshub`'s `lightpath` walks the z-ordered beam path and computes path-level transmission and the first blocking device from each device's inserted / removed state. CORA already has the static z-ordered walk and the location-not-identity discipline; only the dynamic computed half is deferred (the passive-beam-path tier). `lightpath/path.py` is a ready precedent.

## What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** MFX earns no catalog change; the XFEL recipes are carried pending on the [SLAC Practices](../slac/index.md). No catalog Model is bound.
- **The von Hamos as a graduated Family.** `EmissionSpectrometer` is carried loose (single deployment), not graduated; the same gap at MAX IV Balder (SCANIA-2D) means the rule-of-three may be near (SPEC-1). It is routed to naming-r3.
- **Sample delivery and the Subject custody thread.** The liquid jet / fixed target is endstation-specific and deferred (SAMPLE-1); no Family is coined.
- **Integration scenarios.** No `test_lcls_mfx_*.py` registers MFX Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
