# Controls

*The control plane P10 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P10 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p10/motor/...`).
- The guard slits are Galil DMC slit controllers (`p10/galildmcslit/...`).
- The fine sample stages are SmarAct (`smaractmcsmotor`, `smaractmotor`) and AttoCube (`attocubemotor`) controllers; the E1 hexapod is a hexapod controller (`hexapodmotor`); the mirrors are SmarPod-style `spk` controllers.
- The monochromator is `dcmmotor` / `dcmener` with a coupled `multiplemotors` energy axis; the undulator a `undulator` device; the beam shutter a `shutter` device.
- The detectors span the widest suite in the PETRA III set: `pilatus`, `eigerdectris`, `pco`, `lambda`, `andor`, `mythen`, `ccdpvcam` (Quadro), `lcxcamera`, and the Lima-controlled `limaccd` / `limampx` / `limaccds`; the fluorescence detectors are `mca`.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the per-endstation device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). The Lambda and Lima cameras report on the bare `p10` host without an endstation token (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The XPCS acquisition (the coherent beam on the sample read by the high-frame-rate Lambda / Eiger, the intensity correlation computed downstream) runs as a Sardana macro coupled to the detector's burst readout.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the 8-ID XPCS seam and the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them, and the high-frame-rate correlation compute is `ComputePort` work, not a beamline device. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `GalilSlitControllers` (`Tango_galildmcslit`), `SmarActControllers` (`Tango_smaract`), `AttoCubeControllers` (`Tango_attocube`), `HexapodControllers` (`Tango_hexapod`), and `TangoMotorControllers` (`Tango_motor_tango`). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
