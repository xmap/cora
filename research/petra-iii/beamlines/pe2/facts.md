# Extracted facts: PE2

Machine-extracted candidate facts for `PE2` (facility `petra-iii`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's configuration/*.xml device objects).

Filtered out 25 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| camera | Camera | - | PE2 | detection | - | yes |
| detector | Camera | `/PE2/detector/pilatus2m` | PE2-EH2 | detection | - | yes |
| diff-backLight | Backlight | `pe2bsd01.embl-hamburg.de:9001` | PE2-EH2 | sample | - | yes |
| diff-beamstop | BeamStop | `pe2bsd01.embl-hamburg.de:9001` | PE2-EH2 | sample | - | yes |
| diff-frontLight | Backlight | `pe2bsd01.embl-hamburg.de:9001` | PE2-EH2 | sample | - | yes |
| diff-zoom | Objective | `pe2bsd01.embl-hamburg.de:9001` | PE2-EH2 | sample | - | yes |
| attenuators | Attenuators (?) | `/P14/transmission/attenuator` | PE2 | source | - | yes |
| beam-info | EMBLBeamInfo (?) | `pe2bsd01.embl-hamburg.de:9001` | PE2 | source | - | yes |
| detector-distance | TINEMotor (?) | `/PE2/collection/distance` | PE2-EH2 | source | - | yes |
| diff-aperture | Aperture | `pe2bsd01.embl-hamburg.de:9001` | PE2-EH2 | source | - | yes |
| energy | EMBLEnergy (?) | `/P14/Energy/P14Energy` | PE2 | source | - | yes |
| fast-shut | Shutter | `p14md301.embl-hamburg.de:9001` | PE2 | source | - | yes |
| primary-crl | Transfocator | `/P14/p14CRLs.CDI/LensOut` | PE2 | source | - | yes |
| resolution | TINEMotor (?) | `/PE2/collection/resolution` | PE2-EH2 | source | - | yes |
| safshut | Shutter | `/PE2/collection/mx-standard` | PE2 | source | - | yes |
| table_hor | LinearStage | - | PE2-EH2 | source | - | yes |
| table_ver | LinearStage | - | PE2-EH2 | source | - | yes |

## Candidate enclosures

`PE2`, `PE2-EH2` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **attenuators** (`Attenuators`)
    - family is the MXCuBE class 'Attenuators'; the CORA Family needs a human
    - MXCuBE object at 'attenuators'; endstation to enclosure is a guess
- **beam-info** (`EMBLBeamInfo`)
    - family is the MXCuBE class 'EMBLBeamInfo'; the CORA Family needs a human
    - MXCuBE object at 'beam-info'; endstation to enclosure is a guess
- **camera** (`VimbaVideo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'camera'; endstation to enclosure is a guess
- **detector** (`EMBLDetector`)
    - MXCuBE object at 'eh2/detector'; endstation to enclosure is a guess
    - vendor model '2M' read from the config; confirm against the floor
- **detector-distance** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh2/detector-distance'; endstation to enclosure is a guess
- **diff-aperture** (`EMBLAperture`)
    - MXCuBE object at 'eh2/diff-aperture'; endstation to enclosure is a guess
- **diff-backLight** (`MicrodiffLight`)
    - MXCuBE object at 'eh2/diff-backLight'; endstation to enclosure is a guess
- **diff-beamstop** (`EMBLBeamstop`)
    - MXCuBE object at 'eh2/diff-beamstop'; endstation to enclosure is a guess
- **diff-frontLight** (`MicrodiffLight`)
    - MXCuBE object at 'eh2/diff-frontLight'; endstation to enclosure is a guess
- **diff-zoom** (`ExporterZoom`)
    - MXCuBE object at 'eh2/diff-zoom'; endstation to enclosure is a guess
- **energy** (`EMBLEnergy`)
    - family is the MXCuBE class 'EMBLEnergy'; the CORA Family needs a human
    - MXCuBE object at 'energy'; endstation to enclosure is a guess
- **fast-shut** (`MDFastShutter`)
    - MXCuBE object at 'fast-shut'; endstation to enclosure is a guess
- **primary-crl** (`EMBLCRL`)
    - MXCuBE object at 'primary-crl'; endstation to enclosure is a guess
- **resolution** (`TINEMotor`)
    - family is the MXCuBE class 'TINEMotor'; the CORA Family needs a human
    - MXCuBE object at 'eh2/resolution'; endstation to enclosure is a guess
- **safshut** (`EMBLSafetyShutter`)
    - MXCuBE object at 'safshut'; endstation to enclosure is a guess
- **table_hor** (`EMBLTableMotor`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'eh2/table_hor'; endstation to enclosure is a guess
- **table_ver** (`EMBLTableMotor`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'eh2/table_ver'; endstation to enclosure is a guess
