# Controls

*The control plane P22 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P22 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`. P22's defining control fact is that it **shares its optics with P09**:

- The undulator, DCM, mirrors (spk), phase retarder, and absorber are P09 devices, on `p09/` addresses (the P09-MONO host). P22 reads / drives them as the HAXPES branch of the shared optics chain (`SHARED-1`, `HOST-1`).
- The HAXPS endstation motors are P22 devices (`p22/motor/...`), driven by OMS MAXv-58 controllers (`oms58`).
- The electron analyzer is a self-contained instrument with its own control system, not a Tango motor device in this registry slice (`DET-1`).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The HAXPES acquisition (the photon-energy / analyzer sweep over the sample) runs as a Sardana macro coordinated with the analyzer's own acquisition.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. The shared P09 optics mean P22's source-conditioning state is coupled to P09 (`SHARED-1`), a coordination fact CORA's Federation / Trust model would carry. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, the HAXPS sample bank) and `TangoMotorControllers` (`Tango_motor_tango` / spk, the shared P09 optics and coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
