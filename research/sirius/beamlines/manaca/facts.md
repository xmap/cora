# Extracted facts: MANACA

Machine-extracted candidate facts for `MANACA` (facility `sirius`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's per-device configuration objects, classic *.xml or newer *.yaml).

Filtered out 18 bookkeeping rows (MXCuBE software services: the Bluesky HTTP bridge, LIMS/ISPyB, machine-info, session, queue manager, sample-view centring, beamline-actions, and the composite beamline-config / diffractometer objects) not modelled as devices; the inventory below is the modellable remainder.

!!! note "First Sirius device pass, unlocked via the newer YAML MXCuBE config"
    Sirius's beamline controls source is firewalled (`gitlab.cnpem.br` is CNPEM-network-only), so Sirius had a survey but zero device passes. The exception is Manaca's MXCuBE config, public in [`cnpem/mxcubeweb-lnls`](https://github.com/cnpem/mxcubeweb-lnls). Unlike ALBA XALOC and SOLEIL PX1 (classic per-device XML in upstream `mxcubecore`), Manaca uses the **newer per-device YAML** HardwareObjects format, so this pass also adds a YAML reader to the `--source mxcube` extractor path. Real EPICS handles were verified verbatim from the config (`MNC:` = Manaca): the goniometer motor stack (`MNC:B:PB05:m8` omega, `m7` kappa, `m6` kappaphi, `m1/m2/m3` samp/phi), energy (`MNC:A:DCM01:`), cryostream (`MNC:CRYCON:RTEMP`), flux (`MNC:B:PICO02:FluxCividec`), transmission, sample robot (`MNC:B:ROBCS801:`), and the APU22 undulator phase (`SI-09SA:ID-APU22:Phase-Mon`, confirming Manaca = Sirius sector 09SA). This confirms the survey's EPICS + Bluesky (sophys) house-style.

!!! note "Curation pass (human family mapping)"
    The machine table below carries the raw MXCuBE / EPICS class in the "Suggested family" column with a `(?)` flag (a name-fallback, not a confident map). The `LNLS.EPICS.*` classes are generic EPICS wrappers (`EPICSMotor`, `EPICSActuator`, `EPICSNState`), so they carry no CORA-family signal on their own; the mapping to catalog Families, read from each device's logical name and role, is below. The raw table is kept as provenance. Manaca is a clean MX beamline: pure reuse of the existing MX vocabulary, no new family.

    | MXCuBE device(s) | Catalog Family | Note |
    | --- | --- | --- |
    | `diffractometer` + its `udiff_omega` / `udiff_kappa` / `udiff_kappaphi` / `udiff_phiy` / `udiff_phiz` / `udiff_sampx` / `udiff_sampy` / `udiff_sampz` motors | Goniometer (Assembly: kappa-geometry MD) | The `LNLSDiffractometer` composite is the MD; its omega + kappa + kappaphi + sample-centring axes are the Goniometer. Same shape as XALOC / PX1. |
    | `md_camera` | Camera | On-axis sample-view camera (`LNLSCamera`). |
    | `energy`, `wavelength` | PseudoAxis (over the DCM) | `LNLSEnergy` / soft-IOC computed axes over the `MNC:A:DCM01:` monochromator. |
    | `detector_distance`, `resolution` | LinearStage / PseudoAxis | Detector-distance motor + the resolution virtual motor derived from it. |
    | `und_phase` | InsertionDevice | APU22 undulator phase, the source (sector 09SA). |
    | `cryo` | TemperatureController | Cryostream (`MNC:CRYCON:RTEMP`). |
    | `flux` | FluxMonitor | Cividec diamond flux monitor. |
    | `transmission` | Filter (attenuator) | Transmission actuator. |
    | `safety_shutter` | Shutter | PPS safety shutter (`MNC:A:PPS01:`). |
    | `sample_changer` | Positioner (robot) | 48-pin sample-changer robot (`MNC:B:ROBCS801:`), folds to Positioner like the XALOC CATS. |
    | `udiff_backlight` / `udiff_frontlight` (+ switches) | Backlight | Sample-illumination lights. |
    | `udiff_zoom` | Objective | Zoom level of the on-axis viewing optic. |
    | `xrf` | EnergyDispersiveSpectrometer | XRF fluorescence readout (no real handle in config; confirm). |

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| cryo | EPICSActuator (?) | `MNC:CRYCON:RTEMP` | MANACA | source | - | yes |
| detector_distance | EPICSMotor (?) | `MNC:B:PB04:CS1:m9` | MANACA | source | - | yes |
| diffractometer | LNLSDiffractometer (?) | - | MANACA | source | - | yes |
| energy | LNLSEnergy (?) | `MNC:A:DCM01:` | MANACA | source | - | yes |
| flux | EPICSActuator (?) | `MNC:B:PICO02:FluxCividec` | MANACA | source | - | yes |
| md_camera | LNLSCamera (?) | - | MANACA | source | - | yes |
| resolution | ResolutionVirtualMotor (?) | `MNC:B:SoftIOC:Resolution` | MANACA | source | - | yes |
| safety_shutter | EPICSToggle (?) | `MNC:A:PPS01:` | MANACA | source | - | yes |
| sample_changer | LNLSSampleChanger (?) | `MNC:B:ROBCS801:` | MANACA | source | - | yes |
| transmission | EPICSActuator (?) | `MNC:B:TRANSMISSION:` | MANACA | source | - | yes |
| udiff_backlight | LNLSRestrictedActuator (?) | `MNC:B:LUCIOLE01:LIGHT_CH1` | MANACA | source | - | yes |
| udiff_backlightswitch | LNLSRestrictedNState (?) | `MNC:B:PB03:PV_ACTIVATE_BACKLIGHT` | MANACA | source | - | yes |
| udiff_frontlight | LNLSRestrictedActuator (?) | `MNC:B:LUCIOLE01:LIGHT_CH2` | MANACA | source | - | yes |
| udiff_frontlightswitch | LNLSRestrictedNStateInterval (?) | `MNC:B:LUCIOLE01:LIGHT_CH2` | MANACA | source | - | yes |
| udiff_kappa | LNLSRestrictedMotorDetachable (?) | `MNC:B:PB05:m7` | MANACA | source | - | yes |
| udiff_kappaphi | LNLSRestrictedMotorDetachable (?) | `MNC:B:PB05:m6` | MANACA | source | - | yes |
| udiff_omega | LNLSRestrictedMotor (?) | `MNC:B:PB05:m8` | MANACA | source | - | yes |
| udiff_phiy | LNLSRestrictedMotor (?) | `MNC:B:PB05:m2` | MANACA | source | - | yes |
| udiff_phiz | LNLSRestrictedMotor (?) | `MNC:B:PB05:m3` | MANACA | source | - | yes |
| udiff_sampx | LNLSUpdateGridPositionHorizontal (?) | `MNC:B:PB05:m1` | MANACA | source | - | yes |
| udiff_sampy | LNLSUpdateGridPositionVertical (?) | `MNC:B:PB05:CS1:m8` | MANACA | source | - | yes |
| udiff_sampz | LNLSRestrictedMotor (?) | `MNC:B:PB05:CS1:m9` | MANACA | source | - | yes |
| udiff_zoom | EPICSNState (?) | `MNC:B:BZOOM:cam1:ZoomLevel` | MANACA | source | - | yes |
| und_phase | EPICSActuator (?) | `SI-09SA:ID-APU22:Phase-Mon` | MANACA | source | - | yes |
| wavelength | EPICSActuator (?) | `MNC:B:SoftIOC:Resolution:Wavelength_RBV` | MANACA | source | - | yes |
| xrf | LNLSXRF (?) | - | MANACA | source | - | yes |

## Candidate enclosures

`MANACA` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **cryo** (`EPICSActuator`)
    - family is the MXCuBE class 'EPICSActuator'; the CORA Family needs a human
    - MXCuBE object at 'cryo'; endstation to enclosure is a guess
- **detector_distance** (`EPICSMotor`)
    - family is the MXCuBE class 'EPICSMotor'; the CORA Family needs a human
    - MXCuBE object at 'detector_distance'; endstation to enclosure is a guess
- **diffractometer** (`LNLSDiffractometer`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'LNLSDiffractometer'; the CORA Family needs a human
    - MXCuBE object at 'diffractometer'; endstation to enclosure is a guess
- **energy** (`LNLSEnergy`)
    - family is the MXCuBE class 'LNLSEnergy'; the CORA Family needs a human
    - MXCuBE object at 'energy'; endstation to enclosure is a guess
- **flux** (`EPICSActuator`)
    - family is the MXCuBE class 'EPICSActuator'; the CORA Family needs a human
    - MXCuBE object at 'flux'; endstation to enclosure is a guess
- **md_camera** (`LNLSCamera`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'LNLSCamera'; the CORA Family needs a human
    - MXCuBE object at 'md_camera'; endstation to enclosure is a guess
- **resolution** (`ResolutionVirtualMotor`)
    - family is the MXCuBE class 'ResolutionVirtualMotor'; the CORA Family needs a human
    - MXCuBE object at 'resolution'; endstation to enclosure is a guess
- **safety_shutter** (`EPICSToggle`)
    - family is the MXCuBE class 'EPICSToggle'; the CORA Family needs a human
    - MXCuBE object at 'safety_shutter'; endstation to enclosure is a guess
- **sample_changer** (`LNLSSampleChanger`)
    - family is the MXCuBE class 'LNLSSampleChanger'; the CORA Family needs a human
    - MXCuBE object at 'sample_changer'; endstation to enclosure is a guess
- **transmission** (`EPICSActuator`)
    - family is the MXCuBE class 'EPICSActuator'; the CORA Family needs a human
    - MXCuBE object at 'transmission'; endstation to enclosure is a guess
- **udiff_backlight** (`LNLSRestrictedActuator`)
    - family is the MXCuBE class 'LNLSRestrictedActuator'; the CORA Family needs a human
    - MXCuBE object at 'udiff_backlight'; endstation to enclosure is a guess
- **udiff_backlightswitch** (`LNLSRestrictedNState`)
    - family is the MXCuBE class 'LNLSRestrictedNState'; the CORA Family needs a human
    - MXCuBE object at 'udiff_backlightswitch'; endstation to enclosure is a guess
- **udiff_frontlight** (`LNLSRestrictedActuator`)
    - family is the MXCuBE class 'LNLSRestrictedActuator'; the CORA Family needs a human
    - MXCuBE object at 'udiff_frontlight'; endstation to enclosure is a guess
- **udiff_frontlightswitch** (`LNLSRestrictedNStateInterval`)
    - family is the MXCuBE class 'LNLSRestrictedNStateInterval'; the CORA Family needs a human
    - MXCuBE object at 'udiff_frontlightswitch'; endstation to enclosure is a guess
- **udiff_kappa** (`LNLSRestrictedMotorDetachable`)
    - family is the MXCuBE class 'LNLSRestrictedMotorDetachable'; the CORA Family needs a human
    - MXCuBE object at 'udiff_kappa'; endstation to enclosure is a guess
- **udiff_kappaphi** (`LNLSRestrictedMotorDetachable`)
    - family is the MXCuBE class 'LNLSRestrictedMotorDetachable'; the CORA Family needs a human
    - MXCuBE object at 'udiff_kappaphi'; endstation to enclosure is a guess
- **udiff_omega** (`LNLSRestrictedMotor`)
    - family is the MXCuBE class 'LNLSRestrictedMotor'; the CORA Family needs a human
    - MXCuBE object at 'udiff_omega'; endstation to enclosure is a guess
- **udiff_phiy** (`LNLSRestrictedMotor`)
    - family is the MXCuBE class 'LNLSRestrictedMotor'; the CORA Family needs a human
    - MXCuBE object at 'udiff_phiy'; endstation to enclosure is a guess
- **udiff_phiz** (`LNLSRestrictedMotor`)
    - family is the MXCuBE class 'LNLSRestrictedMotor'; the CORA Family needs a human
    - MXCuBE object at 'udiff_phiz'; endstation to enclosure is a guess
- **udiff_sampx** (`LNLSUpdateGridPositionHorizontal`)
    - family is the MXCuBE class 'LNLSUpdateGridPositionHorizontal'; the CORA Family needs a human
    - MXCuBE object at 'udiff_sampx'; endstation to enclosure is a guess
- **udiff_sampy** (`LNLSUpdateGridPositionVertical`)
    - family is the MXCuBE class 'LNLSUpdateGridPositionVertical'; the CORA Family needs a human
    - MXCuBE object at 'udiff_sampy'; endstation to enclosure is a guess
- **udiff_sampz** (`LNLSRestrictedMotor`)
    - family is the MXCuBE class 'LNLSRestrictedMotor'; the CORA Family needs a human
    - MXCuBE object at 'udiff_sampz'; endstation to enclosure is a guess
- **udiff_zoom** (`EPICSNState`)
    - family is the MXCuBE class 'EPICSNState'; the CORA Family needs a human
    - MXCuBE object at 'udiff_zoom'; endstation to enclosure is a guess
- **und_phase** (`EPICSActuator`)
    - family is the MXCuBE class 'EPICSActuator'; the CORA Family needs a human
    - MXCuBE object at 'und_phase'; endstation to enclosure is a guess
- **wavelength** (`EPICSActuator`)
    - family is the MXCuBE class 'EPICSActuator'; the CORA Family needs a human
    - MXCuBE object at 'wavelength'; endstation to enclosure is a guess
- **xrf** (`LNLSXRF`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'LNLSXRF'; the CORA Family needs a human
    - MXCuBE object at 'xrf'; endstation to enclosure is a guess
