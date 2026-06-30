# Controls

*The control stack and trigger scheme. Modelling exercise; handles not public.*

I-TOMCAT runs on the SLS control stack: EPICS at the floor ("control of the beamline and experiment is fully implemented in EPICS"), with the BEC (Beamline and Experiment Control) microservice scan/orchestration layer over ophyd introduced for SLS 2.0. EPICS is the same floor the APS pilot uses; the BEC scan layer is the SLS-specific edge.

## The seam

CORA's lens names the facility's software only to draw the boundary:

- **EPICS (floor): drive through.** CORA actuates and observes the beamline over EPICS, never replacing it. This matches the 2-BM and FXI posture (EPICS is the floor).
- **BEC (edge): replace.** CORA's edge would replace BEC's scan and experiment steering, conducting over EPICS rather than replacing it, the way it replaces TomoScan at 2-BM. The wrinkle is that BEC adopts the same ophyd device model CORA's edge would, which keeps a drive-through reading (integrate at the `bec_messages` / ophyd boundary) open. This is the single most consequential seam decision and is carried as SEAM-1 on [Open questions](../questions.md).
- **SciCat + the reconstruction pipeline: replace / observe.** The Ra/SLURM Fiji reconstruction pipeline and the SciCat catalog are plumbing CORA observes; CORA owns its own Dataset rather than adopting SciCat as its source-of-record.

## The EPICS floor, confirmed at the signal level

The "EPICS is the floor" claim is not just inferred from BEC running on ophyd; it is confirmed at the signal level from the public BEC `ophyd_devices` source. The shared PSI motor bases all subclass ophyd `EpicsMotor` / `EpicsSignalBase` over EPICS MotorRecord PV suffixes: `EpicsMotor`, `EpicsMotorEC` (the ECMC EtherCAT variant, suffixes `-EnaAct` / `-PosAct` / `-VelAct` / `-PosErr` / `-SumIlockFwd`), `EpicsUserMotorVME`, and `PSIPositionerBase` ([psi_motor.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/psi_motor.py), [psi_positioner_base.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/interfaces/base_classes/psi_positioner_base.py)). Area-detector cameras use `EpicsSignalWithRBV` over PV suffixes ([cam.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/areadetector/cam.py)), and the public deployment template carries a Channel Access gateway env line (`EPICS_CA_ADDR_LIST` with `sls-x12sa-cagw.psi.ch:5836`). So the floor CORA's `ControlPort` actuates over is EPICS Channel Access, the same protocol family as the APS pilots, with no new control substrate to build.

The tomography rotation lineage is `EpicsRotationBase(OphydRotationBase, EpicsMotor)`, exposing rotation modes `["target", "radiography"]` and `allow_mod360` ([ophyd_rotation_base.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/interfaces/base_classes/ophyd_rotation_base.py)); it was added in the same commit as the now-removed `tomcat_rotation_motors.py`, so it is the surviving generic base the concrete TOMCAT rotation axis subclassed.

## The fast-path: not all triggering is EPICS

The air-bearing rotation stage is the master clock, feeding the camera trigger inputs for continuous and streaming acquisition. The trigger surface is not plain EPICS: the public `PandaBox` device (`panda_box.py`) talks a raw TCP socket (`import socket` + the `pandablocks` library, data socket on port 8889); its `*IDN?` / `SEQ1.TABLE>` strings are PandABox ASCII protocol commands, not EPICS PVs ([panda_box.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/panda_box/panda_box.py)). Whether I-TOMCAT's specific trigger chain uses PandABox, an Aerotech PSO output, or an EtherCAT path is not determinable from public source (TRIG-1), but the shape is clear: CORA's `ControlPort` at I-TOMCAT must span EPICS Channel Access plus at least one direct-socket adapter, the heterogeneous-control-plane pattern also seen at MX3 (EPICS + Exporter + REST). The chain is modelled as a single `TimingController` device carrying the scheme.

PSI's signature high-speed camera, GigaFRoST, has no public ophyd class anywhere in the BEC tree (no `gigafrost` path, no changelog entry), so whether its control surface is an EPICS areaDetector device, a socket fast-path like PandABox, or firewalled entirely is an open question (DET-1).

## Device handles

CORA models each device's control handle as an opaque string set at the edge, independent of the control system. For I-TOMCAT the per-beamline EPICS PV prefix scheme is not public and the concrete BEC ophyd device manifest (the `tomcat_bec` plugin) lives on the internal `gitea.psi.ch`, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real handle is tracked by CTRL-1 on [Open questions](../questions.md).

The public BEC deployment registry [`bec_atlas`](https://github.com/bec-project/bec_atlas) names both TOMCAT realms (S-TOMCAT `x02da`, I-TOMCAT `x02sa`) and their production deployment hosts (`x02da-bec-001.psi.ch`, `x02sa-bec-001.psi.ch`), but binds no devices: the device list is runtime data populated from the firewalled deployment. The shared PSI base classes are public; the concrete per-device subclasses and their PVs are not.
