# Controls

*The control plane P65 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P65 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p65/motor/...`).
- The energy axis is a channel-cut DCM (`cdcmenergy`); the slit / table are `vmexecutor` virtual axes; the `a2_dmy*` stubs are `tangomotor` dummy / placeholder devices.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). P65 shares its optics host (`hasnp64`) with the advanced-XAS sibling [P64](../../p64/index.md); the energy / optics devices report on that host (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The XAS acquisition (the CDCM energy scan read against the transmission / fluorescence signal) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the BMM / ISS XAS seams and the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, the optics + sample banks) and `TangoMotorControllers` (`Tango_motor_tango`, the CDCM energy axis and the a2 dummy stubs). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
