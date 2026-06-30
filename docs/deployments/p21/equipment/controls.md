# Controls

*The control plane P21 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P21 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines. P21 is a Swedish-collaboration beamline, but the beamline controls are the PETRA III Tango / Sardana stack (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p21/motor/...`).
- The slits are `vmexecutor` virtual axes.
- The beamline is split across three Tango hosts: `hasep212oh` (the P21.2 optics), `hasep21eh3` (the EH3 endstation), and `haspp21lab` (the LAB station). A fourth, `hasep211eh` (P21.1), exposed only bookkeeping devices in this slice (`HOST-1`).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The high-energy diffraction acquisition runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, the optics + sample banks) and `TangoMotorControllers` (`Tango_motor_tango`, the coupled / virtual axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
