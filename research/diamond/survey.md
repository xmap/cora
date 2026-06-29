# Diamond Light Source research brief

*Retrospective survey. Unlike the PSI / ALS / PETRA III surveys (written before any modeling), this records a fleet that was already modeled: the Diamond beamlines were built deployment-by-deployment by reading the public `dodal` controls library per beamline at build time, so the "research pass" lived in each deployment's build rather than in a standing brief. This page captures the roster, the modellable set, and the seam after the fact, so the facility has a Tier-1 home like the others. For the live modeled roster read `deployments/diamond/site.yaml`, never a count quoted here.*

!!! note "Reading posture"
    Diamond's `dodal` controls library is the source of CONTROL FACTS (device topology, real EPICS PV prefixes per beamline). It does NOT carry calibrated numbers, hutch / PSS safety, the passive beam-path tier, or Capability / Method binding; those stay questions. Mine `dodal` as data to learn from, never as a spec to mirror. Every value a deployment reads from `dodal` is carried `confirm` until Diamond staff verify it.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Diamond Light Source, storage-ring light source | https://www.diamond.ac.uk |
| Operator | Diamond Light Source Ltd, Harwell, UK | https://www.diamond.ac.uk |
| Beamline count | ~33 operating beamlines (I / B / K prefixes) | https://www.diamond.ac.uk/Instruments.html |
| Controls library | `dodal` (public, per-beamline ophyd_async device defs) | https://github.com/DiamondLightSource/dodal |

Diamond is CORA's third Site and a deliberate off-roadmap generalization exercise: it tests that the dry-fact `dodal` seed feeds CORA's intentional model, and that the model generalizes beyond tomography (SCOPE-1).

---

## 2. Candidate beamlines

Diamond publishes `dodal`, the open controls library, with per-beamline ophyd_async device definitions carrying real EPICS PV prefixes. This makes the per-beamline device topology directly readable, so Diamond beamlines are modeled by reading the `dodal` module rather than via a pre-extracted Tier-2 facts pass. The modellable set is the `dodal` beamline-module roster (`src/dodal/beamlines/`), excluding sim / training / optics / shared / supervisor helper modules.

**Modeled so far:** read `deployments/diamond/site.yaml`. As of this writing: I22, I03, I15-1, I11, I24, I06, I10, I20-1, I19, I13-1.

**Strongest remaining picks** (verify against `dodal` before committing, and re-check the live site list, the fleet moves fast):

| Beamline | `dodal` module | Technique | What it would earn |
| --- | --- | --- | --- |
| I21 | `i21.py` | RIXS | resolves the loose `SpectrometerArm` family at n=2 |
| I05 | `i05.py` / `i05_1.py` | ARPES | Diamond's first photoemission (twin of NSLS-II ESM) |
| I09 | `i09*.py` | HAXPES (dual hard+soft branch) | new-axis photoemission |
| I07 | `i07.py` | surface & interface diffraction | reuse + reinforce |
| I16 | `i16.py` | materials & magnetism (resonant scattering) | reuse |
| I04 | `i04.py` | rotation MX (~29 devices) | clone / reinforce; graduates nothing (light eval) |
| B18 / I18 | `b18.py` / `i18.py` | core EXAFS / microfocus spectroscopy | the energy_scan Capability earn, IF a live scanning DCM exists |

**Energy_scan caveat:** the pending `energy_scan` Capability still wants a tunable XAS / EXAFS beamline whose scanning mono is actually instantiated in `dodal`. I18's DCM is `skip=True`; I20-1's `p51.py` is the EDE branch (dispersive, the polychromator absent: POLY-1 / STRIP-1); B18 is thin. The scanning-XAS earn may not be satisfiable from current `dodal`.

**Identifier scheme:** Diamond uses `I##` / `B##` / `K##` beamline IDs, with `dodal` PV roots like `BL22I` (I22), `BL51P` (I20-1 / p51). Differs from the APS `sector.station` scheme the pilot assumes.

---

## 3. Control-system stack, by layer

### Device IO (the floor)

EPICS. `dodal` device classes are ophyd_async wrappers over real EPICS PV prefixes. This is below CORA's seam; CORA's ControlPort actuates through the EPICS floor, exactly as at the 2-BM pilot.

### Scan orchestration (the seam layer)

Diamond runs bluesky plans over `dodal` devices (the `BlueAPI` / GDA lineage). This is the layer CORA's EdgeConductor would conduct over, incrementally and routine-by-routine. `dodal` is DATA to learn from (device topology, axis grouping), not a spec to mirror.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| DiamondLightSource/dodal | per-beamline ophyd_async device defs with real PV prefixes | https://github.com/DiamondLightSource/dodal |

`dodal` gives device topology + PV addressing (dry, correct). It does NOT give calibrated numbers, safety tiers, or Capability binding. Because `dodal` carries the real `pv` per device, Diamond deployments record real control handles, unlike design-report-only deployments.

---

## 5. Data management

Diamond's data catalog (ISPyB for MX, the facility's GDA / SciCat-adjacent stack) is not surveyed here; it is a future seam question for any deployment that must publish into it.

---

## 6. The CORA seam (initial read)

**Where the floor stays the floor.** Diamond device IO is EPICS; the APS-pilot ControlPort model carries over with no new control substrate to build.

**What CORA replaces.** The bluesky / GDA scan orchestration over `dodal`. CORA's EdgeConductor conducts routines over the EPICS floor where bluesky plans sit today.

**Source-of-truth contest.** Diamond's catalog (ISPyB / GDA) is a future contest, deferred until a Diamond deployment that must publish into it is in scope.

---

## 7. Open questions (for Diamond staff)

Per-beamline questions live on each deployment's open-questions page (calibrated ranges, hutch / PSS safety, Capability / Method binding, the passive beam-path tier). Facility-level:

1. Which scan-orchestration surface (BlueAPI, GDA) is authoritative per beamline, and what is the replace-vs-drive-through boundary?
2. The data-catalog seam (ISPyB for MX, the imaging catalog): mandatory ingestion, and at what point?

---

## 8. Source list

- Diamond beamlines: https://www.diamond.ac.uk/Instruments.html
- dodal controls library: https://github.com/DiamondLightSource/dodal
