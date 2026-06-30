# Extracted facts: P14

Machine-extracted candidate facts for `P14` (facility `petra-iii`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's configuration/*.xml device objects).

Filtered out 27 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| axis-camera | Camera | - | P14 | detection | - | yes |
| detector-eiger16m | Camera | `/P14/detector/eiger16m` | P14-EH1 | detection | - | yes |
| detector-eiger16m-cdte | Camera | `/P14/detector/eiger16m-cdte` | P14-EH1 | detection | - | yes |
| detector-eiger4m-cdte | Camera | `/P14/detector/eiger4m-cdte` | P14-EH1 | detection | - | yes |
| flux | FluxMonitor | `/P14/PinDiode/Device0` | P14 | detection | - | yes |
| oav-camera | Camera | - | P14 | detection | - | yes |
| sample-changer-camera | Camera | - | P14 | detection | - | yes |
| xray-imaging | Camera | - | P14 | detection | - | yes |
| xrf-spectrum | EnergyDispersiveSpectrometer | `/P14/fluorescence-scan/fls-scan` | P14 | detection | - | yes |
| diff-back-light | Backlight | `p14md302.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-backLight | Backlight | `p14md301.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-beamstop | BeamStop | `p14md302.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-front-light | Backlight | `p14md302.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-frontLight | Backlight | `p14md301.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-light | Backlight | `p14md301.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diff-zoom | Objective | `p14md302.embl-hamburg.de:9001` | P14-EH1 | sample | - | yes |
| diffractometer | Goniometer | `p14md302.embl-hamburg.de:9001` | P14 | sample | - | yes |
| P14BCU | LinearStage | `/P14/P14BCU` | P14-EH1 | source | - | yes |
| P14DetTrans | LinearStage | `/P14/P14DetTrans` | P14-EH1 | source | - | yes |
| P14ExpTbl | LinearStage | `/P14/P14ExpTbl` | P14-EH1 | source | - | yes |
| P14KB | LinearStage | `/P14/P14KB` | P14-EH1 | source | - | yes |
| attoGroup | LinearStage | `/P14/P14Atto` | P14-EH1 | source | - | yes |
| beam | EMBLBeam (?) | `p14md302.embl-hamburg.de:9001` | P14 | source | - | yes |
| beam-centring | EMBLBeamCentring (?) | `/P14/PinDiode/Device0` | P14 | source | - | yes |
| beamAttocube | Slit | - | P14-EH1 | source | - | yes |
| beamFocusing | Mirror | `/P14/collection/distance` | P14-EH1 | source | - | yes |
| crl | Transfocator | `/P14/p14CRLs.CDI/LensOut` | P14 | source | - | yes |
| detector-distance | TINEMotor (?) | `/P14/collection/distance` | P14-EH1 | source | - | yes |
| diff-aperture | Aperture | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-focus | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-holder-length | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-kappa | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-kappaphi | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-omega | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-phix | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-phiy | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-phiz | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-sampx | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| diff-sampy | ExporterMotor (?) | `p14md302.embl-hamburg.de:9001` | P14-EH1 | source | - | yes |
| energy | TINEEnergy (?) | `/P14/Energy/P14Energy` | P14-EH1 | source | - | yes |
| energy | EMBLEnergy (?) | `/P14/Energy/P14Energy` | P14 | source | - | yes |
| energy-motor | TINEMotor (?) | `/P14/collection/wavelength` | P14-EH1 | source | - | yes |
| fast-shutter | Shutter | `p14md302.embl-hamburg.de:9001` | P14 | source | - | yes |
| motor-hfm-pitch | TINEMotor (?) | `HFMpitch` | P14-OH1 | source | - | yes |
| motor-perp | EMBLPiezoMotor (?) | `Perp` | P14-OH1 | source | - | yes |
| motor-roll-second | TINEMotor (?) | `Roll2nd` | P14-OH1 | source | - | yes |
| motor-vfm-pitch | TINEMotor (?) | `VFMpitch` | P14-OH1 | source | - | yes |
| resolution | TINEMotor (?) | `/P14/collection/resolution` | P14-EH1 | source | - | yes |
| safety-shutter | Shutter | `/P14/collection/mx-standard` | P14 | source | - | yes |
| slits | Slit | - | P14-EH1 | source | - | yes |
| slits | Slit | - | P14-EH1 | source | - | yes |
| slitsGroup | LinearStage | `/P14/P14Atto` | P14-EH1 | source | - | yes |

## Candidate enclosures

`P14`, `P14-EH1`, `P14-OH1` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **P14BCU** (`EMBLMotorsGroup`)
    - MXCuBE object at 'eh1/beamFocusingMotors/P14BCU'; endstation to enclosure is a guess
- **P14DetTrans** (`EMBLMotorsGroup`)
    - MXCuBE object at 'eh1/beamFocusingMotors/P14DetTrans'; endstation to enclosure is a guess
- **P14ExpTbl** (`EMBLMotorsGroup`)
    - MXCuBE object at 'eh1/beamFocusingMotors/P14ExpTbl'; endstation to enclosure is a guess
- **P14KB** (`EMBLMotorsGroup`)
    - MXCuBE object at 'eh1/beamFocusingMotors/P14KB'; endstation to enclosure is a guess
- **attoGroup** (`MotorsGroup`)
    - MXCuBE object at 'eh1/attocubeMotors/attoGroup'; endstation to enclosure is a guess
- **axis-camera** (`QtAxisCamera`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'axis-camera'; endstation to enclosure is a guess
- **beam** (`EMBLBeam`)
    - family is the MXCuBE class 'EMBLBeam'; the CORA Family needs a human
    - MXCuBE object at 'beam'; endstation to enclosure is a guess
- **beam-centring** (`EMBLBeamCentring`)
    - family is the MXCuBE class 'EMBLBeamCentring'; the CORA Family needs a human
    - MXCuBE object at 'beam-centring'; endstation to enclosure is a guess
- **beamAttocube** (`BeamSlitBox`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'eh1/beamAttocube'; endstation to enclosure is a guess
- **beamFocusing** (`EMBLBeamFocusing`)
    - MXCuBE object at 'eh1/beamFocusing'; endstation to enclosure is a guess
- **crl** (`EMBLCRL`)
    - MXCuBE object at 'crl'; endstation to enclosure is a guess
- **detector-distance** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/detector-distance'; endstation to enclosure is a guess
- **detector-eiger16m** (`EMBLDetector`)
    - MXCuBE object at 'eh1/detector-eiger16m'; endstation to enclosure is a guess
    - vendor model '16M' read from the config; confirm against the floor
- **detector-eiger16m-cdte** (`EMBLDetector`)
    - MXCuBE object at 'eh1/detector-eiger16m-cdte'; endstation to enclosure is a guess
    - vendor model '16M' read from the config; confirm against the floor
- **detector-eiger4m-cdte** (`EMBLDetector`)
    - MXCuBE object at 'eh1/detector-eiger4m-cdte'; endstation to enclosure is a guess
    - vendor model '4M' read from the config; confirm against the floor
- **diff-aperture** (`EMBLAperture`)
    - MXCuBE object at 'eh1/diff-aperture'; endstation to enclosure is a guess
- **diff-back-light** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-back-light'; endstation to enclosure is a guess
- **diff-backLight** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-backLight'; endstation to enclosure is a guess
- **diff-beamstop** (`EMBLBeamstop`)
    - MXCuBE object at 'eh1/diff-beamstop'; endstation to enclosure is a guess
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
- **diff-light** (`MicrodiffLight`)
    - MXCuBE object at 'eh1/diff-light'; endstation to enclosure is a guess
- **diff-omega** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-omega'; endstation to enclosure is a guess
- **diff-phix** (`ExporterMotor`)
    - family is the MXCuBE class 'ExporterMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/diff-phix'; endstation to enclosure is a guess
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
- **motor-hfm-pitch** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-hfm-pitch'; endstation to enclosure is a guess
- **motor-perp** (`EMBLPiezoMotor`)
    - family is the MXCuBE class 'EMBLPiezoMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-perp'; endstation to enclosure is a guess
- **motor-roll-second** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-roll-second'; endstation to enclosure is a guess
- **motor-vfm-pitch** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'oh1/motor-vfm-pitch'; endstation to enclosure is a guess
- **oav-camera** (`VimbaVideo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'oav-camera'; endstation to enclosure is a guess
- **resolution** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh1/resolution'; endstation to enclosure is a guess
- **safety-shutter** (`EMBLSafetyShutter`)
    - MXCuBE object at 'safety-shutter'; endstation to enclosure is a guess
- **sample-changer-camera** (`QtAxisCamera`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'sample-changer-camera'; endstation to enclosure is a guess
- **slits** (`EMBLSlitBox`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'eh1/slits'; endstation to enclosure is a guess
- **slits** (`EMBLSlitBox`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'eh1/slitsMotors/slits'; endstation to enclosure is a guess
- **slitsGroup** (`EMBLMotorsGroup`)
    - MXCuBE object at 'eh1/slitsGroup'; endstation to enclosure is a guess
- **xray-imaging** (`EMBLXrayImaging`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'xray-imaging'; endstation to enclosure is a guess
- **xrf-spectrum** (`EMBLXRFSpectrum`)
    - MXCuBE object at 'xrf-spectrum'; endstation to enclosure is a guess
