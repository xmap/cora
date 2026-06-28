# ID19

*Hard X-ray parallel-beam microtomography, radiography, and phase-contrast imaging on the long imaging beamline at the ESRF. This page describes how CORA would model and run ID19, reverse-engineered from the beamline's own public BLISS control configuration; it is not yet confirmed by ESRF staff. ID19 is CORA's first deployment on a non-EPICS control floor.*

| Property | Value |
| --- | --- |
| Asset | `ID19` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ESRF](../esrf/index.md) (bound via `facility_code = "esrf"`, `FacilityKind = Site`) |
| Sector | ID19, the long imaging / tomography beamline; two tomography endstations modelled (micro-resolution MR, high-resolution HR) |
| Status | Reverse-engineered from the public ID19 BLISS config; source, optics, and the MR + HR endstations modelled; other endstations noted (ENDSTATION-1) |
| Source | ESRF-EBS insertion devices: undulators (u13a, u32a, u17-6c, u32c) and the w150b wiggler, per mode (SRC-1) |
| Control stack | **ESRF BLISS (Tango-based), not EPICS** (CTRL-1) |

!!! warning "How CORA would land on ID19, and the confirm-pending posture"
    These pages describe how CORA would model, govern, and conduct ID19. They are not a survey of the beamline's current software. The hardware facts (devices, BLISS objects, Tango handles) are read from ID19's own public Beacon device database ([`gitlab.esrf.fr/id19/beamline_configuration`](https://gitlab.esrf.fr/id19/beamline_configuration), the live `/users/blissadm/local/beamline_configuration` YAML tree; extraction in [`research/esrf-reverse-engineering/`](https://github.com/xmap/cora/tree/main/research/esrf-reverse-engineering)). Device names and control handles are real; vendor part numbers, serials, energy ranges, and physical positions are not in the config and are open questions. Every value is carried `confirm` until ID19 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. This cut models the source, the optics, and the two main tomography endstations (MR and HR); the further endstations in the config (MH, MED, laminography, radiography, PCO) are noted, not modelled (ENDSTATION-1).

## What makes ID19 different

ID19 is CORA's first beamline on a **non-EPICS control floor**. The whole fleet to date sits on EPICS, in one variant or another: the APS, Diamond, NSLS-II, and SLAC deployments are all ophyd / bluesky / dodal / pcdshub, and the one prior non-EPICS model, MAX IV [TomoWise](../tomowise/index.md), is design-phase only. ESRF runs **BLISS**, a Tango-based control system, so ID19 is the fleet's first *live* non-EPICS floor.

It is worth being honest about where the novelty does, and does not, sit.

- **The technique is not the novelty.** Microtomography is plain `tomography` Method reuse, the same Method the [2-BM](../2-bm/index.md) operational pilot and MAX IV [TomoWise](../tomowise/index.md) carry. A sample is spun through the beam while an area detector records a stack of projection radiographs; a real-space volume is reconstructed downstream. ID19 coins no new technique.
- **The instrument is not the novelty.** The rotation stages bind the catalog `RotaryStage`, the sample and detector positioning stages bind `LinearStage`, the detectors bind `Camera` (which presents the Detector Role), and the optics bind `Monochromator`, `Slit`, `Transfocator`, `Filter`, and `Shutter`. All are already in the catalog. ID19 coins no new Family and changes nothing in the catalog.
- **The novelty is the control plane.** The seam model that today reads "EPICS is the floor" generalizes here to "BLISS / Tango is the floor". In BLISS a motion stage is a controller class with named axes (driven by Elmo serial controllers and IcePAP racks), and a detector is a Lima device server addressed by a Tango name (`id19/limaccd/frelon1`); CORA's edge conducts the tomographic scan over its `ControlPort` against that floor rather than EPICS. This is the test that the seam abstraction is not secretly EPICS-shaped (CTRL-1).

The net: ID19 holds the device families and the technique constant and moves one axis, the control plane. Nothing graduates, nothing in the catalog changes; its contribution is the first non-EPICS, BLISS / Tango floor.

## Scope: what is and is not modelled

| In this cut | Noted, not modelled |
| --- | --- |
| The insertion-device source: undulators + the w150b wiggler (SRC-1) | the MH and MED tomography endstations (ENDSTATION-1) |
| The optics: TripleMono, primary / secondary slits, transfocator, attenuators (OPT-1) | the LATOMO laminography endstation (MicosAnka over TCP, tilt-transformation, ENDSTATION-1) |
| The front-end and beam shutters (PSS-1) | the RADIO and PCOTOMO sessions (ENDSTATION-1) |
| The **MR** endstation: rotation + sample + detector + propagation stages (SAMPLE-1, DET-1) | the SmarAct multi-tower stack and the fluorescence MCAs (ENDSTATION-1) |
| The **HR** endstation: rotation + sample + detector + propagation stages (SAMPLE-1, DET-1) | vendor models, serials, energy reach (carried confirm) |

Two enclosures are modelled: the optics hutch `id19-optics` and the experiment hutch `id19-experiment` (ENC-1).

## Key modelling decisions

- **Zero new families.** Microtomography reuses the catalog `RotaryStage`, `LinearStage`, `Camera`, `Monochromator`, `Slit`, `Transfocator`, `Filter`, and `Shutter`; nothing graduates and the catalog is unchanged.
- **Microtomography is the existing `tomography` Method.** ID19 is a further consumer of the Method the 2-BM pilot and TomoWise already carry, carried pending as a Practice on the ESRF Site (`ID19_microtomography_practice`, TECH-1).
- **Two endstations, two stage groups each.** MR (micro-resolution, high-throughput) and HR (high-resolution) are distinct BLISS sessions sharing the source and optics; each is modelled as its own sample and detection group under the experiment hutch (SAMPLE-1, DET-1).
- **The attenuators fold into `Filter`.** ID19's white-beam attenuator banks bind the existing `Filter` Family, the i03 precedent, not a new `Attenuator` kind (OPT-1).
- **The control floor is BLISS / Tango, with real handles.** ESRF runs BLISS over Tango; the descriptor `pv` field (the opaque control-handle slot) carries the real BLISS object names and Tango device names read from the config. See [Controls](equipment/controls.md) (CTRL-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the insertion-device source and the conditioning optics (TripleMono, slits, transfocator, attenuators) and the safety shutters (SRC-1, OPT-1, PSS-1).
- [Sample](equipment/sample.md): the MR and HR tomographic rotation stages and their sample positioning stacks (SAMPLE-1).
- [Detector](equipment/detector.md): the MR and HR Lima area detectors (Frelon / PCO / Basler) and their propagation-distance stages (DET-1).

Cutting across, and central to this deployment:

- [Controls](equipment/controls.md): the ESRF BLISS (Tango-based) control stack, CORA's first non-EPICS floor, with the real handles read from the config (CTRL-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).

The cross-cutting reference view is the [Inventory](inventory.md), authored from the same descriptor as the generated [Source](beamline.md) walk.

## Techniques

[Techniques](techniques.md): parallel-beam microtomography, radiography, and propagation phase-contrast imaging, the existing `tomography` Method bound through a pending [ESRF Practice](../esrf/index.md#the-techniques-adapted-here) (`ID19_microtomography_practice`, TECH-1). ID19 coins no new Method.

## Governance

[Governance](governance.md): who may act at ID19 and the trust shape CORA applies. People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#who-acts-here), gated by a trust shape (Zone + Conduit + Policy). Clearances are issued at the ESRF Site; the operator pool and review are carried pending (GOV-1).

## Model

[Model](model.md): the developer's by-kind index into where each ID19 aggregate's content lives, why this first non-EPICS deployment coins no new vocabulary, what the BLISS / Tango control seam is, and the record of what is deliberately deferred.

## Not yet documented

ID19 is not yet driven by CORA, so the operations runbook (procedures, recipes, cautions, enclosure permits) and the live experiment view are deliberately not written yet: a runbook for a beamline CORA does not yet drive would be invention, not record. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The further endstations (MH, MED, laminography, radiography, PCO) are noted, not modelled (ENDSTATION-1); the PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).
