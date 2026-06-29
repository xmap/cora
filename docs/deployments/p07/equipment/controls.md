# Controls

*The control plane P07 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P07 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines. Although P07 is jointly operated by Helmholtz-Zentrum Hereon and DESY, the beamline controls are the PETRA III Tango / Sardana stack (`CTRL-1`, `OPERATOR-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the optics and sample motor banks (`p07/motor/...`).
- The monochromator is a multi-bounce DCM (`dcmmotor` first / second crystal axes + `dcmenergy`); the slits are `slt` + `galildmcslit` devices; the OH z-stage a `beckhoffmotor`.
- The diffractometer is a four-circle Eulerian (`e4cv`) + the two-theta arm (`twothetap07`); the hexapod a `hexapodmotor`; the magnet a `magnet17tf` device; the Linkam a `t95tempproglinkam` device.
- The detectors are `pilatus`, `pedetector_old` (PerkinElmer, legacy controller), and `mca`.

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). Only the EH2 registry slice is public; the other P07 hutches (EH1 / EH3 / EH4) are not in it (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The high-energy diffraction / high-field acquisition (the diffractometer / field scan coupled to the area-detector capture) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `GalilSlitControllers` (`Tango_galildmcslit`, the slits), `HexapodControllers` (`Tango_hexapod`, the EH2 hexapod), and `TangoMotorControllers` (`Tango_motor_tango`, the DCM / OH z-stage / coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
