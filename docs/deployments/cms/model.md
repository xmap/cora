# Model

*The developer's index into where CMS content lives, why this deployment coins no new family, how it models specular reflectivity without a device, and the record of what is deliberately deferred. First cut.*

CMS is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/cms/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cms/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `CMS` added to its beamline list, with SAXS / WAXS / GISAXS / reflectivity Practices |
| Extraction provenance | [NSLS2/cms-profile-collection](https://github.com/NSLS2/cms-profile-collection) | the `startup/*.py` device definitions the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the scattering and reflectivity Methods are pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers CMS Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes CMS new

The honest answer is: not much on the scattering, and one real thing on reflectivity. CMS measures soft-matter and thin-film structure by small- and wide-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). The scattering overlaps the fleet heavily: CMS is the direct NSLS-II twin of SMI (12-ID), and shares its science axis with Diamond I22 and APS 9-ID / 12-ID-E. That scattering reuses the existing `Camera` / `Goniometer` / `Slit` / `BeamStop` / `FluxMonitor` / `Monochromator` / `Mirror` vocabulary and contributes reinforcement, not novelty.

CMS's two genuinely distinct contributions are:

- **Specular X-ray reflectivity (XR), the fleet's first hard X-ray reflectometry.** It measures the specularly reflected intensity as a function of incidence angle to recover a film's depth profile. What is interesting for CORA is the mechanism: there is no physical two-theta detector arm. The area detector stays fixed, and the "two-theta" is synthetic, a software region-of-interest that slides across the fixed Pilatus face to where the reflected beam lands as the sample theta (sth) is stepped. So XR is purely a Method, realized over existing devices.
- **CMS as a further NSLS-II beamline, re-testing the Site and Federation kernel.** Its double-multilayer monochromator reuses the same `Monochromator` Family as the APS 2-BM DMM, reinforcing that reuse.

## No new families

CMS coins no new Family and changes nothing in the catalog.

- **11-BM is a bending-magnet source, not an insertion device** (the 2-BM / 7-BM pattern), so there is no `InsertionDevice` Asset; the machine state is observed through the loose `StorageRing`, and the source detail is `SRC-1`.
- **The DMM binds `Monochromator`** (a multilayer Bragg optic, the 2-BM double-multilayer precedent, not the soft X-ray `GratingMonochromator`); the incident energy is a `PseudoAxis` over its Bragg angle.
- **The scattering devices all reuse:** the focusing mirrors bind `Mirror`; the slits bind `Slit`; the attenuator foils bind `Filter`; the sample-orientation circles bind `Goniometer` (sth is the grazing / specular incidence axis); the surface-leveling stage binds `TiltStage`; the SAXS / WAXS / MAXS Pilatus detectors bind `Camera`; the detector translations and the telescoping flight path bind `LinearStage`; the beamstop binds `BeamStop`; the ion chamber, electrometers, and scintillation counter bind `FluxMonitor`; the diamond-diode beam-position monitor binds the loose `BeamPositionMonitor` (already held under review, `DIAG-1`); the Linkam stage binds `TemperatureController`; the support table binds `Table`.

## How reflectivity is modelled (no device)

Specular reflectivity (XR) is modelled as a Method (a Practice) over existing devices, not as a new device or a new detector arm:

- the incidence angle is the `Goniometer` sample theta (sth);
- the reflected-beam intensity is read on the `Camera` (the Pilatus 2M, the same detector as SAXS) over a tracked region-of-interest;
- the incident flux for normalization is the `FluxMonitor` ion chamber.

The "two-theta" is synthetic: the detector does not move, and the region-of-interest is slid across the fixed detector face to follow where the reflected beam lands as sth is stepped. So XR coins no device, no `Diffractometer` detector arm, and no point detector. The reflectivity Method is **shared with i10** (its soft X-ray RASOR sibling); CMS is the second consumer (`XR-1`). i10 (point-detector, soft X-ray) and CMS (area-detector region-of-interest, hard X-ray) are the rule-of-three pressure that could eventually graduate one reflectivity Method into the catalog; the soft-versus-hard and point-versus-area distinctions are Practice-level adaptations, not a Method split.

## Deliberately not here yet

- **The GIBar sample-exchange arm (`ROBOT-1`).** The multi-axis sample-bar loader is genuinely new automation that no catalog Family covers. Per earn-the-abstraction it is modelled by its stage axes (`LinearStage` / `RotaryStage`) at n=1, and no `SampleExchanger` Family is coined; a second fleet sample robot would earn the abstraction. The garage-indexed pick / place semantics are carried as a note, not modelled.
- **The auxiliary analog I/O and viewing cameras.** The generic analog diode box is carried as flux / diagnostic channels per its wiring, not a Family; the Prosilica sample-viewing cameras are not modelled in this cut.
- **The scattering and reflectivity Methods.** Whether SAXS, WAXS, GISAXS, and XR enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. The scattering Methods are shared with i22 / SMI / 9-ID and the reflectivity Method with i10 (`TECH-1`, `XR-1`).
- **The chamber rebinding and the sth / schi swap.** The beamline_stage configurations rebind the logical goniometer axes across physical PVs at startup, and staff have at times swapped sth and schi; CORA models the logical `Goniometer` and carries the active binding as a setting (`SAMPLE-1`), not as separate Assets.
- **The simulated devices and full asset-tree scenarios.** No `test_cms_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
