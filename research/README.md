# Facility research

Tracked in the repo, but not published to the docs site. This tree holds what CORA can learn about real facilities from public sources, ahead of (or alongside) modeling them as deployments. It is the upstream fact-gathering that feeds `docs/deployments/<id>/` and the descriptors under `deployments/`, never the other way around. The published deployment pages cite their external upstream sources directly (the controls repos, facility pages) rather than linking back here, so this tree can evolve without touching the staff-facing docs. Only the regenerable shallow-clone cache the extractor writes (`research/*/.cache/`) is gitignored.

The rule the whole tree obeys: **mine public sources as data to learn from, never as a spec to mirror.** For physical facts defer to the source plus the operator, never to CORA's own internal consistency. CORA models an event-sourced governance and provenance spine that no facility corpus carries; confirming that absence across a facility is itself part of the justification for the spine.

## Two tiers

Research happens in two passes, and the layout mirrors them:

```
research/<facility>/
  survey.md                       # Tier 1: facility survey
  beamlines/<beamline>/
    facts.md                      # Tier 2: per-beamline device topology
    beamline.candidate.yaml       # draft descriptor (where a device source exists)
```

**Tier 1, the facility survey (`survey.md`).** The first pass over a facility: the beamline roster, techniques and trends, the control-system stack, the data-management stack, an initial read of the CORA seam, and the questions for staff. Its job is to decide *which beamlines are even modellable from public source* and *which are the strongest next picks*. Written to the deployment-page lens but with uncertainty flags and speculative seam reads that do not belong on a staff-facing page. Template: [`_templates/survey.md`](_templates/survey.md).

**Tier 2, the per-beamline device pass (`beamlines/<bl>/`).** The follow-up for a specific beamline being modeled: device topology, control handles (PV / BLISS object / Tango URL), Role hints, and a self-validating candidate descriptor. Originated from the shape of CORA's own deployment pages, then fed from a facility's public controls source where one exists. Template: [`_templates/facts.md`](_templates/facts.md).

Tier 2 only exists where a facility publishes per-beamline device config with real handles (Diamond `dodal`, ESRF Beacon, NSLS-II profile collections, APS `*-bits`). Where the device source is firewalled (ALBA, Sirius, PSI's gitea), the survey routes device topology to the staff questions rather than inferring it; inference from shared base classes is not source.

## Why this exists separately from `docs/deployments/`

`docs/deployments/<id>/` is the published, staff-facing deployment page: what CORA designs and does landing on a beamline. A research artifact is the opposite audience: internal development dossiers with confidence flags, ask-staff lists, and speculative seam reads. Keeping them apart means the published tree stays staff-facing and the research tree stays honest about uncertainty. A survey graduates *into* a deployment page (and a descriptor); it never becomes one.

## Facilities

A survey can exist with no deployment yet (a candidate facility), and a deployment can exist with no survey yet (modeled before this tree was organized, source read at build time). Both are legitimate; the table is the honest state, not an aspiration. For the live deployment roster per Site, read `deployments/<site>/site.yaml`, never a count quoted here.

| Facility | Survey | Tier-2 device passes | Deployments | Control source |
| --- | --- | --- | --- | --- |
| APS | yes | 11 (`*-bits`) | yes | EPICS, public `*-bits` instrument repos |
| ESRF | yes | 2 (ID19, ID16B) | yes | BLISS / Tango, public Beacon config |
| PSI | yes | none | yes | EPICS + BEC; device source on gitea (firewalled) |
| ALBA | yes | none | yes | device source firewalled |
| Sirius | yes | none | yes | device source firewalled |
| Elettra | yes | none | yes | Tango / DonkiOrchestra; acquisition source private |
| NSRRC | yes | none | yes | EPICS / Blu-Ice-DCSS; scattered personal repos |
| ALS | yes | none | none | candidate facility |
| PETRA III | yes | none | none | candidate facility |
| Diamond | yes (retrospective) | (per-beamline from `dodal` at build time) | yes | EPICS, public `dodal` controls library |
| NSLS-II | yes (retrospective) | (per-beamline from profile collections) | yes | EPICS / bluesky, public profile collections |
| SLAC | yes (retrospective) | (from `pcdshub` at build time) | yes | EPICS / `pcdshub` |
| Australian Synchrotron | yes (retrospective) | none | yes | heterogeneous (EPICS + Exporter + REST + TCP) |
| MAX IV | needed | none | yes | Tango / Sardana |

"needed" marks a modeled Site that does not yet carry a Tier-1 survey (only MAX IV remains). "retrospective" marks a survey written after the fleet was already modeled: some EPICS facilities (Diamond, NSLS-II, SLAC) are modeled by reading the public controls library per beamline at build time rather than via a pre-extracted Tier-2 pass, so their survey records the roster, the modellable set, and the seam after the fact rather than ahead of it.

## APS extraction tooling (EPICS-specific)

`scripts/reverse_engineer/` automates the APS Tier-2 pass: it reads the Guarneri `devices.yml`, AST-walks the ophyd device classes, parses `user_group_permissions.yaml`, and emits candidates to `research/aps/beamlines/<repo>/` plus a cross-fleet `research/aps/recurrence.md`. It never writes to `deployments/` or `catalog/`. This is EPICS / `*-bits`-specific and does not generalize; BLISS / Tango facilities (ESRF, Elettra) and firewalled facilities are surveyed by hand. See [`aps/survey.md`](aps/survey.md) and [`aps/catalog-graduation-decisions.md`](aps/catalog-graduation-decisions.md).

## Adding a facility

1. Copy [`_templates/survey.md`](_templates/survey.md) to `research/<facility>/survey.md` and fill it from public sources, every claim cited and confidence-flagged.
2. Decide from the survey whether a Tier-2 device pass is buildable (is the device source public?). If yes, copy [`_templates/facts.md`](_templates/facts.md) to `research/<facility>/beamlines/<bl>/facts.md` per beamline you model.
3. Promote confirmed facts into a descriptor (`deployments/<id>/beamline.yaml`) and a published page (`docs/deployments/<id>/`) when a modeling decision lands. The research artifact stays as provenance.
