# Detector

*The area detector, beam-view cameras, beam-position monitors, and counters. First cut; PVs read from the beamline config, carried confirm.*

The detection side of POLAR is a mix: an Eiger area detector for diffraction patterns, flag-view cameras for beam alignment, beam-position and intensity monitors that diagnose and normalize the beam, and scaler counters. They are modelled in the detection stage of the [descriptor](../inventory.md). The Eiger and flag cameras reuse the `Camera` Family and the scalers the `GenericProbe` Family; the beam-position monitors bind a loose `BeamPositionMonitor` Family.

## Detector chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Eiger1M` | `Camera` | Eiger 1M area detector (`4idEiger:`); model and frame rate unconfirmed (`DET-1`) |
| `FlagCamera_HHL`, `FlagCamera_Mono` | `Camera` | beam-view flag cameras at 4-ID-A (Vimba) |
| `VortexFluorescence` | `BeamPositionMonitor` (loose) | SGZ Vortex; a fluorescence / energy-dispersive point detector, classification a placeholder (`DET-2`, `TOPO-3`) |
| `XBPM_G`, `XBPM_H` | `BeamPositionMonitor` (loose) | X-ray beam-position monitors at 4-ID-G / H |
| `Sydor_G`, `Sydor_H` | `BeamPositionMonitor` (loose) | Sydor electrometer position monitors |
| `TetrAMM_B` | `BeamPositionMonitor` (loose) | TetrAMM picoammeter / position monitor at 4-ID-B |
| `Scaler_1`, `Scaler_2` | `GenericProbe` | CTR8 scaler channel sets, shared across B / G / H |

## Families

Reused from the catalog: `Camera` (the Eiger and flag cameras) and `GenericProbe` (the scalers). The beam-position and intensity monitors are bound to a loose `BeamPositionMonitor` Family, held for gate-review (it recurs across beamlines but the Sensor fold-vs-promote question is open, DIAG-1/FLUX-1; see [Model](../model.md#loose-family-graduation)). Whether each monitor is a true position monitor or an intensity (I0) normalizer is `BPM-1`; the Vortex classification is `DET-2`. The detector camera model is `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
