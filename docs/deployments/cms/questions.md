# Open questions

*What CORA needs the CMS team to confirm before the model can be trusted.*

CMS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/cms-profile-collection](https://github.com/NSLS2/cms-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones XF:11BMA (first optics) and XF:11BMB (endstation) two separate hutches? | Two enclosures: a `cms-optics` zone and the `cms-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 11-BM source: a bending magnet or a three-pole wiggler (absent from the profile collection as a device). | A bending-magnet source, observed only through the machine state. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state CMS reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DMM multilayer d-spacing, the energy range (calibrations near 13.5 keV), and the energy partition rule. | A double-multilayer `Monochromator`; the energy is a `PseudoAxis` over the Bragg angle; d-spacing pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The toroidal and elliptical mirror coatings and bend mechanisms. | Focusing mirrors bound to `Mirror`; coatings and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (the FOE slit and the five endstation JJ slits, including the s4 transmission / grazing geometry presets). | Four-blade and center / gap slits bound to `Slit`. | The slit Asset detail. |
| ATTN-1 | Nice-to-have | The attenuator foil set (the eight pneumatic absorbers) and whether it folds into `Filter` or earns a distinct `Attenuator` kind (the fleet-wide question). | The foils bound to `Filter` (the i03 / i15-1 precedent). | The attenuator's catalog home. |

## Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-goniometer axes, the grazing / specular incidence axis (the historical sth versus schi swap), and the chamber rebinding (the beamline_stage configurations remap the logical axes across physical PVs at startup). | A `Goniometer` with sth as the incidence axis; the swap and the rebinding carried as settings. | The sample-stage modelling. |
| ROBOT-1 | Nice-to-have | The GIBar sample-exchange arm (a multi-axis sample-bar loader) and whether it earns a `SampleExchanger` Family or stays modelled as stage axes. | Modelled as `LinearStage` / `RotaryStage` axes at n=1; no `SampleExchanger` Family coined pending a second fleet sample robot. | The sample-exchange modelling; the CORA family decision is on [Model](model.md#deliberately-not-here-yet). |
| TEMP-1 | Nice-to-have | The Linkam thermal / tensile stage temperature range and the tensile-load axis. | A `TemperatureController` Asset presenting the `Regulator` Role; range and load axis pending. | The temperature-environment modelling. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SAXS / WAXS / MAXS Pilatus detector assignment (which 800K head is powered per configuration), the detector-distance calibrations, and the flux / beam-position channel map. | Three `Camera` Assets (Pilatus 2M SAXS, two 800K WAXS / MAXS); the monitors bind `FluxMonitor` and the diode beam-position monitor the loose `BeamPositionMonitor`. | The detector modelling. |
| XR-1 | Blocks-go-live | The specular reflectivity (XR) realization: a fixed area detector read over a software region-of-interest tracking the reflected beam as the sample theta is stepped, with no physical two-theta arm. | XR is a Method over `Goniometer` (sth) + `Camera` (the Pilatus region) + `FluxMonitor`; no device coined; the reflectivity Method is shared with i10. | The reflectivity modelling; the CORA decision is on [Model](model.md#deliberately-not-here-yet). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics, the sample chamber, the SAXS flight path) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the scattering and reflectivity techniques (SAXS, WAXS, GISAXS, XR) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; the scattering Methods are shared with i22 / SMI / 9-ID and the reflectivity Method with i10; none coined. | The technique Capabilities. |
