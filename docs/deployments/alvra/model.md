# Model

*The developer's by-kind index: where each CORA aggregate's Alvra content lives, how the device families fold at a second XFEL, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Alvra |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The headline: the families fold again, at a second XFEL

[LCLS-MFX](../lcls-mfx/model.md) found that an XFEL's device families fold and its gaps are architectural. Alvra re-runs that test against an independently-built free-electron laser, mined from PSI's `eco` rather than SLAC's `pcdshub`, and reaches the same finding. Of Alvra's full `eco` device set, **none** had no CORA Family: every device reuses an existing one. The offset and KB mirrors fold into `Mirror`, the solid attenuators into `Filter`, the slits into `Slit`, the pulse picker into `Shutter` (PULSE-1), the profile monitors into `Scintillator` + `Camera`, the PBPS / PBIG monitors into `FluxMonitor` + `Diagnostic`, the double-crystal mono into `Monochromator`, the Huber sample stage into `LinearStage`, the optical table into `Table`, the sample microscope and the Jungfrau into `Camera`, and the pump-probe and reference lasers into the catalog `Laser` Family (the LCLS-MFX / 4-ID precedent). The von Hamos spectrometer binds the graduated `EmissionSpectrometer` Family, a **fourth sighting** after LCLS-MFX (which introduced it), NSLS-II ISS (which graduated it), and the MAX IV Balder near-sighting (SPEC-1). Each fold was reviewed against coining a synonym and rejected.

So the device taxonomy generalizes from storage rings to an XFEL almost untouched, and that result is now confirmed at two independent XFELs. What does not generalize is the **acquisition ontology**, the same as at LCLS-MFX. That is the product of this exercise, recorded next.

## Deliberately not here yet (the architectural gap register)

These are the parts of Alvra this scaffold leaves out on purpose. Unlike the open questions (facts the PSI team owns), each is a CORA scope decision: a shape the model does not yet have, with the seam it would extend named. None is built speculatively; an XFEL is the trigger that would justify the work, and Alvra is the second sighting of each gap, strengthening the case that the work is real and not LCLS-specific.

- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The load-bearing gap, re-confirmed. CORA's acquisition is a single-detector poll-to-Done loop plus a sub-Hz scalar observation logbook with no pulse-ID key. SwissFEL's `sf-daq` collects a free-running `bsread` stream of per-shot frames correlated by pulse-ID at beam rate, exactly the shape LCLS's DAQ has. The Run-as-provenance-envelope survives and the per-shot data plane lives in the SwissFEL data API (CORA references a `Dataset`, as it does for reconstructions via `ComputePort`), but representing a DAQ run as an actuation is a new event-stream axis. Its shape is sketched as a forward-looking design note in CORA's design memory (gated, not built); Alvra is the second deployment to need it.
- **Beam-synchronous event-system timing (TIMING-1).** The SwissFEL event system (EVR receivers, e.g. `SLAAR11-LTIM01-EVR0`) gates acquisition at beam rate, the analog of LCLS's EventSequencer. CORA's `TimingController` Family carries the device, but "acquire on event-code N at rate R" has no typed parameter home; today it would be opaque setpoints.
- **Femtosecond pump-probe synchronization (LASER-1).** The optical pump-probe laser and the FEL are two synchronized timing domains; the `eco` `lxt` timing chain holds them together and the PALM / PSEN arrival-time monitors correct the residual jitter. CORA's `PartitionRule` is single-domain spatial math; a cross-timing-domain synchronization is a relationship it cannot express. The laser device itself folds (catalog `Laser`); the sync is the gap, and Alvra is the second XFEL to expose it (LCLS-MFX's TimeTool is the same role as Alvra's PSEN).
- **One switched Aramis source feeding co-equal stations (TOPO-1).** One linac and Aramis undulator line serve the Alvra, Bernina, and Cristallina stations, beam routed one at a time. CORA models each beamline as a root Unit owning its source; a shared, switched source feeding co-equal Units has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model. This is the same gap LCLS-MFX's shared-linac topology exposed.
- **Attenuator transmission solver (ATT-1).** The `eco` `AttenuatorAramis` driver solves a foil combination for a requested transmission, energy-dependent. CORA's `Filter` covers the discrete selection; the solve is the deferred `Attenuable` + `SolverReference` leg. With both LCLS-MFX and Alvra carrying the same energy-dependent attenuator solve, the rule-of-three for this leg is well past its trigger.

## What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Alvra earns no catalog change; the XFEL recipes are carried pending on the [PSI Practices](../psi/index.md), reusing the pending LCLS-MFX Methods. No catalog Model is bound.
- **Sample delivery and the Subject custody thread.** The fixed-target / liquid-jet delivery on the Prime sample stage is endstation-specific and deferred (SAMPLE-1); no Family is coined, mirroring how LCLS-MFX carries its liquid jet.
- **The eco cross-line references (XREF-1).** Several Alvra `eco` drivers reference `SAROP21-*` PVs (a sibling Aramis line) for an aperture and an energy readback. Whether that is correct for Alvra or a copy-paste artifact is not determinable from source; carried as an open question, not silently modelled.
- **Integration scenarios.** No `test_alvra_*.py` registers Alvra Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.
