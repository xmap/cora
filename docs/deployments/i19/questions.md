# Open questions

*What CORA needs the i19 team to confirm before the model can be trusted.*

i19 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i19*.py` factories and the `src/dodal/devices/` classes), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology, scope, and the dual-hutch seam

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The EH1 / EH2 grouping: which experiment hutch holds the four-circle and the Eiger, and which holds the on-axis viewing, and how the two hutches sit relative to the shared optics. | A shared `i19-optics` zone feeding two experiment hutches `i19-1` (EH1) and `i19-2` (EH2); the four-circle in EH2. | The Enclosure grouping. |
| ACCESS-1 | Blocks-go-live | The dual-hutch shared-optics access-control: only the active hutch may drive the shared optics, enforced by the i19-blueapi optics arbiter against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`). How should CORA represent the active-hutch permit and the arbiter? | An Enclosure-permit + Trust-gate over the shared-optics Assets, with the arbiter as an actuate-floor seam partner (the "EPICS is the floor" pattern). | The governance seam; the CORA modelling is on [Model](model.md#the-dual-hutch-access-control-seam). |
| SRC-1 | Nice-to-have | The undulator period and type (`SR19I-MO-SERVC-01`). | An undulator coordinated with the DCM on an energy move; period pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i19 reads (current, fill). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut, the energy / wavelength range, and the energy partition rule (the variable-wavelength capability). | A double-crystal `Monochromator`; the energy is a `PseudoAxis` over the DCM and undulator; range pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the stripe energy bands (Si / Rh / Pt), and whether the stripe is hutch-keyed. | Focusing mirrors bound to `Mirror`; coating stripe a hutch-keyed setting (Si 5-10, Rh 10-20, Pt 20-30 keV). | The mirror Asset detail. |
| ATTN-1 | Nice-to-have | The absorber-wedge attenuator and whether it folds into `Filter` or earns a distinct `Attenuator` kind (the fleet-wide question). | The wedge absorber bound to `Filter` (the i03 precedent). | The attenuator's catalog home. |

## Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The Newport kappa four-circle circle roles (phi / omega / kappa sample circles, the 2theta detector arm, det_z, the sample centring) and whether they compose an Assembly. | A `Goniometer` (kappa a setting) plus a 2theta detector arm; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the four-circle (the kappa-to-eulerian / hkl rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / i06-1. | The reciprocal-space Asset. |
| SERIAL-1 | Nice-to-have | The serial / microfocus fixed-target arm (`BL19I-MO-SRL-01`, x / y / z / phi) and its raster sub-mode. | A second `Goniometer` for the serial / microfocus delivery; the fixed-target raster carried as a note. | The serial-arm modelling. |
| APERTURE-1 | Nice-to-have | The MAPT pinhole + collimator microfocus aperture and whether it binds `Aperture` (the i03 MAPT precedent) despite being a driven, size-selectable opening. | The pinhole + collimator bound to `Aperture`, the configuration sizes a Capability settings schema. | The aperture Family. |
| DET-1 | Blocks-go-live | The Eiger detector model, the OAV viewing-camera roles, the beamstops, and the backlight. | The Eiger and OAVs bind `Camera`; the beamstops bind `BeamStop`; the backlight reuses the loose `Backlight`. | The detector and viewing modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct, and is the i19-blueapi arbiter the live optics-control path? | The handles in the descriptor are taken from dodal and carried confirm; the arbiter is the actuate seam (ACCESS-1). | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from dodal beyond the interlocked optics shutter). | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the shared optics. | Photon beam, cooling water, and vacuum on the optics. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does single-crystal diffraction (chemical crystallography) enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` Method that 4-ID / 8-ID / CSX share; none coined. | The diffraction Capability. |
