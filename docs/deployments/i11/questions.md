# Open questions

*What CORA needs the I11 team (and Diamond's documentation) to confirm before the model can be trusted.*

I11 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles; it does not give the calibrated numbers, the hutch / PSS safety meaning, or the Capability / Method binding. This is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I11 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise? | A generalization exercise; not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the two hutches? | Both hutches exist; permit signals to be named. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones, not the access-gated hutch. | The standard optics + experiment hutch split. | The per-device Enclosure assignment. |

## The thermal earn (the headline)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TEMP-1 | Blocks-go-live | I11's four continuous-setpoint thermal actuators (the two Cyberstar/Eurotherm blowers + two cryostreams) make `TemperatureController` rule-of-three (after I22 + I03). Should CORA graduate the `TemperatureController` Family AND earn a new settable-continuous-setpoint actuator Role? | Yes, both are earned, but the Role is a code change (`SEED_ROLES`, drift-guarded) + core vocabulary, so it is routed to a SEPARATE gate-reviewed change; carried loose here. | The TemperatureController graduation and the settable-actuator Role, via gate-review. |

## Source, optics, diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the I11 source and its energy range? dodal does not pin it (the Synchrotron device is facility-wide, observe-only). | A source carried `confirm`; energy range is calibration to supply. | The source and beamline energy range. |
| OPT-1 | Nice-to-have | What are the DCM crystal d-spacing and thermal model? dodal exposes the axes and the Si(111) default, not the calibrated values. | Settings / a bound Model on the existing Monochromator Family. | The mono calibration. |
| MACHINE-1 | Nice-to-have | How should the storage-ring state be modelled: loose `StorageRing`, observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |
| GONIO-1 | Nice-to-have | Is the diffractometer (theta / two_theta / delta) correctly modelled as per-axis `RotaryStage` (not the I03-graduated `Goniometer`)? | Yes: theta is a sample rotation and two_theta / delta are detector-arm angles, not an MX orientation cradle. | That the diffractometer stays RotaryStage, not Goniometer. |
| DIFF-1 | Blocks-go-live | What are the diffractometer axis PVs and ranges (the dodal class was not read axis-by-axis), and the detector-arm geometry? | Per-axis RotaryStage under a DiffractometerStage Assembly; axes to confirm. | The diffractometer per-axis Assets and geometry. |
| SPIN-1 | Nice-to-have | Is the capillary spinner correctly a `RotaryStage` (a sample-rotation device for powder averaging), and what speed range? | Yes, a RotaryStage; speed is calibration. | The spinner modelling and speed range. |

## Detector, robot, technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MYTHEN-1 | Blocks-go-live | How is the Mythen3 (a 1D position-sensitive strip detector) modelled: reuse `Camera` (Detector Role), or does a strip / PSD warrant a distinct shape? And what are its threshold / deadtime values? It is skip-flagged in dodal (issue I11-916). | Reuse `Camera` / Detector Role, with the strip-vs-2D nuance noted; calibration to supply. | The strip-detector Role choice and calibration. |
| ROBOT-1 | Blocks-go-live | What is the sample-changing robot + carousel, how is autonomous loading gated, and what is the sample custody lifecycle? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance, vendor in a bound Model (the I03 / 19-BM shape); not a new Family. | The robot Asset, its Clearance gate, and the Subject custody thread. |
| TECH-1 | Blocks-go-live | What is the powder-diffraction Capability and its Methods (binding the diffractometer + Mythen3 + spinner, often over a temperature ramp)? | A new powder-diffraction Capability not yet in the catalog, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags)? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
