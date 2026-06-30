# Extracted facts: PX1

Machine-extracted candidate facts for `PX1` (facility `soleil`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's configuration/*.xml device objects).

Filtered out 8 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

!!! note "Curation pass (human family mapping)"
    The machine table below carries the raw MXCuBE class in the "Suggested family" column with a `(?)` flag (a name-fallback, not a confident map). The human mapping to catalog Families, the step the `(?)` asks for, is below; the raw table is kept as provenance. Real Tango handles were verified from the `soleil_px1` hardware-objects (e.g. `i10-c-cx1/ex/sgonaxis` Smargon, `i10-c-c00/ex/beamlineenergy`, `i10-c-cx1/dt/detdist.1-control`, `i10-c-cx1/dt/ketek.2`, `i10-c-cx1/dt/pilatus`). PX1 is a clean MX beamline, pure reuse, no new family.

    | MXCuBE device(s) | Catalog Family | Note |
    | --- | --- | --- |
    | smargon, omega, phi, phiz, chi, minidiff, uglide{x,y,z} | Goniometer | Smargon six-axis MX goniometer (the i03 family); axes are components of the one Goniometer Asset, not separate devices |
    | energy, hu_640 (undulator), energyscan | Monochromator + InsertionDevice | DCM energy + HU640 undulator; energyscan is a scan plan over them |
    | detectordistance, resolution | LinearStage | detector-distance stage (resolution is a pseudo-axis over it) |
    | attenuators_filters, attenuators_pslits | Filter | attenuator/filter sets |
    | fastshut, frontend, obx, safety_shutter, pss-exp, pss-opt | Shutter | SOLEIL shutters + PSS permits (PSS folds to Enclosure permit, not a device) |
    | pilatus | Camera | Pilatus diffraction detector (PX1Pilatus = Tango Lima) |
    | ketek | EnergyDispersiveSpectrometer | KETEK SDD fluorescence |
    | ge1350c, zoom, focus, light, lightarm | Camera + LinearStage | on-axis Prosilica Lima camera + sample-view optics (zoom/focus/backlight) |
    | flux, beam-info | FluxMonitor + GenericProbe | flux channel + beam-size info |
    | cryotong, catsmaint, cryospy, ln2regul, countdown | Positioner + TemperatureController | CATS cryotong robot (folds to Positioner + Clearance + Subject custody) + cryo regulation |
    | mach | GenericProbe | machine/ring current status |
    | mxcollect, energyscan, queue, ednaparams, dbconnection, session, ruche, shape-history, px1configuration, px1environment, lims-rest | (not devices) | MXCuBE services: collection plan, queue model, ISPyB/EDNA, data movement (RUCHE), session, config; the orchestration + LIMS seam, not Assets |

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| detectordistance | Camera | `Detector Distance` | PX1 | detection | - | yes |
| minidiff | Goniometer | `Minidiff` | PX1 | sample | - | yes |
| Qt4_graphics-manager | Qt4_GraphicsManager (?) | - | PX1 | source | - | yes |
| attenuators_filters | PX1Attenuator (?) | `Filters` | PX1 | source | - | yes |
| attenuators_pslits | PX1Attenuator (?) | `Attenuators by Primary Slits` | PX1 | source | - | yes |
| beam-info | PX1BeamInfo (?) | - | PX1 | source | - | yes |
| catsmaint | PX1CatsMaint (?) | `CatsMaint` | PX1 | source | - | yes |
| chi | SmargonAxis (?) | `chi` | PX1 | source | - | yes |
| countdown | ChannelObject (?) | `Cryotong Countdown` | PX1 | source | - | yes |
| cryospy | TangoCryo (?) | `Cryo` | PX1 | source | - | yes |
| cryotong | PX1Cryotong (?) | `CryoTong` | PX1 | source | - | yes |
| dbconnection | SOLEILISPyBClient (?) | - | PX1 | source | - | yes |
| ednaparams | EdnaWorkflow (?) | - | PX1 | source | - | yes |
| energy | PX1Energy (?) | `Energy` | PX1 | source | - | yes |
| energyscan | PX1EnergyScan (?) | - | PX1 | source | - | yes |
| fastshut | SOLEILShutter (?) | `FastShutter` | PX1 | source | - | yes |
| flux | ChannelObject (?) | `flux` | PX1 | source | - | yes |
| focus | TangoDCMotor (?) | `FocusMotor` | PX1 | source | - | yes |
| frontend | SOLEILShutter (?) | `FrontEnd` | PX1 | source | - | yes |
| ge1350c | Qt4_TangoLimaVideo (?) | `Prosilica Lima` | PX1 | source | - | yes |
| hu_640 | SOLEILUndulator (?) | `HU 460` | PX1 | source | - | yes |
| ketek | Ketek (?) | - | PX1 | source | - | yes |
| light | TangoDCMotor (?) | `BackLight` | PX1 | source | - | yes |
| lightarm | PX1TangoLight (?) | `Light Arm` | PX1 | source | - | yes |
| ln2regul | ChannelObject (?) | `Cryotong Countdown` | PX1 | source | - | yes |
| mach | TangoMachCurrent (?) | `Mach` | PX1 | source | - | yes |
| mxcollect | PX1Collect (?) | - | PX1 | source | - | yes |
| obx | SOLEILShutter (?) | `OBX` | PX1 | source | - | yes |
| omega | SmargonAxis (?) | `omega` | PX1 | source | - | yes |
| phi | SmargonAxis (?) | `phi` | PX1 | source | - | yes |
| phiz | SmargonAxis (?) | `zOffset` | PX1 | source | - | yes |
| pilatus | PX1Pilatus (?) | - | PX1 | source | - | yes |
| pss-exp | PX1Pss (?) | `expPss` | PX1 | source | - | yes |
| pss-opt | PX1Pss (?) | `optPss` | PX1 | source | - | yes |
| px1configuration | PX1Configuration (?) | - | PX1 | source | - | yes |
| px1environment | PX1Environment (?) | `PX1Environment` | PX1 | source | - | yes |
| resolution | PX1Resolution (?) | `Resolution` | PX1 | source | - | yes |
| ruche | SOLEILRuche (?) | - | PX1 | source | - | yes |
| session | SOLEILSession (?) | - | PX1 | source | - | yes |
| shape-history | Shapes (?) | - | PX1 | source | - | yes |
| smargon | Smargon (?) | - | PX1 | source | - | yes |
| uglidex | SmargonAxis (?) | `xOffset` | PX1 | source | - | yes |
| uglidey | SmargonAxis (?) | `yOffset` | PX1 | source | - | yes |
| uglidez | SmargonAxis (?) | `zOffset` | PX1 | source | - | yes |
| zoom | TangoDCMotorWPositions (?) | `Zoom` | PX1 | source | - | yes |

## Candidate enclosures

`PX1` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **Qt4_graphics-manager** (`Qt4_GraphicsManager`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Qt4_GraphicsManager'; the CORA Family needs a human
    - MXCuBE object at 'Qt4_graphics-manager'; endstation to enclosure is a guess
- **attenuators_filters** (`PX1Attenuator`)
    - family is the MXCuBE class 'PX1Attenuator'; the CORA Family needs a human
    - MXCuBE object at 'attenuators_filters'; endstation to enclosure is a guess
- **attenuators_pslits** (`PX1Attenuator`)
    - family is the MXCuBE class 'PX1Attenuator'; the CORA Family needs a human
    - MXCuBE object at 'attenuators_pslits'; endstation to enclosure is a guess
- **beam-info** (`PX1BeamInfo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'PX1BeamInfo'; the CORA Family needs a human
    - MXCuBE object at 'beam-info'; endstation to enclosure is a guess
- **catsmaint** (`PX1CatsMaint`)
    - family is the MXCuBE class 'PX1CatsMaint'; the CORA Family needs a human
    - MXCuBE object at 'catsmaint'; endstation to enclosure is a guess
- **chi** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'chi'; endstation to enclosure is a guess
- **countdown** (`ChannelObject`)
    - family is the MXCuBE class 'ChannelObject'; the CORA Family needs a human
    - MXCuBE object at 'countdown'; endstation to enclosure is a guess
- **cryospy** (`TangoCryo`)
    - family is the MXCuBE class 'TangoCryo'; the CORA Family needs a human
    - MXCuBE object at 'cryospy'; endstation to enclosure is a guess
- **cryotong** (`PX1Cryotong`)
    - family is the MXCuBE class 'PX1Cryotong'; the CORA Family needs a human
    - MXCuBE object at 'cryotong'; endstation to enclosure is a guess
- **dbconnection** (`SOLEILISPyBClient`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'SOLEILISPyBClient'; the CORA Family needs a human
    - MXCuBE object at 'dbconnection'; endstation to enclosure is a guess
- **detectordistance** (`PX1DetectorDistance`)
    - MXCuBE object at 'detectordistance'; endstation to enclosure is a guess
- **ednaparams** (`EdnaWorkflow`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'EdnaWorkflow'; the CORA Family needs a human
    - MXCuBE object at 'ednaparams'; endstation to enclosure is a guess
- **energy** (`PX1Energy`)
    - family is the MXCuBE class 'PX1Energy'; the CORA Family needs a human
    - MXCuBE object at 'energy'; endstation to enclosure is a guess
- **energyscan** (`PX1EnergyScan`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'PX1EnergyScan'; the CORA Family needs a human
    - MXCuBE object at 'energyscan'; endstation to enclosure is a guess
- **fastshut** (`SOLEILShutter`)
    - family is the MXCuBE class 'SOLEILShutter'; the CORA Family needs a human
    - MXCuBE object at 'fastshut'; endstation to enclosure is a guess
- **flux** (`ChannelObject`)
    - family is the MXCuBE class 'ChannelObject'; the CORA Family needs a human
    - MXCuBE object at 'flux'; endstation to enclosure is a guess
- **focus** (`TangoDCMotor`)
    - family is the MXCuBE class 'TangoDCMotor'; the CORA Family needs a human
    - MXCuBE object at 'focus'; endstation to enclosure is a guess
- **frontend** (`SOLEILShutter`)
    - family is the MXCuBE class 'SOLEILShutter'; the CORA Family needs a human
    - MXCuBE object at 'frontend'; endstation to enclosure is a guess
- **ge1350c** (`Qt4_TangoLimaVideo`)
    - family is the MXCuBE class 'Qt4_TangoLimaVideo'; the CORA Family needs a human
    - MXCuBE object at 'ge1350c'; endstation to enclosure is a guess
- **hu_640** (`SOLEILUndulator`)
    - family is the MXCuBE class 'SOLEILUndulator'; the CORA Family needs a human
    - MXCuBE object at 'hu_640'; endstation to enclosure is a guess
- **ketek** (`Ketek`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Ketek'; the CORA Family needs a human
    - MXCuBE object at 'ketek'; endstation to enclosure is a guess
- **light** (`TangoDCMotor`)
    - family is the MXCuBE class 'TangoDCMotor'; the CORA Family needs a human
    - MXCuBE object at 'light'; endstation to enclosure is a guess
- **lightarm** (`PX1TangoLight`)
    - family is the MXCuBE class 'PX1TangoLight'; the CORA Family needs a human
    - MXCuBE object at 'lightarm'; endstation to enclosure is a guess
- **ln2regul** (`ChannelObject`)
    - family is the MXCuBE class 'ChannelObject'; the CORA Family needs a human
    - MXCuBE object at 'ln2regul'; endstation to enclosure is a guess
- **mach** (`TangoMachCurrent`)
    - family is the MXCuBE class 'TangoMachCurrent'; the CORA Family needs a human
    - MXCuBE object at 'mach'; endstation to enclosure is a guess
- **minidiff** (`PX1MiniDiff`)
    - MXCuBE object at 'minidiff'; endstation to enclosure is a guess
- **mxcollect** (`PX1Collect`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'PX1Collect'; the CORA Family needs a human
    - MXCuBE object at 'mxcollect'; endstation to enclosure is a guess
- **obx** (`SOLEILShutter`)
    - family is the MXCuBE class 'SOLEILShutter'; the CORA Family needs a human
    - MXCuBE object at 'obx'; endstation to enclosure is a guess
- **omega** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'omega'; endstation to enclosure is a guess
- **phi** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'phi'; endstation to enclosure is a guess
- **phiz** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'phiz'; endstation to enclosure is a guess
- **pilatus** (`PX1Pilatus`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'PX1Pilatus'; the CORA Family needs a human
    - MXCuBE object at 'pilatus'; endstation to enclosure is a guess
    - vendor model '6M_F' read from the config; confirm against the floor
- **pss-exp** (`PX1Pss`)
    - family is the MXCuBE class 'PX1Pss'; the CORA Family needs a human
    - MXCuBE object at 'pss-exp'; endstation to enclosure is a guess
- **pss-opt** (`PX1Pss`)
    - family is the MXCuBE class 'PX1Pss'; the CORA Family needs a human
    - MXCuBE object at 'pss-opt'; endstation to enclosure is a guess
- **px1configuration** (`PX1Configuration`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'PX1Configuration'; the CORA Family needs a human
    - MXCuBE object at 'px1configuration'; endstation to enclosure is a guess
- **px1environment** (`PX1Environment`)
    - family is the MXCuBE class 'PX1Environment'; the CORA Family needs a human
    - MXCuBE object at 'px1environment'; endstation to enclosure is a guess
- **resolution** (`PX1Resolution`)
    - family is the MXCuBE class 'PX1Resolution'; the CORA Family needs a human
    - MXCuBE object at 'resolution'; endstation to enclosure is a guess
- **ruche** (`SOLEILRuche`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'SOLEILRuche'; the CORA Family needs a human
    - MXCuBE object at 'ruche'; endstation to enclosure is a guess
- **session** (`SOLEILSession`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'SOLEILSession'; the CORA Family needs a human
    - MXCuBE object at 'session'; endstation to enclosure is a guess
- **shape-history** (`Shapes`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Shapes'; the CORA Family needs a human
    - MXCuBE object at 'shape-history'; endstation to enclosure is a guess
- **smargon** (`Smargon`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Smargon'; the CORA Family needs a human
    - MXCuBE object at 'smargon'; endstation to enclosure is a guess
- **uglidex** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'uglidex'; endstation to enclosure is a guess
- **uglidey** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'uglidey'; endstation to enclosure is a guess
- **uglidez** (`SmargonAxis`)
    - family is the MXCuBE class 'SmargonAxis'; the CORA Family needs a human
    - MXCuBE object at 'uglidez'; endstation to enclosure is a guess
- **zoom** (`TangoDCMotorWPositions`)
    - family is the MXCuBE class 'TangoDCMotorWPositions'; the CORA Family needs a human
    - MXCuBE object at 'zoom'; endstation to enclosure is a guess
