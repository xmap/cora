# Open questions

*What CORA needs the i10 team to confirm before the model can be trusted.*

i10 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i10*.py` factories and the `src/dodal/devices/` classes), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones BL10I (optics spine), ME01D (RASOR), and BL10J (i10-1) three separate hutches, and how do the two endstations share the source? | Three enclosures: a shared `i10-optics` zone and the `i10-rasor` and `i10-1` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The two APPLE-II undulator periods, the gap range, and how the downstream (IDD) and upstream (IDU) devices feed the branches. | Two `InsertionDevice` Assets; period carried pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i10 reads (current, energy, fill). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The plane-grating monochromator gratings, the cff constant, and the incident-energy range and partition rule. | A soft X-ray PGM bound to `GratingMonochromator`; gratings and range pending. | The monochromator and incident-energy Assets. |

## Beam axes: energy and polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENERGY-1 | Nice-to-have | Both APPLE-IIs are driven sources (energy_dd over IDD, energy_ud over IDU); should CORA carry one incident-energy axis or two, and how do they map to the branches? | One `BeamEnergy` `PseudoAxis` over the PGM and the APPLE-II gap; the two-source wiring pending. | The incident-energy Asset wiring. |
| POL-1 | Blocks-go-live | The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants and the continuous linear-arbitrary-angle) and the polarization-to-phase conversion: pin it as a CORA Calibration, or run the axis rule-less and let the live controller own it? | A `PseudoAxis` over the APPLE-II phase rows; the linear-arbitrary-angle is the continuous realization of LA in the same axis; rule-less by default. | The polarization-axis modelling. |

## RASOR endstation (i10-rasor)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The RASOR diffractometer circle roles (two-theta scattering arm, sample theta / chi, chamber X, alpha) and whether they compose an Assembly. | A `Goniometer` for the sample circles; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the RASOR circles (the inverse-kinematics rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / i06-1. | The reciprocal-space Asset. |
| POL-2 | Blocks-go-live | Does RASOR run genuine polarization analysis on the PaStage (the POLAN arm), and is the loose `PolarizationAnalyzer` Family the right home, or does the analyzer arm fold into a detector-arm stage with the crystal as a setting? | The PaStage binds the loose `PolarizationAnalyzer`, its second sighting after 4-ID; dodal exposes the motors only, the analyzer crystal is implicit; the Family is held under review. | The analyzer Family; the CORA promotion decision is on [Model](model.md#loose-families-at-a-second-sighting). |
| STAGE-1 | Nice-to-have | Whether the cryostat sample stage warrants a `Manipulator` rather than `LinearStage`, and whether the pinhole is an `Aperture` or a plain stage. | The sample stage bound to `LinearStage` (plain in-air translation); the pinhole bound to `Aperture`. | The sample-stage and pinhole Families. |
| TEMP-1 | Nice-to-have | The Lakeshore 340 (RASOR) and Lakeshore 336 (i10-1) temperature ranges and channel assignment. | Two `TemperatureController` Assets presenting the `Regulator` Role; ranges pending. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The RASOR and i10-1 detection: no area detector exists in dodal, only the current-amplifier / scaler point-counting chains (monitor, scattered-beam point detector, fluorescence, drain-current / total-electron-yield). Is the point detector best a `FluxMonitor`, or does scattered-beam point-counting earn its own Sensor Family? | The scattered-beam point detector and the monitor / fluorescence / yield channels bind `FluxMonitor`; no detector Family invented. | The detector modelling. |

## i10-1 magnet endstation (i10-1)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The i10-1 electromagnet and superconducting field-sweep magnet (field ranges, the sweep mode), and the low-temperature environment; and whether the loose `Magnet` Family is the right home at its second sighting. | The two magnets bind the loose `Magnet` (one Family, the sweep is a per-Asset affordance); held under review after 4-ID; the cryostat folds into the stage. | The magnet modelling; the CORA promotion decision is on [Model](model.md#loose-families-at-a-second-sighting). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from dodal). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the soft X-ray optics and the UHV endstations) and the cooling supply. | Photon beam, cooling water, and ultra-high vacuum on the optics and endstations. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the resonant-scattering, reflectivity, and magnetic-dichroism techniques (RSXS, soft X-ray reflectivity, XMCD, XMLD) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; resonant scattering and XMCD share the 4-ID Methods, XMLD shares the i06 slug, reflectivity is a new pending slug; none coined. | The technique Capabilities. |
