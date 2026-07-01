# Extracted facts: HESEB (ID11L)

Candidate device facts for `heseb` (SESAME ID11L, the Helmholtz-SESAME Beamline, soft X-ray). Candidates only; confirm every row before modeling. Source: the public `SESAME-Synchrotron/HESEBScanTool` + `heseb-pico-6487` repos (read 2026-06). Every value is carried `confirm` until SESAME staff verify it: the facility DAQ repo is strong evidence, not a CORA-owned fact.

!!! note "Leaner public source; EPICS prefix HESEB:"
    HESEB's ScanTool exposes a plane grating monochromator (`PGM:getEnergy`), beamline harmonic rejection (`BL:HarmonicRejection`), an MCA detector, and a sample stage, over EPICS with a `P` prefix `HESEB:`. Much of the public `.db` is scan-metadata records (proposal/PI/file path); the physical-device PVs are fewer than at XAFS/MS, and some are dynamically built (`mca1.R{i}`). Recorded literally where verbatim, flagged where dynamic.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (verbatim from source), role as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (verbatim) | source | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| PlaneGratingMono | GratingMonochromator | `PGM:getEnergy` (+ MonoName/MonoDSpacing scan records) | common.py / HESEB.db | source | yes |
| HarmonicRejection | Filter (?) | `BL:HarmonicRejection` | common.py | source | yes |
| SampleStage | LinearStage | (scan records `XStart`/`YStart`/`XStep`; sample stage) | HESEB.db | sample | yes (motor PV confirm) |
| MCADetector | EnergyDispersiveSpectrometer (?) | `Test:mca1.R{i}` (MCA ROIs; dynamic) | ROIs.py | detection | yes (PV dynamic) |
| PicoAmmeter | FluxMonitor (?) | (Keithley 6487, `heseb-pico-6487` IOC) | heseb-pico-6487 | detection | yes (separate IOC) |

Device-level handles read verbatim from source: `PGM:getEnergy`, `BL:HarmonicRejection`. The sample-stage motor PVs are referenced via scan records (`XStart`/`YStart`/`XStep`) rather than a literal motor handle in the read files; the MCA ROIs are built dynamically (`mca1.R{i}`); the pico ammeter is in the separate `heseb-pico-6487` IOC. These are flagged confirm-pending, not fabricated.

## Role hints

- **Positioner**: the PGM (energy), the sample X/Y stage.
- **Sensor**: the Keithley 6487 pico ammeter (drain/sample current), MCA.
- **Detector**: MCA (energy-dispersive, for soft X-ray fluorescence/absorption).
- **Energy scan**: HESEB scans the PGM energy (soft X-ray NEXAFS/absorption), another scanning-energy beamline (energy_scan Capability relevance, see recurrence).

## Trust hints

Facility-org EPICS DAQ + ScanTool; no queue-server. EPICS-Qt GUI. The ScanTool is the orchestration layer CORA's EdgeConductor would conduct over.

## New-family watch

No new coining:
- **PGM -> GratingMonochromator** (graduated): HESEB is a soft X-ray PGM consumer (joins NSLS-II csx, Diamond i05/i09/i21/b07). Bind directly.
- **MCA -> EnergyDispersiveSpectrometer (?)** (graduated): confirm the MCA binds the energy-dispersive family (it reads an energy spectrum); PV is dynamic, confirm the handle.
- **PicoAmmeter -> FluxMonitor (?)** (graduated): a Keithley 6487 reading sample/drain current; the intensity side is FluxMonitor, confirm.
- **HarmonicRejection -> Filter (?)**: a harmonic-rejection device (mirror or filter); confirm the mechanism (likely a mirror, so possibly Mirror not Filter).
- **SampleStage -> LinearStage** (graduated).

## Deferred / absent

- **PV-confirm:** the sample-stage motor handles and the MCA ROI PVs are referenced indirectly / dynamically; the literal handles need staff confirmation.
- **OPTICS-1:** the PGM grating/mirror motors, slits, and refocusing optics are not literal in the ScanTool; confirm with staff.
- PSS / hutch safety and passive beam-path tier not in the DAQ repo (SCOPE-1).
