# Controls

*The control plane P23 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P23 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 and VME58 controllers (`oms58`, `omsvme58`), driving the experiment motor bank (`p23/motor/...`) and a single dev / commissioning axis on the `hasep23dev` host.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The in-situ diffraction acquisition runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller class read from the registry: `OMS58Controllers` (`Tango_oms58`, the OMS MAXv-58 / VME58 steppers driving the experiment motor bank). This is carried confirm; the physical controller inventory is not in the registry (`CTRL-1`).
