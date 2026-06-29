# SLAC / LCLS research brief

*Retrospective survey. Records the facility behind CORA's first XFEL deployment (LCLS-MFX), modeled by reading SLAC's open `pcdshub` controls stack. This page gives SLAC a Tier-1 home: the roster context, the modellable set, and the seam. For the live modeled roster read `deployments/slac/site.yaml`.*

!!! note "Reading posture"
    SLAC's `pcdshub` stack (LCLS Photon Controls and Data Systems) is the source of CONTROL FACTS (device topology, EPICS PVs, ophyd / `pcdsdevices` classes). It does NOT carry calibrated numbers, safety tiers, or Capability / Method binding. Every read value is carried `confirm` until LCLS staff verify it; do not invent facility specifics, carry them as questions on the LCLS-MFX open-questions page.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | LCLS / LCLS-II X-ray free-electron laser | https://lcls.slac.stanford.edu |
| Operator | SLAC National Accelerator Laboratory, Menlo Park, USA | https://www6.slac.stanford.edu |
| Instrument modeled | MFX (Macromolecular Femtosecond Crystallography) | https://lcls.slac.stanford.edu/instruments/mfx |
| Controls | EPICS + ophyd / `pcdsdevices`; public `pcdshub` stack | https://github.com/pcdshub |

SLAC is CORA's fifth Site and its first X-ray free-electron laser. LCLS-MFX is an off-roadmap exercise chosen as the one deployment that tests whether CORA generalizes beyond the storage-ring acquisition paradigm to an XFEL (pulsed, shot-by-shot, pump-probe).

---

## 2. Candidate beamlines

SLAC publishes `pcdshub` (notably `pcdsdevices`, the ophyd device library, and `happi`, the device database), so the per-instrument device topology is readable from open source.

**Modeled so far:** read `deployments/slac/site.yaml`. As of this writing: LCLS-MFX.

**The novelty modeled:** the XFEL acquisition paradigm. Where a storage-ring beamline scans a continuous beam, an XFEL delivers shots at the machine rep rate; the run model is shot-indexed, pump-probe delay is a first-class axis, and the "detector" is a per-shot area detector keyed to a pulse ID. This is the stress test for whether CORA's Run / acquisition model holds outside the storage-ring assumption.

**Remaining picks:** other LCLS instruments (CXI, XPP, etc.) share the `pcdshub` stack and would reuse the XFEL paradigm; none modeled yet.

---

## 3. Control-system stack, by layer

### Device IO (the floor)

EPICS, with the `pcdsdevices` ophyd library wrapping LCLS PVs and `happi` as the device database. Below CORA's seam.

### Scan orchestration (the seam layer)

LCLS uses bluesky / `nabs` (beamline automation) over `pcdsdevices`, plus the DAQ for shot-synchronized capture. The scan / scan-like orchestration is CORA's seam; the deterministic shot-by-shot DAQ timing loop is floor CORA never enters.

### Fast paths and exceptions

The XFEL DAQ and timing system (pulse-ID-tagged, machine-rep-rate) is a fast path below CORA: CORA governs and records the run, it does not enter the per-shot real-time loop.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| pcdshub/pcdsdevices | ophyd device library for LCLS instruments | https://github.com/pcdshub/pcdsdevices |
| pcdshub/happi | device database | https://github.com/pcdshub/happi |
| pcdshub/nabs | beamline automation / scans | https://github.com/pcdshub/nabs |

---

## 5. Data management

LCLS data management (the DAQ output, psana analysis, the experiment database) is a seam question for any deployment that must publish into it; not surveyed in depth here.

---

## 6. The CORA seam (initial read)

**Where the floor stays the floor.** EPICS device IO via `pcdsdevices`, plus the shot-synchronized DAQ timing loop, which CORA never enters. The ControlPort drives through EPICS.

**What CORA replaces.** The bluesky / `nabs` scan-like orchestration. CORA conducts the run and the pump-probe / scan structure; it does not out-execute the DAQ on shot timing (barred from the real-time loop by construction).

**Source-of-truth contest.** The LCLS experiment database / DAQ output. CORA stays the system of record for the experiment; subsume at the publish seam.

---

## 7. Open questions (for LCLS staff)

Per-beamline questions live on the LCLS-MFX open-questions page. Facility-level:

1. The bluesky / `nabs` vs DAQ boundary: which orchestration is CORA's seam vs the real-time floor?
2. The experiment-database / psana publish seam.
3. Pulse-ID to run / acquisition-context identifier mapping.

---

## 8. Source list

- LCLS MFX instrument: https://lcls.slac.stanford.edu/instruments/mfx
- pcdsdevices: https://github.com/pcdshub/pcdsdevices
- happi: https://github.com/pcdshub/happi
- nabs: https://github.com/pcdshub/nabs
