# Australian Synchrotron (ANSTO) research brief

*Retrospective survey. Records the facility behind CORA's MX3 deployment, modeled by reading the public `mx3-beamline-library`. This page gives the Australian Synchrotron a Tier-1 home: the roster context, the modellable set, and the seam. For the live modeled roster read `deployments/as/site.yaml`.*

!!! note "Reading posture"
    The `AustralianSynchrotron/mx3-beamline-library` is the source of CONTROL FACTS (device topology, the four control planes, ophyd / client classes). It does NOT carry calibrated numbers, safety tiers, the human roster, or Capability / Method binding. Every read value is carried `confirm` until staff verify it; the device library exposes no human roster, so governance is a question (GOV-1).

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Australian Synchrotron, storage-ring light source | https://www.ansto.gov.au/facilities/australian-synchrotron |
| Operator | ANSTO (Australian Nuclear Science and Technology Organisation), Clayton, Australia | https://www.ansto.gov.au |
| Instrument modeled | MX3 (macromolecular crystallography) | https://www.ansto.gov.au |
| Controls | EPICS at the facility level + three first-class non-EPICS planes | https://github.com/AustralianSynchrotron/mx3-beamline-library |

The Australian Synchrotron is CORA's sixth Site and its first Australian facility. MX3 reuses the i03 / FMX Goniometer and MX Methods; the novelty is the Site and its heterogeneous control plane.

---

## 2. Candidate beamlines

The `mx3-beamline-library` exposes MX3's device topology and, distinctively, four control planes. The MX cluster (MX1, MX2, MX3) shares house style; only MX3 has a public device library, so it is the modellable one.

**Modeled so far:** read `deployments/as/site.yaml`. As of this writing: MX3.

**The novelty modeled:** the heterogeneous control plane (below). MX3 graduates nothing new in the Family vocabulary (it reuses the i03 Goniometer and the MX Methods); it earns the multi-plane ControlPort shape.

**Modellable (2026-07 update):** beyond MX3, **IMBL** (Imaging and Medical Beam Line) does publish a public device source, the `AustralianSynchrotron/imbl` C++ Qt control application, mined into a device pass (`beamlines/imbl/`). It carries real EPICS PVs under the `SR08ID01` prefix (storage ring sector 08, ID beamline 01): the wiggler source, a bent-Laue DCM (`SR08ID01DCM01:`), filters, the MRT (Microbeam Radiation Therapy) fast shutter (`SR08ID01MRT01:`), EPS valves, and the PSS. It is the optics/shutter/safety front end only; the imaging detectors and CT sample stage are not in this repo (DET-1 / SAMPLE-1, staff questions). See `recurrence.md`.

**Remaining picks:** other AS beamlines (XFM, SAXS/WAXS, etc.) are not covered by a public per-beamline device library (the `saxs_beamline_library` is a thin `ophyd_api` wrapper, not a device topology); modeling them would need a fresh survey or staff contact.

---

## 3. Control-system stack, by layer

The distinctive Site fact: MX3 is EPICS-PV-bound at the facility level (the storage ring at `SR11*`, the beamline at `MX3*`) but drives three first-class non-EPICS control planes.

### Device IO (the floor)

- **EPICS** for facility / beamline-level PVs (`SR11*`, `MX3*`).
- **MD3 microdiffractometer** over the MXCuBE Exporter protocol (TCP).
- **DECTRIS Eiger** over the SIMPLON REST API.
- **ISARA sample robot** over a TCP client library.

CORA's ControlPort spans all four planes. This is the canonical heterogeneous-control-plane deployment, the shape later echoed at NSRRC (Blu-Ice / DCSS over EPICS) and PSI TOMCAT (EPICS + PandABox socket).

### Scan orchestration (the seam layer)

MXCuBE is the MX experiment-orchestration layer. The replace-vs-drive-through boundary (does CORA conduct the MX collection, or drive through MXCuBE) is the central seam question, analogous to the 2-BM TomoScan decision.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| AustralianSynchrotron/mx3-beamline-library | MX3 device library across the four control planes | https://github.com/AustralianSynchrotron/mx3-beamline-library |

---

## 5. Data management

AS data management (the MX data pipeline, the user portal) is a seam question for any deployment that must publish into it; not surveyed here. The device library exposes no catalog.

---

## 6. The CORA seam (initial read)

**Where the floor stays the floor.** All four control planes (EPICS, MXCuBE Exporter, SIMPLON REST, ISARA TCP) are floor CORA drives through; the ControlPort spans them.

**What CORA replaces.** The MXCuBE MX-collection orchestration, incrementally, the same replace-vs-drive-through question as 2-BM TomoScan.

**Source-of-truth contest.** The AS MX data pipeline; deferred until in scope.

---

## 7. Open questions (for Australian Synchrotron staff)

Per-beamline questions live on the MX3 open-questions page. Facility-level:

1. The operator / safety-review governance structure (GOV-1): the device library exposes no human roster.
2. The MXCuBE replace-vs-drive-through boundary for MX collection.
3. The robot custody / Subject thread for unattended ISARA load-collect-unmount (ROBOT-1).

---

## 8. Source list

- Australian Synchrotron: https://www.ansto.gov.au/facilities/australian-synchrotron
- mx3-beamline-library: https://github.com/AustralianSynchrotron/mx3-beamline-library
- MX3 controls detail: docs/deployments/mx3/equipment/controls.md
