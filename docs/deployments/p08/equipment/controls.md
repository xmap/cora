# Controls

*The control plane P08 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P08 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and diffractometer / sample motor banks (`p08/motor/...`).
- The monochromators are `dcmmotor` / `dcmener` (DCM) and `lom` / `lomenergy` (multilayer); the CRL a `lensctrl` device; the diffractometer a Kohzu controller (`kozhue6cctrl`); the hexapod a `hexapodmotor`; the slits / attenuator `vmexecutor` virtual axes.
- The detectors are `eigerdectris`, `pilatus`, `mythen2`, `pedetector`, and the `sis3302`-read Vortex SDD.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). A shared Lambda detector reports on the bare `petra3` host (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The high-resolution diffraction acquisition (the diffractometer scan coupled to the area / strip detector capture) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `HexapodControllers` (`Tango_hexapod`, the sample hexapod), and `TangoMotorControllers` (`Tango_motor_tango`, the monochromators / Kohzu diffractometer / coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
