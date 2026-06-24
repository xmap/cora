# Procedures

*Staff-run procedures, reverse-engineered from the FXI scan plans and reconstruction code. Each is derived from a public plan, not from operating the beamline, so it is carried `confirm` until FXI staff verify it.*

A Procedure is a staff-run sequence with preconditions and an outcome (often a Calibration). These are read from `startup/41-scans.py`, `startup/94-tomo_recon.py`, and the calibration helpers; the exact step parameters and decision points need staff confirmation.

## Energy-lookup calibration

Builds the table that the energy-change move interpolates.

- Source: `record_calib_pos_new_xh`, `trans_calib_xh` (`startup/41-scans.py`).
- What it does: at a set of reference energies, record the coordinated positions of the DCM (Chi2, Th2), zone plate (X, Y), condenser, aperture, and detector that keep the image in focus and the magnification constant. The points become the `CALIBER` / `trans_calib_xh` lookup.
- Outcome: a Calibration that the [`energy_setting` recipe](recipes.md) reads. Without it, the coupled energy move cannot interpolate.

## Rotation-center finding

Locates the tomographic rotation axis on the detector before or during reconstruction.

- Source: `find_rot`, `rotcen_test` (`startup/94-tomo_recon.py`).
- What it does: reconstruct trial slices across a range of candidate center offsets and pick the sharpest, or derive the center from a 0/180-degree projection pair.
- Outcome: the rotation-center value used by the reconstruction (Reckoner) leg.

## Focus and field alignment

- Knife-edge / scintillator-focus and secondary-source-slit (`ssa`) alignment scans appear in the supporting plans. They set the scintillator Z and the illumination, producing focus and field Calibrations.
- These are named in source but their step detail is not fully captured this pass; they are carried `confirm` pending staff confirmation.

## Recovery

The profile collection does not expose a documented recovery runbook (FXI's equivalent of 2-BM's hexapod-reboot script was not found in this pass). Recovery procedures will be added when the controller boxes are identified (DRIVE-1) and a real runbook is confirmed; a runbook invented from absence would not be record.
