# Model

*The developer's index into where ISR content lives, why this deployment is deliberately partial, why it coins no new family, and the record of what is deferred. First cut.*

ISR is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection, and a deliberately **partial** one: the public source is an early / commissioning, optics-first profile collection. It exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/isr/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/isr/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `ISR` added to its beamline list, with the resonant / diffraction Practices |
| Extraction provenance | [NSLS2/isr-profile-collection](https://github.com/NSLS2/isr-profile-collection) | the `startup/` device definitions the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; resonant_scattering (4-ID / CSX) and diffraction (4-ID / 8-ID) are reused pending (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers ISR Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Why ISR is partial

ISR's name, In Situ and Resonant, promises a multi-circle diffractometer, a tunable resonant energy axis, in-situ sample environments, and often polarization analysis. The public profile collection does not yet contain them. It is an optics-and-detectors-first scaffold: the front-end slit, the undulator gap (read-only), the DCM, the focusing and harmonic-rejection mirrors, the attenuator bank, the Eiger 1M, the diagnostic screen cameras, and only two bound sample axes (`th`, `zeta`). The flux-monitor electrometers are commented out, the energy axis is a non-functional stub, and the databroker catalog has a placeholder name, all commissioning signals.

CORA models what is PV-bound and routes the four mission-critical gaps to open questions rather than inventing them. This is the same discipline the [i20-1](../i20-1/model.md) (EDE) partial uses: where the source is thin, model the real handles and name the absences, never fabricate the headline device.

## No new families

ISR coins no new Family and changes nothing in the catalog.

- **4-ID is an undulator beamline** (read-only gap in source); machine state is observed through the loose `StorageRing`, and the undulator detail is `SRC-1`.
- **The optics reuse the catalog:** the DCM binds `Monochromator`; the bendable focusing pair and the harmonic-rejection mirror bind `Mirror`; the front-end slit binds `Slit`; the attenuator bank binds `Filter`.
- **The one bound sample rotation binds `RotaryStage`, not `Goniometer`.** With only `th` + `zeta` bound and no detector arm or reciprocal-space engine, there is no basis for a multi-circle `Goniometer`; it is one `RotaryStage` Asset with the full diffractometer deferred (`DIFF-1`).
- **The Eiger 1M and the screen cameras bind `Camera`; the motorized BPM stage binds the loose `BeamPositionMonitor`** (held under review, `DIAG-1`). The flux-monitor electrometers are commented out, so no `FluxMonitor` Asset is modelled (`DET-1`).

## No new Methods

ISR's science reuses two pending Methods rather than coining: `resonant_scattering` (APS 4-ID POLAR, CSX) and `diffraction` (4-ID, 8-ID). Both are doubly deferred here because the diffractometer they run on is absent from source (`TECH-1`, `DIFF-1`). When ISR's diffractometer lands and the techniques are driven, ISR becomes a further consumer of each, strengthening the case for cataloging them, an owner decision, not an automatic one.

## Deliberately not here yet

- **The multi-circle diffractometer (`DIFF-1`).** Only `th` + `zeta` are bound under the `Dif:ISD` IOC; the orientation circles, the detector two-theta arm, and the reciprocal-space / hkl engine are absent from source and not invented. When they land, the sample side would be a `Goniometer` plus reciprocal-space `PseudoAxis` (the IXS six-circle / CSX TARDIS precedent), with a detector-arm `RotaryStage` / `LinearStage`.
- **The in-situ sample environment (`INSITU-1`).** No temperature / electrochemistry / gas / cryostat device is PV-bound. When it lands it reuses `TemperatureController` / the loose `FlowController` and the Subject / Supply / Procedure seam, not a new family.
- **The resonant energy axis and polarization analysis (`RESONANT-1`).** The energy axis is a non-functional stub; no polarization analyzer or phase retarder is bound. When wired, the energy axis is a `PseudoAxis` over the DCM and polarization hardware reuses the loose `PolarizationAnalyzer` / `PhaseRetarder` (4-ID).
- **The flux monitors (`DET-1`).** The QuadEM electrometers and the secondary-source slit are defined but commented out in source; not modelled until live.
- **The Methods.** Whether `resonant_scattering` and `diffraction` enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_isr_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive, and whose primary instrument is not even in source, would be invention; they land when the diffractometer is bound and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
