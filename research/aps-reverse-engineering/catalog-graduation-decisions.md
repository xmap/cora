# Catalog graduation decisions (step 2)

Step 2 of the roadmap: take the recurring candidates from `recurrence.md` through an
intentional graduate / model-as-Assembly / fold / leave-loose decision, with the naming-r3
gate applied to every name a future graduation will use.

## The honest outcome: zero speculative catalog edits now

No new Family lands in `catalog/catalog.yaml` in this step, on purpose. Two reasons:

1. The recurrence is evidence over external `*-bits` repos, not over CORA deployments. CORA's
   graduation rule is two or more CORA deployments reusing a Family. The corpus tells us which
   Families WILL recur when these beamlines are curated; it does not by itself meet the trigger.
   Adding orphan Families on the strength of `*-bits` class names would be the exact
   mirror-not-model antipattern this whole recon warned against.
2. The single strongest signal (Diffractometer, three beamlines) is an Assembly, not a Family.

So graduation is correctly coupled to step 3: graduate each Family in the SAME commit that
first curates a CORA deployment referencing it. The names below are pre-cleared by naming-r3,
so that commit carries no naming risk.

## Decisions

| Candidate | `*-bits` evidence | CORA status today | Decision | naming-r3 |
| --- | --- | --- | --- | --- |
| Diffractometer | 8-ID, POLAR, 6-ID-B | none | model as Assembly (design in step 3) | `Diffractometer` passes (Assembly) |
| Chopper | POLAR, 6-ID-B | loose at 7-BM (CHOP-1 pending) | resolve CHOP-1 toward graduating; staff owns the boundary | `Chopper` passes |
| BeamPositionMonitor | 8-ID, POLAR, 6-ID-B | loose at 2-BM (Sensor) | graduate when a 2nd CORA deployment references it (closest to ready) | spelled-out form passes; not `XBPM` |
| TemperatureController | 8-ID, POLAR, 6-ID-B | none | graduate with first deployment using it | passes (`<Domain>Controller`) |
| Magnet | POLAR, 6-ID-B | none | graduate with first deployment using it | passes (bare thing-noun) |
| Transfocator | 8-ID, 9-ID, 6-ID-B | none | graduate with first deployment using it | passes (prefer over `CompoundRefractiveLens`) |
| Preamplifier | POLAR, 6-ID-B | none | graduate with first deployment; confirm device-is (preamp vs electrometer) | passes (or `Electrometer`) |

Excluded as non-hardware (not Families): `DM_WorkflowConnector` is the APS Data Management
handoff, which maps to the Reckoner / Porter seam, not a catalog Family; `mb_creator` and
`ad_creator` are ophyd construction factories, not device types.

## Detail

### Diffractometer is an Assembly, not a Family

The recurrence ranks Diffractometer high because diffraction beamlines all carry one, but a
diffractometer is a composition: multiple goniometer circles (theta, two-theta, chi, phi)
plus a reciprocal-space pseudo-axis (hklpy2). That is the Microscope pattern. The CORA shape
is an `Assembly(Diffractometer)` presenting the `Positioner` Role, with circle slots bound to
`RotaryStage` (and `TiltStage` where range is limited) and the reciprocal-space axis as the
existing `PseudoAxis` Family (its `partition_rule` resolves to the real circle setpoints, the
same mechanism as the 2-BM `objective_selector`). Do not mint a `Goniometer` Family for the
circles; `RotaryStage` covers them. This is a design slice to run in step 3 against the first
diffraction beamline curated (POLAR or 6-ID-B), not a catalog row to add now.

### Chopper: evidence strengthens CHOP-1, staff still owns the boundary

`Chopper` is already a loose Family at 7-BM with the open question CHOP-1: is it a distinct
Family, or a `Shutter` / `RotaryStage` plus settings? The corpus adds POLAR and 6-ID-B, so
the device type now recurs across three beamlines, past the rule-of-three threshold. That
strengthens the case to earn `Chopper` as a Family, but CHOP-1 is a modeling-boundary
decision the beamline staff own (whether a chopper is meaningfully distinct from a fast
shutter at these beamlines). Recommendation: carry the corpus evidence into CHOP-1 and lean
toward graduating; do not graduate unilaterally.

### The five graduate-with-curation Families

`BeamPositionMonitor`, `TemperatureController`, `Magnet`, `Transfocator`, `Preamplifier` are
genuine new device-type Families, each recurring across two or three diffraction or
sample-environment beamlines, none used by any current CORA deployment. Their names are
pre-cleared. Each graduates in the commit that first curates a deployment referencing it.
`BeamPositionMonitor` is closest to ready: it is already loose at 2-BM as a Sensor-presenting
device, so the first additional reference makes it a clean two-deployment graduation.

## How graduation actually lands (the rule for step 3)

For each Family above, when curating a deployment that references it:

1. Add the Family to `catalog/catalog.yaml` with its `presents_as` Role (`Sensor` for
   `BeamPositionMonitor` and `Preamplifier`; `Controller` for `TemperatureController`;
   confirm for `Magnet` and `Transfocator`).
2. Reference it from the curated `deployments/<id>/beamline.yaml`.
3. Run the descriptor tests manually (`tests/unit/deployments/`), since catalog edits pass
   pre-commit but can break referential integrity.
4. The naming is already gated here; no second naming-r3 pass is needed unless the shape
   changes.
