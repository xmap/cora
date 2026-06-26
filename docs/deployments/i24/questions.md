# Open questions

*What CORA needs the i24 team to confirm before the model can be trusted.*

i24 was reverse-engineered from Diamond's open controls library ([dodal](https://github.com/DiamondLightSource/dodal), `src/dodal/beamlines/i24.py` and its device classes), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the source rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The i24 insertion-device source (gap, type), which dodal does not expose as a device here. | An undulator source; only the Synchrotron machine state is read. | The source Asset detail. |
| ENC-1 | Blocks-go-live | Is i24 one optics hutch plus one experiment hutch, or a different enclosure split? | Two enclosures: i24-optics and i24-experiment. | The Enclosure grouping. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The machine source state i24 reads (ring current, top-up, mode) and its PVs. | Observe-only via dodal's Synchrotron device, a loose `StorageRing`. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut, d-spacing, and incident-energy range. | A double-crystal monochromator on `BL24I-MO-DCM-01:`; values pending. | The monochromator Asset. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the selectable focus modes. | Focusing mirrors bound to `Mirror` (dodal FocusMirrorsMode); modes pending. | The mirror Asset detail. |
| ATTN-1 | Nice-to-have | The attenuator filter set and transmission levels. | A filter-based attenuator bound to `Filter`, not a new kind (the I03 / i15-1 precedent). | The attenuator Asset. |
| OPT-2 | Nice-to-have | The aperture, beamstop, and detector-stage axis roles. | Beam-defining aperture / positioned beamstop / detector translation; axes pending. | The optic Asset detail. |

## Sample and serial collection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The vertical goniometer circle and pin-translation axes. | A vertical pin goniometer bound to the catalog `Goniometer`; axes pending. | The goniometer Asset. |
| CHIP-1 | Blocks-build | How is the fixed-target chip addressed: the grid geometry, the well / aperture layout, and how a collection window maps to a stage position? | An addressable chip on the XYZ chip stage; the grid map lives in beamline software, not a PV. | The chip addressing; the CORA Fixture / Subject-grid modelling is on [Model](model.md#deliberately-not-here-yet). |
| SSX-1 | Blocks-go-live | The serial-collection sequence: the raster pattern, the per-window dwell, and the laser / Zebra trigger timing. Does serial crystallography enter CORA's catalog as a Capability? | A triggered chip-raster fly-collection; the Capability is deferred, the Practice rendered pending. | The serial-collection shape; the CORA Capability is on [Model](model.md#deliberately-not-here-yet). |
| LASER-1 | Nice-to-have | The PMAC-controlled lasers: are they a pump-probe excitation source CORA should model, or only a trigger setting and a hazard? | Carried as a trigger setting on the chip-collection seam, not a device; modelling deferred. | The laser model or hazard treatment. |
| BACKLIGHT-1 | Nice-to-have | The dual backlight PV root and its positions. | Reuses I03's loose `Backlight` family; the root `BL24I` and positions pending. | The backlight Asset. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector configuration: the Eiger as the production detector, the Jungfrau as commissioning, and the beam-centre. | Eiger is the primary `Camera` (Detector Role); Jungfrau carried as commissioning. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals behind the interlocked hutch shutter. | The hutch shutter is dodal's InterlockedHutchShutter; the permit leaves are to be named, not invented here. | The Enclosure permit signals. |
| SUP-1 | Nice-to-have | The vacuum extent and the facility supplies a run draws on. | Photon beam, cooling water, and vacuum on the optics path. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |
