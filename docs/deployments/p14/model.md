# Model

*The developer's by-kind index: where each CORA aggregate's P14 content lives, the multi-endstation topology it exercises, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P14 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P14 new

P14 is CORA's second EMBL Hamburg beamline (the sibling of P13) and the **first two-endstation MX beamline** CORA models: one source / optics chain feeding two experiment hutches, EH1 (the EMBLMiniDiff + Eiger detectors) and EH2 (the EMBLBSD + Pilatus 2M). At the vocabulary level it is a reuse-and-reinforce deployment; the new thing it exercises is the **multi-endstation topology under one beamline**, plus the high-energy CdTe detector variants and the X-ray imaging camera.

## Two endstations, one source (the new modelling exercise)

P13 established the EMBL sub-operator control-domain; P14 reuses it and adds the multi-hutch shape. The optics chain (KB mirrors, CRL transfocator, beam-defining slits, shared photon energy) feeds two experiment hutches, each with its own diffractometer host. CORA models this as three enclosures (`p14-oh`, `p14-eh1`, `p14-eh2`) under one root Asset, with the energy and CRL services shared and each hutch carrying its own goniometer, detector, and sample optics (`EH-1`). The trust shape would scope per hutch while sharing the source, a governance nuance carried with the enclosure question.

## No new families (the MX spine reuses the i03 precedent)

P14 coins no new Family. Both diffractometers bind the graduated `Goniometer`; the area detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the CRL binds `Transfocator`; the slits bind `Slit`; the focusing optic binds `Mirror`; the sample illumination binds the catalog `Backlight` (graduated across the MX / imaging fleet); the optics motions bind `LinearStage`, the energy and detector distance `PseudoAxis`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as P13 and the wider MX fleet do).

## The honest limitation: published mockups

The EH2 config (`embl_hh_pe2`) publishes some axes as `MotorMockup`, a simulation placeholder rather than a live device handle. Rather than present these as real, the EH2 diffractometer and table are carried with a caution marker (`MOCK-1`): the instrument is named and bound, but whether each axis is live on the floor or a config stub is a confirm. This is the same "model what the source supports, flag the rest" posture P11 and P13 take, applied to a source that mixes live and simulated entries.

## The control plane

P14 sits on EMBL Hamburg's MXCuBE + Exporter + TINE domain, distinct from the DESY Tango / Sardana floor, with the diffractometer motions Exporter-hosted (`p14md301` / `p14md302` for EH1, `pe2bsd01` for EH2) and the detector / energy / beam services on TINE (`/P14/...`, `/PE2/...`). The handles are read from EMBL's public MXCuBE configs and carried confirm (`CTRL-1`). The rotation-MX acquisition runs as an MXCuBE data-collection routine; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A and its sibling P13.

## Deliberately not here yet

- **The source (`SRC-1`).** The MXCuBE config exposes the energy service, not the undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`, `ENERGY-1`).** The monochromator and KB mirror Assets are not individually labelled; the motions are grouped, the energy carried as a pseudo-axis, the CRL and slits bound but uncharacterized.
- **The goniometer geometries (`MX-1`).** Both diffractometers are named and bound to `Goniometer`, but their kappa ranges and axis offsets are not in the configs.
- **The EH2 mockups (`MOCK-1`).** Some EH2 axes are `MotorMockup`; whether each is live or simulated is a confirm.
- **The EH2 table handle (`TABLE-1`).** The EH2 positioning table carries no control handle in the config object.
- **The cryostream (`CRYO-1`).** Not a labelled device in the configs; carried as a question, with the liquid nitrogen a Supply.
- **The sample changer (`ROBOT-1`).** MXCuBE bookkeeping, not a device; a deferred sample-exchange Procedure.
- **The detector model detail (`DET-1`).** The Eiger variants and Pilatus 2M are named; the ROI modes and geometry are pending.
- **The imaging / on-axis camera handles (`OAV-1`, `IMG-1`).** The viewing and X-ray imaging cameras carry no control handle in the config objects.
- **The handle freshness (`CTRL-1`).** The configs are the upstream `develop` branch; some handles may lag the live beamline.
- **The operator / safety boundary (`GOV-1`).** The EMBL-operated beamline on the DESY-hosted ring splits operator from interlock host; the boundary is pending.
- **The MX Method (`TECH-1`).** Whether MX enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the existing slug.
- **The PSS permit signals (`PSS-1`).** Not in the configs; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p14_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
