# Cristallina

*The Cristallina hard X-ray station on SwissFEL's Aramis branch at PSI, the third station alongside [Alvra](../alvra/index.md) and [Bernina](../bernina/index.md): a pump-probe instrument for time-resolved diffraction and scattering on quantum materials, with a dilution-fridge vector-magnet sample environment, plus a serial-crystallography endstation. This page walks the beamline as it is being modelled; everything here is reverse-engineered from PSI's open `slic` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `Cristallina` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PSI](../psi/index.md) (bound via `facility_code = "psi"`, `FacilityKind = Site`); the third beamline on PSI's SwissFEL |
| Source | shared SwissFEL Aramis undulator line (the `SAROP31` branch); per-shot photon energy (5-13 keV), fed one station at a time (SRC-1, TOPO-1) |
| Status | Off-roadmap modelling exercise (not a CORA pilot) |
| Technique | time-resolved hard X-ray diffraction / scattering (quantum materials), serial femtosecond crystallography |
| Beam | SASE hard-X-ray free-electron laser; one shared linac and Aramis undulator line feeding co-equal stations; per-shot photon energy |
| Control stack | the `slic` EPICS device library (on `gitea.psi.ch`), the SwissFEL event-driven DAQ (`sf-daq` / `bsread`), and the CTA / EVR event timing |

!!! note "How CORA would land on Cristallina, and what is and is not in source"
    Cristallina is a real, operating station, but it is **not** on the CORA pilot roadmap. It is modelled here, like [Alvra](../alvra/index.md) and [Bernina](../bernina/index.md), from PSI's open controls source. The distinctive provenance fact: Cristallina is **not in `eco`**; it lives in the [`slic`](https://gitea.psi.ch/slic/cristallina) library on PSI's gitea (publicly reachable, branch `master`), `eco`'s active successor. This makes it a **fuller cut than Bernina**: the device facts are in-repo Python literals, not externalized to a non-public file. Every read value is carried `confirm` until staff verify it; the motor units, limits, and Aramis source parameters that `slic` does not carry are deferred, not invented. See [Open questions](questions.md).

## What Cristallina adds

Cristallina sits next to Alvra and Bernina on the same Aramis branch and adds three things, none of them a new device Family.

### The third station: the shared-source triad closed

Alvra named the **switched shared source** (TOPO-1); Bernina made it concrete as a second co-equal station. Cristallina is the **third**: the Aramis undulator line feeds Alvra, Bernina, and Cristallina one at a time. Modelling the third Unit on the same source moves CORA from a two-Unit case to the full three-Unit routing problem, the shape the `Supply("PhotonBeam")` seam would have to carry, and the routing state ("which of three stations has beam now") it does not yet model (TOPO-1).

### A new control source: `slic`, not `eco`

Alvra and Bernina were mined from `eco`. Cristallina is **CORA's first deployment mined from `slic`**, the library that succeeds `eco` at SwissFEL. It is on a different host (`gitea.psi.ch`, not GitHub) and a different shape (categorized PV-channel lists plus driver classes), and unlike Bernina's `eco` config it keeps the device facts in-repo rather than in a non-public JSON. That a third PSI station, on a different controls library, reaches the same family-fold and acquisition-gap findings strengthens the case that those findings are about the facility class, not one library's house style.

### A dilution-fridge vector-magnet sample environment

Cristallina's quantum-materials endstation carries a **dilution refrigerator with a 3-axis vector superconducting magnet** (the "DilSc": a LakeShore 372 thermometry / heater and an Oxford Mercury iPS vector magnet, to 5.2 Tesla on the z-axis). This is the most novel sample environment in the PSI set. It still coins no new Family:

- the **magnet** binds the **loose `Magnet`** family, which is held at the rule-of-three (its three consumers are [4-ID](../4-id/index.md), [i10-1](../i10/index.md), and [ESRF ID32](../id32/index.md)). Cristallina is the **fourth consumer**, reinforcing the held graduation, but the graduation stays deferred to its dedicated gated PR (MAG-1).
- the **LakeShore 372** binds the **graduated `TemperatureController`** Family (the ID32 VTI precedent).

### No pump-probe laser in source

Unlike Alvra and Bernina, the `slic` source carries **no pump-probe optical laser** (no `SLAAR` / `PALM` / `PSEN` devices); the only laser is the X-ray **alignment** laser (`SAROP31-OLAS147`). Pump-probe timing is mediated by the CTA sequencer and the EVR, with a server-side pulse-tube synchronization service. So this cut carries no pump-probe-laser Asset, and whether one exists in another controls layer is carried as an open question (LASER-1).

The rest of the device set folds as at Alvra and Bernina: the offset and KB mirrors into `Mirror`, the attenuators into `Filter`, the slits into `Slit`, the double-channel-cut mono into `Monochromator`, the pulse picker into `Shutter`, the profile monitors into `Scintillator` + `Camera`, the PBPS / gas monitors and the photon spectrometer into `FluxMonitor` + `Diagnostic`, the two diffractometers into the graduated `Diffractometer` Assembly (DIFF-1), the Jungfraus into `Camera`, and the CTA / EVR timing into `TimingController`. The architectural XFEL gaps are the same: per-shot pulse-ID DAQ (DAQ-1) and beam-synchronous timing (TIMING-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the Aramis FEL source, the front-end gas monitors and photon spectrometer, the front-end slit and attenuator, and the `SAROP31` Aramis optics hutch (offset mirrors, double-channel-cut mono, slits, pulse picker, attenuator, KB focusing mirrors, alignment laser), rendered as the generated source-stage device walk.
- [Endstation](equipment/endstation.md): the Cristallina endstation, the I0 chamber, the DM1 dilution-fridge and DM2 pulsed-magnet diffractometers, the DilSc dilution refrigerator and its vector magnet, and the Cristallina-MX fast sample stage.
- [Detector](equipment/detector.md): the per-shot Jungfrau area detectors and the DAQ data plane they feed.

Cutting across all of them:

- [Controls](equipment/controls.md): the `slic` EPICS device library, the SwissFEL CTA / EVR timing, and the event-driven DAQ that CORA references but does not own.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the `slic`-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cristallina/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): time-resolved hard X-ray diffraction / scattering (quantum materials) and serial crystallography, carried pending on the [PSI Practices](../psi/index.md).

## Governance

[Governance](governance.md): who would act at Cristallina and the trust shape that gates their commands, including the Clearance that would gate the high-field magnet and its cryogens. People and agents are facility principals at the [PSI Site](../psi/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's Cristallina content lives, the `Diffractometer` Assembly and `Magnet` rule-of-three decisions, and the `slic` provenance boundary.

## Not yet documented

Cristallina is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The [2-BM deployment](../2-bm/index.md) shows the shape they would take.
