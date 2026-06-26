# Model

*The developer's index into where IXS content lives, the one new loose family this first hard inelastic-scattering deployment introduces, and the record of what is deliberately deferred. First cut.*

IXS is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/ixs/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ixs/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `IXS` added to its beamline list, with an inelastic-scattering Practice |
| Extraction provenance | [NSLS2/ixs-profile-collection](https://github.com/NSLS2/ixs-profile-collection) | the `startup/*.py` device classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; one new device class stays loose at n=1 (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the inelastic-scattering Method is not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers IXS Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes IXS new

IXS is CORA's first photon-in / photon-out energy-LOSS technique. The fleet already has elastic scattering (SAXS/WAXS, XPDF, powder, XPCS, MX), XRF microprobe, hard X-ray absorption (BMM), and soft resonant inelastic scattering (SIX), but no hard inelastic scattering. The novelty is the acquisition shape: set the momentum transfer Q with a six-circle reciprocal-space pseudo-axis, then scan the incident energy (the DCM, and the high-resolution monochromator for meV steps) against a fixed crystal analyzer, point-detecting the energy-analyzed scattered beam to build I(Q, energy-loss). That is a new Capability, deferred as a question (TECH-1); it forces no new device families beyond the analyzer below.

## New loose families

IXS introduces one device class no existing catalog Family covers: the crystal energy analyzer. Per earn-the-abstraction, it is held **loose at n=1** and graduates nothing: a second independent hard crystal-analyzer beamline must earn the abstraction before any catalog change. The name was cleared by the naming-r3 gate.

| Loose family | Presents (when graduated) | What it is | Earns when |
| --- | --- | --- | --- |
| `EnergyAnalyzer` | Positioner (Sensor-vs-Positioner a confirm) | a diced multi-crystal Bragg analyzer that selects the final photon energy of the scattered beam, focusing energy-selected photons onto the point detectors | a 2nd hard crystal-analyzer / IXS beamline (`ANALYZER-1`) |

`EnergyAnalyzer` is deliberately not stretched onto an existing Family. It is not the catalog `EnergyDispersiveSpectrometer` (a per-event point Sensor that reads energy, where the analyzer positions crystals and the reading happens downstream at the electrometers), nor the catalog `Monochromator` (an upstream incident-beam optic), nor SIX's loose `SpectrometerArm` (a soft X-ray energy-dispersive arm; IXS uses a driven scanning crystal analyzer, not a dispersive one). naming-r3 chose `EnergyAnalyzer` over `Analyzer` and `CrystalAnalyzer`: it is the `<Quantity>Analyzer` sibling of 4-ID's loose `PolarizationAnalyzer` (the qualifier names the analyzed quantity), and it avoids the `CrystalAnalyzer` / `AnalyzerCrystal` read-aloud homograph. Whether `EnergyAnalyzer` and `PolarizationAnalyzer` later merge into one `Analyzer` Family differentiated by a setting is the open `ANALYZER-1`, a gate decision at the second sighting, not this PR's.

## Deliberately not here yet

- **The six-circle arm binds the catalog `Goniometer`, not a new family.** The spectrometer arm (tth / th / chi / phi driven by the H/K/L reciprocal-space pseudo-axis) is the 8-ID / 4-ID six-circle diffractometer anatomy. In descriptor mode it binds the catalog `Goniometer` directly (the 8-ID / 4-ID scaffold pattern), and SIX's dispersive `SpectrometerArm` is the wrong anatomy for a driven scanning arm. The reciprocal-space layer binds the catalog `PseudoAxis`.

- **The analyzer-Assembly question (`ANALYZER-1`).** Whether the crystal analyzer plus the six-circle arm compose an `Assembly(Diffractometer)`-style Fixture is deferred, exactly as 8-ID and 4-ID deferred materializing their diffractometer Assemblies in descriptor mode. The first cut is a flat loose `EnergyAnalyzer` Asset plus a `Goniometer` arm Asset, with the Assembly named as the follow-on. An Assembly is earned at n=2 across independent beamlines; coining one at n=1 would be over-modelling.

- **The diced-crystal identity (`XTAL-1`).** The six diced crystals each carry their own theta / phi and PID temperature, so each is identity-bearing. The lower-risk first cut carries them as settings on the one `EnergyAnalyzer` Asset; promoting each to a child Asset via `parent_id` is exactly the nested-component-identity convention, which is itself at a rule-of-three gate (applied only for `RotaryDriveChassis` so far), so IXS flags `XTAL-1` as a candidate trigger rather than asserting it. The six crystal-temperature PID loops are carried as one `TemperatureController` Asset for the same reason (`TEMP-1`).

- **The high-resolution-mono beamstop (`HRM-1`).** The high-resolution monochromator carries an in-line beamstop; whether it is a distinct child `BeamStop` Asset is gated under the same nested-component rule-of-three.

- **The IXS Method.** Whether momentum-resolved inelastic scattering enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_ixs_*.py` registers the IXS asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
