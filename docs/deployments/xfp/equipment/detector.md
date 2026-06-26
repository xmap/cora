# Detector

*The flux and beam-position monitors that measure the delivered dose, and why XFP has no imaging detector: the footprinting structural readout is offline mass spectrometry. Reverse-engineered from `NSLS2/xfp-profile-collection` (`startup/`); PVs read from the profile collection, carried confirm.*

This is the page where XFP departs most sharply from the rest of the fleet, so state it plainly: **XFP has no scattering, area, or imaging detector at all.** It is a dose-delivery beamline. The thing it "measures" on the instrument is the **incident flux**, which together with the exposure time and the attenuation is the **delivered dose**. The structural readout, which residues of the macromolecule were modified, is done **offline by mass spectrometry**, downstream of the beamline and entirely absent from the profile collection. So the detection side models flux / dose monitors plus the offline-readout seam.

## Detection chain (flux / dose monitors)

| Device | Family | PV | Role |
| --- | --- | --- | --- |
| `FluxMonitor` | `FluxMonitor` | `XF:17BM-BI{EM:1}EM180:` | the primary QuadEM electrometer: incident flux plus a per-exposure time-series, the basis for the delivered dose (`DET-1`, `DOSE-1`) |
| `BeamPositionMonitor` | `BeamPositionMonitor` (loose) | `XF:17BM-BI{EM:BPM1}` | the Sydor four-channel monitor: per-quadrant currents, beam x / y, and a sum-current total flux (`DIAG-1`) |

The chain measures the beam, not a sample signal. The QuadEM electrometer reads the incident flux and records a per-exposure time-series, which is what lets a run compute the delivered dose; a DIODE PDM array-logger (`XF:17BMA-CT{DIODE-PDM:1}`) accumulates the dose array as a further monitor, and a second electrometer (`XF:17BM-BI{EM:2}`) adds channels. The Sydor monitor reads the beam position (for stability and alignment) and a sum current (a further total-flux readback). Beamline alignment is done by scanning a motor against one of these flux monitors and taking the centre of mass, not by imaging (there is no alignment camera in the profile collection).

The **flux-to-absorbed-dose calibration**, the conversion from measured photons to the hydroxyl-radical dose the sample actually received, is not in the profile collection; it lives in offline analysis. CORA records the measured flux and the exposure as the dose evidence and treats the absorbed-dose calibration as a seam constant to be sourced from staff (`DOSE-1`, `READOUT-1`).

## Why there is no imaging detector: the offline-readout seam

A footprinting experiment is read out by mass spectrometry, which is a separate instrument in a separate lab. The beamline's role ends when it has delivered a known dose to a sample and captured the irradiated aliquot. So what a CORA run at XFP produces is:

- a **footprinted sample**, the irradiated aliquot, often captured into a fraction-collector tube (see [Sample](sample.md)); and
- a **dose record**: the exposure time, the filter thickness, the flux time-series, and the well or tube identity.

There are no measurement frames to store. The mass-spectrometry analysis that turns the footprinted sample into a structural map is the **offline-readout seam**: it happens downstream, off the beamline, and is absent from the profile collection. CORA is the system of record for the dose and the sample provenance; the structural readout is a separate, later step that a future integration could link back to the run, but is not modelled here (`READOUT-1`).

This is the genuinely-new shape XFP brings to the fleet: a beamline whose product is a dosed sample plus a provenance record, not a detector image.

## Why no new detector family

The detection side reuses the catalog: the QuadEM electrometer binds `FluxMonitor`, the same role the fleet's other flux monitors fill, and the Sydor monitor binds the loose `BeamPositionMonitor` already held under review across the fleet (4-ID, 8-ID, 9-ID, ISS, FMX) pending the sensor fold-versus-promote decision; XFP adds a sighting, not a new Family (`DIAG-1`). No `Camera`, no `Scintillator`, no area detector is modelled, because none exists: the readout is offline. The dose-delivery role is expressed by the [Source](../beamline.md) gating (shutters + `TimingController` + `Filter`) and these flux monitors, not by a new detector class.

## Families

Reused from the catalog: `FluxMonitor` (the QuadEM electrometer and the DIODE array-logger). Loose and held under review: `BeamPositionMonitor` (the Sydor monitor, `DIAG-1`). New families: none; nothing graduates and the catalog is unchanged. There is no Detector-role imaging device; the footprinting readout is offline mass spectrometry (`READOUT-1`). The flux-to-dose calibration is a seam constant (`DOSE-1`). See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family decisions, and [beamline.md](../beamline.md) for the source walk.
