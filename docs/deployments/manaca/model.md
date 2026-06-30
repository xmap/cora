# Model

*The developer's index into where MANACA content lives, its place as Sirius's first MX beamline, and the record of what is deliberately deferred. First cut.*

MANACA is a descriptor-and-docs scaffold today, reverse-engineered from Sirius's public facility pages: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/manaca/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/manaca/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; control handles unbound (`CTRL-1`) |
| Site descriptor | [`deployments/sirius/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/sirius/site.yaml) | the existing Sirius facility surface (shared with the MOGNO scaffold); MANACA adds the MX Practices |
| Extraction provenance | the [MANACA facility page](https://lnls.cnpem.br/facilities/manaca/) and the MX device anatomy shared with i03 / FMX / AMX / MX3 | the public sources the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; MANACA reuses the MX Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the MX Methods reuse the pending i03 slugs (`TECH-1`, `ROBOT-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers MANACA Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes MANACA new

MANACA is a new beamline at an existing Site, and nothing new at the vocabulary level. It is **Sirius's first macromolecular-crystallography beamline**, CORA's second modelled Sirius beamline after the [MOGNO](../mogno/index.md) tomography scaffold. Its science is macromolecular crystallography (serial and room-temperature) at 5-20 keV: rotation MX on a goniometer reading an area detector, with an automated 48-pin sample changer. The control plane is the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI; Bluesky / Ophyd (the LNLS sophys family) is named as a facility orchestration direction, the same migration question MOGNO records (`ORCH-1`).

## No new families (the MX spine reuses the i03 / FMX / AMX / MX3 precedent)

MANACA coins no new Family. The goniometer binds the graduated `Goniometer`; the monochromator binds `Monochromator` and the energy is a `PseudoAxis`; the attenuators bind `Filter`; the cryostream binds the graduated `TemperatureController`; the beamstop binds `BeamStop`; the area detector and the on-axis camera bind `Camera`, the detector stage `LinearStage`, the flux monitor the graduated `FluxMonitor`; the shutters bind `Shutter`; the machine state binds the supply-loose `StorageRing`, and the sample backlight the loose `Backlight` (held, `DET-1`). Nothing in the catalog changes. The automated 48-pin sample changer is a deferred sample-exchange Procedure, not a device family (the i03 / i24 / MX3 `ROBOT-1` precedent).

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
