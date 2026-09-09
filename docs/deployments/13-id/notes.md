# Notes

## Techniques

*What the modelled part of 13-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 13-ID runs monochromatic X-ray diffraction on a sample held in a diamond anvil cell under extreme pressure and double-sided laser heating: high-pressure powder diffraction and high-pressure single-crystal diffraction. Both reuse Methods that the fleet already carries (or has pending), so the slugs below render unlinked and are carried pending until one enters scope (TECH-1). Nothing here coins a new technique. The novelty at 13-ID is the sample environment, not the measurement.

### High pressure is a sample environment, not a technique

The diamond anvil cell squeezes the sample between two anvils and heats it from both sides, so the diffraction is measured at extreme pressure and temperature rather than at ambient conditions. That is a difference in the conditions the sample sits in, not a difference in what the beam measures or how the pattern is read. A powder ring is a powder ring whether the powder is at ambient pressure or inside a cell; a single-crystal reflection is a single-crystal reflection either way.

So high pressure binds the same Methods as ordinary diffraction, carried as a Plan-level sample-environment difference. This follows the [4-ID precedent](../4-id/notes.md#techniques), where high-pressure diffraction is the same `diffraction` Method run with a pressure cell, a Plan setting over the same measurement and not a new slug. The cell, its heating, and its in-situ pressure and temperature metrology are modelled as equipment (the catalog [PressureCell](sample.md) family and its capabilities), and the conditions they impose are expressed in the Plan, not in the technique name.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-pressure powder diffraction | `powder_diffraction` | monochromatic powder rings from the cell, recorded on the [area detector](detector.md); shares the i11 powder Capability; high pressure is a Plan-level sample-environment setting, pending (TECH-1) |
| High-pressure single-crystal diffraction | `diffraction` | reciprocal-space reflections from a single crystal in the cell on the [area detector](detector.md), oriented on the [diffractometer stage](sample.md); shares the 4-ID / 8-ID / CSX / i19 diffraction Capability; high pressure is a Plan-level sample-environment setting, pending (TECH-1) |

Both techniques need the [incident beam chain](source.md) (the shared 13-ID-A monochromator, the K-B focusing mirror, the beam-defining and clean-up apertures, and the attenuator filter bank), the [pressure cell and its diffractometer stage](sample.md), the [area detector on its 2theta arm](detector.md), and the ion-chamber and photodiode [flux monitors](detector.md) for normalization. The diffraction spine is entirely catalog reuse; see [Model](#model) for why nothing in the measurement path graduates.

### What the cell lets the science do

The diamond anvil cell is what makes 13-ID distinct. It lets the experiment probe matter at extreme pressure and temperature, conditions that reach toward planetary interiors and that no other deployment in the fleet has reached. The science is to watch how a material's structure responds as it is squeezed and heated: phase transitions, equations of state, and structural changes under pressure and temperature that do not appear at ambient conditions.

Two cell capabilities do the work, and both are modelled as capabilities of the single [PressureCell](sample.md) Asset rather than as separate families:

- **Pressure.** The cell presents the Regulator Role for its membrane gas pressure, driven through the PACE5000 membrane controller. Setting and reading the membrane pressure is the actuated handle on the squeeze (PRESSURE-1, HP-1).
- **Double-sided laser heating.** Two IPG YLR fibre lasers heat the sample from both sides, balanced, so the heated volume is hot through its thickness rather than only on one face (HEAT-1). The live heating is open-loop on commanded laser power: there is no closed-loop temperature Regulator today, the lasers are a power actuator and the temperature is inferred from the sample's own thermal emission (HEAT-1).

These two together open the pressure-temperature space that the diffraction then samples. The cell sets the conditions; the diffraction reads the structure.

### The in-situ metrology is part of the cell

Knowing the pressure and temperature at the sample is itself measured in situ, and that metrology belongs to the cell as a capability, not to a technique:

- **Temperature** is read from thermal-emission spectroradiometry: the sample's own glow, dispersed and fit to a thermal spectrum, gives the temperature on each side (HEAT-1, HP-1). The spectrometer that records it binds the catalog [Camera](detector.md) family (LightField PIMAX / PIXIS), the cell's pressure-and-temperature metrology detector.
- **Pressure** is read from ruby fluorescence, Raman, or Brillouin measurements on the cell (PRESSURE-1, HP-1). These calibrate the pressure that the membrane controller commands against an in-situ standard.

This metrology is not a separate Method. It is how the cell knows the conditions it is imposing, the same way a temperature controller knows its setpoint. It is modelled as part of the PressureCell capability and its [metrology spectrometer](detector.md), and it does not appear in the technique table above.

### Not modelled yet

The concrete acquisition recipes are not written yet: the powder and single-crystal scan sequences, the laser-power ramp and balancing during heating, the ruby / Raman / Brillouin pressure-calibration steps, and how a Plan threads the pressure and temperature setpoints through a diffraction run. They join as the deployment approaches the point where CORA conducts over the floor.

Whether `powder_diffraction` and `diffraction` enter CORA's catalog, and who owns them across the facilities that share them, is an owner-scope decision and is deferred (TECH-1); minting a cross-facility Method is not done from a modelling exercise until a technique enters a real scope. The Practices are carried pending on the [APS Site](../aps/index.md#the-techniques-adapted-here): `13ID_powder_diffraction_practice` (`powder_diffraction`) and `13ID_diffraction_practice` (`diffraction`), both pending TECH-1.

The 2theta swing transform that would bind a `PseudoAxis` on the [detector arm](detector.md) is deferred, not invented: the arm's prefix was seen only in a controller test template, so the binding is left open (DET-1). A closed-loop temperature Regulator for the heating is likewise not modelled, because today's heating is open-loop on commanded power (HEAT-1). See [Open questions](#open-questions) for the world-facts to confirm first, and [Model](#model) for how the PressureCell family, introduced here, graduated to the catalog across 13-ID and P02 (HP-1).

## Governance

*Who will act at 13-ID, and the trust shape that will gate it. First cut.*

Governance at 13-ID follows the same model as the other APS beamlines: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

13-ID is not yet driven by CORA, so this shape is not yet instantiated. As a reverse-engineered scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The GSECARS EPICS support tree exposes device templates and startup scripts, not the human roster, so the APS / GSECARS operator pool and the safety-review structure are carried pending at the [APS Site](../aps/index.md#safety-and-governance), shared across the beamlines (`GOV-1`).

### The safety envelope

The safety tier is the other piece that is not yet settled, and at 13-ID it carries an extra leg the other APS beamlines do not. Clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and 13-ID links up to them rather than restating them. What is specific to this station is the stack of hazard classes that an experiment Clearance would have to carry together: a hard X-ray beamline, plus the class-4 double-sided heating lasers at the sample, plus the pressurized gas membrane system that loads the diamond anvil cell. Those three land with the instruments that bring them, and the high-pressure sample environment is the novelty here (`HP-1`).

The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the EPICS-native config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`).

### The laser-safety permit leaf

13-ID adds a distinct enclosure permit axis the rest of the fleet has not needed: a dedicated laser-safety permit gating laser emission, separate from the X-ray PSS leaf. A Koyo safety PLC governs whether the heating lasers may emit into the enclosure. CORA models this as an Enclosure permit concern on the laser-emission axis, not as a device. It is carried pending and its logic is not invented here (`LASER-1`, `PSS-1`); the heating capability of the cell stays open-loop on commanded power and is not a closed-loop controller (`HEAT-1`).

### Where this lands

The concrete Zone, Conduit, and Policy instances, the operator pool, and both safety leaves (the PSS X-ray permit and the laser-emission permit) materialize when the deployment approaches the point where CORA drives 13-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 13-ID content lives, the first extreme-conditions deployment (high-pressure diamond anvil cell), and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 13-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes 13-ID new

13-ID is CORA's first extreme-conditions deployment. The fleet has modelled thermal sample environments (the graduated `TemperatureController`), magnetic ones (the graduated `Magnet`), and pump-probe lasers (the graduated `Laser`), but never a high-pressure one. 13-ID holds the sample in a diamond anvil cell (DAC): the anvils are squeezed by a gas membrane (a PACE5000 pneumatic controller) to the megabar regime, the sample is heated from both sides by two fibre lasers to thousands of kelvin, and the pressure and temperature are read optically in situ (thermal-emission spectroradiometry for temperature; ruby fluorescence, Raman, and Brillouin for pressure). The X-ray probe is otherwise familiar powder and single-crystal diffraction; the novelty is entirely the sample environment.

### The PressureCell family (graduated)

13-ID introduced one device class no existing catalog Family then covered: the high-pressure sample cell. It has since graduated to the catalog, earned across 13-ID and PETRA III P02 (the fleet's second diamond-anvil-cell environment). The name was chosen via the naming-r3 gate.

| Catalog family | Presents | What it is | Earned across |
| --- | --- | --- | --- |
| `PressureCell` | Regulator (membrane pressure) | a high-pressure sample environment (the diamond anvil cell): membrane gas pressure loading, double-sided laser heating, and in-situ pressure / temperature metrology, as one Asset | 13-ID and PETRA III P02 (`PRESSURE-1`) |

The name is deliberately the bare, regime-generic role-noun `PressureCell`, not `HighPressureCell` (the qualifier names the regime, the `OpticalTable` to `Table` mistake), nor `DiamondAnvilCell` (the qualifier names the implementation mechanism, which would force a near-duplicate family for the large-volume press or a clamp cell). `PressureCell` spans the DAC, the large-volume press, and clamp cells, so it did not fragment when the next high-pressure environment landed. It graduated to the catalog across 13-ID and PETRA III P02; further high-pressure environments (APS HPCAT 16-ID, the sibling 13-BM-D large-volume press in the same GSECARS source tree, the 4-ID pressure cell) now bind the graduated Family (`PRESSURE-1`).

The cell is modelled as **one Asset** presenting the `Regulator` Role for its membrane pressure (the PACE5000 setpoint and readback, settling to a target). Its double-sided laser heating and its in-situ pressure / temperature metrology are capabilities of the same cell, not separate families. It does not swallow the metrology spectrometer (which binds the catalog `Camera`) or the X-ray detectors; those are sibling Assets.

### The heating lasers are not the Laser family

The two fibre lasers that heat the DAC sample do **not** bind the catalog `Laser` Family. CORA binds by Role, not mechanism: a heating laser is a power-delivery / thermal-actuation role, distinct from the pump-probe `Laser` (4-ID, LCLS-MFX, whose model-versus-hazard question heating does not touch). Binding them to `Laser` would corrupt the signal that hold protects. They are the heating capability of the `PressureCell`. Whether that capability is ever a clean `TemperatureController` is `HEAT-1`: the live heating is open-loop on commanded power (`13IDD:US_LaserPower` / `DS_LaserPower`) with temperature inferred from emission, so today it is a power actuator, not a temperature `Regulator`. The upstream and downstream beams are one device with two sides (balanced double-sided heating), not two instances.

### No new families on the XRD spine

The X-ray probe spine reuses the catalog throughout: the silicon DCM binds `Monochromator` (the 2-BM precedent); the K-B and carbon mirrors bind `Mirror` with their curvature as `PseudoAxis`; the slits bind `Slit`; the clean-up pinhole binds `Aperture`; the attenuator binds `Filter`; the DAC positioning stage binds `Goniometer` (the i03 Smargon precedent); the Eiger2 / Pilatus area detectors and the LightField metrology spectrometer bind `Camera`; the ion chambers and photodiode bind `FluxMonitor`; the Dante MCA binds `EnergyDispersiveSpectrometer`; the incident energy binds `PseudoAxis`; the fibre illumination binds the catalog `Backlight` (graduated across the MX / imaging fleet); the machine state binds the loose `StorageRing`.

High-pressure diffraction is **not** a new technique: it reuses the pending `diffraction` (4-ID / 8-ID / CSX / i19) and `powder_diffraction` (i11) Methods, with high pressure a Plan-level sample-environment difference (the 4-ID high-pressure-diffraction precedent). The Practices render unlinked, pending (`TECH-1`).

### Deliberately not here yet

- **The PressureCell membrane / load control (`PRESSURE-1`).** The family has graduated to the catalog (earned across 13-ID and P02); the membrane / gas-loading control detail remains a staff confirmation.
- **The heating-control binding (`HEAT-1`).** Whether any heating path closes a temperature-setpoint loop (a clean `TemperatureController`) versus the open-loop power actuation modelled here is a staff confirmation.
- **The laser-safety PLC and the metrology excitation lasers (`LASER-1`).** The Koyo DL205 PLC is the laser-emission enclosure permit axis, an Enclosure concern, not a device; the Verdi / Raman excitation lasers live on a separate metrology host (`13RAMAN2`).
- **The detector 2theta-arm transform (`DET-1`).** The swing transform binds `PseudoAxis`, but its live prefix was seen only in a Galil test template, so the binding is deferred rather than invented.
- **The 13-BM stations and the large-volume press (`HP-1`).** A different multi-anvil probe spine, out of this station's scope; would bind the catalog `PressureCell` Family when exposed.
- **The diffraction Methods.** Whether high-pressure powder and single-crystal diffraction enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_13_id_d_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the GSECARS 13-ID team to confirm before the model can be trusted.*

13-ID was reverse-engineered from the GSECARS EPICS support tree ([CARS-UChicago/GSECARS-EPICS](https://github.com/CARS-UChicago/GSECARS-EPICS)), so the control handles on the [device pages](index.md) are the beamline's real PVs, reconstructed from the `iocBoot` startup scripts, the `CARSApp/Db` device templates, and the `CARSApp/op/adl` screens rather than confirmed by staff. This is an EPICS-native source (not a dodal or BITS Python roster), so the device-to-PV reconstruction is rougher and carried at medium confidence. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are 13-ID-A (first optics) and 13-ID-D (endstation) separate hutches, and how does the laser-safety enclosure relate? | Two enclosures: a shared `13-ID-optics` zone and the `13-ID-D` endstation; the laser-safety PLC adds a laser-emission permit axis. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 13-ID undulator (shared across 13-ID-C/D/E), energy-tracked with the mono. | An undulator, not surfaced as a device in the support tree read. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state 13-ID reads. | Observe-only machine state, a loose `StorageRing`; PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The 13-ID-A Si monochromator crystal cut, the energy range, and the energy partition rule. | A silicon double-crystal `Monochromator`; the energy is a `PseudoAxis` (`13IDE:En`). | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The K-B and carbon mirror coatings, the curvature / ellipticity axes. | Focusing mirrors bound to `Mirror`; curvature / ellipticity a `PseudoAxis`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of the beam-defining and DAC table-top slits (DACV / DACH). | Slits bound to `Slit`. | The slit Asset detail. |
| APERTURE-1 | Nice-to-have | The clean-up pinhole and its X / Y / Z carriers. | The opening bound to `Aperture`, the carriers `LinearStage`. | The pinhole Asset. |
| ATTN-1 | Nice-to-have | The attenuator foil set (`13IDD:filter:`) and whether it folds into `Filter` or earns a distinct `Attenuator` kind. | The attenuator bound to `Filter` (the 2-BM precedent). | The attenuator's catalog home. |

### The high-pressure sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| HP-1 | Blocks-build | How is the diamond anvil cell configured: the membrane pressure range, the double-sided laser-heating geometry, and the in-situ pressure / temperature metrology, and are they one cell or separate units? | One `PressureCell` Asset presenting the `Regulator` Role for the membrane pressure (PACE5000), with laser heating and metrology as its capabilities. | The DAC modelling; the CORA structural choice is on [Model](#the-pressurecell-family-graduated). |
| HEAT-1 | Blocks-go-live | Does any heating path close a loop on a temperature setpoint (a clean `TemperatureController`), or is the live laser heating open-loop on commanded power with temperature inferred from emission? | Open-loop on commanded power (`13IDD:US_LaserPower` / `DS_LaserPower`), temperature read by spectroradiometry; a power actuator, not a temperature `Regulator`. | The heating-control modelling. |
| PRESSURE-1 | Nice-to-have | The `PressureCell` membrane / gas-loading / pressure-ramp control detail, beyond the PACE5000 setpoint / readback. | The `PressureCell` Family has graduated to the catalog (earned across 13-ID and P02); the membrane / load control detail is pending. | The PressureCell control modelling. |
| LASER-1 | Blocks-go-live | The Koyo laser-safety PLC (`13IDD_laserPLC:`) enable / enclosure signals, and the metrology excitation lasers on the separate `13RAMAN2` host. | The PLC is a laser-emission enclosure permit axis (not a device); the excitation lasers are a cell metrology capability. | The laser-safety permit and the excitation lasers. |

### Sample stage and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The DAC positioning stage / micro-diffractometer axes (Galil X / Z / Y / Omega and the Newport XPS-16 trajectory stage) and the single-Omega geometry. | A `Goniometer` (the i03 Smargon precedent); Galil-vs-XPS controller and single Omega are settings. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The XRD detector assignment (Eiger2 9M versus the Pilatus 1M CdTe / Si), the detector 2theta-arm transform (seen only in a Galil test template), and the flux / fluorescence channel map. | The Eiger2 / Pilatus bind `Camera`; the 2theta swing binds `PseudoAxis` (binding deferred); the ion chambers bind `FluxMonitor` and the Dante MCA `EnergyDispersiveSpectrometer`. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles reconstructed from the GSECARS support tree current and correct? | The handles in the descriptor are reconstructed from the support tree and carried confirm at medium confidence. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals, plus the laser-safety enclosure permit. | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the high-pressure gas supply the membrane controller uses. | Photon beam, cooling water, vacuum, and process gas. | The Supply observations. |
| GOV-1 | Nice-to-have | The APS / GSECARS operator pool and safety-review structure. | Carried pending on the APS Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do high-pressure powder and single-crystal diffraction enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `powder_diffraction` (i11) and `diffraction` (4-ID) Methods, with high pressure a Plan-level sample-environment difference; none coined. | The diffraction Capabilities. |
