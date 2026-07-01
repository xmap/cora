# Model

*The developer's index into where ID28 content lives, why it coins no new family, the further SpectrometerArm consumer it adds (the sighting that helped earn the graduation), and the record of what is deliberately deferred. First cut.*

ID28 is a descriptor-and-docs scaffold today, reverse-engineered from the ESRF's BLISS Beacon device database: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/id28/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id28/beamline.yaml) | the device walk with bound handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/esrf/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/esrf/site.yaml) | the ESRF facility surface; `ID28` added to its beamline list, with an IXS Practice |
| Extraction provenance | [gitlab.esrf.fr/id28/beamline_configuration](https://gitlab.esrf.fr/id28/beamline_configuration) | the public BLISS Beacon device database the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | ID28 coins none; it is a further `SpectrometerArm` consumer, a sighting that reinforced the now-landed graduation (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the IXS Method is pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers ID28 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes ID28 new

ID28 is CORA's second ESRF beamline (after ID32), and it deepens the fleet's inelastic-scattering coverage with a distinct flavor: **momentum-resolved hard X-ray inelastic scattering (IXS)**. A high-resolution backscattering monochromator sets a meV-resolution incident energy, the sample scatters, and a multi-analyzer crystal spectrometer on a two-theta arm energy-analyzes the scattered beam in backscattering, mapping phonon and collective-excitation dispersions across momentum transfer. The fleet already has soft RIXS (SIX, ID32) and the NSLS-II IXS beamline; ID28 is the ESRF hard X-ray IXS instrument, reusing the pending `inelastic_x_ray_scattering` Method as the second consumer (`TECH-1`).

The second value is the Site re-test: ID28 exercises the ESRF Site and the BLISS / Tango / IcePAP control plane a second time, confirming the ID32 house-style modelling generalizes within the facility.

A modelling note worth surfacing: ID28's incident energy is **not** scanned by a Bragg angle. The high-resolution backscattering monochromator selects energy by the silicon crystal's lattice spacing, which is tuned by **temperature** (the ASL F700 controller carries a paired `monot` setpoint / `deltae` energy axis). CORA still models the incident energy as a `PseudoAxis`, but it is realized over the F700 temperature controller rather than a goniometer, so the `Monochromator` Asset and the `BeamEnergy` `PseudoAxis` are decoupled in a way an angle-scanned beamline's are not. This is the kind of mechanism the descriptor records (read from the config) so the model is intentional, not a mirror of an angular-mono assumption.

## A further SpectrometerArm consumer, held

ID28's IXS spectrometer is a `TwoThetaMultilayer` two-theta arm carrying an array of inclined analyzer crystals (`a2_inca` / `a3_inca` / `a4_inca`, each with chi / th), which binds the `SpectrometerArm` Family. This is a **further consumer** of the family that SIX coined and ID32 brought to a rule-of-three (SIX RIXS arm + ID32 RIXS arm + ID32 XES arm). ID28 is a further sighting that reinforced it, and the family has since **graduated** into the catalog (`RIXS-1`); ID28's arm binds it like any catalog Family, so this scaffold makes no catalog change of its own.

`SpectrometerArm` is the right home: it is an arm that **positions** an energy-dispersing element (here a crystal array, at SIX / ID32 a grating) and **carries** a detector, presenting the `Positioner` Role, which is why it never fit the point-Sensor families.

## No new families

Beyond the graduated `SpectrometerArm`, ID28 reuses the catalog throughout: the backscattering monochromator binds `Monochromator` (the meV backscattering reflection is a per-Asset setting); the HFM / VFM benders bind `Mirror`; the beam-defining slits bind `Slit`; the two in-vacuum undulators bind `InsertionDevice`; the incident energy is a `PseudoAxis` realized over the ASL F700 backscattering-crystal temperature controller (`monot` / `deltae`), not over a Bragg angle; the Basler / PCO detectors bind `Camera`; the sample-temperature environments (the 10 K displex LakeShore 340, the Oxford 700, the nanodac gas blower) bind `TemperatureController`; the oh2 Elettra beam-position monitor binds the graduated catalog `PositionMonitor` (presenting the `Sensor` Role, distinct from `FluxMonitor` by measuring beam position rather than flux); the front-end shutter binds `Shutter`; and the machine state binds the loose `StorageRing` via the BLISS MachInfo.

## Deliberately not here yet

- **The analyzer-crystal array identity (`IXS-1`).** The multi-analyzer arm carries an array of inclined analyzer crystals, each with its own chi / th and cylinder slit. The config provisions nine analyzer-slit positions (`a1h..a9h` / `a1v..a9v`) and `inca` controllers for `a2` / `a3` / `a4`; how many crystals are populated is `IXS-1`. The first cut carries the array as a per-Asset setting on the one `SpectrometerArm` Asset; promoting each crystal to a child Asset via `parent_id` is the nested-component-identity convention, itself at a rule-of-three gate (the IXS 10-ID diced-crystal `XTAL-1` question is the sibling), so ID28 flags it rather than asserting it.
- **The SpectrometerArm graduation (`RIXS-1`).** Landed; the family graduated into the catalog (SIX + ID32 RIXS/XES + ID28), so ID28's arm binds it directly. Only the per-Asset arm geometry stays pending.
- **The exact sample-stage and per-analyzer-detector handles (`SAMPLE-1`, `DET-1`).** Carried confirm-pending; the spectrometer arm, mono, mirrors, and sample cryostats carry their real BLISS handles.
- **The IXS Method.** Whether momentum-resolved IXS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the NSLS-II IXS slug (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_id28_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
