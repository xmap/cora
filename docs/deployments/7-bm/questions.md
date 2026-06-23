# Open questions

*What CORA needs the 7-BM team to confirm before the model can be trusted.*

7-BM is in the design phase and its operations documentation is partial, so this page is long by design: almost every value in the [Inventory](inventory.md) is taken from the 7-BM docs or inferred, not confirmed with staff. Each row below is a fact the beamline team owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

A note on what 7-BM tests that 2-BM did not: 7-BM is multi-technique (high-speed imaging, radiography, tomography, energy-dispersive diffraction, fluorescence), runs white, monochromatic, and focused beam, and carries a flow and combustion sample environment. The questions below concentrate on the new shapes; the tomography path itself reuses the 2-BM model unchanged.

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV handles for each device? | Control handles are unassigned; CORA leaves the device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS search-and-secure permit signals for the 7-BM-A and 7-BM-B hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |
| HAZ-1 | Blocks-go-live | Do combustion, flammable-gas, or radioactive-check-source experiments need a review / approve / expire workflow distinct from the standard APS ESAF clearance? | The flow and combustion hazard surface is handled by ESAF clearances plus operator Cautions plus alarms, not a separate hazard aggregate. | Whether a Hazard lifecycle is earned beyond Clearance and Caution. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the 7-BM source after APS-U? The docs do not state it. | A bending-magnet source, carried `confirm`, mirroring the 2-BM source representation. | The `Source` device and beamline `source` field. |
| BEAM-1 | Blocks-build | Which beam mode (white, monochromatic via the DMM, or focused via the KB mirrors) is canonical for each technique, and is the DMM split-stripe dual-energy mode used routinely? | Beam mode is a per-technique choice over one set of optics, not a fixed source property. | Binding each technique and Practice to a beam mode. |
| OPT-1 | Nice-to-have | Which optics sit in the routine pilot path: the DMM, the multilayer mirror, the KB focusing pair, the polycapillary optics, and the channel-cut calibration crystals? | The DMM, multilayer mirror, and KB pair are modelled; the polycapillary and channel-cut crystals are deferred until a confirmed technique needs them. | Which optics are Assets and which stay deferred. |
| CHOP-1 | Blocks-go-live | Is the rotary chopper permanently installed or fitted per time-resolved run, is its duty cycle a commanded setting or a manual mechanical re-index, and is the photoeye a tracked Sensor or inseparable floor wiring? | A loose `Chopper` family, pending whether it is a new catalog Family or an existing `Shutter` / `RotaryStage` plus settings. | The chopper modelling boundary. |

## Techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which techniques are in scope for the CORA pilot: tomography, high-speed imaging, radiography, energy-dispersive diffraction, confocal fluorescence, and which combine (the docs note EDD running simultaneously with tomography)? | Tomography reuses the 2-BM Methods; the other techniques are design intent, carried pending on the [APS site Practices](../aps/index.md#the-techniques-adapted-here). | Which Methods and Practices the pilot binds. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Is the germanium energy-dispersive detector the same physical device as the fluorescence MCA, and is XRF a routine standalone technique or only an EDD energy-scale calibration step? | One `EnergyDispersiveSpectrometer` device presenting the Sensor Role, with fluorescence as a calibration step, not a separate detector. | One versus two Sensor-backed detector Assets, and whether a spectroscopy Method is earned. |
| RAD-1 | Blocks-go-live | For time-resolved radiography, what is the point-detector chain (PIN diode plus ADQ14 digitizer or oscilloscope plus DataGrabber), and is one acquisition trace one Dataset? | A `Photodiode` device presenting the Sensor Role; the digitizer / scope / DataGrabber stay on the floor; the data unit is unconfirmed. | The radiography detector Family and the Run / Dataset shape. |
| HSI-1 | Blocks-go-live | For high-speed imaging, is one chopper-gated movie burst one Run / Dataset (and the N-sequence set one Campaign), and how are top-up-blanked frames represented (invalid-marked, dropped, gap)? | One high-speed `Camera`; the acquisition unit and blanking semantics are unconfirmed. | The Run / Dataset / Acquisition shape for time-resolved capture. |

## Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLOW-1 | Blocks-build | Must CORA command the gas-flow and compressed-air setpoints (the Sierra Smart-Trak controllers and the electronic air regulator), or only read them back, and is there a third settable sample-environment actuator? | A loose `FlowController` family with a settable setpoint, pending whether a settable-actuator affordance or Family is earned. | The settable-actuator decision and the next control-port consumer. |
| ENV-1 | Blocks-go-live | Is there an installed combustion, spray, or fuel-injection device at 7-BM, or is combustion an intended use served by the air, gas, and vacuum infrastructure? | No combustion rig Asset is modelled; combustion is served by the facility Supplies and bound to the specimen Subject. | Whether a combustion-rig Asset and a fuel-vapor Caution are modelled. |

## Controls and site

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Nice-to-have | Should the DG645 delay generators, softGlue FPGA, Machine Status Link P0 reference, and top-up inhibit be one `TimingController` device, or do any of them deserve separate modelling? | One `TimingController` carries the whole scheme, mirroring the 2-BM Timing device. | The timing-subsystem Asset shape. |
| SECTOR-1 | Nice-to-have | Confirm 7-BM is in Sector 7, and whether it shares any governed resource (optics, safety system, compute) with another APS beamline. | 7-BM is a separate beamline in Sector 7 under the APS Site, sharing no governed resource with 2-BM. | The sector label and any cross-beamline shared-resource governance. |
