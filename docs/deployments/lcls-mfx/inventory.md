# Inventory

*The CORA Asset model for LCLS-MFX: the planned device tree, the `pcdshub`-derived control handles, and what still needs confirming.*

MFX is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Optics and endstation](equipment/optics.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lcls-mfx/beamline.yaml) descriptor that the Source page renders from.

As at the Diamond exercises, the **control handles are known**: `pcdshub`'s `device_config/db.json` and `mfx/beamline.py` record the real EPICS PV prefixes (`FEE1` / `XRT` / `HFX` front-end and transport, `MFX` hutch, `ECS:SYS0` timing). Devices bind to catalog [Families](../../catalog/families.md) where one fits. No vendor Model is bound: `pcdshub` names hardware (Dectris / Rayonix detectors, the von Hamos) but none is procured into the CORA catalog.

## The Asset tree

Root Asset `LCLS-MFX` (`tier = Unit`, `facility_code = slac`); sub-systems nest below by `parent_id`. Bold families are loose design-intent names not in the catalog (they render as plain text). PV prefixes are the `pcdshub` dry facts, carried `confirm`.

| Asset | Family | Control handle (pcdshub) | Notes |
| --- | --- | --- | --- |
| `LCLS-MFX` | (root) | | bound to the SLAC Site; FEL source shared across instruments (TOPO-1) |
| `Undulator` | InsertionDevice | (per-shot energy; vernier / USEG) | SASE HXR source; per-shot photon energy is a DAQ datum (SRC-1, DAQ-1) |
| `GasDetector` | **FluxMonitor** | `GDET:FEE1:241:ENRC` | FEL pulse-energy gas detector; Sensor Role; read via `BeamStats` |
| `FrontEndAttenuator` | Filter | `SATT:FEE1:320` | solid-Si attenuator; Filter covers it; transmission solver deferred (ATT-1) |
| `FrontEndMirror1` | Mirror | `FEE1:M1H` | first horizontal offset mirror |
| `FrontEndMirror2` | Mirror | `FEE1:M2H` | second horizontal offset mirror |
| `TransportMirror2` | Mirror | `XRT:M2H` | X-ray-transport steering mirror |
| `TransportMirror3` | Mirror | `XRT:M3H` | transport mirror that routes the beam to the branch; the switched-source seam (TOPO-1) |
| `TransportStopper` | Shutter | `HFX:DG2:STP:01` | PPS-interlocked beam stopper (PSS-1) |
| `TransportSlits` | Slit | `HFX:DG2:JAWS` | transport-line 4-blade slits |
| `TransportIPM` | **FluxMonitor** | `HFX:DG2:IPM` | intensity-position monitor; flux + position Sensor (DIAG-1) |
| `TransportImager` | Scintillator | `HFX:DG2:PIM` | profile imager (YAG + camera) |
| `PulsePicker` | Shutter | `MFX:DIA:MMS:07` | fast single-pulse selector; Shutter Role (Shutter-vs-Chopper open, PULSE-1) |
| `Attenuator` | Filter | `MFX:ATT` | solid-Si attenuator; transmission solver deferred (ATT-1) |
| `DCCM` | Monochromator | (diamond channel-cut) | mono for some modes; pink-vs-mono boundary (MONO-1) |
| `Transfocator` | Transfocator | `MFX:LENS` | Be CRL stack; reuses the graduated `Transfocator` catalog Family (a CRL focusing optic) |
| `Prefocus` | Transfocator | `MFX:DIA:XFLS` | upstream CRL prefocus; reuses the graduated `Transfocator` catalog Family (a CRL focusing optic) |
| `MFXSlits` | Slit | `MFX:DG1:JAWS` | DG1 4-blade slits |
| `MFXSlitsDownstream` | Slit | `MFX:DG2:JAWS:US` | DG2 slit set |
| `MFXIntensityMonitor` | **FluxMonitor** | `MFX:DG1:IPM` | intensity-position monitor (DIAG-1) |
| `MFXImager` | Scintillator | `MFX:DG1:PIM` | DG1 profile imager |
| `TimeTool` | **Diagnostic** | `MFX:ATM` | X-ray/laser arrival-time monitor; Sensor Role; drift-corrects the pump-probe delay (LASER-1) |
| `Wave8` | **FluxMonitor** | `MFX:DG1:MMS:08` | fast per-shot intensity / wavefront Sensor (DIAG-1) |
| `PumpProbeLaser` | **Laser** | `LAS:FS45` / `MFX:LAS:MMN:*` | fs optical pump-probe laser; loose family reused from 4-ID; fs sync is the gap (LASER-1) |
| `LiquidJet` | (deferred) | `MFX:LJH` | liquid-jet / fixed-target sample delivery; no Family coined yet (SAMPLE-1) |
| `EmissionSpectrometer` | **EmissionSpectrometer** | `MFX:SPEC` | von Hamos 6-crystal XES spectrometer; the single new loose family (SPEC-1) |
| `Detector` | Camera | (Rayonix / ePix10k / Jungfrau) | per-shot area detector; frames flow through the DAQ data plane (DAQ-1, DET-1) |
| `EventSequencer` | TimingController | `ECS:SYS0:7` | beam-synchronous event-code sequencer; event-code parameter has no typed home (TIMING-1) |

Reused catalog Families (no new Family needed): `InsertionDevice`, `Filter`, `Mirror`, `Shutter`, `Slit`, `Scintillator`, `Monochromator`, `Camera`, `TimingController`, and `Transfocator` (the graduated CRL focusing optic, also bound at I22 / 4-ID / 8-ID). **No new catalog Family graduated here.** Loose families reused from sibling deployments: `FluxMonitor` and `Diagnostic` (Sensor families, from I22 / 2-BM), `Laser` (from 4-ID POLAR). Only one genuinely new loose family: `EmissionSpectrometer` (the von Hamos, a crystal-analyzer emission spectrometer no Family carries; the same gap appeared at MAX IV Balder). The liquid jet presents an endstation Role and is carried with its shape deferred rather than minting a Family, mirroring how I03 and 19-BM handle sample delivery and the exchange arm.

## Pending confirmations

Every value below is reverse-engineered from `pcdshub` or inferred, awaiting the beamline team or a SLAC source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Shared switched FEL source: one-vs-many Units, routing state | `LCLS-MFX`, `TransportMirror3` | `unknown-pending-confirmation` | (TOPO-1) |
| LCLS PPS permit signals and the pump-probe BTPS interlock | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which enclosure each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Undulator parameters and the per-shot photon-energy mechanism | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Linac machine-state modelling boundary | `GasDetector` | `unknown-pending-confirmation` | (MACHINE-1) |
| Attenuator transmission solver (target transmission to foil set) | `FrontEndAttenuator`, `Attenuator` | `unknown-pending-confirmation` | (ATT-1) |
| DCCM internals and the pink-vs-mono mode model | `DCCM` | `unknown-pending-confirmation` | (MONO-1) |
| Per-shot pulse-ID event DAQ representation | `Detector`, `EventSequencer` | `unknown-pending-confirmation` | (DAQ-1) |
| Event-code-sequence parameter model | `EventSequencer` | `unknown-pending-confirmation` | (TIMING-1) |
| Pump-probe fs synchronization and laser model-vs-hazard | `PumpProbeLaser`, `TimeTool` | `unknown-pending-confirmation` | (LASER-1) |
| Diagnostics Sensor modelling | `TransportIPM`, `MFXIntensityMonitor`, `Wave8`, `GasDetector` | `unknown-pending-confirmation` | (DIAG-1) |
| Sample-delivery model and Subject custody thread | `LiquidJet` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Emission-spectrometer Family and analyzer-crystal composition | `EmissionSpectrometer` | `unknown-pending-confirmation` | (SPEC-1) |
| Detector model and per-shot frame referencing | `Detector` | `unknown-pending-confirmation` | (DET-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1, the computed lightpath LIGHTPATH-1, and the pulse-picker Family PULSE-1) are on [Open questions](questions.md) without a placeholder here.
