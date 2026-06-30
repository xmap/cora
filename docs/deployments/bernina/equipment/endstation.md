# Endstation

*The Bernina diffraction endstation: the GPS six-circle and XRD You-geometry diffractometers, the hexapod sample table, the pump-probe laser, and the sample-view cameras. Design-phase, with the `eco`-derived handles recorded and the configuration state carried unknown (CONFIG-1).*

The Bernina experiment hutch is where the focused beam meets the sample and the time-resolved diffraction happens. It is the stage that distinguishes Bernina from its sibling [Alvra](../../alvra/equipment/endstation.md): where Alvra's endstation is a sample manipulator plus an emission spectrometer, Bernina's is a pair of reconfigurable diffractometers. Both fold into existing CORA shapes; the diffractometers reuse a graduated Assembly rather than a new Family.

## The diffraction platforms

Bernina exposes two diffraction platforms, both built by the same `eco` driver (`bernina_diffractometers.py`) from literal PV suffixes:

- **GPS** (`SARES22-GPS`): a six-circle "general purpose station" goniometer, with a `SixCircleBernina` reciprocal-space conversion.
- **XRD** (`SARES21-XRD`): a You-geometry station carrying a base (gamma / mu plus translations and tilts), a 2-theta detector arm (`delta`, detector translation), a polarization-analyzer branch (pol / pthe / ptth), a kappa goniometer with on-the-fly kappa-to-Eulerian (eta / chi / phi) conversion, a heavy-load goniometer table, and a PI hexapod.

This is materially more than the catalog `Goniometer` (the integrated single-device orienter from [I03](../../i03/index.md) and [MX3](../../mx3/index.md)). It is, exactly, the graduated [`Diffractometer` Assembly](../../../catalog/assemblies.md) that [4-ID](../../4-id/index.md) and [8-ID](../../8-id/index.md) earned: it composes a `Goniometer` (the sample circles plus x / y / z), zero or more `RotaryStage` detector-arm circles (the `delta` 2-theta arm), and a reciprocal-space `PseudoAxis` (the hkl inverse kinematics, plus XRD's kappa-to-You conversion). So each platform is modelled as a `Goniometer` Asset + a `PseudoAxis` Asset (and, for XRD, a `RotaryStage` detector-arm Asset) composed through that Assembly: **no new Family, no new Assembly**. The GPS and XRD platforms are its third and fourth bindings, the first at an XFEL (DIFF-1, with the reciprocal-space partition rule as DIFF-2).

The one thing the public source does **not** give is which of XRD's sub-assemblies (base / arm / polana / kappa / heavy-load / hexapod / robot) are currently mounted: the `eco` driver reads that from a non-public config object, so it is carried unknown (CONFIG-1). The axis topology is recoverable; the instantiation is not.

The `USDTable` upstream hexapod (`HexapodSymmetrie`) folds into the `Hexapod` Family. The Staeubli TX200 robot that handles samples and the detector runs over PShell (HTTP), not EPICS, and is deferred (ROBOT-1), the same posture I03 and MX3 take for their sample-exchange arms.

## The pump-probe laser

The femtosecond optical laser (`SLAAR21-LMOT`) excites the sample before the X-ray probe, the same role it plays at Alvra. The laser device folds into the loose `Laser` family, and its delay stages are `LinearStage`s. What does not fold is the synchronization: the `eco` `lxt` timing chain holds the optical-laser and FEL timing domains together at the femtosecond level, and the [PSEN arrival-time monitor](../beamline.md) in the optics hutch corrects the residual jitter, a cross-timing-domain relationship CORA's single-domain `PartitionRule` cannot express (LASER-1). The laser is also a class-4 hazard gated by a Clearance (see [Governance](../governance.md)). The laser shutter (`SLAAR21-LTIM01-EVR0`) is driven through a SwissFEL event receiver, the beam-synchronous timing system (TIMING-1).

## Sample viewing

The below-sample microscope (`SARES20-CAMS142-C1`, with a zoom stage) presents the Detector Role for sample viewing and alignment and binds `Camera`, the same way the Alvra sample microscope and the i13-1 side camera do.

See the [Detector](detector.md) page for how the recorded shots leave the hutch, and [Open questions](../questions.md) for the endstation items still to confirm.
