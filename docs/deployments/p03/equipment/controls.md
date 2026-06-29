# Controls

*The control plane P03 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P03 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as [P01](../../p01/equipment/controls.md), [P04](../../p04/equipment/controls.md), [P06](../../p06/equipment/controls.md), and [P11](../../p11/equipment/controls.md) (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`. P03 brings two motion-controller protocols new to the PETRA III set CORA models:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the sample / instrument motor banks (`p03/motor/...`, `p03nano/motor/...`).
- The guard slits are Galil DMC slit controllers (`p03/galildmcslit/...`, `p03nano/galildmcslit/...`), exposing blades plus center / gap virtual axes.
- The GINIX waveguide is a SmarPod controller (`p03nano/smarpodmotor/...`).
- The CRL and GINIX sample hexapods are hexapod controllers (`hexapodmotor`); the GINIX rotation is a Smaract controller (`smaractmotor`); the mirrors are SmarPod-style `spk` controllers.
- The monochromator is a `lom` (multilayer) device with a coupled `lomenergy` axis; the detectors are `pilatus`, `mca`, `XIA`, `lambda` device servers; the temperature controller a `eurotherm2604` device; the BPMs `i404` electrometers.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the per-endstation device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). The first defining slit reports on the P02 optics host (`haspp02oh1`, the shared P02 / P03 optics) and a Lambda detector on the bare `petra3` host (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The SAXS / WAXS acquisition (the sample scan coupled to the Pilatus frame capture, the GINIX waveguide-scanning nano-imaging) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the other PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `GalilSlitControllers` (`Tango_galildmcslit`, the guard slits), `SmarPodControllers` (`Tango_smarpodmotor`, the GINIX waveguide), `HexapodControllers` (`Tango_hexapod`, the CRL and GINIX sample hexapods), `SmarActControllers` (`Tango_smaract`, the GINIX rotation), and `TangoMotorControllers` (`Tango_motor_tango`, the mono / mirrors / coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
