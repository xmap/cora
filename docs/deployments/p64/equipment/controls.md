# Controls

*The control plane P64 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P64 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p64/motor/...`).
- The monochromator is a Tsai-geometry DCM (`DcmTsai` + `dcmener`) whose energy axis couples the undulator (`coupledmonoundmove`); the slits are `vmexecutor` virtual axes; the fine stages are NewFocus 8742 picomotor devices.
- The detectors are `lambda750k` area detectors and the `sis3302` multi-element fluorescence digitizer.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). P64 shares its optics host (`hasnp64`) with the applied-XAS sibling [P65](../../p65/index.md).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The XAS acquisition (the coupled mono + undulator energy scan read against the transmission / multi-element fluorescence signal) runs as a Sardana macro, often as a continuous energy fly-scan (QEXAFS).

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the BMM / ISS XAS seams and the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them, and is barred from the deterministic real-time energy-fly-scan loop by construction. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `PicomotorControllers` (`Tango_newfocuspico8742`, the fine stages), and `TangoMotorControllers` (`Tango_motor_tango`, the Tsai mono and the coupled energy axis). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
