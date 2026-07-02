# Model

*The developer's by-kind index: where each CORA aggregate's Bernina content lives, how the diffraction platform composes as an Assembly rather than a Family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Bernina |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the reciprocal-space `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The headline: the diffraction platform is an Assembly, not a Family

Bernina's defining endstation is two reconfigurable diffraction platforms: GPS (`SARES22-GPS`, a six-circle station) and XRD (`SARES21-XRD`, a You-geometry station). The `eco` driver `bernina_diffractometers.py` builds, from literal PV suffixes, a base (gamma / mu plus translations and tilts), a 2-theta detector arm (delta / detector translation), a polarization-analyzer branch (pol / pthe / ptth), a kappa goniometer (with on-the-fly kappa-to-Eulerian eta / chi / phi conversion), a heavy-load goniometer table, and a PI hexapod, with an optional Staeubli robot contributing gamma / delta.

That is far more than the catalog `Goniometer`, the integrated single-device sample orienter that [I03](../i03/model.md) graduated and [MX3](../mx3/model.md) reused. But it is **exactly the graduated `Diffractometer` Assembly** that 4-ID and 8-ID earned: a composed scattering instrument that

- binds **one `Goniometer`** for the sample-orientation circles plus x / y / z centring,
- binds **zero or more `RotaryStage`** detector-arm circles (here the `delta` 2-theta arm), and
- binds **one reciprocal-space `PseudoAxis`** whose partition rule resolves the inverse kinematics (here the `SixCircleBernina` and kappa-to-You conversions).

So Bernina coins **no new Family and adds no new Assembly**. Each platform is modelled as a `Goniometer` Asset + a `PseudoAxis` Asset (and, for XRD, a `RotaryStage` detector-arm Asset), composed through the existing `Diffractometer` Assembly. The GPS and XRD platforms are its third and fourth bindings, reinforcing the 4-ID / 8-ID graduation from a third facility and, for the first time, at an XFEL (DIFF-1). The reciprocal-space partition rule (the hkl inverse kinematics, and the kappa-to-Eulerian conversion XRD adds) is the same `PartitionRule` design the synchrotron diffractometers carry, deferred here as DIFF-2.

## Deliberately not here yet: the externalized configuration (CONFIG-1)

This is the boundary that makes Bernina a partial first cut, and it is a different boundary from i13-1's. At i13-1 the upstream source was simply absent from the public module. At Bernina the device **list** and the diffractometer **axis topology** are public (in `bernina.py` and `bernina_diffractometers.py`), but the **configuration state** is loaded at runtime from non-public PSI files:

- `eco/bernina/config.py`'s entire `components` device list is commented out and `extend`-ed from `/sf/bernina/config/eco/bernina_config_eco.json` (not in the repo).
- `bernina.py` reads `/sf/bernina/config/eco/configuration/bernina_config.json` for the per-diffractometer flags that decide **which sub-assemblies are mounted** (base / arm / polana / kappa / heavy-load / hexapod / robot) and **which detectors attach to each diffractometer**.

So CORA can model the platforms' shape but not their current instantiation: the inventory carries the recoverable devices, and the mount state and detector wiring are carried unknown, not guessed (CONFIG-1). This is the honest scope line, and it is recorded so a later cut (or a staff confirmation) can fill it without re-deriving the topology.

## The architectural gap register (shared with the other XFELs)

These are the same deferrals Alvra and LCLS-MFX recorded; Bernina re-confirms them on a diffraction platform rather than a spectroscopy one, which is itself the point (the gaps are about acquisition, not technique).

- **One switched Aramis source feeding co-equal stations (TOPO-1).** Now concrete: Bernina is the second root Unit on the same source as Alvra. Two co-equal Units sharing one upstream source has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model.
- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The `sf-daq` records a free-running `bsread` stream of per-shot frames correlated by pulse-ID; CORA's poll-to-Done acquisition has no representation for it. The Run stays the provenance envelope and the per-shot plane is a referenced `Dataset`.
- **Beam-synchronous event-system timing (TIMING-1).** The SwissFEL master timing, CTA sequencer, and EVR receivers gate acquisition at beam rate; `TimingController` carries the device but the trigger pattern has no typed home.
- **Femtosecond pump-probe synchronization (LASER-1).** The `eco` `lxt` timing chain and the PSEN arrival-time monitor hold and correct the laser-to-X-ray delay; CORA's single-domain `PartitionRule` cannot express the cross-timing-domain sync. The laser folds (catalog `Laser`); the sync is the gap.

## What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Bernina earns no catalog change; the pump-probe and diffraction recipes are carried pending on the [PSI Practices](../psi/index.md). No catalog Model is bound.
- **The Staeubli TX200 robot (ROBOT-1).** The sample / detector handling robot runs over PShell (HTTP), not EPICS, and its modelling is deferred, the same posture I03 and MX3 take for their sample-exchange arms.
- **The RIXS / tape-drive / liquid-jet sample environments (ENV-1).** `eco` defines these but their appends are commented out, so they are not in the live module; deferred, not invented.
- **The eco cross-line reference (XREF-1).** A live Bernina profile monitor (`prof_mirr_alv1`) carries an Alvra-line PV (`SAROP11-PPRM066`); whether that is a real shared device or a copy-paste residue is carried as an open question.
- **Integration scenarios.** No `test_bernina_*.py` registers Bernina Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.
