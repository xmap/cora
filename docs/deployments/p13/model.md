# Model

*The developer's index into where P13 content lives, its place as CORA's first EMBL Hamburg beamline, and the record of what is deliberately deferred. First cut.*

P13 is a descriptor-and-docs scaffold today, reverse-engineered from EMBL Hamburg's public MXCuBE HardwareObjects configuration: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p13/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p13/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Exporter / TINE handles read from the MXCuBE config (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P13 adds the EMBL Hamburg sub-operator house-style section and the MX Practice (`SEAM-1`) |
| Upstream source | [EMBL P13 MXCuBE config](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p13) | the beamline's own public MXCuBE HardwareObjects device topology the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P13 reuses the MX Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; MX reuses the pending i03 `mx_data_collection` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P13 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P13 new

P13 is CORA's first EMBL Hamburg beamline, and the first **sub-operator** at an existing Site: it sits on the PETRA III ring but is operated by EMBL Hamburg, not DESY, with its own control domain. Its science is rotation MX (a crystal on the EMBLMiniDiff, cryo-cooled, read by an Eiger or Pilatus). At the vocabulary level it is a reuse-and-reinforce deployment; the new thing it exercises is the **sub-operator seam**, not a new device or technique.

## The sub-operator seam (the new modelling exercise)

The PETRA III Site already carries the DESY house style (Tango / Sardana / OnlineXML). P13 adds a distinct control-domain *within* the same Site and Facility: EMBL Hamburg runs MXCuBE over the Exporter protocol (the microdiff host) and TINE channels. This is recorded as an EMBL-Hamburg house-style section on the [PETRA III Site](../petra-iii/index.md) descriptor, so the Site now documents two operators with two control floors on one ring (`SEAM-1`). It is the first time CORA models operator and control-floor heterogeneity below the Site boundary; the [seam model](../../architecture/index.md) treats the floor (EPICS / Tango / MXCuBE+Exporter+TINE) as the wall CORA's edge conducts over, never owns.

## No new families (the MX spine reuses the i03 precedent)

P13 coins no new Family. The EMBLMiniDiff binds the graduated `Goniometer`; the area detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the aperture / beamstop / objective bind `Aperture` / `BeamStop` / `Objective`; the sample illumination binds the catalog `Backlight` (graduated across the MX / imaging fleet); the optics motions bind `LinearStage`, the energy and detector distance `PseudoAxis`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as MANACA, TPS 07A, and P11 do).

## The gain over P11: a config that names the instrument

Unlike P11's OnlineXML (area-grouped motor banks, no named goniometer), EMBL's MXCuBE config names the EMBLMiniDiff and its omega / kappa / sample-centring axes, the aperture, the beamstop, the detectors by model. So P13's experiment hutch resolves into a real `Goniometer` instrument rather than grouped stages. This is the same "model what the source supports" posture P11 takes, but the richer source supports more: the limitation moves from "what is the instrument" to "what are its exact geometry and ranges" (`MX-1`).

## The control plane

P13 sits on EMBL Hamburg's MXCuBE + Exporter + TINE domain, distinct from the DESY Tango / Sardana floor, with the diffractometer motions Exporter-hosted (`p13md201.embl-hamburg.de:9001`) and the detector / energy / beam services on TINE (`/P13/...`). The handles are read from EMBL's public MXCuBE config and carried confirm (`CTRL-1`). The rotation-MX acquisition (the goniometer oscillation coupled to the Eiger) runs as an MXCuBE data-collection routine; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A.

## Deliberately not here yet

- **The source (`SRC-1`).** The MXCuBE config exposes the energy service, not the undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`, `ENERGY-1`).** The monochromator and KB mirror Assets are not individually labelled; the motions are grouped, the energy carried as a pseudo-axis.
- **The goniometer geometry (`MX-1`).** The EMBLMiniDiff is named and bound to `Goniometer`, but its kappa range and axis offsets are not in the config.
- **The cryostream (`CRYO-1`).** Not a labelled device in the config; carried as a question, with the liquid nitrogen a Supply.
- **The sample changer (`ROBOT-1`).** MXCuBE bookkeeping, not a device; a deferred sample-exchange Procedure.
- **The detector model detail (`DET-1`).** The Eiger 16M and Pilatus 6M are named; the ROI modes and geometry are pending.
- **The on-axis camera handle (`OAV-1`).** The viewing cameras carry no control handle in the config object.
- **The handle freshness (`CTRL-1`).** The config is the upstream `develop` branch; some handles may lag the live beamline.
- **The operator / safety boundary (`GOV-1`).** The EMBL-operated beamline on the DESY-hosted ring splits operator from interlock host; the boundary is pending.
- **The MX Method (`TECH-1`).** Whether MX enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the existing slug.
- **The PSS permit signals (`PSS-1`).** Not in the config; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p13_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
