# Detector

*The SAXS / WAXS Pilatus area detectors, the scanning-mode fluorescence spectrometer, the detector translations, the beamstop, the flux and beam-position monitors, and the Zebra trigger. Reverse-engineered from `NSLS2/lix-profile-collection` (`startup/`); PVs read from the profile collection, carried confirm.*

LIX's measurement is the scattering pattern on a Pilatus area detector: a small-angle pattern on the SAXS head and a wide-angle pattern on the WAXS head, recorded as the solution flows through the cell or the microbeam rasters across a sample. In the scanning-microbeam mode, a fluorescence spectrometer adds an element map. Every device on the detection side binds an existing catalog Family, so this page coins nothing.

## Detection chain

| Device | Family | PV | Role |
| --- | --- | --- | --- |
| `SaxsDetector` | `Camera` | `XF:16IDC-DT{Det:SAXS}` | Pilatus 1M, small-angle scattering (bio-SAXS); the primary scattering detector (`DET-1`) |
| `WaxsDetector` | `Camera` | `XF:16IDC-DT{Det:WAXS2}` | Pilatus 900K, wide-angle scattering (`DET-1`) |
| `FluorescenceDetector` | `EnergyDispersiveSpectrometer` | `XF:16IDC-ES{Xsp:1}` | Xspress3 multi-channel fluorescence detector, used in the scanning-microbeam mode for element mapping (`DET-1`) |
| `DetectorStage` | `LinearStage` | `XF:16IDC-ES{Stg:SAXS}` | the SAXS / WAXS detector translations and the sample-to-detector distance (`DET-1`) |
| `Beamstop` | `BeamStop` | `XF:16IDC-ES{BS:SAXS}` | blocks the SAXS direct beam (`DET-1`) |
| `EndstationFluxMonitor` | `FluxMonitor` | `XF:16IDC-BI{BPM:1}` | TetrAMM electrometers reading incident and transmitted flux for normalization (`DET-1`) |
| `BeamPositionMonitor` | `BeamPositionMonitor` (loose) | `XF:16IDB-CT{Best}` | the Best aggregator deriving beam x / y from the TetrAMM quadrant currents (`DIAG-1`) |
| `Trigger` | `TimingController` | `XF:16IDC-ES{Zeb:1}` | the Zebra generating detector triggers (a soft-input pulse and position capture) gated from the Newport XPS (`TRIG-1`) |

The chain reads outward from the sample. The Pilatus 1M records the small-angle scattering, the structure-bearing signal for a protein in solution; the Pilatus 900K records the wide-angle pattern. The detector stage translates them to set the sample-to-detector distance, which selects the accessible Q-range. The beamstop blocks the direct beam off the SAXS detector face; no separate beamstop diode is in the profile collection, so the direct-beam intensity is read off the detector. The TetrAMM electrometers read incident and transmitted flux as scalars for normalization, essential for solution scattering where the signal is weak and the buffer must be subtracted. The Best aggregator derives the beam position from the TetrAMM quadrants for diagnostics.

A note on what is and is not live. A third Pilatus, a 300K WAXS1 head, is present but **commented out** in the profile collection, so it is not modelled (`DET-1`). The Xspress3 fluorescence detector is initialized in a try / except and may be absent on a given run, so its per-run availability is carried pending (`DET-1`). The Kinetix area camera and the Prosilica viewing cameras are not modelled in this cut. Detector distances are calibration values carried as settings on the stage, not invented here (`DET-1`).

## Triggering

Exposures are software-driven, with the Zebra producing the detector triggers. The fast shutter (see [Source](../beamline.md)) is driven by a TTL pulse from the timing seam; the Zebra (`XF:16IDC-ES{Zeb:1}`) generates a soft-input pulse (`SOFT_IN:B0`) and, for fly scans, position capture, gated from the Newport XPS trajectory controller. The Zebra binds the catalog `TimingController` Family, the same role the fleet's other position-capture boxes fill. There is no Struck / SIS scaler and no delay generator in the profile collection; the triggering is the Zebra plus the fast-shutter TTL (`TRIG-1`).

## Why no new detector family

The detection side reinforces the catalog rather than extending it. The two Pilatus heads reuse `Camera`; the Xspress3 reuses the graduated `EnergyDispersiveSpectrometer`; the detector translations reuse `LinearStage`; the SAXS beamstop reuses `BeamStop`; the TetrAMM electrometers reuse `FluxMonitor`. The only loose binding is the `BeamPositionMonitor` Family for the Best-aggregated beam position, and that Family is already held under review across the fleet (4-ID, 8-ID, 9-ID, ISS, FMX) pending the sensor fold-versus-promote decision; LIX adds a sighting, not a new Family (`DIAG-1`).

LIX's scattering detection overlaps the materials-scattering fleet heavily: the Pilatus / FluxMonitor / BeamStop vocabulary is shared with SMI, CMS, I22, and 9-ID, with zero new families. What is distinct at LIX is not the detector but the Subject and the fluidic delivery (see [Sample](sample.md)); the detection side is reinforcement.

## Families

Reused from the catalog: `Camera` (the two Pilatus heads), `EnergyDispersiveSpectrometer` (the Xspress3), `LinearStage` (the detector translations), `BeamStop` (the SAXS beamstop), `FluxMonitor` (the TetrAMM electrometers), and `TimingController` (the Zebra). Loose and held under review: `BeamPositionMonitor` (the Best-aggregated beam position, `DIAG-1`). New families: none; nothing graduates and the catalog is unchanged. The disabled WAXS1 head, the optional Xspress3, and the detector-distance calibration are `DET-1`. See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family decisions, and [beamline.md](../beamline.md) for the source walk.
