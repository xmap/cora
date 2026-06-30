# Controls

*The control plane P11 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P11 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as [P01](../../p01/equipment/controls.md), [P04](../../p04/equipment/controls.md), and [P06](../../p06/equipment/controls.md) (`CTRL-1`).

## The floor: Tango devices

The whole beamline reports on a single Tango host (`haspp11oh`). Each device is a Tango device addressed by `domain/family/member`:

- A motion axis is a Tango motor device, e.g. `p11/motor/eh.2.01`, driven by an OMS MAXv-58 controller (the `oms58` class).
- The fine sample axes are piezomotor devices (`p11/piezomotor/eh.4.*`).
- The high-speed axis is a servomotor device (`p11/servomotor/eh.1.01`).
- The cryostream is a `cryo` device (`p11/cryo/eh.01`).
- The detectors are `pilatus` (`p11/pilatus/eh.01`) and `xia` (`p11/xia/oh.1`) device servers.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). The single Tango host means the optics / experiment hutch split is inferred from the device-name prefixes, not from distinct hosts (`ENC-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The rotation-MX acquisition (the goniometer oscillation coupled to the Pilatus frame capture) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A and the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, the oh / granite / eh motor banks), `PiezoMotorControllers` (`Tango_piezomotor`, the experiment-hutch fine piezo bank), and `TangoMotorControllers` (`Tango_motor_tango`, the servo and coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
