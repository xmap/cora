# Open questions

*What CORA needs the GSECARS 13-ID-D team to confirm before the model can be trusted.*

13-ID-D was reverse-engineered from the GSECARS EPICS support tree ([CARS-UChicago/GSECARS-EPICS](https://github.com/CARS-UChicago/GSECARS-EPICS)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, reconstructed from the `iocBoot` startup scripts, the `CARSApp/Db` device templates, and the `CARSApp/op/adl` screens rather than confirmed by staff. This is an EPICS-native source (not a dodal or BITS Python roster), so the device-to-PV reconstruction is rougher and carried at medium confidence. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are 13-ID-A (first optics) and 13-ID-D (endstation) separate hutches, and how does the laser-safety enclosure relate? | Two enclosures: a shared `13-ID-optics` zone and the `13-ID-D` endstation; the laser-safety PLC adds a laser-emission permit axis. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 13-ID undulator (shared across 13-ID-C/D/E), energy-tracked with the mono. | An undulator, not surfaced as a device in the support tree read. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state 13-ID-D reads. | Observe-only machine state, a loose `StorageRing`; PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The 13-ID-A Si monochromator crystal cut, the energy range, and the energy partition rule. | A silicon double-crystal `Monochromator`; the energy is a `PseudoAxis` (`13IDE:En`). | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The K-B and carbon mirror coatings, the curvature / ellipticity axes. | Focusing mirrors bound to `Mirror`; curvature / ellipticity a `PseudoAxis`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of the beam-defining and DAC table-top slits (DACV / DACH). | Slits bound to `Slit`. | The slit Asset detail. |
| APERTURE-1 | Nice-to-have | The clean-up pinhole and its X / Y / Z carriers. | The opening bound to `Aperture`, the carriers `LinearStage`. | The pinhole Asset. |
| ATTN-1 | Nice-to-have | The attenuator foil set (`13IDD:filter:`) and whether it folds into `Filter` or earns a distinct `Attenuator` kind. | The attenuator bound to `Filter` (the 2-BM precedent). | The attenuator's catalog home. |

## The high-pressure sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| HP-1 | Blocks-build | How is the diamond anvil cell configured: the membrane pressure range, the double-sided laser-heating geometry, and the in-situ pressure / temperature metrology, and are they one cell or separate units? | One `PressureCell` Asset presenting the `Regulator` Role for the membrane pressure (PACE5000), with laser heating and metrology as its capabilities. | The DAC modelling; the CORA structural choice is on [Model](model.md#new-loose-family-the-pressurecell). |
| HEAT-1 | Blocks-go-live | Does any heating path close a loop on a temperature setpoint (a clean `TemperatureController`), or is the live laser heating open-loop on commanded power with temperature inferred from emission? | Open-loop on commanded power (`13IDD:US_LaserPower` / `DS_LaserPower`), temperature read by spectroradiometry; a power actuator, not a temperature `Regulator`. | The heating-control modelling. |
| PRESSURE-1 | Nice-to-have | The rule-of-three for the `PressureCell` Family: the named triggers are APS HPCAT 16-ID, the 13-BM-D large-volume press, and the 4-ID pressure cell. | Held loose at n=1; graduates when a second independent high-pressure environment lands. | The PressureCell graduation. |
| LASER-1 | Blocks-go-live | The Koyo laser-safety PLC (`13IDD_laserPLC:`) enable / enclosure signals, and the metrology excitation lasers on the separate `13RAMAN2` host. | The PLC is a laser-emission enclosure permit axis (not a device); the excitation lasers are a cell metrology capability. | The laser-safety permit and the excitation lasers. |

## Sample stage and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The DAC positioning stage / micro-diffractometer axes (Galil X / Z / Y / Omega and the Newport XPS-16 trajectory stage) and the single-Omega geometry. | A `Goniometer` (the i03 Smargon precedent); Galil-vs-XPS controller and single Omega are settings. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The XRD detector assignment (Eiger2 9M versus the Pilatus 1M CdTe / Si), the detector 2theta-arm transform (seen only in a Galil test template), and the flux / fluorescence channel map. | The Eiger2 / Pilatus bind `Camera`; the 2theta swing binds `PseudoAxis` (binding deferred); the ion chambers bind `FluxMonitor` and the Dante MCA `EnergyDispersiveSpectrometer`. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles reconstructed from the GSECARS support tree current and correct? | The handles in the descriptor are reconstructed from the support tree and carried confirm at medium confidence. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals, plus the laser-safety enclosure permit. | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the high-pressure gas supply the membrane controller uses. | Photon beam, cooling water, vacuum, and process gas. | The Supply observations. |
| GOV-1 | Nice-to-have | The APS / GSECARS operator pool and safety-review structure. | Carried pending on the APS Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do high-pressure powder and single-crystal diffraction enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `powder_diffraction` (i11) and `diffraction` (4-ID) Methods, with high pressure a Plan-level sample-environment difference; none coined. | The diffraction Capabilities. |
