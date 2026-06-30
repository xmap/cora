# Controls

*The control plane P61 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P61 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the experiment motor bank (`p61/motor/...`) on the `hasnp61eh2` host.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61`. Note this is the only PETRA III extras package published on the `debian/stretch` branch (the others are `debian/jessie`), so its snapshot vintage may differ; the handles are read from that public registry and carried confirm (`CTRL-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The high-energy white-beam / energy-dispersive diffraction acquisition runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller class read from the registry: `OMS58Controllers` (`Tango_oms58`, the OMS MAXv-58 steppers driving the experiment motor bank). This is carried confirm; the physical controller inventory is not in the registry (`CTRL-1`).
