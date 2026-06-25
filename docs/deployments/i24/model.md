# Model

*The developer's index into where i24 content lives, why this first serial-crystallography deployment coins no new vocabulary, and the record of what is deliberately deferred. First cut.*

i24 is a descriptor-and-docs scaffold today, reverse-engineered from Diamond's dodal controls library: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i24/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i24/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; `I24` added to its beamline list, with a serial-crystallography Practice |
| Extraction provenance | [DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal) | `src/dodal/beamlines/i24.py` and its device classes, the source the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; i24 coins no new Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the serial-crystallography Method is not yet coined (SSX-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers i24 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes i24 new

i24 is CORA's first serial / fixed-target crystallography. Unlike I03 rotation MX (one crystal, a continuous omega sweep), i24 raster-scans a fixed-target chip holding thousands of static crystals, taking one diffraction snapshot per addressable window, hardware-sequenced on the PMAC motion controller with Zebra TTL gating and no goniometer rotation. The novelty is the acquisition shape, a triggered chip-raster fly-collection over a sample grid, which is a new Capability deferred as a question (SSX-1). It forces no new device Family.

## No new families

i24 introduces no new device class. Every device reuses an existing catalog or loose Family, which is the strongest possible outcome for the families-only descriptor mode:

- The vertical pin goniometer reuses the catalog `Goniometer`, the Family I03 graduated.
- The fixed-target chip stage (dodal's PMAC, an XYZ stage) reuses `LinearStage`. The serial raster trajectory, the encoder position-compare, and the laser triggers run on the PMAC controller; they are the orchestration seam CORA's edge replaces, not a device Family.
- The Eiger and Jungfrau detectors reuse `Camera` (Detector Role); the on-axis viewer reuses `Camera`; the Zebra reuses `TimingController`; the DCM reuses `Monochromator`; the focusing mirrors reuse `Mirror`; the attenuator reuses `Filter` (the I03 / i15-1 precedent, not a new Attenuator kind); the aperture, beamstop, and detector / chip stages reuse `Aperture` / `BeamStop` / `LinearStage`; the shutters reuse `Shutter`.
- The dual backlight reuses I03's loose `Backlight`; the machine source state reuses the loose `StorageRing`. No new loose family either.

## Deliberately not here yet

- **The fixed-target chip as a Fixture / Subject grid (`CHIP-1`).** The chip is a holder of thousands of static crystals that the stage rasters one window at a time. The chip stage is a `LinearStage` Asset; the chip itself (the addressable grid, the well / aperture map) is a Fixture, and the crystals are Subjects, a CORA modelling decision. The grid map lives in beamline software, not a PV, so it is carried as the open `CHIP-1` rather than modelled now. Whether the chip windows are Subjects in a custody grid is the load-bearing question for the serial Subject thread.

- **The serial-crystallography Capability (`SSX-1`).** The chip-raster fly-collection (set a window, gate the exposure, step to the next) is a new acquisition Capability. Whether it enters CORA's catalog as a Method is an owner decision; the Practice renders unlinked, pending. i24 is the first synchrotron consumer; the SLAC LCLS-MFX XFEL deployment carries the same Method pending, so the second consumer is the graduation watch-item.

- **The PMAC laser triggers (`LASER-1`).** The PMAC fires lasers via M-variables on rising / falling encoder edges. Whether these are a pump-probe excitation source CORA should model as a device, or only a trigger setting and a Clearance hazard, is deferred.

- **The collection-Assembly question.** Whether the goniometer, chip stage, and detector compose an Assembly is deferred, as the other Diamond deployments deferred their Assemblies in descriptor mode; the first cut is flat Assets.

- **The simulated devices and full asset-tree scenarios.** No `test_i24_*.py` registers the i24 asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
