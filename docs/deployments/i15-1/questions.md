# Open questions

*What CORA needs the I15-1 team (and Diamond's documentation) to confirm before the model can be trusted.*

I15-1 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles; it does not give the calibrated numbers, the hutch / PSS safety meaning, or the Capability / Method binding. This is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Scope, safety, and the modelling decisions

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I15-1 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise? | A generalization exercise; not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the two hutches? dodal records interlock readbacks (BL15I-PS-IOC-02:M11:LOP, BL15I-VA-OMRON-01:INT3:ILK) but not confirmed permits. | Both hutches exist; the dodal interlock readbacks are permit-signal candidates. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones, not the access-gated hutch. | The standard optics + experiment hutch split. | The per-device Enclosure assignment. |
| INTERLOCK-1 | Nice-to-have | Are the PSS / gonio interlocks correctly modelled as the Enclosure `permit_signal` (not as equipment devices)? | Yes: an interlock is the read-only permit behind the Enclosure aggregate, not an Asset. | That interlocks stay on the Enclosure, not the device walk. |
| SAFEBEAM-1 | Blocks-go-live | Are the blower / cobra / cryostream correctly modelled as Positioner + Indexable SAFE/BEAM (not TemperatureController), and is the cobra/cryostream rail-interchange a Fixture-style swap or an Assembly? | Positioner with two named positions; the interchange is a Fixture-style swap (they share the ENV:X rail motor). | The sample-environment actuator shape and the exchange modelling. |
| RAIL-1 | Nice-to-have | Is the rail correctly the existing Table Family, and what are its exchange semantics? | The existing Table Family (the TomoWISE DetectorGantry precedent), not a new Rail kind. | The rail Family and exchange shape. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the I15-1 source (it is a branch line) and its energy range? dodal does not pin it. | A source carried `confirm`; energy range is calibration to supply. | The source and beamline energy range. |
| ENERGY-1 | Blocks-go-live | Is the bent-Laue energy ever a goto-command (driving y to hit a target energy via inverse lookup), or only the fixed-selection read-only readback dodal exposes? | A read-only y-to-energy lookup readback; the pending energy_scan Capability is NOT earnable here. | Whether energy is a commandable axis and whether energy_scan applies. |
| OPT-1 | Nice-to-have | What are the bent-Laue crystal lookup table, the multilayer mirror coating, and the attenuator transmission-vs-foil table? dodal exposes the axes, not the calibrated values. | The optic internals are settings / a bound Model / a Calibration on the existing Families. | The optic calibration. |
| MACHINE-1 | Nice-to-have | How should the storage-ring state be modelled: loose `StorageRing`, observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |
| ATTN-1 | Nice-to-have | Are the ATTN-01 three-stick stage and the ATTN-02 transmission selector two physically distinct attenuator stations, or two control surfaces of one unit? | Two distinct stations (separate EPICS roots), the selector folding into Filter via Indexable named positions. | The attenuator station topology. |

## Sample, detector, technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLUX-1 | Blocks-go-live | How is the incident-flux monitor (the JBPM TetrAMM i0) modelled, and what beam-center calibration does it need? | The existing Sensor Role, carried as the loose `FluxMonitor` family reused from I22 (now a 2nd deployment, building rule-of-three). | The flux-monitor modelling and beam-center. |
| ROBOT-1 | Blocks-go-live | What is the powder/capillary sample-changing robot, how is autonomous loading gated, and what is the puck custody lifecycle? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance, vendor in a bound Model (the I03 / 19-BM shape); not a new Family. | The robot Asset, its Clearance gate, and the Subject custody thread. |
| DET-1 | Blocks-go-live | What are the Eiger threshold energy and beam-center, the two-theta arm geometry, and the second detector translation ranges? | The Eiger reuses `Camera`; calibration to supply. | The detector calibration and arm geometry. |
| TECH-1 | Blocks-go-live | What are the total-scattering / PDF Capability and Methods (binding the mono + Eiger + two-theta arm + the powder robot exchange)? | A new total-scattering Capability not yet in the catalog, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags)? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
