# Extracted facts: ID16B

Device facts for `ID16B` (facility `esrf`), read from the public ID16B BLISS Beacon config
(`gitlab.esrf.fr/id16b/beamline_configuration`, commit `7cba4dd`, 2026-05-19). Candidates:
confirm every row with ID16B staff before treating as a CORA-owned fact (a config snapshot is
strong evidence, not a guarantee against the live system). Handles are BLISS object names and
Tango device names, carried in the descriptor `pv` field (the opaque control-handle slot);
ESRF runs BLISS / Tango, not EPICS. The control Tango domain is `id16b` / `id16na` (the nano
branch).

ID16B is the ESRF nano-analysis / nano-imaging beamline: it focuses the beam to a nanoprobe
with KB mirrors and runs two modes, **nano-tomography** (`daiquiri_tomo`) and **nano-XRF /
fluorescence microscopy** (`daiquiri_fluo`, `daiquiri_fluo3d`, including fluorescence-tomography).
It is the second ESRF deployment after ID19 and the fleet's first nanoprobe on a BLISS floor.

This cut models the source, the optics (including the KB nanofocus), the sample-scanning stack,
and the two detection chains (the XRF spectrometers and the area detectors). The sample
environments (cryo, furnace, xeol) are noted, not modelled (ENV-1).

## Source (insertion device)

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| InsertionDevice | InsertionDevice | U205 undulator (ESRF_Undulator) | the ID16B straight-section undulator source (SRC-1) |

## Optics (OH)

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| Monochromator | Monochromator | `kohzu` (ID16Bkohzu DCM); axes `mono`/`Edcm`/`Edcmund` (iceid162); crystals Si111/Si333/Si311 | Kohzu double-crystal monochromator, energy + tracking (OPT-1) |
| PrimarySlits | Slit | `s1h_slits`/`s1v_slits` (s1fh/s1bh/s1fv/s1bv, gap+offset) | white-beam primary slits |
| SecondarySlits | Slit | `s2_slits` (s2fh/s2bh, gap+offset) | secondary slits |
| BeamMonitors | FluxMonitor | EBV beamviewers `bpm2`/`bpm3`/`bpm5` (Lima `id16na/limaccds/bpm*` + diode counters) | beam-position / intensity monitors (DIAG-1) |

## KB nanofocus + sample (EH)

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| KBMirrors | Mirror | `kbx`, `cfocus`, `cfocus2` (iceid164) | Kirkpatrick-Baez focusing mirror pair, the nanoprobe (OPT-1) |
| SampleRotation | RotaryStage | `srot`/`srot_enc` (etel Tango `id16b/dsc2p/rot16`), `srot2` (iceid164) | tomographic / mapping sample rotation (SAMPLE-1) |
| SampleStage | LinearStage | `sx` (etel), `sy`/`sz` (iceid164, encoded) | coarse sample positioning / centring (SAMPLE-1) |
| SampleScanner | LinearStage | `sampy`/`sampz` (vscanner1, PI piezo), `sypz` (vscanner2) | fine piezo raster scanner for XRF mapping (SAMPLE-1) |
| ThirdSlits | Slit | `s3h_slits`/`s3v_slits` (s3fh/s3bh/s3uv/s3dv, iceid164) | sample-side defining slits |

## Detection

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| FluoDetector | EnergyDispersiveSpectrometer | FalconX `fxb` (`id16b/moscav1/fxb`), `fx8` (`tcp://wid16bfx:8000`) | multi-element silicon-drift XRF detector; reuses the 2-ID/SRX/XFM EnergyDispersiveSpectrometer family (DET-1) |
| OpticalSpectrometer | EnergyDispersiveSpectrometer | QEPro `qepro` (OceanOptics, `id16b/moscav1/qepro`); Hamamatsu `hama1` | optical-emission / xeol spectrometer (DET-2) |
| TomoDetector | Camera | PCO `pco1`/`pco2` (`id16na/limaccds/pco*`), Zyla (`id16b/limaccds/zyla`) | indirect-detection area detectors for nano-tomography; Camera presents the Detector Role (DET-1) |
| DetectorStage | LinearStage | `DETPOS` (DetectorPositioning), `detpos` axes | detector positioning / propagation distance (DET-1) |

## Shutters

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| FastShutter | Shutter | `fshut` (iceid164 `fshut_motor`) | sample-side fast shutter (PSS-1 for the PSS leaves) |

## Noted, not modelled in this cut

- Sample environments: cryostream (`EH/cryo`), furnace (`EH/furnace`), xeol (`EH/xeol`),
  Eurotherm/nanodac regulation (`regul/`). A `Cryostat` Family is not yet in the catalog; the
  sample environment is deferred to keep this cut vocabulary-neutral (ENV-1).
- The `mapping`, `oda`, `taurus`, `webui`, `services` software layers (not beamline devices).
- The simulation sessions (`SIMUL`, `simulmot`, sim_* axes).

## Open confirms

- **CTRL-1** -- the BLISS / Tango handles are read from the public config; verify current.
- **SRC-1** -- the U205 undulator energy reach and gap mapping.
- **OPT-1** -- the Kohzu crystal-pair selection per energy and the KB focal spot / working distance.
- **SAMPLE-1** -- the operative rotation / coarse / piezo-scanner axis set per mode (tomo vs fluo).
- **DET-1 / DET-2** -- the operative XRF detector and area detector per mode; the optical spectrometer role.
- **ENV-1** -- whether the cryo / furnace / xeol sample environments enter a later cut.
- **PSS-1** -- the personnel-safety permit signals behind the front-end / fast shutters.
