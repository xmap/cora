# Notes

## Techniques

*What CORA would run at HXN: the Capabilities and portable [Catalog](../../catalog/methods.md) Methods, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here).*

HXN does scanning nano-XRF mapping, ptychography, nano-tomography, and spectro-tomography, all variants of one act: raster the sample through the focus and read the per-point detectors. The big modeling question HXN raises is whether scanning and ptychography are new Capabilities or fit existing ones; this scaffold **defers** coining them, following the Diamond i03/i22 and 32-ID precedent (no new Capability coined for a design-phase reverse-engineered deployment until a real conduct-path consumes it).

| HXN technique | CORA expression | Earn-the-abstraction call |
| --- | --- | --- |
| Scanning XRF mapping | Method under `acquisition` (a raster of per-point spectra) | **Defer** coining a `scanning` Capability; trigger = first raster conduct-path, or a 2nd scanning beamline |
| Ptychography | the same raster with a `Camera` in the detector slot + offline reconstruction | **Defer**; ptychography is not its own Capability. The reconstruction is a `ComputePort` leg, not a beamline Method |
| Nano-tomography | [`tomography`](../../catalog/methods.md) | reuse; raster x rotation, the same family as 2-BM/FXI tomography |
| Spectro-tomography | compose `tomography` + energy change | reuse; do not coin `spectro_tomography` |
| XANES / energy change | [`beamline_energy_change`](../../catalog/methods.md) | reuse; but the HXN energy change co-moves the zone-plate refocus per element (ENERGY-1), a richer move than FXI's mono-only change |
| Alignment | [`alignment`](../../catalog/methods.md) | reuse (line-center, knife-edge, center-of-mass) |

The central new shape, **scanning-probe acquisition with multi-modal per-point detection**, is the strongest in-kind argument the catalog has seen for a `scanning` Capability (the raster *is* the measurement, not a frame at a fixed pose). It is held open deliberately, not because it is weak, but because the discipline is to coin a Capability when a conduct-path forces it, not at scaffold time. See [Controls](controls.md) for how CORA's conducting engine would run the raster over the ControlPort and the ptychographic reconstruction over the ComputePort.

## Governance

*Who may act at HXN and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An HXN beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a run, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody; CORA confirms entitlement against the facility's proposal identity but applies its own per-Actor authority on top.

### Agents and the scanning loop

HXN's scanning workflows (auto-alignment, adaptive mapping) are where an autonomous or adaptive Agent would naturally act: proposing the next scan region or correction inside the conduct loop. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each proposed move would be a [Decision](../../architecture/modules/decision/index.md) (the inference-recorder path for any LLM-backed agent). None is declared for HXN yet.

## Model

*The developer's by-kind index: where each CORA aggregate's HXN content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at HXN |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) (3-ID-A optics, 3-ID-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring 32-ID and 7-BM. Left out on purpose:

- **The scanning / ptychography Capabilities.** Coined when a real conduct-path consumes a raster, not at scaffold time (see [Techniques](#techniques)). HXN is the first scanning-probe deployment, so this is the live earn-the-abstraction question, deferred deliberately.
- **`MultilayerLaueLens` catalog graduation.** A loose family at its first sighting (OPTIC-3); graduates at a second MLL beamline.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the HXN team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/hxn-profile-collection`](https://github.com/NSLS2/hxn-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector roster are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build` (changes the model structure), `Blocks-go-live` (needed before CORA controls or observes the hardware), `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU20 undulator period, gap range, and harmonic usage. The device (`SR:C3-ID:G1{IVU20:1}`) is confirmed; parameters are not in source. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs per hutch. Only the photon shutter `XF:03IDB-PPS{PSh}` is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Is the `XF:03IDB` intermediate zone (secondary-source aperture, slow shutter) a distinct enclosure, or part of the endstation? HXN spans three PV zones (3-ID-A/B/C). | Two enclosures (3-ID-A optics, 3-ID-C experiment); 3-ID-B folded. | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | DCM crystal cut and energy range. | A double-crystal monochromator; cut/range blank. | The Monochromator settings. |
| OPTIC-1 | Blocks-go-live | Are the zone plate and the multilayer Laue lens both permanently installed and operator-selected, or is one decommissioned? Both appear in source. | Both modelled, switchable. | The focusing-optic roster. |
| OPTIC-2 | Nice-to-have | Zone-plate parameters (outer-zone width, diameter, material). | A ZonePlate Asset, parameters blank. | The ZonePlate settings. |
| OPTIC-3 | Nice-to-have | Should `MultilayerLaueLens` become a catalog Family? HXN is its only sighting (a 1D crossed-pair lens, distinct from the circular ZonePlate). | A loose family name that renders as text; not yet graduated. | Catalog Family graduation (Federation-scoped). |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The tomographic rotary (`sth`, on an ANC350) hardware, encoder resolution, and max speed. | A RotaryStage, specs blank. | The SampleRotary settings. |
| STAGE-2 | Nice-to-have | Does the SmarAct Smarpod 6-DOF pod fit the `Hexapod` Family (single coordinated parallel-kinematics move)? | Modelled as a Hexapod. | The SamplePod Family fit. |
| DET-1 | Blocks-go-live | The Xspress3 fluorescence detector: vendor (Quantum Detectors?), element count, energy resolution. Source shows 4 channels (C1-C4) plus a second unit. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; specs blank. | The detector Model and element count. |
| CAM-1 | Blocks-go-live | Which pixel detectors are physically installed and active? Source has Merlin (x2), Eiger 1M, and Dexela; some classes are duplicated (`USE_RASMI`-gated). | Merlin1, Eiger1, Dexela1 modelled as Cameras; dormant duplicates excluded. | The detector roster and the per-scan detector slot. |
| DIAG-1 | Nice-to-have | The scaler / ion-chamber flux channel map (which channel is I0 for ptycho normalization). | Read-only flux counters, channel map blank. | The FluxCounter bindings. |

### Controls and techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, serials, and IPs. HXN exposes the controller PVs (Power PMAC `Ppmac:1` + `MC:2-8`; Attocube `ANC350:1-8`), which FXI did not, but vendor/firmware detail is still not in source. | Families bound (MotionController), models named where evident (PMAC, Attocube), specifics blank. | The MotionController Models and Drive identities. |
| ZEBRA-1 | Nice-to-have | Is `nanoZebra` (`Zeb:3`) the live trigger master, and is the PandABox (`67-nano-panda`, currently partly commented) the go-forward box? | One live Zebra; PandA deferred. | The TimingController set. |
| ENERGY-1 | Nice-to-have | Does an energy change co-move the zone-plate refocus per element edge, and is that table operator-data or a CORA Calibration? | Energy axis drives the monochromator; the optic co-move is noted, not modelled. | The energy-change Method shape. |
