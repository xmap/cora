# Procedures

*The staff-run procedures CORA would carry for FXI. This is CORA's procedure design; the beamline's existing routines are the evidence that each procedure is needed, not the specification CORA copies.*

A CORA Procedure is a staff-run sequence with preconditions and an outcome, often a Calibration. Each is carried `confirm` until FXI staff verify the step detail.

## Energy-lookup calibration

Builds the table the energy-change recipe interpolates.

- What CORA does: at a set of reference energies, record the coordinated positions of the monochromator, zone plate, condenser, aperture, and detector that keep the image focused and the magnification constant.
- Outcome: a Calibration the [energy-setting recipe](recipes.md) reads. Without it, the coupled energy move has nothing to interpolate.
- Evidence it is needed: the beamline maintains exactly such a lookup today; CORA owns building and storing it as a Calibration.

## Rotation-center finding

Locates the tomographic rotation axis on the detector before or during reconstruction.

- What CORA does: reconstruct trial slices across candidate center offsets and select the sharpest, or derive the center from a 0/180-degree projection pair.
- Outcome: the rotation-center value the reconstruction (Reckoner) leg consumes.

## Focus and field alignment

- What CORA does: set the scintillator focus and the secondary-source/illumination field, producing focus and field Calibrations.
- These routines exist on the floor today; their exact step detail is carried `confirm` pending staff confirmation.

## Recovery

No documented recovery runbook is available from public sources, and the controller identities are not public (DRIVE-1), so CORA does not yet carry an FXI recovery Procedure. Inventing one from absence would not be record; it joins these pages once the controllers are identified and a real recovery routine is confirmed.
