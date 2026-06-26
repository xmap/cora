# Open questions

*What CORA needs the I20-1 team to confirm. This model is reverse-engineered from the public dodal controls library (`src/dodal/beamlines/p51.py`, the i20-1 commissioning module): the EPICS PVs are read from it, but it is a thin commissioning roster and the dispersive heart of EDE is not in it. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## The dispersive heart (absent from source)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POLY-1 | Blocks-build | The bent-crystal polychromator that fans the energy band across the sample, the defining EDE optic. It is not in the dodal module (only the turbo slit at the polychromator enclosure `BL51P-OP-PCHRO-01` is). What are its PVs and axes (crystal bend, Bragg, position)? It is a genuinely new optic class (an energy-dispersing bent crystal, distinct from a Monochromator); CORA would weigh a new `Polychromator` Family once it is PV-bound. | Not modelled; named here, no Family coined without a source PV. | The polychromator Asset and a possible new Family. |
| STRIP-1 | Blocks-build | The position-sensitive strip detector that reads the dispersed absorption spectrum in one shot, the EDE primary detector (e.g. an XH / germanium microstrip). It is not in the dodal module. What is its PV, and does it fit `Camera` (a 1D frame) or warrant a new detector class? | Not modelled; named here, no device coined without a source PV. | The strip-detector Asset and its family. |

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device source, front-end, and primary mirror: none is in the commissioning module. The PV root `BL51P` would carry them. | An insertion-device source, identity-only, no PV. | The Source and front-optics Assets. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs (not in the dodal module). | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names (the dodal module exposes no enclosure structure). | An optics hutch plus an experiment hutch. | The Enclosure set and roles. |

## Sample, detector, controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The sample alignment stage axis set and reconnection: the dodal module constructs `alignment_x` / `alignment_y` (`BL51P-MO-STAGE-01:X` / `Y`) as a mock, noting the motors are being reconnected on the beamline. | A `Manipulator` Asset (X / Y); the PVs are real but not yet connected. | The SampleStage axes and live PVs. |
| DET-1 | Nice-to-have | The Xspress3 fluorescence detector (`BL51P-EA-DET-03:`, 16-channel) is defined but constructed with `skip=True` in dodal (not loaded by default). Is it live, and what is the I0 / It / ion-chamber flux chain (none is in the module)? | One `EnergyDispersiveSpectrometer` Asset; flux chain blank. | The detector roster and flux monitors. |
| DRIVE-1 | Blocks-go-live | The PMAC trajectory controller (`BL51P-MO-STEP-06:`) and PandA box (`BL51P-EA-PANDA-01/02:`) firmware / IPs. | Families bound (MotionController, TimingController), specifics blank. | The controller Models. |
| TECH-1 | Blocks-go-live | Does the energy-dispersive-EXAFS Capability enter CORA's catalog, or stay deferred? It is the dispersive complement to the scanning-XAS / energy-scan question (the BMM ENERGY-1 cohort). | The EDE Method is a pending Practice, not yet in the catalog. | The EDE Capability scope. |
