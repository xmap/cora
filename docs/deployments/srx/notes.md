# Notes

## Techniques

*What CORA would run at SRX, several techniques on one beamline, each a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). SRX exercises the multi-Capability-per-beamline shape.*

SRX is a microprobe that does much: it maps elements, scans absorption edges, reconstructs 3D element distributions, takes diffraction, and images. The point for CORA is that all of this reuses Capabilities and Families the fleet already has, the techniques compose from existing parts rather than forcing new vocabulary.

| SRX technique | CORA expression | Reuse note |
| --- | --- | --- |
| Scanning XRF mapping | a raster reading the `EnergyDispersiveSpectrometer` | the HXN scanning shape; `scanning` Capability deferred (ENERGY-1 cohort) |
| XANES | an energy sweep over the `EnergyAxis` | the BMM energy-scan question; `energy_scan` deferred |
| XRF-tomography | [`tomography`](../../catalog/methods.md), raster x rotation | reuse; XRF maps at each angle |
| Diffraction | a raster/exposure reading a `Camera` pixel detector | reuse; the technique is the detector choice |
| Full-field imaging | the PCO `Camera` | reuse; the FXI/2-BM imaging shape |
| Alignment | beam, KB, and slit tuning | reuse [`alignment`](../../catalog/methods.md) |

### The multi-Capability-per-beamline shape

SRX is the first deployment where one beamline carries several distinct techniques at once. In CORA terms, one Unit Asset presents the equipment for multiple Capabilities (imaging, scanning XRF, energy-scan spectroscopy, tomography, diffraction), and a measurement selects the Capability plus the detector(s) it needs from the shared set. Nothing here is new vocabulary: it reinforces that the Capability/Method layer composes, the same `tomography` Method that serves 2-BM serves SRX's XRF-tomography (with a different detector in the slot), and the `EnergyDispersiveSpectrometer` that BMM uses for transmission-reference fluorescence serves SRX's XRF mapping.

Two Capabilities stay deferred, exactly as their originating beamlines left them: `scanning` (HXN) and `energy_scan` (BMM). SRX reinforces the case for both without coining either, per the design-phase discipline. The reconstruction/fitting legs (XRF fitting, tomographic reconstruction) are `ComputePort` work, not beamline Methods.

## Governance

*Who may act at SRX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An SRX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a scan, switch technique, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### Multi-technique and agents

SRX's breadth (a user may map, then scan an edge, then take a tomogram in one beamtime) is a place where an autonomous Agent could choose the next technique or region. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each choice would be a [Decision](../../architecture/modules/decision/index.md). SRX also carries an auto-alignment routine in source; conducted by CORA, that is the engine's, with any agent-proposed corrections recorded as Decisions. None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's SRX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SRX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) (5-ID-A optics, 5-ID-D nano endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN, BMM, and the Diamond beamlines. Left out on purpose:

- **No new Family or Capability.** SRX is the reuse-and-reinforce deployment: every device binds an existing catalog Family (`EnergyDispersiveSpectrometer`, `FluxMonitor`, `TemperatureController` among the recently-graduated ones), and the techniques compose from existing Capabilities. The deferred `scanning` (HXN) and `energy_scan` (BMM) Capabilities are reinforced, not coined, here.
- **The micro endstation.** SRX has a micro endstation (05IDB) alongside the nano (KB) endstation modelled here; it is noted and deferred (ENDSTATION-1), the way 32-ID modelled one of several instruments.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the SRX team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/srx-profile-collection`](https://github.com/NSLS2/srx-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector/endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU21 undulator period, gap range, and harmonic usage. The device (`SR:C5-ID:G1{IVU21:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:05ID-PPS{Sh:WB}`, `05IDA-PPS:1{PSh:2}`, `05IDB-PPS:1{PSh:4}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout: which PV zones (05IDA optics, 05IDB micro endstation, 05IDD nano endstation) are distinct enclosures? | Two enclosures, optics + experiment (nano). | The Enclosure set and roles. |

### Optics and sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HDCM crystal cut and energy range. | High-heat-load DCM, range blank. | The Monochromator settings. |
| STAGE-1 | Blocks-go-live | The XRF-tomography sample rotation hardware, encoder resolution, and max speed. | A RotaryStage, specs blank. | The SampleRotary settings. |
| ENDSTATION-1 | Nice-to-have | The micro endstation (05IDB): is it a distinct sample stack from the nano endstation modelled here, and how are the two selected? | The nano (KB) endstation is modelled; the micro endstation is noted, deferred. | The micro-endstation Assets. |

### Detectors and controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Xspress3 fluorescence detector element count and vendor. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; specs blank. | The detector Model and element count. |
| CAM-1 | Blocks-go-live | Which pixel/area detectors are live vs legacy? Source has Merlin, Dexela, Eiger 1M, a PCO imaging camera, and legacy detectors. | Merlin/Dexela/Eiger/PCO modelled as Cameras; legacy excluded. | The detector roster and per-technique detector slot. |
| DIAG-1 | Nice-to-have | The scaler / ion-chamber flux channel map (which channel is I0). | Read-only flux counters (`FluxMonitor`), channel map blank. | The FluxCounter bindings. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| ENERGY-1 | Nice-to-have | Does SRX's XANES sweep warrant the `energy_scan` Capability the catalog anticipates (shared with BMM), or stay under `characterization`? | XANES mapped to existing Capabilities; energy_scan deferred (the BMM question). | The spectroscopy Capability decision. |
