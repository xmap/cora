# Alvra

*The Alvra hard X-ray pump-probe station on SwissFEL's Aramis branch at PSI: a femtosecond optical-pump / X-ray-probe instrument for time-resolved spectroscopy (XAS / XES) and serial crystallography. This page walks the beamline as it is being modelled; everything here is reverse-engineered from PSI's open `eco` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `Alvra` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PSI](../psi/index.md) (bound via `facility_code = "psi"`, `FacilityKind = Site`), CORA's eighth Site and its second XFEL |
| Source | shared SwissFEL Aramis undulator line; per-shot photon energy, fed one station at a time (SRC-1, TOPO-1) |
| Status | Off-roadmap modelling exercise (not a CORA pilot) |
| Technique | femtosecond optical pump-probe, time-resolved XAS / XES (HERFD), serial femtosecond crystallography |
| Beam | SASE hard-X-ray free-electron laser; one shared linac and Aramis undulator line feeding co-equal stations; per-shot photon energy |
| Control stack | the `eco` EPICS device library, the SwissFEL event-driven DAQ (`sf-daq` / `bsread`), and the event-system timing |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    Alvra is a real, operating station, but it is **not** on the CORA pilot roadmap (APS to MAX IV). It is modelled here, like the Diamond beamlines, FXI, and LCLS-MFX, to test that the dry, correct device facts in PSI's open [`eco`](https://github.com/paulscherrerinstitute/eco) controls library seed CORA's intentional model. Its specific job is to be CORA's **second XFEL**: a check that the model generalizes beyond the storage-ring acquisition paradigm not just once (LCLS-MFX) but across two independently-built free-electron lasers. Every value is reverse-engineered from `eco` or inferred, carried as `confirm` until PSI staff verify it. The `eco` manifest carries no units, no motor limits, and no Aramis source parameters, so those are deferred, not invented. What CORA still needs the team to confirm is on [Open questions](questions.md).

## What Alvra adds: a second XFEL, from an independent control stack

[LCLS-MFX](../lcls-mfx/index.md) was CORA's first XFEL and made the headline finding: at an X-ray free-electron laser the **device families fold**, and the genuine gaps are **architectural** (the acquisition ontology), not taxonomic. Alvra's value is **reinforcement from an independent source**. LCLS-MFX was mined from SLAC's [`pcdshub`](https://github.com/pcdshub) stack; Alvra is mined from PSI's [`eco`](https://github.com/paulscherrerinstitute/eco) stack. The two facilities were built by different teams with different house styles, including a completely different PV-naming convention (`SARFE10-` front end, `SAROP11-` Aramis optics, `SARES11-` Alvra endstation). If the same finding recurs at the second XFEL, that is evidence the model generalizes beyond one facility's conventions, not just beyond storage rings.

It does recur. Alvra graduates **no** new device Family:

- **The device families fold, again.** Every device in the `eco` Alvra manifest reuses a catalog Family or an existing loose family. The offset and KB mirrors fold into `Mirror`, the solid attenuators into `Filter`, the four-blade and pos/width slits into `Slit`, the X-ray pulse picker into `Shutter`, the profile monitors into `Scintillator` + `Camera`, the PBPS / PBIG intensity-position monitors into `FluxMonitor` + `Diagnostic`, the double-crystal mono into `Monochromator`, the Huber sample stage into `LinearStage`, the optical table into `Table`, the sample microscope and the Jungfrau detector into `Camera`, and the pump-probe and reference lasers into the loose `Laser` family. The one post-sample analyzer instrument, the **von Hamos emission spectrometer**, reuses the `EmissionSpectrometer` Family that LCLS-MFX introduced and NSLS-II ISS graduated: Alvra is its **fourth sighting** (SPEC-1).
- **The gaps are the same architectural ones.** What does not fold is, again, how the detector is read and how the experiment is timed. These are recorded as deliberate deferrals on [Model](model.md), each naming the LCLS-MFX gap it re-confirms: per-shot pulse-ID event DAQ (DAQ-1), beam-synchronous event-system timing (TIMING-1), femtosecond pump-probe synchronization (LASER-1), one switched Aramis source feeding co-equal stations (TOPO-1), and the attenuator transmission solver (ATT-1).

What Alvra keeps the same as the other exercises: the descriptor carries the real `eco` PV prefixes, and the model reuses existing Families wherever one fits.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the Aramis FEL source and its front-end intensity monitors, then the front-end shutters, slit, and attenuator, and the Aramis optics hutch (offset mirrors, double-crystal mono, pulse picker, attenuator, KB focusing mirrors, and the PALM / PSEN timing diagnostics), rendered as the generated source-stage device walk.
- [Endstation](equipment/endstation.md): the Alvra Prime endstation, the Huber sample manipulator, the optical table, the sample-view microscope, the pump-probe laser, and the von Hamos emission spectrometer.
- [Detector](equipment/detector.md): the per-shot Jungfrau area detector and the DAQ data plane it feeds.

Cutting across all of them:

- [Controls](equipment/controls.md): the `eco` EPICS device library, the SwissFEL event-system timing, and the event-driven DAQ that CORA references but does not own.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the `eco`-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/alvra/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what Alvra is designed to do, as design intent. Femtosecond pump-probe, time-resolved XAS / XES, and serial crystallography are new Methods over the spine; none of the catalog's tomography Methods fit an XFEL, so all are carried pending (the [PSI Practices](../psi/index.md)), reusing the pending Methods LCLS-MFX introduced.

## Governance

[Governance](governance.md): who would act at Alvra and the trust shape that gates their commands, including the Clearance that would gate the class-4 pump-probe laser. People and agents are facility principals at the [PSI Site](../psi/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's Alvra content lives, and the architectural gap register this second-XFEL exercise re-confirms.

## Not yet documented

Alvra is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The [2-BM deployment](../2-bm/index.md) shows the shape they would take.
