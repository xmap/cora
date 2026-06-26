# Open questions

*What CORA needs the 4-ID POLAR team to confirm before the model can be trusted.*

4-ID POLAR was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/polar-bits](https://github.com/BCDA-APS/polar-bits)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, but read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](model.md#deliberately-not-here-yet) instead, including which loose Families graduate and the diffractometer Assembly). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Do the three experiment stations (`4-ID-B`, `4-ID-G`, `4-ID-H`) run off one beam in series, or are any canted / branched off separate beams? Which optics are shared versus per-station? | One root Unit Asset `4-ID POLAR` with one optics spine feeding the three stations; KB mirrors and filters are per-station. | One-vs-many beam walks and the shared-vs-per-station optics split in the [descriptor](inventory.md). |
| TOPO-2 | Blocks-go-live | The `4-ID-Raman` station: what instruments and devices does it carry? (Its `devices.yml` is a symlink that did not resolve in the source clone, so it did not extract.) | The Raman station exists but is out of this cut. | The Raman station devices and a fifth enclosure if warranted. |
| TOPO-3 | Nice-to-have | Two PVs gave ambiguous station hints: `4iddMZ0:` (the SGZ Vortex detector) and `4idkepco:` (a Kepco magnet supply). What station does each sit in? | The Vortex is placed at `4-ID-G` and the Kepco magnet at `4-ID-G`, both confirm. No `4-ID-D` / `4-ID-K` enclosures are declared. | The station assignment for those two devices. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the polar-bits config current and correct for each device? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | What are the PSS search-and-secure permit signals for the four hutches (`4-ID-A/B/G/H`)? | Four hutches exist with permit signals to be named. | The Enclosure permit signals. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The undulator pair on S04ID: device types, periods, and gaps. | One `InsertionDevice` Asset for the pair (`PolarUndulatorPair`); periods unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | Should the pair be one Asset or two (one per undulator)? | Modelled as one Asset. | One-vs-two source Assets. |
| MONO-1 | Blocks-go-live | The VDCM monochromator: energy range, crystal set behind `crystal_select`, and per-axis roles. | One `Monochromator` Asset (4idVDCM) with a crystal-select axis; range unconfirmed. | The monochromator energy model. |
| OPT-1 | Nice-to-have | The toroidal pre-focusing mirror and the HHL bendable mirror: coatings, stripes, and the bender / piezo axis roles. | Two `Mirror` Assets; the HHL axis map is taken from the config, coatings unconfirmed. | The mirror specs. |
| OPT-2 | Blocks-go-live | The transfocator (`4idPyCRL:CRL4ID:`): lens material, count, and which stations it focuses. | One `Transfocator` Asset (catalog Family); serves 4-ID-G and 4-ID-H. | The transfocator spec. |
| OPT-3 | Nice-to-have | The per-station KB mirror (`bkb`/`gkb`/`hkb`) internal axis maps. | Three `Mirror` Assets; only the 4-ID-B KB carries a partial axis map. | The KB axis maps. |

## Polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POL-1 | Blocks-go-live | The three phase retarders (`pr1`/`pr2`/`pr3`): diamond crystal type, thickness, and how they coordinate to set a polarization state. | Three `PhaseRetarder` Assets (loose Family), each th/x/y, energy-tracking. | The phase-retarder specs and the polarization-state model. |
| POL-2 | Blocks-go-live | The polarization analyzer (`pol`, th/y): analyzer crystal and the scattered-beam polarization it resolves. | One `PolarizationAnalyzer` Asset (loose Family) at 4-ID-B. | The analyzer spec. |

## Diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The Huber Eulerian and high-pressure diffractometers: the real circle set (4-circle Eulerian? 6-circle?) and which motor is which circle (omega, chi, phi, two-theta). | Two diffractometers modelled as plain devices with the config's axis maps; the circle roles are partial. | The circle geometry, which decides the `Assembly(Diffractometer)` slot shape (see [Model](model.md#deliberately-not-here-yet)). |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: is hklpy2 driving an (h, k, l, energy) pseudo-axis, and over what geometry? | A reciprocal-space PseudoAxis is assumed for the Assembly design; not yet a device. | The pseudo-axis model. |

## Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The sample magnets: the two 2 T magnets (`bmag`/`emag`) and the high-field magnet (`magnet911`) field ranges and control PVs (the 2 T magnets had no control PV in the config), and the Kepco-driven `gmag`. | Four `Magnet` Assets (loose Family); fields and several PVs unconfirmed. | The magnet specs and handles. |
| TEMP-1 | Nice-to-have | The LakeShore 336 and 340 controllers: sensor channels and the sample stages they regulate. | Two `TemperatureController` Assets (catalog Family, presents `Regulator`) at 4-ID-G. | The temperature-controller model. |
| SAMPLE-1 | Nice-to-have | The Ventus laser at 4-ID-H: is it a pump-probe source CORA should model as a device, or only carry as a Clearance hazard? | One `Laser` Asset (loose Family); modelling-versus-hazard is open. | The laser model or hazard treatment. |
| SAMPLE-2 | Nice-to-have | The preamplifiers, lock-in (`srs810`), and high-pressure-cell controllers (Pace `PC1`/`PC2`) are in the config but not modelled here. Which are beamline equipment versus user-brought? | Deferred as peripheral. | Whether these become Assets. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Eiger area detector model, sensor, and frame rate. | One `Camera` Asset (`4idEiger:`); model unconfirmed. | The detector Model binding. |
| DET-2 | Nice-to-have | The SGZ Vortex (`4iddMZ0:`): is it a fluorescence / energy-dispersive point detector, and what Family fits? | Bound to a loose `BeamPositionMonitor` Family as a placeholder; classification unconfirmed (see `TOPO-3`). | The Vortex classification and Family. |

## Beam-position monitors and supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BPM-1 | Nice-to-have | The XBPMs, Sydor electrometers, and TetrAMM: which are true beam-position monitors versus intensity (I0) normalizers? | All bound to a loose `BeamPositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| SUP-1 | Nice-to-have | The cryogen and process-gas supplies the magnet and low-temperature environments draw on. | Liquid helium and liquid nitrogen carried pending in the descriptor. | The Supply records. |
