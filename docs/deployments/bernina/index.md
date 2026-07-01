# Bernina

*The Bernina hard X-ray diffraction and scattering pump-probe station on SwissFEL's Aramis branch at PSI, the sibling of [Alvra](../alvra/index.md): a femtosecond optical-pump / X-ray-probe instrument for time-resolved diffraction and scattering on two reconfigurable diffractometers. This page walks the beamline as it is being modelled; everything here is reverse-engineered from PSI's open `eco` controls library or inferred, not a commissioned measurement, and it is a deliberately partial first cut.*

| Property | Value |
| --- | --- |
| Asset | `Bernina` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PSI](../psi/index.md) (bound via `facility_code = "psi"`, `FacilityKind = Site`); the second beamline on PSI's SwissFEL |
| Source | shared SwissFEL Aramis undulator line (the `SAROP21` branch); per-shot photon energy, fed one station at a time (SRC-1, TOPO-1) |
| Status | Off-roadmap modelling exercise (not a CORA pilot); **deliberately partial** (the live device config is externalized, CONFIG-1) |
| Technique | femtosecond pump-probe, time-resolved hard X-ray diffraction and scattering |
| Beam | SASE hard-X-ray free-electron laser; one shared linac and Aramis undulator line feeding co-equal stations; per-shot photon energy |
| Control stack | the `eco` EPICS device library, the SwissFEL event-driven DAQ (`sf-daq` / `bsread`), and the event-system timing |

!!! warning "Design phase, a deliberate off-roadmap exercise, and a partial first cut"
    Bernina is a real, operating station, but it is **not** on the CORA pilot roadmap. It is modelled here, like [Alvra](../alvra/index.md), from PSI's open [`eco`](https://github.com/paulscherrerinstitute/eco) controls library. **This is a deliberately partial first cut, for a specific reason:** Bernina's `eco` config is partially externalized. The device list in `eco/bernina/config.py` is commented out and loaded at runtime from a non-public path (`/sf/bernina/config/eco/bernina_config_eco.json`), and the live module reads a second non-public config for which diffractometer sub-assemblies are mounted and which detectors attach to each. So what is recoverable from public source is the **device list with PV prefixes** and the **diffractometer motor-axis topology**; what is not is the **configuration state** (CONFIG-1). Every read value is carried `confirm` until staff verify it; the externalized state is carried unknown, not invented. See [Open questions](questions.md).

## What Bernina adds: a shared source, and a diffractometer platform

Bernina sits next to [Alvra](../alvra/index.md) on the same Aramis branch, and it adds two things the fleet did not have, neither of them a new device Family.

### A second station on one source: the TOPO-1 seam, made concrete

Alvra raised the deferred question of **one switched Aramis source feeding co-equal stations** (TOPO-1) but, as a single station, could only name it. Bernina is one of those co-equal stations: the Aramis undulator line feeds Alvra, Bernina, and Cristallina one at a time. Modelling a **second** root Unit on the **same** source is the first time the fleet actually exercises the shared-switched-source seam rather than describing it. CORA models each beamline as a root Unit owning its source; two co-equal Units sharing one upstream source has no home except the `Supply("PhotonBeam")` seam, and the routing state ("which station has beam now") is the gap Bernina makes real (TOPO-1).

### A reconfigurable diffractometer, which the catalog already covers

Bernina's defining endstation is a pair of diffraction platforms: the **GPS** six-circle station (`SARES22-GPS`) and the **XRD** You-geometry station (`SARES21-XRD`), the latter carrying a 2-theta detector arm, a polarization-analyzer branch, a kappa goniometer with on-the-fly kappa-to-Eulerian conversion, a heavy-load goniometer table, and a PI hexapod. This is materially richer than the catalog `Goniometer` (the integrated single-device sample orienter from [I03](../i03/index.md) and [MX3](../mx3/index.md)).

It is, however, **exactly the graduated `Diffractometer` Assembly** ([4-ID](../4-id/index.md), [8-ID](../8-id/index.md)): a composed instrument that binds a `Goniometer` for the sample circles, zero or more `RotaryStage` detector-arm circles, and a reciprocal-space `PseudoAxis`. So Bernina coins **no new Family**: each platform is modelled as a `Goniometer` Asset plus a `PseudoAxis` Asset reusing that Assembly, with the composition designed on [Model](model.md) (DIFF-1). The right home for an FEL diffraction platform is the existing Assembly, not a new "FEL diffractometer" Family.

The rest of the device set folds the same way Alvra's did: the offset and KB mirrors into `Mirror`, the attenuators into `Filter`, the slits into `Slit`, the double-crystal mono into `Monochromator`, the pulse picker into `Shutter`, the profile monitors into `Scintillator` + `Camera`, the PBPS / gas monitors into `FluxMonitor` + `Diagnostic`, the PSEN arrival-time monitor into the loose `Diagnostic`, the hexapod into `Hexapod`, the Jungfrau into `Camera`, and the pump-probe and reference lasers into the catalog `Laser` Family. The architectural XFEL gaps are the same ones Alvra and LCLS-MFX recorded: per-shot pulse-ID DAQ (DAQ-1), beam-synchronous timing (TIMING-1), and femtosecond pump-probe synchronization (LASER-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the Aramis FEL source and its front-end monitors, then the front-end shutters and attenuator, and the `SAROP21` Aramis optics hutch (offset mirrors, double-crystal mono, pulse picker, attenuator, KB focusing mirrors, and the PSEN timing diagnostic), rendered as the generated source-stage device walk.
- [Endstation](equipment/endstation.md): the Bernina diffraction endstation, the GPS six-circle and XRD You-geometry diffractometers, the hexapod sample table, the pump-probe laser, and the sample-view cameras.
- [Detector](equipment/detector.md): the per-shot Jungfrau area detector and the DAQ data plane it feeds.

Cutting across all of them:

- [Controls](equipment/controls.md): the `eco` EPICS device library, the SwissFEL event-system timing, the event-driven DAQ that CORA references but does not own, and the non-public config files the live device list is loaded from (CONFIG-1).

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the `eco`-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/bernina/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): femtosecond pump-probe and time-resolved hard X-ray diffraction / scattering, carried pending on the [PSI Practices](../psi/index.md). The pump-probe Method is shared with Alvra and LCLS-MFX; the diffraction Method is new.

## Governance

[Governance](governance.md): who would act at Bernina and the trust shape that gates their commands, including the Clearance that would gate the class-4 pump-probe laser. People and agents are facility principals at the [PSI Site](../psi/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's Bernina content lives, the `Diffractometer` Assembly design (DIFF-1), and the externalized-config boundary that makes this a partial cut (CONFIG-1).

## Not yet documented

Bernina is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The [2-BM deployment](../2-bm/index.md) shows the shape they would take.
