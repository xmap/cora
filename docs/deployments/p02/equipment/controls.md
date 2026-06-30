# Controls

*The control plane P02 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P02 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p02/motor/...`).
- The monochromator is `dcmmotor` (bragg / parallel / perp) + `dcmener`; the bendable HFM / VFM mirrors are `attributemotor` devices (curvature / ellipticity / tilt / z, with `gp` variants); the slits are `slt` devices.
- The detectors are `pilatus` (1M), `pedetector` (PerkinElmer), `mca`, and `sis3302`; the sample environment is `eurotherm2604` (Anton-Paar), `eurotherm2408`, and `lks336tempctrl` (Lakeshore); the beam monitor a `caenelsah501d` picoammeter.
- Two tiny `tangomotor` dummy stubs (`ch1a_dmy01/02`, `ch2_dmy01/02`) are test / placeholder devices, noted but not modelled (`STUB-1`).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). P02 owns the OH1 high-heatload optics hutch shared with P03 (the `haspp02oh1` host that P03's registry cross-references).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The powder / total-scattering / high-pressure acquisition (the sample scan or parametric ramp coupled to the area-detector capture) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, the optics + sample banks) and `TangoMotorControllers` (`Tango_motor_tango`, the mono, the bendable-mirror attribute motors, and the CH dummy stubs). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
