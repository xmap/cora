# Controls

*The control plane P04 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P04 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as [P01](../../p01/equipment/controls.md) and CORA's wider Tango / Sardana house style (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- A motion axis is a Tango motor device, e.g. `p04/motor/exp1.01`, driven by an OMS MAXv-58 controller (the `oms58` class).
- A soft X-ray mirror or exit-slit axis is a SmarPod-style `spk` controller device, e.g. `p04/spk/exp.01`.
- The plane-grating monochromator is a `MonoP04` device (`p04/monop04/exp2.01`); the undulator a `UndulatorP04` device (`p04/undulatorp04/exp2.01`, with the gap as a sub-attribute).
- A coupled axis is a virtual-motor executor (`p04/vmexecutor/...`).
- The diagnostic cameras are `TangoVimba` devices (`p04/tangovimba/...`) and the Prosilica viewing camera a `module_tango` device; the electrometers are `Keithley 6517A` device servers (`p04/keithley6517a/...`).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses` (the `MonoP04` and `undulatorp04` classes are P04-specific entries there); the per-endstation device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). The optics devices (undulator, PGM, mirrors, exit slits) report on the `haspp04exp2` host but are logically the optics section (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The soft X-ray absorption acquisition (the photon-energy scan coupling the undulator gap and the plane-grating monochromator, read against the drain-current electrometer) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as P01 and the wider Tango / Sardana deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry:

- `OMS58Controllers` (`MotionController`, protocol `Tango_oms58`): the OMS MAXv-58 stepper controllers driving the experiment and screen motors.
- `SPKControllers` (`MotionController`, protocol `Tango_spk`): the SmarPod-style controllers driving the soft X-ray mirror and exit-slit axes.
- `TangoMotorControllers` (`MotionController`, protocol `Tango_motor_tango`): the generic Tango motor controllers backing the monochromator, undulator, and virtual axes.

These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
