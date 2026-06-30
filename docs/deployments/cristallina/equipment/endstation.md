# Endstation

*The Cristallina endstation: the I0 chamber, the DM1 and DM2 diffractometers, the DilSc dilution-fridge vector magnet, and the Cristallina-MX sample stage. Design-phase, with the `slic`-derived handles recorded.*

The Cristallina experiment hutch is where the focused beam meets the sample and the time-resolved diffraction happens, in a low-temperature, high-magnetic-field environment. It is the most novel sample environment in the PSI set, and every part of it folds into an existing CORA shape: the diffractometers into a graduated Assembly, the magnet into a held loose family, the thermometry into a graduated Family.

## The diffractometers

Cristallina-Q has two diffraction platforms, both built by the `slic` `Diffractometer` driver from ECMC servo-motor axes:

- **DM1** (`SARES31-GPS`): the dilution-fridge diffractometer (twotheta / theta plus base and sample translations).
- **DM2** (`SARES32-GPS`): the pulsed-magnet diffractometer (DM1's axes plus rot_x / rot_z swivels). Its PV channels are commented out of the active `slic` config, so it is carried as present-hardware-not-acquired (DISABLED-1).

Each is the graduated [`Diffractometer` Assembly](../../../catalog/assemblies.md): a composed `Goniometer` (the sample circles), a `RotaryStage` 2-theta detector arm, and a reciprocal-space `PseudoAxis`. The Bernina GPS / XRD platforms were the Assembly's third and fourth bindings; the Cristallina DM1 / DM2 are its fifth and sixth. No new Family or Assembly is coined (DIFF-1, reciprocal-space partition rule DIFF-2).

## The dilution-fridge vector magnet

The defining sample environment, the "DilSc". It is a dilution refrigerator with a 3-axis vector superconducting magnet, and it folds into two existing CORA shapes:

- **Thermometry** (`SARES31-DIL-LS1`): a LakeShore 372 regulating the mixing-chamber temperature through a PID loop, with per-band calibration curves. It binds the **graduated `TemperatureController`** Family (presents the Regulator Role), the [ESRF ID32](../../id32/equipment/sample.md) VTI precedent.
- **The magnet** (`SARES31-MAG-IPS1`): an Oxford Mercury iPS power supply driving three field axes (X, Y to ±0.6 T; Z to ±5.2 T; ramp capped at 0.5 T/min). It binds the **loose `Magnet`** family, which is held at the rule-of-three. Its three consumers are 4-ID, i10-1, and the ID32 9 T XMCD magnet; Cristallina is the **fourth**. That reinforces the case for graduating `Magnet`, but the graduation stays deferred to its dedicated gated PR rather than being slipped in here (MAG-1). The vector geometry (three independently-ramped axes) is a per-Asset setting, not a Family split, the same way axis counts are for diffractometers.

The magnet and its liquid-helium cryogens are a personnel- and quench-safety hazard, gated by a Clearance (see [Governance](../governance.md)). An alternative SECoP / Frappy magnet driver (`dilsc.psi.ch:5000`) and the pulsed-magnet's server-side pulse-tube synchronization service are not in the operational EPICS path modelled here (ENV-1).

## Serial crystallography

The Cristallina-MX endstation runs serial crystallography on a fast XY sample stage (`SAR-EXPMX`, the `slic` swissmx driver), which folds into `LinearStage`. The sample delivery beyond the fast stage is endstation-specific and deferred (SAMPLE-1).

## No pump-probe laser

Unlike the [Alvra](../../alvra/equipment/endstation.md) and [Bernina](../../bernina/equipment/endstation.md) endstations, the `slic` source carries no pump-probe optical laser: there are no `SLAAR` / `PALM` / `PSEN` devices. The only laser is the X-ray alignment laser in the [optics hutch](../beamline.md). Pump-probe timing is mediated by the CTA sequencer and the EVR (see [Controls](controls.md)). Whether a pump-probe laser exists in another controls layer is carried as an open question (LASER-1).

See the [Detector](detector.md) page for how the recorded shots leave the hutch, and [Open questions](../questions.md) for the endstation items still to confirm.
