# Controls

*The control plane P06 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P06 runs on the **PETRA III Tango control system with Sardana as the scan / motion SCADA layer**, the same floor as [P01](../../p01/equipment/controls.md) and [P04](../../p04/equipment/controls.md). P06 is the most controller-diverse PETRA III beamline modelled so far (`CTRL-1`).

## The floor: Tango devices

Each device is a Tango device addressed by `domain/family/member`. P06's controller diversity reflects its scanning-probe role:

- Stepper axes are OMS MAXv-58 controllers (`oms58`), driving the `mono`, `mi`, and `nat` motor banks (`p06/motor/...`).
- The fly-scan raster stages are Aerotech controllers (`p06/aerotechmotor/...`), the continuous-motion axes for scanning microscopy.
- The nano-probe hexapods and sample piezos are SmarAct controllers (`p06/smaractmotor/...`, `p06/hexasmarmotor1`, `p06/hexasmarmotor2`).
- The MC01 hexapod is a hexapod controller (`p06/hexapodmotor/...`).
- The fine sample stages are PI piezo controllers (`p06/piezopi`, `p06/piezopie871`) and SMC-Hydra controllers (`p06/hydramotor`).
- The sample rotation is a Pegasus controller (`p06/pegasusmotor`).
- The monochromators are `dcmmotor` / `dcmener` (DCM) and `lom` (multilayer); the undulator a `undulator` device with `attributemotor` gap / harmonic / taper; coupled axes are `vmexecutor` / `vmexecutors`.
- The detectors are `eigerdectris`, `lambda`, `pilatus`, `ccd` (PCO), `prosilica` (cameras), `maia*` (the XRF array), `xia` (fluorescence), and `i404` (the quad BPMs).

The device servers behind these classes live in `gitlab.desy.de/tango-ds/deviceclasses`; the per-endstation device registry (the source of the handles in this descriptor) is the OnlineXML at `gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06`. The handles are read from that public registry and carried confirm; the registry branch (`debian/jessie`) is a deployment-packaging branch, so some entries may lag the live Tango database (`CTRL-1`). Several detectors report on a bare `p06` / `petra3` host without an endstation token (`HOST-1`).

## The scan layer: Sardana

Above the Tango floor, Sardana provides the scan orchestration (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). The scanning fluorescence / diffraction microscopy acquisition (the Aerotech raster fly-scan coupled to the Maia XRF readout and the area detectors) runs as a Sardana macro; this is a continuous-motion fly-scan, the kind of routine where the deterministic real-time coupling between motion and detector triggering lives in the Sardana / hardware layer.

## The seam: where CORA's edge conducts

The Sardana macro orchestration is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the Sardana macro per routine, the same shape as P01 / P04. CORA never owns the Tango devices, the device servers, or the Tango database; it conducts the scan over them, and is barred from the deterministic real-time fly-scan loop by construction. The NeXus file-writing (the `nexdatas` chain) and the Maia mapping data stream are plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the motion-controller classes read from the registry: `OMS58Controllers` (`Tango_oms58`), `AerotechControllers` (`Tango_aerotech`, the fly-scan raster stages), `SmarActControllers` (`Tango_smaract`, the nano-probe hexapods and piezos), `HexapodControllers` (`Tango_hexapod`, the MC01 hexapod), `PiezoControllers` (`Tango_piezo`, the PI and SMC-Hydra fine stages), and `TangoMotorControllers` (`Tango_motor_tango`, the mono / undulator / virtual / Pegasus axes). These are carried confirm; their physical controller inventory is not in the registry (`CTRL-1`).
