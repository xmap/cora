# NSLS-II research brief

*Retrospective survey. Like the Diamond brief, this records a fleet that was already modeled deployment-by-deployment, reading each beamline's public bluesky profile collection at build time rather than via a standing research pass. This page gives NSLS-II a Tier-1 home: the roster, the modellable set, and the seam. For the live modeled roster read `deployments/nsls2/site.yaml`, never a count quoted here, the fleet grows fast.*

!!! note "Reading posture"
    The NSLS-II per-beamline bluesky profile collections (`NSLS2/<beamline>-profile-collection`) are the source of CONTROL FACTS (device topology, real EPICS PVs, ophyd device classes, axes). They do NOT carry calibrated numbers, safety tiers, or Capability / Method binding. Source-read the repo BEFORE writing a descriptor: fabricated PVs and invented device functions are the failure mode (caught by adversarial verify on past builds). Every read value is carried `confirm` until NSLS-II staff verify it.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | National Synchrotron Light Source II, storage ring | https://www.bnl.gov/nsls2 |
| Operator | Brookhaven National Laboratory, Upton NY, USA | https://www.bnl.gov |
| Beamline count | ~29 operating beamlines | https://www.bnl.gov/nsls2/beamlines |
| Controls | EPICS + bluesky / ophyd; public per-beamline profile collections | https://github.com/NSLS2 |

NSLS-II is CORA's fourth Site. Like Diamond it is reverse-engineered from public open source (the bluesky profile collections), not a design report or a live connection.

---

## 2. Candidate beamlines

NSLS-II publishes per-beamline bluesky profile collections (`NSLS2/<beamline>-profile-collection`) with real ophyd device definitions and EPICS PVs. The device topology is directly readable, so beamlines are modeled by reading the profile collection rather than via a pre-extracted Tier-2 facts pass.

**Modeled so far:** read `deployments/nsls2/site.yaml`. The fleet spans hard and soft X-ray and most technique classes (TXM, nanoprobe, XAS / EXAFS, XRF, RIXS, coherent / XPCS, soft scattering, powder / PDF, ARPES, SAXS / WAXS, hard IXS, multi-endstation soft-and-tender, inner-shell spectroscopy, MX, complex-materials scattering, solution scattering, footprinting, and more).

**Graduations earned here:** Manipulator (ESM), GratingMonochromator (CSX), Transfocator / CRL (rule-of-three across the fleet), ElectronAnalyzer (esm + sst), EnergyAnalyzer (IXS, loose). FlowController reached rule-of-three (i22 + 7-bm + lix + xfp) and is a graduation candidate. SpectrometerArm stays loose at n=1, needs a second RIXS.

**Remaining picks:** the live site list is the source of truth; re-verify before picking, parallel sessions ship beamlines faster than this page updates.

**Identifier scheme:** NSLS-II uses named beamlines mapped to sector IDs (e.g. FXI = 18-ID, HXN = 3-ID, ESM = 21-ID). CORA's deployment dir uses the lowercase beamline name (`fxi`, `hxn`), not the sector ID, to avoid collision with APS `N-ID` dirs.

---

## 3. Control-system stack, by layer

### Device IO (the floor)

EPICS. Profile-collection ophyd classes wrap real EPICS PVs. Below CORA's seam; the ControlPort drives through it as at the 2-BM pilot.

### Scan orchestration (the seam layer)

bluesky plans + the queueserver, per beamline. This is CORA's seam: CORA replaces the bluesky plans + queue-server orchestration and drives through ophyd / EPICS. `nslsii` is the Site kernel.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| NSLS2/`<beamline>`-profile-collection | per-beamline ophyd devices + bluesky plans + real PVs | https://github.com/NSLS2 |
| nslsii | Site-level bluesky kernel | https://github.com/NSLS-II/nslsii |

Build the descriptor from a source-read of the profile collection. Past lesson: SIX and CHX had zero fabricated PVs because they were source-read first; an early build that inferred PVs fabricated them. Adversarial verify catches invented device functions, not just PVs.

---

## 5. Data management

NSLS-II's data catalog (the bluesky document model + databroker / Tiled) is a seam contest, not a dependency: CORA owns its own data-of-record (PG event store) and would subsume the bluesky documents at the debrief / publish seam. Tiled is explicitly not adopted as CORA's store. Deferred until a deployment forces the decision.

---

## 6. The CORA seam (initial read)

**Where the floor stays the floor.** EPICS device IO; the APS-pilot ControlPort model carries over.

**What CORA replaces.** The bluesky plans + queue-server scan orchestration. CORA's EdgeConductor conducts routines over ophyd / EPICS where bluesky sits today. Treat the profile collection as DATA to learn from (Families, Assets, axes, Trust), not a spec to mirror.

**Source-of-truth contest.** The bluesky document model / databroker / Tiled. CORA stays the system of record; subsume the documents at the publish seam, do not adopt Tiled.

---

## 7. Open questions (for NSLS-II staff)

Per-beamline questions live on each deployment's open-questions page. Facility-level:

1. The queue-server replace-vs-drive-through boundary per beamline.
2. The databroker / Tiled seam: is downstream ingestion expected, and at what point?

---

## 8. Source list

- NSLS-II beamlines: https://www.bnl.gov/nsls2/beamlines
- NSLS2 profile collections (GitHub org): https://github.com/NSLS2
- nslsii Site kernel: https://github.com/NSLS-II/nslsii
