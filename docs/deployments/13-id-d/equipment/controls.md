# Controls

*The control stack and the orchestration seam. Handles reconstructed from the GSECARS EPICS support tree, carried confirm at medium confidence.*

13-ID-D runs on APS EPICS, the same floor as the other APS beamlines. GSECARS layers SPEC and Python orchestration on top of that floor. CORA observes the floor and, where it replaces the SPEC / Python orchestration of the high-pressure acquisition, conducts over it through the `ControlPort`; it does not replace EPICS itself.

## Device handles

The control handles are reconstructed from the GSECARS EPICS support tree ([CARS-UChicago/GSECARS-EPICS](https://github.com/CARS-UChicago/GSECARS-EPICS)): the `iocBoot` startup scripts, the `CARSApp/Db` device templates, and the `CARSApp/op/adl` MEDM screens. This is an EPICS-native source, not a Python device roster, so the device-to-PV reconstruction is rougher than for the dodal / BITS beamlines and is carried at medium confidence (`CTRL-1`). The namespaces split by IOC and subsystem:

| Namespace | What it carries |
| --- | --- |
| `13IDA:` | the shared 13-ID-A first-optics IOC, including the silicon double-crystal monochromator (`MONO-1`) |
| `13IDE:En` | the derived beamline-energy axis (`MONO-1`) |
| `13IDD:` | the 13-ID-D endstation IOC: the attenuator (`13IDD:filter:`), the ion-chamber scaler (`13IDD:scaler1`), the DAC photodiode (`13IDD:Photodiode`), the heating-laser power (`13IDD:US_LaserPower` / `DS_LaserPower`) and emission-temperature readbacks (`13IDD:us_las_temp` / `ds_las_temp`), and the fibre sample illumination (`13IDD:US_IllumOnOff`) |
| `13IDD_PACE5000:PC1:` | the membrane gas-pressure controller (`Setpoint` / `Pressure_RBV`) |
| `13IDDLF1:` | the LightField metrology spectrometer for in-situ pressure / temperature |
| `13EIG2_9M:` | the Eiger2 X 9M area detector |
| `13IDD_Dante1:` | the XGLab Dante fluorescence MCA |

These handles remain confirm-pending: a value reconstructed from `.db`, `.substitutions`, and `.adl` files is evidence to verify with staff, not a CORA-owned fact, and the binding is rougher than a Python roster would give (`CTRL-1`). The stage controllers (Galil and Newport XPS) and the detector 2theta-arm swing remain partly unresolved: the swing PseudoAxis was seen only in a Galil test template, so its binding is deferred rather than invented (`DET-1`, `SAMPLE-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam, not the device roster.

## The orchestration seam

The high-pressure acquisition runs through GSECARS SPEC and Python: the coupled XRD-plus-temperature collection (diffraction taken while the emission-spectroradiometry temperature is logged), the balanced double-sided laser-power ramp that drives the two IPG YLR fibre lasers (`13IDD:US_LaserPower` / `DS_LaserPower`) in step, the membrane pressure steps on the GE / Druck PACE5000 (`13IDD_PACE5000:PC1:Setpoint`), and the metrology spectra read on the LightField spectrometer. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving the cell, the stage, and the detectors through EPICS rather than replacing it.

The heating is open-loop on commanded power, with temperature inferred from thermal emission, so CORA drives a power actuator, not a closed-loop temperature setpoint, in this cut (`HEAT-1`). Whether any heating path ever closes a temperature loop is a staff confirmation, not a CORA assumption.

The X-ray probe is otherwise familiar powder and single-crystal diffraction, reusing the existing scattering Capabilities; high pressure is a Plan-level sample-environment difference, not a new technique (`TECH-1`). The area-detector file-writing to the GSECARS filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are not resolved in the EPICS support tree and are not invented here (`PSS-1`). 13-ID-D adds a second permit axis the other APS stations do not carry: a laser-safety enclosure permit, gated by a Koyo DL205 safety PLC (`13IDD_laserPLC:`) governing laser emission for the class-4 heating lasers (`LASER-1`). Both are pending, carried but not invented.

If CORA later models either, it would not model the interlock logic itself. The Koyo PLC is an Enclosure permit axis, not a device: CORA observes the permit signal and gates conduct on it, mapping the outcome to an Enclosure permit status, the same way it treats the PSS search-and-secure state. That observe-only mapping is not modelled in this cut.

The [APS Site](../../aps/index.md#the-safety-envelope) page carries the shared safety envelope these permits sit within.
