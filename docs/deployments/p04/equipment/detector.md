# Detector

*The detection Assets at P04: the drain-current electrometers and the EXP2 beam-path diagnostics. First cut, reverse-engineered from the OnlineXML.*

P04's detection for soft X-ray absorption is the **drain-current electrometer** (total electron yield), present at both endstations. EXP2 additionally carries a line of motorized phosphor screens with beam-monitor cameras for beam-path diagnostics. The photoemission analyzer (the EXP endstation spectrometer) is not a motor row in the registry and is not modelled here (`DET-1`).

## Electrometers

- `Electrometer` (EXP1) binds `FluxMonitor`: the EXP1 Keithley 6517A electrometer (`p04/keithley6517a/exp1.01`); sample drain-current / I0 measurement for XAS (total electron yield).
- `Electrometer` (EXP2) binds `FluxMonitor`: the EXP2 Keithley 6517A electrometer (`p04/keithley6517a/exp2.01`).

## EXP2 beam-path diagnostics

- `DiagnosticScreens` binds the catalog `Screen` Family: the EXP2 motorized phosphor screens (`Screen_aft_PGM2 / RMU2 / EXP2 / EXSU2 / PIPE`), inserted into the beam path at points along the experiment section for alignment.
- `BeamMonitorCameras` binds `Camera`: the EXP2 Vimba / Allied Vision cameras imaging the diagnostic screens.

## Families and confirmations

The electrometers bind the catalog `FluxMonitor` Family, the cameras `Camera`, the screens the catalog `Screen` Family (the 2-BM `FLAG-1` precedent). No new Family is coined. The measured channel of each electrometer (drain current vs I0), the screen positions, and the camera-to-screen mapping are not in the registry and are pending (`DET-1`, `DIAG-1`); the photoemission analyzer is a named endstation instrument not exposed in the OnlineXML. See [Open questions](../questions.md).
