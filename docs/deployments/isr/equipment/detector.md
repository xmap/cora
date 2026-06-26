# Detector

*The Eiger 1M area detector, the diagnostic screen cameras, the motorized beam-position monitor, and the commented-out flux monitors. Reverse-engineered from `NSLS2/isr-profile-collection` (`startup/`); PVs read from the profile collection, carried confirm.*

ISR's detection side, in the public source, is the Eiger 1M area detector plus diagnostics. Because the multi-circle diffractometer is absent (see [Sample](sample.md)), there is no detector two-theta arm and no point / scaler counter; the scattered intensity is read from the Eiger, and a rocking scan of the sample `th` is the working measurement. Every device here binds an existing catalog Family.

## Detection chain

| Device | Family | PV | Role |
| --- | --- | --- | --- |
| `AreaDetector` | `Camera` | `XF:04IDD-ES{Det:Eig1M}` | the Dectris Eiger 1M, the primary scattering detector (the only detector in the profile collection's scan plans) (`DET-1`) |
| `DiagnosticCamera` | `Camera` | `XF:04IDC-BI:1{Scr:3}` | the diagnostic YAG fluorescent-screen beam-viewing cameras (three Prosilica in zones A and C) (`DIAG-1`) |
| `BeamPositionMonitor` | `BeamPositionMonitor` (loose) | `XF:04IDB-BI:1{BPM:3}` | the motorized beam-position-monitor stage (only its stage motors are bound) (`DIAG-1`) |

The Eiger 1M carries the scattering-geometry metadata (detector distance, beam center, photon energy, threshold energy) as detector configuration, not as a motorized arm; its write path in source is a commissioning `testing/` path with a simulated file plugin, a signal that the profile collection is early-stage (`DET-1`). The Prosilica screen cameras are YAG-screen beam diagnostics, not a science detector. The beam-position-monitor `BPM:3` binds the loose `BeamPositionMonitor` Family, but only its stage motors are bound; the QuadEM electrometers that would read its flux / position are commented out in source.

## Flux monitoring is commented out

ISR's three QuadEM electrometers (`EM:1`, `EM:2`, `EM:3`) are defined in the profile collection but **all commented out**, along with the secondary-source slit that embeds one of them. So no `FluxMonitor` Asset is modelled in this cut: an incident-flux / I0 monitor is a real need for resonant and diffraction work, but CORA does not model a device the source has disabled. The flux-monitor coverage is carried as an open question (`DET-1`). There is likewise no point detector or scaler for diffraction counting in source; intensity is read from the Eiger ROI / stats.

## Why no new detector family

The detection side reuses the catalog: the Eiger 1M and the screen cameras bind `Camera`, and the motorized BPM stage binds the loose `BeamPositionMonitor` already held under review across the fleet (4-ID, 8-ID, 9-ID, ISS, FMX) pending the sensor fold-versus-promote decision; ISR adds a sighting, not a new Family (`DIAG-1`). No new detector family is warranted, and because the diffractometer is absent, there is no detector-arm device to model (`DIFF-1`).

## Families

Reused from the catalog: `Camera` (the Eiger 1M and the screen cameras). Loose and held under review: `BeamPositionMonitor` (the motorized BPM stage, `DIAG-1`). New families: none; nothing graduates and the catalog is unchanged. The flux-monitor electrometers are commented out in source, so no `FluxMonitor` Asset is modelled (`DET-1`). See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family decisions, and [beamline.md](../beamline.md) for the source walk.
