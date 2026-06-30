# Extracted facts: BM25

Candidate device facts for `bm25` (ESRF BM25 SpLine, the Spanish CRG beamline; XRD / XAS / surface science). Candidates only; confirm every row before modeling. Source: the public BM25 BLISS Beacon config (`gitlab.esrf.fr/bm25/beamline_configuration`, commit `81da855`, last activity 2025-12-08). Every value is carried `confirm` until BM25 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! warning "Sparse public config: detectors + sample environment only"
    BM25's public Beacon config is the thinnest in the ESRF set. It carries ONLY the detectors (Eiger2 area detectors, a FalconX fluorescence MCA), a Eurotherm gas blower, the P201 counter cards, and the WAGO crates. It carries NO monochromator, NO motors / stages, NO slits, NO shutters, and NO source device, and the one session (`mcl`) has an empty `config-objects` list. This is what the public mirror contains, not a defect in the read: the optics / motion / source half of the beamline is evidently maintained elsewhere (a private repo or a separate BLISS config not mirrored publicly). Per the practice, the absent halves are recorded as open questions, NOT inferred. SpLine (BM25) is a Spanish CRG bending-magnet beamline; the device topology below is the public-config subset only.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding. Only the devices present in the public config are listed; the optics / motion / source devices are absent from source (see deferred / absent).

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| AreaDetector4c | Camera | `d25/limaccds/eiger2_4c` (BLISS `eiger4c`, Lima, `lima/eiger.yml`) | Eiger2 4c photon-counting area detector | eh | detection | yes |
| AreaDetector6c | Camera | `d25/limaccds/eiger2_6c` (BLISS `eiger6c`, Lima) | Eiger2 6c photon-counting area detector | eh | detection | yes |
| AreaDetectorS2D2 | Camera | `d25/limaccds/eiger2_s2d2` (BLISS `eigers2d2`, Lima) | Eiger2 S2D2 photon-counting area detector | eh | detection | yes |
| FluorescenceMCA | EnergyDispersiveSpectrometer | `tcp://lap2bm25:8000` (BLISS `fxbm25`, FalconX, `devices/XIA/falconx.yml`) | XIA FalconXn fluorescence MCA (config dir `C:\\blissadm\\falconx\\config\\BM25`) | eh | detection | yes |
| SampleTemperatureController | TemperatureController | `bm25gasblower.esrf.fr` (BLISS `euro3500`, Eurotherm2000 model 3500, `regulation/eurotherm3508.yml`); Tango loop `d25/regulation/euro_loop` (BLISS `euro`) | gas-blower loop: input `euro_in` (Celsius), output `euro_out` (%), loop `euro_loop` | eh | sample | yes |
| AnalyzerCounters | GenericProbe (?) | `tcp://ld254:8909` / `:8910` (BLISS `p201_ld254_0` / `p201_ld254_1`, CT2 P201); `tcp://ld255:8909` (`p201_ld255`); `tcp://0.0.0.0:8909` (`p201_d25lab`) | beam-monitor / counting channels (P201 CT2 cards) | eh | detection | yes |

The device-level handles above are read verbatim from the cloned config (`lima/eiger.yml`, `devices/XIA/falconx.yml`, `regulation/eurotherm3508.yml`, `counters/*.yml`). The `p201_d25lab` card binds `tcp://0.0.0.0:8909` (a lab / template address, not a production host); recorded verbatim as it appears in source. The WAGO crates (`wcd25b/d/f/h`) carry analog I/O mappings (gains, thresholds) but are infrastructure, not beamline Assets (see deferred / absent).

## Role hints

- **Detector**: the three Eiger2 area detectors (4c / 6c / S2D2) for XRD / scattering.
- **Sensor**: the FalconX fluorescence MCA (energy-dispersive, presents Sensor by what it measures, the EnergyDispersiveSpectrometer lineage); the P201 CT2 counter cards.
- **Regulator** (settable continuous setpoint): the Eurotherm 3500 gas-blower loop (TemperatureController, presenting Regulator).
- **No Positioner, no Controller, no source** is present in the public config: there are no motors, no monochromator, no slits, and no insertion-device / machine device. This is the config's state, not an omission in the read.

## Trust hints

The BM25 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has none). SpLine is a Spanish CRG (operated by CSIC / Spanish partners on an ESRF bending-magnet port), the same CRG-governance seam note as BM26 / DUBBLE: partner-operated scope under the ESRF Site, which a CORA Federation / Trust model would represent distinctly. The empty `mcl` session and the partial public config mean the orchestration layer is not fully visible in public source. No binding here.

## New-family watch

Nothing to coin from BM25. The few devices present all bind already-graduated families:

- **Eiger2 -> Camera (graduated), FalconX -> EnergyDispersiveSpectrometer (graduated), Eurotherm -> TemperatureController (graduated).** BM25 is a further consumer of each; nothing new.
- **The XRD / XAS techniques have no optics in source.** SpLine runs XRD and XAS, which require a monochromator and motorized diffractometer / sample stages, but none appear in the public config. So unlike a normal pass, BM25 contributes almost nothing to the recurrence counts (only the detection / sample-environment subset). This is flagged, not worked around.
- **GenericProbe (?) for the P201 chain.** Same loose binding as the other ESRF beamlines; held, not coined.

## Deferred / absent

This beamline's deferred list is unusually large because the public config is a partial mirror. None of the following is a defect in the read; each is genuinely absent from public source and recorded as an open question, not inferred.

- **Monochromator (`MONO-1`).** SpLine runs XRD / XAS, which need an energy-selecting mono; none is in the public config.
- **Motion / stages / diffractometer (`MOTION-1`).** No motors, no IcePAP, no slits, no sample stage, no diffractometer in the public config. The `mcl` session has an empty `config-objects` list.
- **Shutters and source (`PSS-1`, `SRC-1`).** No front-end / beam shutters and no bending-magnet / machine device in the public config.
- **The full beamline config location (`CONFIG-1`).** The optics / motion / source half of BM25 is evidently maintained outside this public mirror (a private repo or a separate BLISS config). Confirm with BM25 staff where the production Beacon config lives before treating this subset as the whole beamline.
- **WAGO crates (`INFRA-1`).** The `wcd25b/d/f/h` crates carry analog I/O (gain / threshold setpoint values) but are infrastructure, not beamline Assets; not mapped.
