# Extracted facts: P13

Machine-extracted candidate facts for `P13` (facility `petra-iii`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's configuration/*.xml device objects).

Filtered out 20 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| axis-camera | Camera | - | P13 | detection | - | yes |
| detector-eiger16m | Camera | `/P13/detector/eiger16m` | P13-EH1 | detection | - | yes |
| detector-pilatus6m | Camera | `/P13/detector/pilatus6m` | P13-EH1 | detection | - | yes |
| flux | FluxMonitor | `/P13/PinDiode/Device0` | P13 | detection | - | yes |
| oav-camera | Camera | - | P13 | detection | - | yes |
| sample-changer-camera | Camera | - | P13 | detection | - | yes |
| xrf-spectrum | EnergyDispersiveSpectrometer | `/P13/fluorescence-scan/fls-scan` | P13 | detection | - | yes |
| diff-back-light | Backlight | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diff-backLight | Backlight | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diff-beamstop | BeamStop | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diff-front-light | Backlight | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diff-frontLight | Backlight | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diff-zoom | Objective | `p13md201.embl-hamburg.de:9001` | P13-EH1 | sample | - | yes |
| diffractometer | Goniometer | `p13md201.embl-hamburg.de:9001` | P13 | sample | - | yes |
| beam | EMBLBeam (?) | `p13md201.embl-hamburg.de:9001` | P13 | source | - | yes |
| beam-centring | EMBLBeamCentring (?) | `/P13/BCUIntensity/Device0` | P13 | source | - | yes |
| beam-info | EMBLBeamInfo (?) | `p13md201.embl-hamburg.de:9001` | P13 | source | - | yes |
| detector-distance | TINEMotor (?) | `/P13/collection/distance` | P13-EH1 | source | - | yes |
| diff-aperture | Aperture | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-centring-vert | TINEMotor (?) | `/P13/MD/MD_0` | P13-EH1 | source | - | yes |
| diff-focus | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-holder-length | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-kappa | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-kappaphi | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-omega | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-phiy | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-phiz | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-sampx | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| diff-sampy | ExporterMotor (?) | `p13md201.embl-hamburg.de:9001` | P13-EH1 | source | - | yes |
| energy | TINEEnergy (?) | `/P13/Energy/P13Energy` | P13-EH1 | source | - | yes |
| energy | EMBLEnergy (?) | `/P13/Energy/P13Energy` | P13 | source | - | yes |
| energy-motor | TINEMotor (?) | `/P13/collection/wavelength` | P13-EH1 | source | - | yes |
| fast-shutter | Shutter | `p13md201.embl-hamburg.de:9001` | P13 | source | - | yes |
| motor-pitch-hfm | TINEMotor (?) | `/P13/P13Kb.CDI/HFMTgtPos` | P13-OH1 | source | - | yes |
| motor-pitch-second | TINEMotor (?) | `Pitch 2nd` | P13-OH1 | source | - | yes |
| motor-pitch-vfm | TINEMotor (?) | `/P13/P13Kb.CDI/VFMTgtPos` | P13-OH1 | source | - | yes |
| motor-pitch-vhm | TINEMotor (?) | `VHM Pitch` | P13-OH1 | source | - | yes |
| motor-roll-second | TINEMotor (?) | `Roll 2nd` | P13-OH1 | source | - | yes |
| resolution | TINEMotor (?) | `/P13/collection/resolution` | P13-EH1 | source | - | yes |
| resolution | TINEMotor (?) | `/P13/collection/resolution` | P13 | source | - | yes |
| safety-shutter | Shutter | `/P13/collection/mx-standard` | P13 | source | - | yes |

## Candidate enclosures

`P13`, `P13-EH1`, `P13-OH1` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **axis-camera** (`QtAxisCamera`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'axis-camera'; endstation to enclosure is a guess
- **beam** (`EMBLBeam`)
    - family is the MXCuBE class 'EMBLBeam'; the CORA Family needs a human
    - MXCuBE object at 'beam'; endstation to enclosure is a guess
- **beam-centring** (`EMBLBeamCentring`)
    - family is the MXCuBE class 'EMBLBeamCentring'; the CORA Family needs a human
    - MXCuBE object at 'beam-centring'; endstation to enclosure is a guess
- **beam-info** (`EMBLBeamInfo`)
    - family is the MXCuBE class 'EMBLBeamInfo'; the CORA Family needs a human
    - MXCuBE object at 'beam-info'; endstation to enclosure is a guess
- **detector-distance** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/detector-distance'; endstation to enclosure is a guess
- **detector-eiger16m** (`EMBLDetector`)
    - MXCuBE object at 'eh1/detector-eiger16m'; endstation to enclosure is a guess
    - vendor model '16M' read from the config; confirm against the floor
- **detector-pilatus6m** (`EMBLDetector`)
    - MXCuBE object at 'eh1/detector-pilatus6m'; endstation to enclosure is a guess
    - vendor model '6M_F' read from the config; confirm against the floor
- **diff-aperture** (`EMBLAperture`)
    - MXCuBE object at 'eh1/diff-aperture'; endstation to enclosure is a guess
- **diff-back-light** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-back-light'; endstation to enclosure is a guess
- **diff-backLight** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-backLight'; endstation to enclosure is a guess
- **diff-beamstop** (`EMBLBeamstop`)
    - MXCuBE object at 'eh1/diff-beamstop'; endstation to enclosure is a guess
- **diff-centring-vert** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-centring-vert'; endstation to enclosure is a guess
- **diff-focus** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-focus'; endstation to enclosure is a guess
- **diff-front-light** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-front-light'; endstation to enclosure is a guess
- **diff-frontLight** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-frontLight'; endstation to enclosure is a guess
- **diff-holder-length** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-holder-length'; endstation to enclosure is a guess
- **diff-kappa** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-kappa'; endstation to enclosure is a guess
- **diff-kappaphi** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-kappaphi'; endstation to enclosure is a guess
- **diff-omega** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-omega'; endstation to enclosure is a guess
- **diff-phiy** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-phiy'; endstation to enclosure is a guess
- **diff-phiz** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-phiz'; endstation to enclosure is a guess
- **diff-sampx** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-sampx'; endstation to enclosure is a guess
- **diff-sampy** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-sampy'; endstation to enclosure is a guess
- **diff-zoom** (`MicrodiffZoom`)
    - MXCuBE object at 'eh1/diff-zoom'; endstation to enclosure is a guess
- **diffractometer** (`EMBLMiniDiff`)
    - MXCuBE object at 'diffractometer'; endstation to enclosure is a guess
- **energy** (`TINEEnergy`)
    - family is the MXCuBE class 'TINEEnergy'; the CORA Family needs a human
    - MXCuBE object at 'eh1/energy'; endstation to enclosure is a guess
- **energy** (`EMBLEnergy`)
    - family is the MXCuBE class 'EMBLEnergy'; the CORA Family needs a human
    - MXCuBE object at 'energy'; endstation to enclosure is a guess
- **energy-motor** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/energy-motor'; endstation to enclosure is a guess
- **fast-shutter** (`MDFastShutter`)
    - MXCuBE object at 'fast-shutter'; endstation to enclosure is a guess
- **flux** (`EMBLFlux`)
    - MXCuBE object at 'flux'; endstation to enclosure is a guess
- **motor-pitch-hfm** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-pitch-hfm'; endstation to enclosure is a guess
- **motor-pitch-second** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-pitch-second'; endstation to enclosure is a guess
- **motor-pitch-vfm** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-pitch-vfm'; endstation to enclosure is a guess
- **motor-pitch-vhm** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-pitch-vhm'; endstation to enclosure is a guess
- **motor-roll-second** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-roll-second'; endstation to enclosure is a guess
- **oav-camera** (`VimbaVideo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'oav-camera'; endstation to enclosure is a guess
- **resolution** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/resolution'; endstation to enclosure is a guess
- **resolution** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'resolution'; endstation to enclosure is a guess
- **safety-shutter** (`EMBLSafetyShutter`)
    - MXCuBE object at 'safety-shutter'; endstation to enclosure is a guess
- **sample-changer-camera** (`QtAxisCamera`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'sample-changer-camera'; endstation to enclosure is a guess
- **xrf-spectrum** (`EMBLXRFSpectrum`)
    - MXCuBE object at 'xrf-spectrum'; endstation to enclosure is a guess
