# Inventory

*The CORA Asset model for Cristallina: the planned device tree, the `slic`-derived control handles, and what still needs confirming.*

Cristallina is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Endstation](equipment/endstation.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cristallina/beamline.yaml) descriptor that the Source page renders from.

The **control handles are known**: PSI's [`slic`](https://gitea.psi.ch/slic/cristallina) library records the real EPICS PV prefixes as in-repo Python literals (`SARFE10-` front end, `SAROP31-` Cristallina Aramis optics, `SARES3x-` / `SAR-EXPMX-` endstation). This is a fuller cut than Bernina, whose device list was externalized; Cristallina's device identities and axes are public. Devices bind to catalog [Families](../../catalog/families.md) where one fits; the diffractometers reuse the graduated [`Diffractometer`](../../catalog/assemblies.md) Assembly (DIFF-1), and the vector magnet binds the graduated `Magnet` Family (MAG-1). No vendor Model is bound.

## The Asset tree

Root Asset `Cristallina` (`tier = Unit`, `facility_code = psi`); sub-systems nest below by `parent_id`. Bold families are loose design-intent names not in the catalog (they render as plain text). PV prefixes are the `slic` dry facts, carried `confirm`.

| Asset | Family | Control handle (slic) | Notes |
| --- | --- | --- | --- |
| `Cristallina` | (root) | | bound to the PSI Site; Aramis FEL source shared across stations (TOPO-1) |
| `Undulator` | InsertionDevice | `SARUN03-15-UIND030` | SASE Aramis source; per-shot energy 5-13 keV is a DAQ datum (SRC-1, DAQ-1) |
| `GasMonitor` | **FluxMonitor** | `SARFE10-PBPG050` | gas pulse-energy monitor; Sensor Role; scan beam-intensity condition (DIAG-1) |
| `FrontEndIntensityMonitor` | **FluxMonitor** | `SARFE10-PBPS053` | intensity / position monitor; flux + position Sensor (DIAG-1) |
| `PhotonSpectrometer` | **Diagnostic** | `SARFE10-PSSS059` | photon single-shot spectrometer (PSSS); Sensor Role; per-shot spectrum (DAQ-1) |
| `FrontEndSlit` | Slit | `SARFE10-OAPU044` | front-end 4-blade slit |
| `FrontEndAttenuator` | Filter | `SARFE10-OATT053` | solid attenuator; Filter covers it; transmission solver deferred (ATT-1, XREF-1) |
| `FrontEndScreen` | Scintillator | `SARFE10-PPRM053` | front-end profile monitor (YAG + camera) |
| `HorizontalMirror1` | Mirror | `SAROP31-OOMH067` | first horizontal offset mirror (M1) |
| `HorizontalMirror2` | Mirror | `SAROP31-OOMH084` | second horizontal offset mirror (M2) |
| `OpticsSlit` | Slit | `SAROP31-OAPU107` | 4-blade slit before the mono |
| `Monochromator` | Monochromator | `SAROP31-ODCC110` | double-channel-cut mono (DCCM); pink-vs-mono boundary (MONO-1); distinct from Bernina's DCM |
| `OpticsIntensityMonitor` | **FluxMonitor** | `SAROP31-PBPS113` | intensity / position monitor, optics hutch (DIAG-1) |
| `OpticsScreen` | Scintillator | `SAROP31-PPRM113` | profile monitor after the mono |
| `ExperimentSlit` | Slit | `SAROP31-OAPU149` | 4-blade slit, experimental hutch |
| `ExperimentIntensityMonitor` | **FluxMonitor** | `SAROP31-PBPS149` | intensity / position monitor, experimental hutch (DIAG-1) |
| `ExperimentAttenuator` | Filter | `SAROP31-OATA150` | solid attenuator for Cristallina; transmission solver deferred (ATT-1) |
| `PulsePicker` | Shutter | `SAROP31-OPPI151` | X-ray pulse picker; Shutter Role (Shutter-vs-Chopper open, PULSE-1) |
| `OffsetMirror3` | Mirror | `SAROP31-ODMV152` | vertical offset mirror (M3) |
| `VerticalKBMirror` | Mirror | `SAROP31-OKBV153` | vertical KB focusing mirror |
| `HorizontalKBMirror` | Mirror | `SAROP31-OKBH154` | horizontal KB focusing mirror |
| `AlignmentLaser` | **Laser** | `SAROP31-OLAS147` | X-ray alignment laser (NOT a pump-probe laser; loose family) (LASER-1) |
| `I0Chamber` | Slit | `SARES30-MCS20610` | I0 chamber: slit blades + foil changer (DIAG-1) |
| `DM1_Goniometer` | Goniometer | `SARES31-GPS` | DM1 dilution-fridge diffractometer goniometer; the Assembly's goniometer slot (DIFF-1) |
| `DM1_DetectorArm` | RotaryStage | (slic `SARES31-GPS:ROT2THETA`) | DM1 2-theta detector arm; the Assembly's detector_arm slot (DIFF-1) |
| `DM1_ReciprocalSpace` | PseudoAxis | (slic diffractometer recspace) | DM1 hkl pseudo-axis; the Assembly's reciprocal_space slot (DIFF-1, DIFF-2) |
| `DM2_Goniometer` | Goniometer | `SARES32-GPS` | DM2 pulsed-magnet diffractometer goniometer; PV channels disabled in slic (DISABLED-1) (DIFF-1) |
| `DilutionFridgeThermometry` | TemperatureController | `SARES31-DIL-LS1` | LakeShore 372 dilution-fridge thermometry / heater; Regulator Role (the ID32 VTI precedent) |
| `VectorMagnet` | Magnet | `SARES31-MAG-IPS1` | Oxford Mercury iPS 3-axis vector magnet (to 5.2 T); catalog `Magnet`, a further consumer, graduated Family (MAG-1) |
| `SampleStageMX` | LinearStage | `SAR-EXPMX` | Cristallina-MX fast XY sample stage; delivery deferred (SAMPLE-1) |
| `AreaDetectorQ` | Camera | (Jungfrau JF16T03V02 1.5M) | Cristallina-Q science detector; frames via sf-daq (DAQ-1, DET-1) |
| `IntensityDetectorI0` | Camera | (Jungfrau JF20T01V01 0.5M) | Cristallina-Q I0 monitor Jungfrau; via sf-daq (DAQ-1, DET-1) |
| `AreaDetectorMX` | Camera | (Jungfrau JF17T16V01 8M) | Cristallina-MX science detector; via sf-daq (DAQ-1, DET-1) |
| `EventTiming` | TimingController | (CTA `SAR-CCTA-ESC`, EVR `SARES30-LTIM01-EVR0`) | beam-synchronous event timing; mediates pump-probe (TIMING-1, LASER-1) |

Reused catalog Families (no new Family needed): `InsertionDevice`, `FluxMonitor`, `Slit`, `Filter`, `Scintillator`, `Mirror`, `Monochromator`, `Goniometer`, `RotaryStage`, `PseudoAxis`, `TemperatureController`, `LinearStage`, `Camera`, `TimingController`, and `Magnet` (the vector superconducting magnet, a further consumer of the graduated Family after 4-ID / i10-1 / ID32, MAG-1). The DM1 and DM2 platforms reuse the graduated `Diffractometer` **Assembly** (Bernina GPS / XRD precedent), their fifth and sixth bindings (DIFF-1). **No new catalog Family or Assembly is coined here**, the same finding as Alvra and Bernina. Loose families reused: `FluxMonitor` and `Diagnostic` (Sensor families), and `Laser` (the X-ray alignment laser).

## Pending confirmations

Every value below is reverse-engineered from `slic` or inferred, awaiting the beamline team or a PSI source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Shared switched Aramis source: one-vs-many Units, three-station routing state | `Cristallina`, `Undulator` | `unknown-pending-confirmation` | (TOPO-1) |
| SwissFEL PPS permit signals and the high-field-magnet hazard | both enclosures, `VectorMagnet` | `unknown-pending-confirmation` | (PSS-1) (MAG-1) |
| Which enclosure each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Aramis undulator parameters (gap tables, source size) and the per-shot energy mechanism | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Linac machine-state modelling boundary | `GasMonitor` | `unknown-pending-confirmation` | (MACHINE-1) |
| Attenuator transmission solver and the front-end transmission cross-reference | `FrontEndAttenuator`, `ExperimentAttenuator` | `read-from-config-pending-confirmation` | (ATT-1, XREF-1) |
| DCCM internals and the pink-vs-mono mode model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| The `Diffractometer` Assembly composition and reciprocal-space partition rule | the DM1 / DM2 goniometers, the PseudoAxis | `unknown-pending-confirmation` | (DIFF-1) (DIFF-2) |
| The vector-magnet field ranges and control handles (Family graduated) | `VectorMagnet` | `unknown-pending-confirmation` | (MAG-1) |
| Whether a pump-probe laser exists in another controls layer | the endstation | `unknown-pending-confirmation` | (LASER-1) |
| Which instantiated-but-disabled stages are live hardware | `DM2_Goniometer`, the SmarAct / Attocube / PuMa stages | `read-from-config-pending-confirmation` | (DISABLED-1) |
| Per-shot pulse-ID event DAQ representation | the detectors, `EventTiming` | `unknown-pending-confirmation` | (DAQ-1) |
| Event-system trigger-pattern parameter model | `EventTiming` | `unknown-pending-confirmation` | (TIMING-1) |
| Diagnostics Sensor modelling | `GasMonitor`, `PhotonSpectrometer`, the PBPS monitors | `unknown-pending-confirmation` | (DIAG-1) |
| Serial-crystallography sample delivery and Subject custody | `SampleStageMX` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Detector models, the per-config wiring, and the commented broker labels | the detectors | `unknown-pending-confirmation` | (DET-1) |
| The SECoP magnet path and the pulse-tube sync service | the endstation | `unknown-pending-confirmation` | (ENV-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1 and the pulse-picker Family PULSE-1) are on [Open questions](questions.md) without a placeholder here.
