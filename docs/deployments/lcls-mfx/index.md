# LCLS-MFX

*The Macromolecular Femtosecond Crystallography (MFX) instrument at SLAC's LCLS X-ray free-electron laser. This page walks the beamline as it is being modelled; everything here is reverse-engineered from SLAC's open `pcdshub` controls stack or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `LCLS-MFX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [SLAC](../slac/index.md) (bound via `facility_code = "slac"`, `FacilityKind = Site`), CORA's fifth Site and its first XFEL |
| Status | Off-roadmap modelling exercise (not a CORA pilot) |
| Technique | serial femtosecond crystallography, fs optical pump-probe, X-ray emission spectroscopy (XES / HERFD) |
| Beam | SASE hard-X-ray free-electron laser; one shared linac and undulator line feeding many instruments; per-shot photon energy |
| Control stack | the `pcdshub` EPICS stack, a separate event-driven DAQ (`psdaq`), and the `lightpath` beam-walk engine |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    MFX is a real, operating instrument, but it is **not** on the CORA pilot roadmap (APS to MAX IV). It is modelled here, like the Diamond beamlines and FXI, to test that the dry, correct device facts in SLAC's open [`pcdshub`](https://github.com/pcdshub) stack seed CORA's intentional model, and to push the model along the one axis no storage-ring pilot reaches: the X-ray-free-electron-laser **acquisition paradigm**. Every value is reverse-engineered from `pcdshub` or inferred, carried as `confirm` until LCLS staff verify it. What CORA still needs the team to confirm is on [Open questions](questions.md).

## What MFX adds over the storage-ring exercises

Every prior modelling exercise (Diamond [I22](../i22/index.md) SAXS, [I03](../i03/index.md) MX, [I11](../i11/index.md) powder, [I15-1](../i15-1/index.md) PDF, NSLS-II [FXI](../fxi/index.md) TXM) is a storage-ring beamline: frame-on-trigger detectors and sub-Hz scalar monitoring. MFX is an XFEL. It collects a per-shot, pulse-ID-tagged event stream at beam rate (120 Hz at LCLS; LCLS-II reaches roughly 1 MHz), times acquisition on beam-synchronous event codes, runs a femtosecond optical pump-probe, and draws from one linac shared across many co-equal instruments. It is the test of whether CORA generalizes beyond the storage-ring acquisition paradigm.

The result is the inverse of I03's. I03 graduated a device Family (Goniometer). MFX graduates **none**:

- **The device families fold.** Of MFX's full device set, exactly one type has no CORA Family: the von Hamos X-ray emission spectrometer, carried as a single new loose family (`EmissionSpectrometer`, SPEC-1). Everything else reuses a catalog Family (`Mirror`, `Filter`, `Slit`, `Shutter`, `Monochromator`, `Scintillator`, `Camera`, `InsertionDevice`, `TimingController`) or an existing loose family (`FluxMonitor`, `Diagnostic`, `Transfocator`, `Laser`). The offset mirrors fold into `Mirror`, the solid-Si attenuators into `Filter`, the pulse picker into `Shutter`, the intensity-position monitors into `FluxMonitor` + `Diagnostic`, all adversarially reviewed.
- **The genuine gaps are architectural, not taxonomic.** What MFX exposes is not missing device kinds but a missing acquisition ontology. These are recorded as deliberate deferrals on [Model](model.md), each pointing at the existing seam it would extend: per-shot pulse-ID event DAQ (DAQ-1), beam-synchronous event-code timing (TIMING-1), femtosecond pump-probe synchronization (LASER-1), one switched FEL source feeding co-equal instruments (TOPO-1), the attenuator transmission solver (ATT-1), and the computed device-state-to-path-transmission lightpath (LIGHTPATH-1).
- **The deepest gap gets a design sketch.** The per-shot event DAQ (DAQ-1) is the load-bearing mismatch: CORA's acquisition is a single-detector poll loop plus a sub-Hz scalar observation logbook with no pulse-ID key. The shape a fix would take is sketched as a forward-looking design note, gated on a real trigger, not built here.

What MFX keeps the same as the other exercises: the descriptor carries the real `pcdshub` PV prefixes (as I22 and I03 did), and the model reuses existing Families wherever one fits.

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the FEL source and its pulse-energy monitor, then the shared front end and X-ray transport (solid attenuators, offset and transport mirrors, the PPS stopper, and transport-line slits and diagnostics), rendered as the generated source-stage device walk.
- [Optics and endstation](equipment/optics.md): the MFX-hutch conditioning (pulse picker, attenuator, channel-cut mono, focusing lenses, slits, and per-shot diagnostics), the pump-probe laser, the liquid-jet sample delivery, and the von Hamos emission spectrometer.
- [Detector](equipment/detector.md): the per-shot area detector and the DAQ data plane it feeds.

Cutting across all three:

- [Controls](equipment/controls.md): the `pcdshub` EPICS stack, the EventSequencer beam-synchronous timing, and the event-driven DAQ that CORA references but does not own.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the `pcdshub`-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lcls-mfx/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what MFX is designed to do, as design intent. Serial femtosecond crystallography, pump-probe, and emission spectroscopy are new Methods over the spine; none of the catalog's tomography Methods fit an XFEL, so all are carried pending (the [SLAC Practices](../slac/index.md)).

## Governance

[Governance](governance.md): who would act at MFX and the trust shape that gates their commands, including the Clearance that would gate the class-4 pump-probe laser. People and agents are facility principals at the [SLAC Site](../slac/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's MFX content lives, and the architectural gap register, the real product of this exercise.

## Not yet documented

MFX is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The 2-BM deployment shows the shape they would take.
