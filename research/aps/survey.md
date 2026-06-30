# APS research brief

Staging notes, not published docs. These files capture what CORA can learn from the
public APS Bluesky deployment corpus (Pete Jemian's personal repos under
`github.com/prjemian` and the APS Beamline Controls and Data Acquisition group under
`github.com/orgs/BCDA-APS`). They are inputs to later modeling decisions, not deployment
documentation. Promote confirmed facts into descriptors (`deployments/<id>/beamline.yaml`,
`catalog/catalog.yaml`) or the published `docs/deployments/<id>/` pages when a decision lands.

## The standing verdict

The corpus is a strong reference for the EPICS floor and the device reality that
`beamline.yaml` points at, and a low-value template for CORA's spine. CORA intentionally
models an event-sourced governance and provenance spine (event store, Trust, Federation,
Asset lifecycle and condition, Capability and affordance contracts, portable Assemblies,
Calibration provenance, Decision and Agent provenance, the Run versus Procedure boundary)
that no corpus repo carries. Mine the corpus as data to learn from, never as a spec to
mirror. This matches the project's intentional-modeling and docs-drift rules: for physical
facts defer to descriptors plus the external source plus the operator, never to CORA's own
internal consistency.

## The extraction pass

`scripts/reverse_engineer/` turns a `*-bits` repo into candidate CORA deployment facts. It
reads the Guarneri `devices.yml`, AST-walks the ophyd device classes, parses
`user_group_permissions.yaml`, and emits candidates only: it never writes to `deployments/`
or `catalog/`. Anything not statically resolvable is flagged `confirm`. Run it from the repo
root (scripts/ is not a package, so use PYTHONPATH):

    PYTHONPATH=scripts python3 -m reverse_engineer.cli --repo BCDA-APS/8id-bits

`beamlines/<repo>/` holds the per-repo `facts.md` (inventory with PV/axis maps, candidate
enclosures, Role hints, and Trust hints from the queueserver permissions) and
`beamline.candidate.yaml` (a draft fragment that self-validates against the real
`scripts/beamline_descriptor.py` loader). `recurrence.md` is the cross-fleet frequency report:
a suggested family in two or more repos is a catalog Family graduation candidate (human and
naming-r3 gated), and families already in `catalog.yaml` are marked graduated. The pass ran
over eleven BCDA-APS `*-bits` repos; the labels and ophyd-class frequency tables in
`recurrence.md` carry the cleanest graduation signal, since the family table mixes confident
suggestions with class-name fallbacks.

A twelfth `*-bits` repo exists but is **not modellable yet**: `BCDA-APS/31ide-lynx-bits`
(31-ID-E LYNX) is a fresh BITS scaffold whose `devices.yml` carries only simulated devices
(`ophyd.sim.motor`, `ophyd.sim.noisy_det`) plus commented-out examples, and whose `devices/`
package is empty; the only real device is the generic `aps` machine-parameters object. It has
no real 31-ID-E PVs in public source (scouted 2026-07), so the extractor returns zero devices.
Re-run when the instrument is populated. This keeps the modellable BCDA-APS set at eleven
beamlines.

Caveat: `recurrence.md` counts by beamline directory, so each directory must be one physical
beamline. `BCDA-APS/6idb-bits` is a fork of `polar-bits` (both the 4-ID instrument) with a
grafted Sector 6 endstation; it is split in the tree into `beamlines/4-id/` (from `polar-bits`)
and the carved `beamlines/6-id-b/`, so the recurrence no longer double-counts 4-ID. Keep that
invariant when adding a beamline: one directory per physical beamline; see
`graduation.md`.

This is step 1 of the roadmap in the approved plan
(`~/.claude/plans/iridescent-gathering-elephant.md`): extraction, then catalog graduation,
then per-beamline curation. Candidates are inputs to that human-gated modeling, not outputs.

## What is here

The spine artifacts (`survey.md`, `recurrence.md`, `graduation.md`) sit at the facility root;
`beamlines/` holds the per-beamline device passes; `reports/` holds the off-pattern derived
analyses (validation diffs, integration field-references) that do not fit the spine.

- `graduation.md`: step 2 of the roadmap. The intentional graduate / Assembly / fold /
  leave-loose decision per recurring candidate from `recurrence.md`, with the naming-r3 gate
  applied to every proposed name. Net result: no speculative catalog edits; Diffractometer is
  an Assembly (not a Family), and the genuine new Families graduate coupled to the first
  deployment that references them (step 3).
- `reports/apsbss-to-external-refs-adapter.md` (a): the field-level shapes of the
  `BCDA-APS/apsbss` data model (the ESAF leg), read from source, as input to the already-locked
  BSS-subscriber design. It does not propose a new adapter; it feeds one. See the caveat below.
- `reports/tomo-bits-fidelity-diff.md` (b): a PV-by-PV cross-check of CORA's 2-BM `Microscope`
  model against the working tomography instrument `BCDA-APS/tomo-bits`
  (`devices/mct_optics.py`). CORA is a strict superset; the diff surfaces a short list of
  genuine enrichment questions for 2-BM staff.

## Relation to existing CORA designs (important)

These notes complement work that is already designed and in some cases shipped. Do not treat
either file as a fresh design.

- The APS scheduling and ESAF ingestion is already gate-reviewed and locked in the memory
  notes `project-aps-scheduling-integration-research` and `project-aps-roster-identity-design`.
  apsbss is only the ESAF leg; the locked primary scheduling source is the beam-api Schedule
  API. The roster, badge identity, and reschedule semantics are locked there. File (a) only
  adds the concrete apsbss field shapes those notes reference.
- The 2-BM Microscope model shipped via `project-microscope-reshape-design`. File (b) is a
  cross-check against the working instrument, not a redesign.
- A sibling reverse-engineering pass over NSLS-II is recorded in
  `project-nsls2-deployment-audit`, and the broader Bluesky comparison in
  `project-bluesky-comparison`. This corpus survey is the APS-org counterpart.
- One concrete code-versus-doc correction surfaced here: the shipped Clearance external arm
  is `ExternalRefBinding(ref=Identifier(scheme, value))`
  (`apps/api/src/cora/safety/aggregates/clearance/state.py`), not the `ExternalBinding(scheme,
  id)` named in `docs/architecture/modules/safety/index.md`. Trust the code.

## Corpus map (for reference)

| Layer | Repos | Reverse-engineering value |
| --- | --- | --- |
| Per-beamline deployments | `tomo-bits`, `8id-bits`, `usaxs-bits`, `polar-bits`, `12id-bits`, `11bm-bits`, `9id_bits`, `28id-bits`, `6idb-bits`, `3idc-bits`, `16bm-bits`, prjemian `gpBits`/`bits2606` | high for floor and device reality |
| Framework and loader | `BITS`/`apsbits`, `guarneri`, `ophyd-registry`, `apstools` | medium, loader contract and query shapes |
| Governance source | `apsbss` (Proposal and ESAF read-model) | high as upstream data, not a design |
| EPICS floor and generation | prjemian `ibek-support`, `epics-docker`, `epics_screens`; BCDA `gestalt`, `BeamlineUI`, `mkioc`, `iocman` | medium, schema and descriptor-driven-generation precedent |

## Gaps neither corpus fills (CORA-native)

Event sourcing and system of record, Asset lifecycle and condition as data, Calibration
provenance (as-shot pinned versus used), Decision and Agent provenance, the Run versus
Procedure output-of-record boundary, Capability and affordance contracts, cross-facility
Federation and per-command authorization, and hash-versioned cross-beamline blueprints.
Confirming their absence across roughly twenty surveyed repos is itself the strongest
justification for the spine.
