# The research practice

How to run a facility from cold start to a deployment-ready fact base. The artifacts are templated under `_templates/`; this is the order to produce them and the judgment calls at each step. Read `README.md` first for the two-tier model and the standing rules.

The one rule the whole practice serves: **mine public sources as data to learn from, never as a spec to mirror.** Everything below is in service of producing a fact base honest enough that a deployment page built from it will survive contact with beamline staff.

## The arc

```
Per facility (once):
  1. survey.md          recon: roster, control stack, data seam, what's modellable
Per chosen beamline:
  2. facts.md           read the controls source, map devices -> candidate Families
  3. beamline.candidate.yaml   draft descriptor, self-validate against the loader
Across the fleet (rolling):
  4. recurrence.md      fold each beamline in; watch the graduation signal
  5. graduation         rule-of-three fires -> separate gate-reviewed catalog PR
Then, only when a modeling decision lands:
  6. promote            confirmed facts -> deployments/<id>/ + docs/deployments/<id>/
```

Steps 1-5 live here in `research/` (tracked, but not the published docs). Step 6 crosses into the public tree and is a different kind of work (a deployment scaffold), out of scope for this doc.

## Step 1: the facility survey (`<facility>/survey.md`)

Copy `_templates/survey.md`. The goal is a *decision*, not a data dump: by the end you must be able to say which beamlines are worth a device pass and whether one is even buildable.

- **Establish the source-of-record posture first.** Does the facility publish per-beamline device config with real handles (Diamond `dodal`, ESRF Beacon, NSLS-II profile collections, APS `*-bits`, DESY OnlineXML)? Or is the device source firewalled (ALBA, Sirius, PSI gitea)? This single fact decides whether Tier-2 is possible. If firewalled, the survey routes device topology to the staff questions; you do not infer it from shared base classes (inference is not source).
- **Separate hardware facts from software facts.** Facility pages give hardware (beamlines, energies, detectors). Source/proceedings give the control stack. Keep the two sourced separately; flag every claim `[verified]` / `[partly verified]` / `[unconfirmed]`.
- **Name the control stack only at the seam.** Sections 3 and 6 are where the facility's software is named, as the floor CORA drives through or the orchestration CORA replaces, never as a spec to mirror.
- **End with staff questions.** Whatever public source could not settle becomes a numbered question for the beamline team. A good survey leaves few.

Output: one `survey.md`, every claim cited. A survey can exist with no beamline pass yet (a candidate facility); that is fine.

## Step 2: the device pass (`<facility>/beamlines/<bl>/facts.md`)

Copy `_templates/facts.md`. One per beamline you choose to model.

- **Source-read BEFORE you write.** Open the actual controls repo/config and read it. The failure mode is fabricated PVs and invented device functions; they are caught late and embarrassingly. Carry every value `confirm` until staff verify it.
- **Map at Asset granularity**, the stage not the per-axis tuning. Put the real control handle (EPICS PV prefix / BLISS object / Tango URL) in the `pv` slot.
- **Resolve every `(?)` against `catalog/catalog.yaml`.** A `Family (?)` is a name-fallback, not a confident map. Either it resolves to an existing Family or it goes in the new-family watch, never silently coined.
- **Fill the four analysis sections honestly:** Role hints, Trust hints, new-family watch, deferred/absent. "Device X missing" is only a defect if X is in source and you omitted it; a device genuinely absent from public source is an open question (`TAG-1`), not a gap to invent around.

## Step 3: the candidate descriptor (`beamline.candidate.yaml`)

A draft `beamline.yaml` fragment that **self-validates against the real loader** (`scripts/beamline_descriptor.py`). For EPICS `*-bits` facilities `scripts/reverse_engineer` emits this for you; for hand-surveyed facilities, draft it and validate. It is a candidate, never written into `deployments/` directly; step 6 curates from it.

## Step 4: fold into recurrence (`<facility>/recurrence.md`)

Copy `_templates/recurrence.md` (or regenerate via the extractor). After each beamline pass, update the cross-fleet frequency. **Count physically distinct beamlines, not repos:** a fork or a multi-endstation repo is one data point. The actionable output is the graduation shortlist: classes that recur across distinct beamlines and are not yet a catalog Family.

## Step 5: graduation (the gated catalog change)

This is where the practice pays off, and where the discipline is strictest.

- **Rule of three.** A Family graduates when three physically distinct beamlines bind the same class with the same contract. Two is a watch, not a trigger.
- **Never coin a Family from one beamline, or from a device not instantiated in source.** That is invention, the exact thing the practice exists to prevent.
- **Know the cost gradient before you propose:**
  - A new **Family** is YAML-only (`catalog.yaml` + docs). Cheap. Scaffold-safe.
  - A new **Role** is a code change (`SEED_ROLES`, drift-guarded by a test) + core vocabulary. Needs gate review and the full contract suite (bootstrap blast radius).
  - A new **affordance** is a second governed closed enum (multiple touchpoints incl the openapi snapshot).
- **Graduation is its own PR**, gate-reviewed, never folded into a deployment scaffold. Run the `naming-r3` reviewer before committing the name.
- A measurement Sensor family graduates by **what it measures** (FluxMonitor=flux, EnergyDispersiveSpectrometer); a position monitor that reads centroid not flux stays loose until its own rule-of-three.

## What stays out

- **No deployment scaffolding here.** Promotion to `deployments/<id>/` + `docs/deployments/<id>/` (step 6) is separate work with its own gate.
- **Published pages never link back into `research/`.** Deployment pages cite the external upstream (the controls repo, the facility page) directly, so this tree can evolve without touching the staff-facing docs.
- **No fabrication, ever.** If public source does not say it, it is an open question, not a value.
