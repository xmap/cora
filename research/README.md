# Facility research

Tracked in the repo, but not published to the docs site. This tree holds what CORA can learn about real facilities from public sources, ahead of (or alongside) modeling them as deployments. It is the upstream fact-gathering that feeds `docs/deployments/<id>/` and the descriptors under `deployments/`, never the other way around. The published deployment pages cite their external upstream sources directly (the controls repos, facility pages) rather than linking back here, so this tree can evolve without touching the staff-facing docs. Only the regenerable shallow-clone cache the extractor writes (`research/*/.cache/`) is gitignored.

The rule the whole tree obeys: **mine public sources as data to learn from, never as a spec to mirror.** For physical facts defer to the source plus the operator, never to CORA's own internal consistency. CORA models an event-sourced governance and provenance spine that no facility corpus carries; confirming that absence across a facility is itself part of the justification for the spine.

## Two tiers

Research happens in two passes, and the layout mirrors them:

```
research/<facility>/
  survey.md                       # Tier 1: facility survey
  recurrence.md                   # cross-fleet device-class frequency (graduation signal)
  graduation.md                   # the graduate / Assembly / fold / leave-loose decisions
  beamlines/<beamline>/
    facts.md                      # Tier 2: per-beamline device topology
    beamline.candidate.yaml       # draft descriptor (where a device source exists)
  reports/                        # off-pattern derived analyses (optional, see below)
    <name>.md
```

The first three files are the **facility spine** (`survey.md`, then `recurrence.md` and
`graduation.md` once a Tier-2 corpus exists); `beamlines/` is the Tier-2 device passes. Anything
else a facility accrues that is neither the spine nor a device pass lives under `reports/`: a
validation diff of a shipped descriptor against its real instrument, a field-level reference for
an integration, or any one-off analysis derived from the passes. A facility has a `reports/`
folder only if it has produced such an artifact (today, only APS), so the absence of `reports/`
elsewhere is expected, not missing work.

**Tier 1, the facility survey (`survey.md`).** The first pass over a facility: the beamline roster, techniques and trends, the control-system stack, the data-management stack, an initial read of the CORA seam, and the questions for staff. Its job is to decide *which beamlines are even modellable from public source* and *which are the strongest next picks*. Written to the deployment-page lens but with uncertainty flags and speculative seam reads that do not belong on a staff-facing page. Template: [`_templates/survey.md`](_templates/survey.md).

**Tier 2, the per-beamline device pass (`beamlines/<bl>/`).** The follow-up for a specific beamline being modeled: device topology, control handles (PV / BLISS object / Tango URL), Role hints, and a self-validating candidate descriptor. Originated from the shape of CORA's own deployment pages, then fed from a facility's public controls source where one exists. Template: [`_templates/facts.md`](_templates/facts.md).

Tier 2 only exists where a facility publishes per-beamline device config with real handles (Diamond `dodal`, ESRF Beacon, NSLS-II profile collections, APS `*-bits`). Where the device source is firewalled (ALBA, Sirius, PSI's gitea), the survey routes device topology to the staff questions rather than inferring it; inference from shared base classes is not source.

## Why this exists separately from `docs/deployments/`

`docs/deployments/<id>/` is the published, staff-facing deployment page: what CORA designs and does landing on a beamline. A research artifact is the opposite audience: internal development dossiers with confidence flags, ask-staff lists, and speculative seam reads. Keeping them apart means the published tree stays staff-facing and the research tree stays honest about uncertainty. A survey graduates *into* a deployment page (and a descriptor); it never becomes one.

## Facilities

A survey can exist with no deployment yet (a candidate facility), and a deployment can exist with no survey yet (modeled before this tree was organized, source read at build time). Both are legitimate; the table is the honest state, not an aspiration. For the live deployment roster per Site, read `deployments/<site>/site.yaml`, never a count quoted here.

| Facility | Survey | Tier-2 device passes | Deployments | Control source |
| --- | --- | --- | --- | --- |
| APS | yes | 11 beamlines (from `*-bits`) | yes | EPICS, public `*-bits` instrument repos |
| ESRF | yes | 8 of 8 (+ recurrence.md) | yes | BLISS / Tango, public Beacon config |
| PSI | yes | none | yes | EPICS + BEC; device source on gitea (firewalled) |
| ALBA | yes | none | yes | device source firewalled |
| Sirius | yes | none | yes | device source firewalled |
| Elettra | yes | none | yes | Tango / DonkiOrchestra; acquisition source private |
| NSRRC | yes | none | yes | EPICS / Blu-Ice-DCSS; scattered personal repos |
| ALS | yes | none | none | candidate facility |
| PETRA III | yes | none | none | candidate facility |
| SPring-8 | yes | none | none | in-house MADOCA (not EPICS); control source firewalled |
| Diamond | yes (retrospective) | (per-beamline from `dodal` at build time) | yes | EPICS, public `dodal` controls library |
| NSLS-II | yes (retrospective) | 28 beamlines (+ recurrence.md); 24 deployed + 4 research-only (qas, tes, nyx, opls) | yes | EPICS / bluesky, public profile collections |
| SLAC | yes (retrospective) | (from `pcdshub` at build time) | yes | EPICS / `pcdshub` |
| Australian Synchrotron | yes (retrospective) | none | yes | heterogeneous (EPICS + Exporter + REST + TCP) |
| MAX IV | needed | none | yes | Tango / Sardana |

"needed" marks a modeled Site that does not yet carry a Tier-1 survey (only MAX IV remains). "retrospective" marks a survey written after the fleet was already modeled: some EPICS facilities (Diamond, NSLS-II, SLAC) are modeled by reading the public controls library per beamline at build time rather than via a pre-extracted Tier-2 pass, so their survey records the roster, the modellable set, and the seam after the fact rather than ahead of it.

## APS extraction tooling (EPICS-specific)

`scripts/reverse_engineer/` automates the APS Tier-2 pass: it reads the Guarneri `devices.yml`, AST-walks the ophyd device classes, parses `user_group_permissions.yaml`, and emits candidates to `research/aps/beamlines/<beamline>/` plus a cross-fleet `research/aps/recurrence.md`. The output directory is the slugified beamline name derived from the device enclosures (e.g. `4-id`); where the enclosures do not encode a station letter, pass `--name <repo-stem>=<beamline>` (e.g. `--name usaxs-bits=12-ID-E`) so the directory is the beamline, not the repo. It never writes to `deployments/` or `catalog/`. This is EPICS / `*-bits`-specific and does not generalize; BLISS / Tango facilities (ESRF, Elettra) and firewalled facilities are surveyed by hand. See [`aps/survey.md`](aps/survey.md) and [`aps/graduation.md`](aps/graduation.md).

## The practice

The full step-by-step (survey -> device pass -> candidate descriptor -> recurrence -> graduation -> promote), with the judgment calls at each step, is in [`WORKFLOW.md`](WORKFLOW.md). The short version:

1. Copy [`_templates/survey.md`](_templates/survey.md) to `research/<facility>/survey.md` and fill it from public sources, every claim cited and confidence-flagged. Decide the modellable set and whether a Tier-2 pass is buildable (is the device source public?).
2. Per beamline you model, copy [`_templates/facts.md`](_templates/facts.md) to `research/<facility>/beamlines/<bl>/facts.md` and draft `beamline.candidate.yaml`. Source-read the controls repo first; carry every value `confirm`. See [`nsls2/beamlines/bmm/`](nsls2/beamlines/bmm/) for a worked example.
3. Fold each beamline into [`_templates/recurrence.md`](_templates/recurrence.md) (`research/<facility>/recurrence.md`); the cross-fleet device-class frequency is the catalog Family graduation signal. A class recurring across three distinct beamlines is the trigger; graduation is a separate, gate-reviewed catalog PR, never folded into a scaffold.
4. Promote confirmed facts into a descriptor (`deployments/<id>/beamline.yaml`) and a published page (`docs/deployments/<id>/`) when a modeling decision lands. The research artifact stays as provenance; the published page cites the external upstream, not this tree.
