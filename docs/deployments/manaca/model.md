# Model

*The developer's by-kind index: where each CORA aggregate's MANACA content lives, its place as Sirius's first MX beamline, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MANACA |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes MANACA new

MANACA is a new beamline at an existing Site, and nothing new at the vocabulary level. It is **Sirius's first macromolecular-crystallography beamline**, CORA's second modelled Sirius beamline after the [MOGNO](../mogno/index.md) tomography scaffold. Its science is macromolecular crystallography (serial and room-temperature) at 5-20 keV: rotation MX on a goniometer reading an area detector, with an automated 48-pin sample changer. The control plane is the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI; Bluesky / Ophyd (the LNLS sophys family) is named as a facility orchestration direction, the same migration question MOGNO records (`ORCH-1`).

## No new families (the MX spine reuses the i03 / FMX / AMX / MX3 precedent)

MANACA coins no new Family. The goniometer binds the graduated `Goniometer`; the monochromator binds `Monochromator` and the energy is a `PseudoAxis`; the attenuators bind `Filter`; the cryostream binds the graduated `TemperatureController`; the beamstop binds `BeamStop`; the area detector and the on-axis camera bind `Camera`, the detector stage `LinearStage`, the flux monitor the graduated `FluxMonitor`; the shutters bind `Shutter`; the machine state binds the supply-loose `StorageRing`, and the sample backlight the catalog `Backlight` (graduated across the MX / imaging fleet, `DET-1`). Nothing in the catalog changes. The automated 48-pin sample changer is a deferred sample-exchange Procedure, not a device family (the i03 / i24 / MX3 `ROBOT-1` precedent).

## The control plane

MANACA sits on the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI driving the goniometer, the detector, and the sample changer. Sirius has named Bluesky / Ophyd (the LNLS sophys family: a RunEngine fronted by bluesky-queueserver and bluesky-httpserver) as a facility orchestration direction, and the MOGNO scaffold records the same migration question (`ORCH-1`); whether MANACA runs it today is not public. LNLS publishes its control software openly but no per-beamline PV manifest, so CORA does not bind the EPICS / MXCuBE handles here; when bound they would be modelled as opaque edge strings over the `ControlPort` (`CTRL-1`). The rotation-MX acquisition runs through MXCuBE and the beamline orchestration layer; that orchestration is the seam CORA's edge replaces or drives through, conducting over the EPICS floor rather than owning it. The detector file-writing to the Sirius data store is plumbing CORA observes, not data it owns.

## Deliberately not here yet

- **The control handles (`CTRL-1`).** No public per-beamline EPICS / MXCuBE manifest exists; the handles are carried pending, not invented.
- **The detector model (`DET-1`).** The area detector is bound to `Camera` but its model (a Pilatus / Eiger-class photon-counting detector) is unpublished, carried pending.
- **The sample-exchange Procedure (`ROBOT-1`).** The automated 48-pin changer is named as a deferred Procedure, not built, following the established MX robot precedent.
- **The exact optics and goniometer detail (`MONO-1`, `ENERGY-1`, `FILT-1`, `OPT-1`, `GONIO-1`).** The monochromator crystal, the energy axis, the attenuators, the mirrors / slits, and the goniometer axes are carried confirm-pending.
- **The MX Methods (`TECH-1`, `ROBOT-1`).** Whether rotation MX, grid scan, and sample exchange enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the i03 slugs.
- **The simulated devices and full asset-tree scenarios.** No `test_manaca_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
