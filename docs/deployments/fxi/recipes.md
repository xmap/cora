# Recipes

*The deployment-bound runbooks CORA would carry for FXI, in ISA-88 shape. CORA's design; the beamline's existing routines are the evidence, not the spec CORA mirrors. Carried `confirm` until staff verify.*

A CORA Recipe is a named, deployment-specific sequence with preconditions, steps, and a result that expands into Procedures.

## Energy setting

Sets the beamline to a target energy by the coupled move that holds magnification constant.

- Preconditions: the energy-lookup Calibration exists (see [Procedures](procedures.md#energy-lookup-calibration)); the target energy is within the calibrated range.
- Steps: interpolate the lookup at the target energy, then co-move the monochromator, zone plate, condenser, aperture, and detector to the interpolated positions.
- Result: the beamline at the target energy with the image still focused and magnified the same. CORA runs this as the energy-change leg of its Conductor.

## Dark and flat capture

Captures the reference frames a tomography reconstruction needs.

- Steps: close the fast shutter and record dark frames; move the sample out and record flat (white) frames; restore.
- Result: dark and flat frame sets attached to the run. CORA models these as subject-less conducted Runs (the Phase-of-Run pattern), not part of the sample projection set.

## Element-edge XANES

Runs energy-resolved imaging across an absorption edge.

- Steps: build the energy list for the chosen element edge, then at each energy run the energy-setting recipe and acquire an image or tomogram.
- Result: a spectro-tomography dataset. The element edges and out-positions are experiment-specific, so this Recipe is deployment-bound, not a portable Method.
