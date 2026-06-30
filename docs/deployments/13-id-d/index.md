# 13-ID-D

*The GSECARS high-pressure X-ray diffraction beamline at APS Sector 13, and CORA's first extreme-conditions sample environment: monochromatic powder and single-crystal diffraction on a sample held in a diamond anvil cell under extreme pressure and double-sided laser heating. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `13-ID-D` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 13` (GSECARS / GeoSoilEnviroCARS; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | The shared 13-ID-A first optics, observed in the `13-ID-optics` zone (`MONO-1`, `SRC-1`) |
| Control stack | APS EPICS (GSECARS runs EPICS plus SPEC plus Python orchestration; the same floor as the other APS beamlines); handles bound from the support tree, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the GSECARS EPICS support tree ([CARS-UChicago/GSECARS-EPICS](https://github.com/CARS-UChicago/GSECARS-EPICS)): the `iocBoot` startup scripts, the `CARSApp/Db` device templates, and the `CARSApp/op/adl` MEDM screens. This is an EPICS-native source, not a dodal or BITS Python device roster, so the device-to-PV reconstruction is rougher and is carried at **medium confidence** until 13-ID-D staff verify it. EPICS PVs read from the support tree are real; vendor part numbers, serials, physical positions, and pressure / temperature regimes are not in the tree and are open questions. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 13-ID-D different

13-ID-D is **CORA's first extreme-conditions deployment**, the first instrument in the fleet whose sample sits in a high-pressure environment. The fleet has modelled thermal sample environments (the graduated `TemperatureController`), magnetic ones (the loose `Magnet`), and pump-probe lasers (the loose `Laser`), but never a high-pressure one. This is the axis the EMA scout flagged the fleet lacked.

The sample lives in a diamond anvil cell (DAC). The anvils are squeezed by a gas membrane driven by a GE/Druck PACE5000 pneumatic controller (`13IDD_PACE5000:PC1:Setpoint` / `Pressure_RBV`); the sample is heated from both sides by two IPG YLR fibre lasers (`13IDD:Laser1` / `Laser2`, power `13IDD:US_LaserPower` / `DS_LaserPower`); and the pressure and temperature are read optically in situ (thermal-emission spectroradiometry for temperature, `13IDD:us_las_temp` / `ds_las_temp`; ruby fluorescence, Raman, and Brillouin for pressure). The X-ray probe is otherwise familiar: monochromatic powder and single-crystal diffraction read on an area detector. The novelty is entirely the sample environment.

13-ID-D **coins one new loose family**, `PressureCell`, for that high-pressure sample environment. No existing catalog Family covers it. The cell is modelled as **one Asset** presenting the `Regulator` Role for its membrane pressure (the PACE5000 setpoint settling to a target); its double-sided laser heating (`HEAT-1`) and its in-situ pressure / temperature metrology (`PRESSURE-1`) are capabilities of the same cell, not separate families. Everything else on the diffraction spine reuses the catalog.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Source / optics (`13-ID-optics`) | Yes | The shared 13-ID-A silicon DCM (`MONO-1`), the K-B and carbon focusing mirrors (`OPT-1`), the beam-defining and DAC table-top slits (`OPT-2`), the clean-up pinhole (`APERTURE-1`), the attenuator filter (`ATTN-1`), and the machine-level storage ring (observe-only, `MACHINE-1`) |
| High-pressure sample (`13-ID-D`) | Yes | The diamond anvil cell as one `PressureCell` Asset, the DAC positioning stage and lift table (`SAMPLE-1`), and the LightField metrology spectrometer (`HP-1`) |
| Detection (`13-ID-D`) | Yes | The Eiger2 / Pilatus area detector (`DET-1`), the detector table and 2theta arm (`DET-1`), the ion-chamber and photodiode flux monitors (`DET-1`), the XGLab Dante fluorescence MCA (`DET-1`), and the fibre sample illumination (`DET-1`) |
| New device classes | One loose `PressureCell` | The high-pressure sample environment, held at n=1; nothing graduates; the catalog is otherwise unchanged (see [Model](model.md)) |
| The heating lasers | Capability of `PressureCell`, not the `Laser` family | Heating is a different role from pump-probe; modelled as an open-loop power actuator, not a temperature `Regulator` (`HEAT-1`) |
| The detector 2theta-arm transform | Named, deferred | The swing transform binds `PseudoAxis`, but its prefix was seen only in a Galil test template, so the binding is deferred, not invented (`DET-1`) |
| The laser-safety PLC | Enclosure permit axis, not a device | The Koyo PLC gates laser emission as a laser-emission enclosure permit (`LASER-1`, `PSS-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **One new loose family: `PressureCell` (`PRESSURE-1`).** The high-pressure sample environment has no fleet analog, so it earns one new loose Family, held **at n=1** and graduating nothing. The name is deliberately the bare, regime-generic role-noun `PressureCell`, **not** `HighPressureCell` (the qualifier names the regime) nor `DiamondAnvilCell` (the qualifier names the mechanism, which would force a near-duplicate family for the large-volume press or a clamp cell). `PressureCell` spans the DAC, the large-volume press, and clamp cells. It is modelled as **one Asset** presenting the `Regulator` Role for its membrane pressure, with heating and metrology as capabilities of the same cell. Its rule-of-three triggers are named: HPCAT 16-ID, the 13-BM-D large-volume press, and the 4-ID cell.
- **The heating lasers do not bind the `Laser` family (`HEAT-1`).** CORA binds by Role, not mechanism: heating is a power-delivery / thermal-actuation role, distinct from the pump-probe `Laser`. The live heating is **open-loop on commanded power** (`13IDD:US_LaserPower` / `DS_LaserPower`) with temperature inferred from emission, so today it is a power actuator, not a temperature `Regulator`. The upstream and downstream beams are one device with two sides (balanced double-sided heating), not two instances.
- **High-pressure diffraction reuses the pending Methods.** High-pressure powder diffraction reuses `powder_diffraction` (shares i11); high-pressure single-crystal diffraction reuses `diffraction` (shares 4-ID / 8-ID / CSX / i19). High pressure is a Plan-level sample-environment difference (the 4-ID precedent), not a new slug.
- **The XRD spine is entirely catalog reuse.** The silicon DCM binds `Monochromator`, the K-B and carbon mirrors bind `Mirror`, the slits bind `Slit`, the clean-up pinhole binds `Aperture`, the attenuator binds `Filter`, the DAC positioning stage binds `Goniometer` (the i03 Smargon precedent), the area and metrology detectors bind `Camera`, the ion chambers and photodiode bind `FluxMonitor`, the Dante MCA binds `EnergyDispersiveSpectrometer`, the incident energy binds `PseudoAxis`, the fibre illumination binds the loose `Backlight`, and the machine state binds the loose `StorageRing`.
- **The Koyo laser-safety PLC is an Enclosure permit axis, not a device (`LASER-1`, `PSS-1`).** It gates laser emission as a laser-emission enclosure permit (`LASER-1`) alongside the PSS search-and-secure permit (`PSS-1`). The novelty is localized to the sample environment.

## The beamline

- [Source](beamline.md): the generated device walk: the storage ring (observe-only, `MACHINE-1`), the shared 13-ID-A silicon double-crystal monochromator (`13IDA:`, `MONO-1`), the derived beamline energy (`13IDE:En`, `MONO-1`), the K-B and carbon focusing mirrors (`OPT-1`), the beam-defining and DAC table-top slits (`DACV` / `DACH`, `OPT-2`), the clean-up pinhole and its carriers (`APERTURE-1`), and the attenuator filter (`13IDD:filter:`, `ATTN-1`).
- [Sample](equipment/sample.md): the diamond anvil cell as the loose `PressureCell` (the PACE5000 membrane regulator, the double-sided IPG YLR heating, and the in-situ pressure / temperature metrology), the DAC positioning stage and lift table (`SAMPLE-1`), and the LightField metrology spectrometer (`13IDDLF1:`, `HP-1`).
- [Detector](equipment/detector.md): the Eiger2 / Pilatus area detector (`DET-1`), the detector table and 2theta arm (`DET-1`), the ion-chamber and photodiode flux monitors (`13IDD:scaler1`, `13IDD:Photodiode`, `DET-1`), the XGLab Dante fluorescence MCA (`13IDD_Dante1:`, `DET-1`), and the fibre sample illumination (`13IDD:US_IllumOnOff`, `DET-1`).

Cutting across them:

- [Controls](equipment/controls.md): the APS EPICS control stack and the SPEC / Python orchestration seam; the Galil and Newport XPS stage controllers; handles bound from the support tree and carried confirm at medium confidence (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/13-id-d/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 13-ID-D is designed to do, as intent. High-pressure powder diffraction reuses the `powder_diffraction` Method (shares i11) and high-pressure single-crystal diffraction reuses the `diffraction` Method (shares 4-ID / 8-ID / CSX / i19); high pressure is a Plan-level sample-environment difference, not a new slug. The `13IDD_powder_diffraction_practice` and `13IDD_diffraction_practice` Practices render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at 13-ID-D and the trust shape that gates their commands. People and autonomous agents are facility principals at the [APS Site](../aps/index.md); on the beamline they surface through the actions they take, gated by a trust shape (Zone, Conduit, Policy). The APS / GSECARS operator pool and review structure are carried pending at the APS Site, shared across the beamlines (`GOV-1`). The PSS search-and-secure permit signals are carried pending (`PSS-1`), plus a laser-safety enclosure permit (the Koyo PLC gating laser emission), carried pending and not invented (`LASER-1`). This is a hard X-ray beamline plus class-4 heating lasers plus a pressurized gas membrane system; CORA follows the 2-BM governance shape. Clearances are issued at the [APS Site](../aps/index.md), not on the beamline.

## Model

[Model](model.md): the developer's by-kind index and the record of what is deliberately deferred. 13-ID-D coins one new loose Family, `PressureCell`, held at n=1; the catalog is otherwise unchanged (see [Families](../../catalog/families.md)).

## Not yet documented

13-ID-D is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The detector 2theta-arm transform is named but its live prefix was seen only in a Galil test template, so its `PseudoAxis` binding is deferred rather than invented (`DET-1`). The PSS search-and-secure permit signals and the Koyo laser-emission permit logic are carried pending, not invented here (`PSS-1`, `LASER-1`).
