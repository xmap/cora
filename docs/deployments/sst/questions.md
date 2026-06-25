# Open questions

*What CORA needs the SST team to confirm before the model can be trusted.*

SST was reverse-engineered from the beamline's own bluesky profile collections (RSoXS + HAXPES) and the shared [NSLS-II-SST/sst-base](https://github.com/NSLS-II-SST/sst-base) library, so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, combined from the `devices.toml` instance prefixes and the library's per-axis grammar rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (EPU60 soft on `SST1:1`, U42 tender on `SST2:1`): periods, polarization model, and how the tender U42 couples to the DCM energy. | Two `InsertionDevice` Assets; phase carried as a setting. | The insertion-device specs. |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:07IDA` / `07ID1` / `07ID2` / `07ID6` / `07ID-ES` separate shielded hutches, and how do they group into the soft / tender branches? | A shared FOE enclosure plus an SST-1 and an SST-2 branch enclosure. | The Enclosure grouping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the config-driven PV handles (devices.toml prefix + sst-base class suffix) current and correct? | The handles in the descriptor are taken from the profile + library and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the shutters are `XF:07ID-PPS{Sh:FE}` and `XF:07IDA-PPS{PSh:4/7/10}`. | The Enclosure permit signals. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Blocks-go-live | The soft PGM (grating line densities, c-value, 71-2250 eV) and the tender Si DCM (crystal set, energy range). | A `GratingMonochromator` (soft) and a `Monochromator` (tender Si DCM). | The monochromator models. |
| OPT-1 | Nice-to-have | The mirrors (M1 FOE, L1 / L2AB tender): coatings, stripes, and the hexapod axis roles. | `Mirror` Assets with the FMB hexapod axis grammar; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The quad slits (FOE, HAXPES analyzed-spot): the blade axis maps. | `Slit` Assets (top/bottom/inboard/outboard blades). | The slit axis maps. |

## Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The RSoXS and HAXPES UHV manipulators: the axis maps, the base pressure, and any cryo / sample-transfer. | Two `Manipulator` Assets (x/y/z + a rotation). | The sample-environment models. |
| PES-1 | Blocks-go-live | The HAXPES Scienta SES analyzer (`XF:07ID-ES-SES`): the model, the lens modes, and the pass-energy / kinetic-energy controls. | An `ElectronAnalyzer` Asset presenting the Detector Role. | The analyzer model. |
| DET-1 | Blocks-go-live | The RSoXS Greateyes WAXS detector, the I0 monitors, and the I400 ion chamber: models and the full channel set (only one I400 channel is instantiated in the profile). | `Camera` + `FluxMonitor` Assets; the I400 channel set carried confirm. | The detector models and channels. |
