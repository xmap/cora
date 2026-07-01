# Inventory

*The CORA Asset model for Alvra: the planned device tree, the `eco`-derived control handles, and what still needs confirming.*

Alvra is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Endstation](equipment/endstation.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/alvra/beamline.yaml) descriptor that the Source page renders from.

As at the LCLS-MFX and Diamond exercises, the **control handles are known**: PSI's [`eco`](https://github.com/paulscherrerinstitute/eco) library records the real EPICS PV prefixes in `eco/alvra/config.py` (`SARFE10-` front end, `SAROP11-` Aramis optics, `SARES11-` / `SLAAR11-` Alvra endstation). The `eco` manifest is code, not a flat table: each device's driver class derives its motor axes from the prefix, so axis-level PVs are derived rather than literal, and several catalogued beam-path components (the shutters and bare offset mirrors) carry an alias and position but no driver. Devices bind to catalog [Families](../../catalog/families.md) where one fits. No vendor Model is bound: `eco` names hardware (the Jungfrau, the Huber stage, the von Hamos) but none is procured into the CORA catalog.

## The Asset tree

Root Asset `Alvra` (`tier = Unit`, `facility_code = psi`); sub-systems nest below by `parent_id`. Bold families are loose design-intent names not in the catalog (they render as plain text). PV prefixes are the `eco` dry facts, carried `confirm`.

| Asset | Family | Control handle (eco) | Notes |
| --- | --- | --- | --- |
| `Alvra` | (root) | | bound to the PSI Site; Aramis FEL source shared across stations (TOPO-1) |
| `Undulator` | InsertionDevice | (per-shot energy; not in eco) | SASE Aramis source; per-shot photon energy is a DAQ datum (SRC-1, DAQ-1) |
| `GasMonitor` | **FluxMonitor** | `SARFE10-PBIG050` | FEL gas intensity monitor; Sensor Role (DIAG-1) |
| `FrontEndIntensityMonitor` | **FluxMonitor** | `SARFE10-PBPS053` | intensity / position monitor; flux + position Sensor (DIAG-1) |
| `UndulatorShutter` | Shutter | `SARFE10-OPSH044` | photon shutter after the undulator; permit binding pending (PSS-1) |
| `UndulatorSlit` | Slit | `SARFE10-OAPU044` | 4-blade slit; eight blade motors derived from the prefix |
| `FrontEndAttenuator` | Filter | `SARFE10-OATT053` | solid attenuator; Filter covers it; transmission solver deferred (ATT-1) |
| `FrontEndScreen` | Scintillator | `SARFE10-PPRM053` | profile monitor (YAG + camera) |
| `FrontEndShutter` | Shutter | `SARFE10-SBST060` | photon shutter at the front-end exit (PSS-1) |
| `OpticsScreen` | Scintillator | `SARFE10-PPRM064` | profile monitor after the front end |
| `HorizontalMirror1` | Mirror | `SAROP11-OOMH064` | first horizontal offset mirror |
| `HorizontalMirror2` | Mirror | `SAROP11-OOMH076` | second horizontal offset mirror |
| `SwitchyardSlit` | Slit | `SAROP11-OAPU104` | 4-blade slit after the switchyard, before the mono |
| `Monochromator` | Monochromator | `SAROP11-ODCM105` | double-crystal mono; Bragg / x / gap / roll / pitch axes derived; pink-vs-mono boundary (MONO-1, XREF-1) |
| `VerticalMirror1` | Mirror | `SAROP11-OOMV108` | first vertical offset mirror |
| `VerticalMirror2` | Mirror | `SAROP11-OOMV109` | second vertical offset mirror |
| `VerticalMirrorScreen` | Scintillator | `SAROP11-PPRM110` | profile monitor after the vertical mirrors |
| `PulsePicker` | Shutter | `SAROP11-OPPI110` | X-ray pulse picker; Shutter Role (Shutter-vs-Chopper open, PULSE-1) |
| `OpticsShutter` | Shutter | `SAROP11-SBST114` | shutter after the optics hutch (PSS-1) |
| `OpticsIntensityMonitor` | **FluxMonitor** | `SAROP11-PBPS117` | solid-target intensity / position monitor (DIAG-1) |
| `OpticsScreenEnd` | Scintillator | `SAROP11-PPRM117` | profile monitor after the optics hutch |
| `ArrivalTimeMonitorPALM` | **Diagnostic** | `SAROP11-PALM118` | THz-streaking arrival-time monitor; drift-corrects the pump-probe delay (LASER-1) |
| `ArrivalTimeMonitorPSEN` | **Diagnostic** | `SAROP11-PSEN119` | spectral-encoding arrival-time monitor (the LCLS-MFX TimeTool analog, LASER-1) |
| `ExperimentAttenuator` | Filter | `SAROP11-OATT120` | solid attenuator for Alvra; transmission solver deferred (ATT-1) |
| `AttenuatorSlit` | Slit | `SAROP11-OAPU120` | pos / width slit behind the attenuator |
| `ReferenceLaser` | **Laser** | `SAROP11-OLAS120` | alignment reference laser before the KBs; aperture PV on SAROP21-* (XREF-1) |
| `AttenuatorIntensityMonitor` | **FluxMonitor** | `SAROP11-PBPS122` | intensity / position monitor after the attenuator (DIAG-1) |
| `AttenuatorScreen` | Scintillator | `SAROP11-PPRM122` | profile monitor after the attenuator |
| `VerticalKBMirror` | Mirror | `SAROP11-OKBV123` | vertical KB focusing mirror; bender / pitch / roll / yaw / bend axes derived |
| `HorizontalKBMirror` | Mirror | `SAROP11-OKBH124` | horizontal KB focusing mirror |
| `SampleStage` | LinearStage | `SARES11-XSAM125` | Huber sample XYZ manipulator; sample delivery deferred (SAMPLE-1) |
| `OpticalTable` | Table | `SARES11-XOTA125` | Prime optical table; six physical + virtual axes |
| `SampleMicroscope` | Camera | `SARES11-XMI125` | on-axis sample-view microscope; Detector Role for alignment |
| `PumpProbeLaser` | **Laser** | `SLAAR11-LMOT` | fs optical pump-probe laser; loose family reused; fs sync is the gap (LASER-1) |
| `LaserShutter` | Shutter | `SLAAR11-LTIM01-EVR0` | pump-probe laser shutter via a SwissFEL EVR (TIMING-1) |
| `EmissionSpectrometer` | **EmissionSpectrometer** | `SARES11-XCRY125` | von Hamos XES / HERFD spectrometer; binds the graduated family, fourth sighting (SPEC-1) |
| `Detector` | Camera | (Jungfrau JF_4.5M) | per-shot area detector; frames flow through the sf-daq data plane (DAQ-1, DET-1) |
| `EventTiming` | TimingController | (SwissFEL EVR; not in eco) | beam-synchronous event timing; event-code parameter has no typed home (TIMING-1) |

Reused catalog Families (no new Family needed): `InsertionDevice`, `FluxMonitor`, `Shutter`, `Slit`, `Filter`, `Scintillator`, `Mirror`, `Monochromator`, `LinearStage`, `Table`, `Camera`, `TimingController`, and `EmissionSpectrometer` (the graduated crystal-analyzer emission-spectrometer Family, here on its fourth sighting). **No new catalog Family graduated here**, the same finding as LCLS-MFX. Loose families reused from sibling deployments: `FluxMonitor` and `Diagnostic` (Sensor families, from I22 / 2-BM / LCLS-MFX), `Laser` (from 4-ID / LCLS-MFX, here for both the pump-probe and the alignment-reference lasers). The fixed-target / liquid-jet sample delivery presents an endstation Role and is carried with its shape deferred rather than minting a Family, mirroring LCLS-MFX and I03.

## Pending confirmations

Every value below is reverse-engineered from `eco` or inferred, awaiting the beamline team or a PSI source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Shared switched Aramis source: one-vs-many Units, routing state | `Alvra`, `Undulator` | `unknown-pending-confirmation` | (TOPO-1) |
| SwissFEL PPS permit signals and the pump-probe laser interlock | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which enclosure each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Aramis undulator parameters and the per-shot photon-energy mechanism | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Linac machine-state modelling boundary | `GasMonitor` | `unknown-pending-confirmation` | (MACHINE-1) |
| Attenuator transmission solver (target transmission to foil set) | `FrontEndAttenuator`, `ExperimentAttenuator` | `unknown-pending-confirmation` | (ATT-1) |
| DCM internals and the pink-vs-mono mode model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| The eco SAROP21-* cross-line references (aperture, energy readback) | `Monochromator`, `ReferenceLaser` | `read-from-config-pending-confirmation` | (XREF-1) |
| Per-shot pulse-ID event DAQ representation | `Detector`, `EventTiming` | `unknown-pending-confirmation` | (DAQ-1) |
| Event-system trigger-pattern parameter model | `EventTiming`, `LaserShutter` | `unknown-pending-confirmation` | (TIMING-1) |
| Pump-probe fs synchronization and laser model-vs-hazard | `PumpProbeLaser`, `ArrivalTimeMonitorPSEN`, `ArrivalTimeMonitorPALM` | `unknown-pending-confirmation` | (LASER-1) |
| Diagnostics Sensor modelling | `GasMonitor`, `FrontEndIntensityMonitor`, `OpticsIntensityMonitor`, `AttenuatorIntensityMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Sample-delivery model and Subject custody thread | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Emission-spectrometer analyzer-crystal composition (child-Asset) | `EmissionSpectrometer` | `unknown-pending-confirmation` | (SPEC-1) |
| Detector model, the further Jungfrau options, and per-shot frame referencing | `Detector` | `unknown-pending-confirmation` | (DET-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1 and the pulse-picker Family PULSE-1) are on [Open questions](questions.md) without a placeholder here.
