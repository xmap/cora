# Controls

*The control plane P09 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P09 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as the other PETRA III beamlines (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`:

- Stepper axes are OMS MAXv-58 and VME58 controllers (`oms58`, `omsvme58`), driving the optics, diffractometer, and sample motor banks (`p09/motor/...`).
- The monochromator is `dcmmotor` / `dcmener` with a coupled `multiplemotors` energy axis; the mirrors are SmarPod-style `spk` controllers; the defining slit is a Galil DMC slit controller (`galildmcslit`).
- The diffractometer is an `e6cctrl` / `diffractometer` device; the 14 T magnet a `magnet` device; the phase retarder (`phaseretarder`), the analyzer (`analyzer`), and the absorber (`absorber` / `absorbercontroller`) their own devices.
- The fine sample stages are AttoCube (`attocubeanc300motor`) and PI (`piezopie710` / `piezopie725`) controllers, plus a hexapod (`hexapodmotor`).
- The detectors are PerkinElmer (`pectrl` / `pedetector`), Pilatus, Andor (Lima `limaccds`), the SIS3302 fluorescence digitizer, and MCAs; instruments connect over GPIB (`gpib`, Keithley `k2410`).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the per-area device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). A shared Lambda detector reports on the bare `petra3` host, and the registry includes a stray `p07/hexapodsmall` row (a P07 device, excluded from P09) (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The resonant-scattering / magnetism acquisition (the energy / diffractometer / field scan coupled to the detector readout, with the phase retarder switching polarization) runs as a Sardana macro.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as the 4-ID seam and the wider PETRA III deployments. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`, OMS MAXv-58 / VME58), `GalilSlitControllers` (`Tango_galildmcslit`), `PiezoControllers` (`Tango_piezo`, PI + AttoCube), `HexapodControllers` (`Tango_hexapod`), and `TangoMotorControllers` (`Tango_motor_tango`, mono / mirrors / coupled axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
