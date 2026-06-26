# Model

*The developer's index into where 13-ID-D content lives, the one new loose family this first extreme-conditions deployment introduces, and the record of what is deliberately deferred. First cut.*

13-ID-D is a descriptor-and-docs scaffold today, reverse-engineered from the GSECARS EPICS support tree: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/13-id-d/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/13-id-d/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface; `13-ID-D` added to its beamline list, with high-pressure powder / single-crystal diffraction Practices |
| Extraction provenance | [CARS-UChicago/GSECARS-EPICS](https://github.com/CARS-UChicago/GSECARS-EPICS) | the `iocBoot` startup scripts, `CARSApp/Db` templates, and `CARSApp/op/adl` screens the descriptor was reconstructed from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; one new device class stays loose at n=1 (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the diffraction Methods are pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 13-ID-D Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes 13-ID-D new

13-ID-D is CORA's first extreme-conditions deployment. The fleet has modelled thermal sample environments (the graduated `TemperatureController`), magnetic ones (the loose `Magnet`), and pump-probe lasers (the loose `Laser`), but never a high-pressure one. 13-ID-D holds the sample in a diamond anvil cell (DAC): the anvils are squeezed by a gas membrane (a PACE5000 pneumatic controller) to the megabar regime, the sample is heated from both sides by two fibre lasers to thousands of kelvin, and the pressure and temperature are read optically in situ (thermal-emission spectroradiometry for temperature; ruby fluorescence, Raman, and Brillouin for pressure). The X-ray probe is otherwise familiar powder and single-crystal diffraction; the novelty is entirely the sample environment.

## New loose family: the PressureCell

13-ID-D introduces one device class no existing catalog Family covers: the high-pressure sample cell. Per earn-the-abstraction it is held **loose at n=1** and graduates nothing. The name was chosen via the naming-r3 gate.

| Loose family | Presents | What it is | Earns when |
| --- | --- | --- | --- |
| `PressureCell` | Regulator (membrane pressure) | a high-pressure sample environment (the diamond anvil cell): membrane gas pressure loading, double-sided laser heating, and in-situ pressure / temperature metrology, as one Asset | a second independent high-pressure environment (`PRESSURE-1`) |

The name is deliberately the bare, regime-generic role-noun `PressureCell`, not `HighPressureCell` (the qualifier names the regime, the `OpticalTable` to `Table` mistake), nor `DiamondAnvilCell` (the qualifier names the implementation mechanism, which would force a near-duplicate family for the large-volume press or a clamp cell). `PressureCell` spans the DAC, the large-volume press, and clamp cells, so it will not fragment when the next high-pressure environment lands. Its rule-of-three triggers are named: APS HPCAT 16-ID, the sibling 13-BM-D large-volume press in the same GSECARS source tree, and the deferred 4-ID pressure cell (`PRESSURE-1`).

The cell is modelled as **one Asset** presenting the `Regulator` Role for its membrane pressure (the PACE5000 setpoint and readback, settling to a target). Its double-sided laser heating and its in-situ pressure / temperature metrology are capabilities of the same cell, not separate families. It does not swallow the metrology spectrometer (which binds the catalog `Camera`) or the X-ray detectors; those are sibling Assets.

## The heating lasers are not the Laser family

The two fibre lasers that heat the DAC sample do **not** bind the loose `Laser` Family. CORA binds by Role, not mechanism: a heating laser is a power-delivery / thermal-actuation role, distinct from the pump-probe `Laser` (4-ID, LCLS-MFX, held with a model-versus-hazard question that heating does not touch). Binding them to `Laser` would corrupt the signal that hold protects. They are the heating capability of the `PressureCell`. Whether that capability is ever a clean `TemperatureController` is `HEAT-1`: the live heating is open-loop on commanded power (`13IDD:US_LaserPower` / `DS_LaserPower`) with temperature inferred from emission, so today it is a power actuator, not a temperature `Regulator`. The upstream and downstream beams are one device with two sides (balanced double-sided heating), not two instances.

## No new families on the XRD spine

The X-ray probe spine reuses the catalog throughout: the silicon DCM binds `Monochromator` (the 2-BM precedent); the K-B and carbon mirrors bind `Mirror` with their curvature as `PseudoAxis`; the slits bind `Slit`; the clean-up pinhole binds `Aperture`; the attenuator binds `Filter`; the DAC positioning stage binds `Goniometer` (the i03 Smargon precedent); the Eiger2 / Pilatus area detectors and the LightField metrology spectrometer bind `Camera`; the ion chambers and photodiode bind `FluxMonitor`; the Dante MCA binds `EnergyDispersiveSpectrometer`; the incident energy binds `PseudoAxis`; the fibre illumination binds the loose `Backlight`; the machine state binds the loose `StorageRing`.

High-pressure diffraction is **not** a new technique: it reuses the pending `diffraction` (4-ID / 8-ID / CSX / i19) and `powder_diffraction` (i11) Methods, with high pressure a Plan-level sample-environment difference (the 4-ID high-pressure-diffraction precedent). The Practices render unlinked, pending (`TECH-1`).

## Deliberately not here yet

- **The PressureCell graduation (`PRESSURE-1`).** Held loose at n=1; the named rule-of-three triggers are HPCAT 16-ID, the 13-BM-D large-volume press, and the 4-ID cell. A second independent high-pressure environment crosses the promotion threshold and forces a recorded hold-or-graduate decision.
- **The heating-control binding (`HEAT-1`).** Whether any heating path closes a temperature-setpoint loop (a clean `TemperatureController`) versus the open-loop power actuation modelled here is a staff confirmation.
- **The laser-safety PLC and the metrology excitation lasers (`LASER-1`).** The Koyo DL205 PLC is the laser-emission enclosure permit axis, an Enclosure concern, not a device; the Verdi / Raman excitation lasers live on a separate metrology host (`13RAMAN2`).
- **The detector 2theta-arm transform (`DET-1`).** The swing transform binds `PseudoAxis`, but its live prefix was seen only in a Galil test template, so the binding is deferred rather than invented.
- **The 13-BM stations and the large-volume press (`HP-1`).** A different multi-anvil probe spine, out of this station's scope; named as a PressureCell rule-of-three candidate.
- **The diffraction Methods.** Whether high-pressure powder and single-crystal diffraction enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_13_id_d_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
