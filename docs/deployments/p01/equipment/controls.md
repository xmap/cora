# Controls

*The control plane P01 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P01 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, not EPICS. This is a further Tango / Sardana control floor (after MAX IV and ALBA) and a sibling of the ESRF BLISS / Tango floor: the seam model that reads "EPICS is the floor" generalizes here to "Tango / Sardana is the floor" (`CTRL-1`).

## The floor: Tango devices

In this stack each device is a Tango device addressed by `domain/family/member`:

- A motion axis is a Tango motor device, e.g. `p01/motor/eh1.02` (the HRM400 theta), driven by an OMS MAXv-58 controller (the `oms58` Tango class, the dominant P01 motor controller and the most common motor class across PETRA III).
- A coupled / computed axis is a virtual-motor executor, e.g. `p01/vmexecutor/hrm_ener` (the high-resolution-monochromator energy) or `p01/vmexecutor/slit1_cx` (a slit center), computed by Sardana from the underlying motors.
- An undulator gap / taper or a fixed-exit offset is an attribute motor, e.g. `p01/attributemotor/gap.01`.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the per-endstation device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan / motion orchestration: a Pool of controllers, a MacroServer running scan macros, and MeasurementGroups defining the acquired channels, with Spock (an IPython CLI) and Taurus (UIs) as the operator surfaces. DESY maintains its own Sardana fork and controller set (`gitlab.desy.de/fsec-sardana`). The NRS energy scan (the high-resolution-monochromator energy axis stepped against the time- / energy-resolved detector readout) and the RIXS scan run as Sardana macros.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the 2-BM TomoScan seam and the MAX IV / ESRF Tango deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The accelerator-side DOOCS / TINE stack and the ASAPO fast-data transport are out of beamline scope. The NeXus file-writing (the `nexdatas` chain: NXSDataWriter, NXSConfigServer) is plumbing CORA observes, not data it owns; CORA keeps its own event-sourced record.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry:

- `OMS58Controllers` (`MotionController`, protocol `Tango_oms58`): the OMS MAXv-58 stepper controllers, the dominant P01 motor class.
- `TangoMotorControllers` (`MotionController`, protocol `Tango_motor_tango`): the generic Tango motor controllers backing the DCM and virtual-axis devices.
- `VirtualMotorExecutors` (`MotionController`, protocol `Tango_vmexecutor`): the Sardana virtual-motor executors computing the coupled energy / slit pseudo axes.

These are carried confirm; their physical controller inventory (counts, racks) is not in the registry (`CTRL-1`).
