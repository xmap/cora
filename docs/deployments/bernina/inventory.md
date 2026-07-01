# Inventory

*The CORA Asset model for Bernina: the planned device tree, the `eco`-derived control handles, and what still needs confirming. Deliberately partial: the live device config is externalized (CONFIG-1).*

Bernina is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Endstation](equipment/endstation.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/bernina/beamline.yaml) descriptor that the Source page renders from.

As at [Alvra](../alvra/inventory.md), the **control handles are known where they are inline**: PSI's [`eco`](https://github.com/paulscherrerinstitute/eco) records the real EPICS PV prefixes in `eco/bernina/bernina.py` (`SARFE10-` front end, `SAROP21-` Aramis optics, `SARES2x-` / `SLAAR21-` endstation). But this cut is **partial in a specific way**: `eco`'s device list and the diffractometer axis topology are public, while the configuration state (which sub-assemblies are mounted, which detector attaches to each diffractometer, all units and limits) is loaded at runtime from non-public PSI config files and is carried unknown (CONFIG-1). Devices bind to catalog [Families](../../catalog/families.md) where one fits; the diffraction platforms reuse the graduated [`Diffractometer`](../../catalog/assemblies.md) Assembly (DIFF-1). No vendor Model is bound.

## The Asset tree

Root Asset `Bernina` (`tier = Unit`, `facility_code = psi`); sub-systems nest below by `parent_id`. Bold families are loose design-intent names not in the catalog (they render as plain text). PV prefixes are the `eco` dry facts, carried `confirm`.

| Asset | Family | Control handle (eco) | Notes |
| --- | --- | --- | --- |
| `Bernina` | (root) | | bound to the PSI Site; Aramis FEL source shared across stations (TOPO-1) |
| `Undulator` | InsertionDevice | (per-shot energy; not in eco) | SASE Aramis source; per-shot photon energy is a DAQ datum (SRC-1, DAQ-1) |
| `GasMonitor` | **FluxMonitor** | (eco mon_und_gas; no inline PV) | FEL gas intensity monitor; Sensor Role (DIAG-1) |
| `FrontEndIntensityMonitor` | **FluxMonitor** | `SARFE10-PBPS053` | intensity / position monitor; flux + position Sensor (DIAG-1) |
| `UndulatorShutter` | Shutter | `SARFE10-OPSH044` | photon shutter after the undulator; permit binding pending (PSS-1) |
| `FrontEndShutter` | Shutter | `SARFE10-OPSH059` | photon shutter at the front-end exit (PSS-1) |
| `FrontEndAttenuator` | Filter | `SARFE10-OATT053` | solid attenuator; Filter covers it; transmission solver deferred (ATT-1) |
| `UndulatorSlit` | Slit | (eco slit_und JJ; no inline PV) | front-end JJ slit; blade motors derived |
| `OffsetMirrors` | Mirror | (eco offset; no inline base PV) | Bernina horizontal offset mirror pair |
| `Monochromator` | Monochromator | `SAROP21-ODCM098` | double-crystal mono; Bragg / translation / gap axes derived; pink-vs-mono boundary (MONO-1) |
| `SwitchyardSlit` | Slit | `SAROP21-OAPU092` | 4-blade slit on the SAROP21 line |
| `MonoSlit` | Slit | `SAROP21-OAPU102` | 4-blade slit after the mono |
| `PulsePicker` | Shutter | `SAROP21-OPPI113` | X-ray pulse picker; Shutter Role (Shutter-vs-Chopper open, PULSE-1) |
| `Attenuator` | Filter | `SAROP21-OATT135` | solid attenuator for Bernina; transmission solver deferred (ATT-1) |
| `AttenuatorSlit` | Slit | `SAROP21-OAPU138` | pos / width slit behind the attenuator |
| `MonoIntensityMonitor` | **FluxMonitor** | `SAROP21-PBPS103` | intensity / position monitor after the mono (DIAG-1) |
| `OpticsIntensityMonitor` | **FluxMonitor** | `SAROP21-PBPS133` | intensity / position monitor after the optics (DIAG-1) |
| `MonoScreen` | Scintillator | `SAROP21-PPRM113` | profile monitor after the mono |
| `OpticsScreen` | Scintillator | `SAROP21-PPRM133` | profile monitor after the optics |
| `AttenuatorScreen` | Scintillator | `SAROP21-PPRM138` | profile monitor after the attenuator |
| `ArrivalTimeMonitorPSEN` | **Diagnostic** | `SAROP21-PSEN135` | spectral-encoding arrival-time monitor; drift-corrects the pump-probe delay (LASER-1) |
| `ReferenceLaser` | **Laser** | `SAROP21-OLAS134` | alignment reference laser; binds the catalog Laser Family (not the pump-probe laser) |
| `VerticalKBMirror` | Mirror | `SAROP21-OKBV139` | vertical KB focusing mirror |
| `HorizontalKBMirror` | Mirror | `SAROP21-OKBH140` | horizontal KB focusing mirror |
| `GPS_Goniometer` | Goniometer | `SARES22-GPS` | the GPS six-circle diffractometer's goniometer; the `Diffractometer` Assembly's goniometer slot (DIFF-1) |
| `GPS_ReciprocalSpace` | PseudoAxis | (eco SixCircleBernina recspace) | GPS hkl pseudo-axis; the Assembly's reciprocal_space slot (DIFF-1, DIFF-2) |
| `XRD_Goniometer` | Goniometer | `SARES21-XRD` | the XRD You-geometry goniometer (kappa, heavy-load, hexapod sub-assemblies; mount state external, CONFIG-1) (DIFF-1) |
| `XRD_DetectorArm` | RotaryStage | (eco `SARES21-XRD:MOT_DT_RX2TH`) | XRD 2-theta detector arm (delta); the Assembly's detector_arm slot (DIFF-1) |
| `XRD_ReciprocalSpace` | PseudoAxis | (eco diffcalc; kappa-to-You) | XRD hkl pseudo-axis; the Assembly's reciprocal_space slot (DIFF-1, DIFF-2) |
| `USDTable` | Hexapod | (eco usd_table, HexapodSymmetrie) | upstream sample / diagnostic hexapod table |
| `SampleCamera` | Camera | `SARES20-CAMS142-C1` | below-sample view microscope; Detector Role for alignment |
| `PumpProbeLaser` | **Laser** | `SLAAR21-LMOT` | fs optical pump-probe laser; binds the catalog Laser Family; fs sync is the gap (LASER-1) |
| `LaserShutter` | Shutter | `SLAAR21-LTIM01-EVR0` | pump-probe laser shutter via a SwissFEL EVR (TIMING-1) |
| `AreaDetector` | Camera | (Jungfrau JF07T32V02 16M / JF01T03V01 1.5M) | per-shot area detector; frames flow through the sf-daq data plane (DAQ-1, DET-1, CONFIG-1) |
| `EventTiming` | TimingController | (SwissFEL master + CTA + EVRs) | beam-synchronous event timing; trigger pattern has no typed home (TIMING-1) |

Reused catalog Families (no new Family needed): `InsertionDevice`, `FluxMonitor`, `Shutter`, `Filter`, `Slit`, `Mirror`, `Monochromator`, `Scintillator`, `Goniometer`, `RotaryStage`, `PseudoAxis`, `Hexapod`, `Camera`, `TimingController`, and `Laser` (the graduated optical sample laser, for both the pump-probe and alignment-reference lasers). The GPS and XRD platforms reuse the graduated `Diffractometer` **Assembly** (4-ID / 8-ID), their third and fourth bindings (DIFF-1). **No new catalog Family or Assembly is coined here**, the same finding as Alvra and LCLS-MFX. Loose families reused: `FluxMonitor` and `Diagnostic` (Sensor families). The Staeubli sample / detector robot is deferred (ROBOT-1), not minted as a Family.

## Pending confirmations

Every value below is reverse-engineered from `eco` or inferred, awaiting the beamline team or a PSI source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The externalized device list and diffractometer mount state (which sub-assemblies, which detectors) | `XRD_Goniometer`, `XRD_DetectorArm`, `AreaDetector` | `read-from-external-config-pending-confirmation` | (CONFIG-1) |
| Shared switched Aramis source: one-vs-many Units, routing state | `Bernina`, `Undulator` | `unknown-pending-confirmation` | (TOPO-1) |
| SwissFEL PPS permit signals and the pump-probe laser interlock | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which enclosure each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Aramis undulator parameters and the per-shot photon-energy mechanism | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Linac machine-state modelling boundary | `GasMonitor` | `unknown-pending-confirmation` | (MACHINE-1) |
| Attenuator transmission solver (target transmission to foil set) | `FrontEndAttenuator`, `Attenuator` | `unknown-pending-confirmation` | (ATT-1) |
| DCM internals and the pink-vs-mono mode model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| The eco SAROP11-* cross-line reference (Alvra-line profile monitor) | the optics diagnostics | `read-from-config-pending-confirmation` | (XREF-1) |
| The `Diffractometer` Assembly composition and reciprocal-space partition rule | `GPS_Goniometer`, `XRD_Goniometer`, the PseudoAxes | `unknown-pending-confirmation` | (DIFF-1) (DIFF-2) |
| Per-shot pulse-ID event DAQ representation | `AreaDetector`, `EventTiming` | `unknown-pending-confirmation` | (DAQ-1) |
| Event-system trigger-pattern parameter model | `EventTiming`, `LaserShutter` | `unknown-pending-confirmation` | (TIMING-1) |
| Pump-probe fs synchronization and laser model-vs-hazard | `PumpProbeLaser`, `ArrivalTimeMonitorPSEN` | `unknown-pending-confirmation` | (LASER-1) |
| Diagnostics Sensor modelling | `GasMonitor`, the PBPS monitors | `unknown-pending-confirmation` | (DIAG-1) |
| The Staeubli sample / detector robot modelling | the endstation | `unknown-pending-confirmation` | (ROBOT-1) |
| Detector model, the Jungfrau variants, and the eco / broker version mismatch | `AreaDetector` | `unknown-pending-confirmation` | (DET-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1, the pulse-picker Family PULSE-1, and the deferred RIXS / tape-drive / liquid-jet environments ENV-1) are on [Open questions](questions.md) without a placeholder here.
