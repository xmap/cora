# Model

*The developer's index into where SST content lives, the `ElectronAnalyzer` graduation this deployment earns, and the record of what is deliberately deferred. First cut.*

SST is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's config-driven profile collections: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/sst/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/sst/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `SST` added with RSoXS + HAXPES Practices |
| Extraction provenance | [NSLS2/sst-rsoxs-profile-collection](https://github.com/NSLS2/sst-rsoxs-profile-collection) + [sst-haxpes](https://github.com/NSLS2/sst-haxpes-profile-collection) + [sst-base](https://github.com/NSLS-II-SST/sst-base) | the config-driven (devices.toml + library) source the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | `ElectronAnalyzer` graduates with this deployment (below); no other change |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; RSoXS reuses `resonant_scattering`, HAXPES is a new pending photoemission Method (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers SST Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What this deployment graduates

SST is a consolidation deployment for the soft / tender X-ray regime. It graduates one family and reuses three:

- **`ElectronAnalyzer` graduates.** ESM (NSLS-II 21-ID) introduced it as a loose family at n=1 (the ARPES Scienta SES). SST's HAXPES endstation carries the **second** Scienta SES hemispherical electron energy analyzer, which earns the rule-of-three, so `ElectronAnalyzer` becomes a catalog Family that both ESM and SST bind (analyzer model, lens-mode set, and pass-energy range are per-Asset settings, not a Family split). ESM's references are swept loose to graduated in the same change. It presents the Detector Role, distinct from the photon detectors. Its naming-r3 review is done.
- **`GratingMonochromator` reused (4th).** The soft PGM is the fourth soft X-ray plane-grating mono after SIX, CSX, ESM.
- **`Monochromator` reused.** The tender Si double-crystal mono binds the catalog crystal-DCM Family.
- **`Manipulator` reused (3rd / 4th).** The RSoXS and HAXPES UHV sample manipulators bind the catalog Family graduated by SIX + ESM.

No new family of SST's own is introduced.

## Deliberately not here yet

- **The UCAL / NEXAFS TES microcalorimeter endstation.** SST-1 also carries a transition-edge-sensor microcalorimeter array with an ADR cryostat: a cryogenic energy-dispersive detector regime CORA has not modelled. It is deferred (a future loose family at first sighting), not extracted in this cut.

- **The VPPEM photoemission electron microscope.** The SST-2 variable-polarization photoemission microscope is an electron-imaging instrument, the same shape as ESM's deferred XPEEM/LEEM branch; deferred to the future `ElectronMicroscope` family (`PEEM-1`).

- **The full multi-channel I400 ion chamber.** Only the single instantiated `:IC1_MON` channel is modelled as a flux monitor; the multi-channel I400 device is not instantiated in the profile, so the channel set is carried `confirm` rather than invented (`DET-1`).

- **The config-driven extraction caveats.** The soft PGM's instance prefix is empty in the devices.toml (a factory call); its real base `XF:07ID1-OP{Mono:PGM1` and the tender DCM's `XF:07ID6-OP{Mono:DCM1` are hardcoded in the `sst-base` library, verified there. The secondary flux diagnostics and the many alignment / screen cameras are not core beam-path devices and are deferred.

- **Full asset-tree scenarios and vendor Models.** No `test_sst_*.py` registers the SST asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
