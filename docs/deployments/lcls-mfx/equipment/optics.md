# Optics and endstation

*The MFX-hutch beam conditioning, the pump-probe laser, the sample delivery, and the emission spectrometer. Design-phase, with the `pcdshub`-derived handles recorded.*

The MFX experiment hutch is where the transported beam is conditioned to its final state and meets the sample. This is the stage that most exercises the family-fold finding: every conditioning device folds into an existing Family, and the one device that does not (the emission spectrometer) is the single new loose family.

## Conditioning the beam

- **Pulse picker** (`MFX:DIA:MMS:07`): a fast single-pulse selector. It folds into the `Shutter` Family as a fast beam gate; whether a rotary pulse-picking chopper deserves its own Family (the loose `Chopper` shape) is open (PULSE-1).
- **Attenuator** (`MFX:ATT`): a solid-Si binary attenuator. The `Filter` Family covers the discrete foil selection. What it does not cover is the `AttBase` solver that picks a foil combination for a requested transmission, energy-dependent; that is the deferred `Attenuable` leg, and MFX is its rule-of-three trigger (ATT-1).
- **DCCM**: a diamond double-channel-cut monochromator for monochromatic and spectroscopy modes; MFX also runs pink / SASE beam with the mono out. It folds into `Monochromator`; the crystal details and the pink-vs-mono mode boundary are carried `confirm` (MONO-1).
- **Transfocator and prefocus** (`MFX:LENS`, `MFX:DIA:XFLS`): compound-refractive-lens (beryllium) stacks that focus the beam. They reuse the graduated `Transfocator` catalog Family (a CRL focusing optic), also bound at I22 / 4-ID / 8-ID. Selecting a lens set for a target focal length is a solver with the same shape as the attenuator (ATT-1).
- **Slits** (`MFX:DG1:JAWS`, `MFX:DG2:JAWS:*`) and **profile imagers** (`MFX:DG1:PIM`): standard 4-blade slits (`Slit`) and YAG-screen imagers (`Scintillator` + `Camera`).

## Per-shot diagnostics

- **Intensity-position monitors** (`MFX:DG1:IPM` and siblings): each reads both flux and beam position per shot, presenting the Sensor Role through the loose `FluxMonitor` and `Diagnostic` families (DIAG-1). Per-shot intensity normalization (dividing each pattern by its incident pulse intensity) is a DAQ-plane concern, not a CORA observation row (DAQ-1).
- **Wave8** (`MFX:DG1:MMS:08`): a fast per-shot intensity / wavefront diagnostic; loose `FluxMonitor`.
- **Timetool / arrival-time monitor** (`MFX:ATM`): measures the X-ray-to-optical-laser timing jitter shot by shot. It presents the Sensor Role (loose `Diagnostic`), but its reason for existing is to drift-correct the pump-probe delay, a cross-timing-domain relationship CORA has no model for (LASER-1).

## The pump-probe laser

The femtosecond optical laser (`LAS:FS45` timing, `MFX:LAS:MMN:*` motors) excites the sample before the X-ray probe. The laser device folds into the loose `Laser` family (the 4-ID POLAR precedent, model-vs-hazard open), and the delay stage is a `LinearStage`. What does not fold is the synchronization: the `lxt_ttc` SyncAxis holds the laser and FEL timing domains together to within a ~50 fs deadband, a cross-timing-domain relationship CORA's single-domain `PartitionRule` cannot express (LASER-1). The laser is also a class-4 hazard gated by a Clearance (see [Governance](../governance.md)).

## The interaction point

- **Sample delivery** (`MFX:LJH`): a Beckhoff-controlled liquid jet (and a fixed-target option) streams microcrystals into the beam for serial crystallography. Sample delivery is endstation-specific with no storage-ring analog; it is carried with its shape and the `Subject` custody lifecycle deferred, and no Family is coined (SAMPLE-1), mirroring how I03 carries its sample-exchange arm.
- **Von Hamos emission spectrometer** (`MFX:SPEC`): a 6-crystal X-ray emission spectrometer for XES and HERFD. It is the **one device with no CORA Family**: a crystal-analyzer dispersive spectrometer that composes analyzer crystals and a 2D detector along a dispersive geometry, structurally distinct from a `Monochromator`. It is carried as the single new loose family, `EmissionSpectrometer`, routed to naming-r3. The same gap appeared at MAX IV Balder (the SCANIA-2D spectrometer), so the rule-of-three that would graduate it may already be near (SPEC-1).

See the [Detector](detector.md) page for how the recorded shots leave the hutch, and [Open questions](../questions.md) for the conditioning and endstation items still to confirm.
