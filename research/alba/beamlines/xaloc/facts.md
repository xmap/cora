# Extracted facts: XALOC

Machine-extracted candidate facts for `XALOC` (facility `alba`). Candidates only; confirm every row before modeling. Source: MXCuBE HardwareObjects (the beamline's configuration/*.xml device objects).

Filtered out 6 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

!!! note "First ALBA device pass, unlocked via MXCuBE"
    ALBA's survey marked per-beamline device topology "largely NOT published" (Sardana/Taurus config gated on `*.cells.es`). The MXCuBE hardware-object config (`alba_xaloc13`, public via upstream `mxcubecore`) is the exception: it exposes XALOC's MX device topology with real Tango handles, so this is ALBA's first device pass. Verified handles: `bl13/eh/pilatuslima` (Pilatus), `bl13/eh/cats` (CATS robot), Taurus motor names (`omega`, `detsamdis`). The `bl13` prefix confirms XALOC = ALBA BL13; the motors are Sardana/Taurus (ALBA's house-style, as the survey notes).

!!! note "Curation pass (human family mapping)"
    The machine table below carries raw MXCuBE classes in the "Suggested family" column with `(?)`. Human mapping to catalog Families (XALOC is a kappa-geometry MX beamline; pure reuse, no new family):

    | MXCuBE device(s) | Catalog Family | Note |
    | --- | --- | --- |
    | mini-diff, omega, kappa, kappaphi, centx, centy, omegax/y/z | Goniometer | kappa-geometry MX goniometer (the i03 family); the axes are components of the one Goniometer Asset |
    | energy, energy_motor, wavelength_motor | Monochromator | DCM energy / wavelength |
    | detector-distance, resolution | LinearStage | detector-distance stage (resolution is a pseudo-axis over it) |
    | transmission, calibration | Filter | attenuation transmission + calibration |
    | fastshut, slowshut, photonshut, frontend | Shutter | fast/slow/photon shutters + front end (ALBAEpsActuator = EPS shutter) |
    | pilatus | Camera | Pilatus diffraction detector (Tango Lima at bl13/eh/pilatuslima) |
    | flux, beam-info | FluxMonitor | flux + beam-size readout |
    | bstopz | BeamStop | beamstop Z |
    | backlight, frontlight, blight, zoom, zoom-auto-brightness, limavideo, Qt4_testvideo | Camera + LinearStage | on-axis sample view: lights + zoom + Lima video |
    | cats, catsmaint | Positioner | CATS sample-changer robot (folds to Positioner + Clearance + Subject custody, not a SampleChanger Family) |
    | mach-info | GenericProbe | machine / ring status |
    | supervisor, mxcollect, data-analysis, parallel-processing, auto-processing, dbconnection, session, Qt4_graphics-manager | (not devices) | MXCuBE services: beamline supervisor, collection plan, EDNA/auto-processing, ISPyB, session; orchestration + LIMS seam, not Assets |

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| flux | FluxMonitor | - | XALOC | detection | - | yes |
| mini-diff | Goniometer | - | XALOC | sample | - | yes |
| Qt4_graphics-manager | Qt4_GraphicsManager (?) | - | XALOC | source | - | yes |
| Qt4_testvideo | Qt4_GraphicsManager (?) | - | XALOC | source | - | yes |
| auto-processing | ALBAAutoProcessing (?) | - | XALOC | source | - | yes |
| backlight | ALBABackLight (?) | `Back` | XALOC | source | - | yes |
| beam-info | ALBABeamInfo (?) | - | XALOC | source | - | yes |
| blight | ALBAZoomMotor (?) | `blight` | XALOC | source | - | yes |
| bstopz | SardanaMotor (?) | `bstopz` | XALOC | source | - | yes |
| calibration | ALBACalibration (?) | `Calibration` | XALOC | source | - | yes |
| cats | ALBACats (?) | `Cats` | XALOC | source | - | yes |
| catsmaint | ALBACatsMaint (?) | `CatsMaint` | XALOC | source | - | yes |
| centx | SardanaMotor (?) | `CentX` | XALOC | source | - | yes |
| centy | SardanaMotor (?) | `CentY` | XALOC | source | - | yes |
| data-analysis | ALBADataAnalysis (?) | - | XALOC | source | - | yes |
| dbconnection | ALBAISPyBClient (?) | - | XALOC | source | - | yes |
| detector-distance | SardanaMotor (?) | `Detector Distance` | XALOC | source | - | yes |
| energy | ALBAEnergy (?) | `Energy` | XALOC | source | - | yes |
| energy_motor | SardanaMotor (?) | `energy` | XALOC | source | - | yes |
| fastshut | Shutter | `Fast Shutter` | XALOC | source | - | yes |
| frontend | ALBAFrontEnd (?) | `Front End` | XALOC | source | - | yes |
| frontlight | ALBAFrontLight (?) | `Front` | XALOC | source | - | yes |
| kappa | SardanaMotor (?) | `Kappa` | XALOC | source | - | yes |
| kappaphi | SardanaMotor (?) | `KappaPhi` | XALOC | source | - | yes |
| limavideo | Qt4_TangoLimaVideo (?) | - | XALOC | source | - | yes |
| mach-info | ALBAMachineInfo (?) | `Mach` | XALOC | source | - | yes |
| mxcollect | ALBACollect (?) | - | XALOC | source | - | yes |
| omega | SardanaMotor (?) | `Omega` | XALOC | source | - | yes |
| omegax | SardanaMotor (?) | `OmegaX` | XALOC | source | - | yes |
| omegay | SardanaMotor (?) | `OmegaY` | XALOC | source | - | yes |
| omegaz | SardanaMotor (?) | `OmegaZ` | XALOC | source | - | yes |
| parallel-processing | ParallelProcessing (?) | - | XALOC | source | - | yes |
| photonshut | ALBAEpsActuator (?) | `Photon Shutter` | XALOC | source | - | yes |
| pilatus | ALBAPilatus (?) | - | XALOC | source | - | yes |
| resolution | SardanaMotor (?) | `Resolution` | XALOC | source | - | yes |
| session | ALBASession (?) | - | XALOC | source | - | yes |
| slowshut | ALBAEpsActuator (?) | `Slow Shutter` | XALOC | source | - | yes |
| supervisor | ALBASupervisor (?) | `Beamline Supervisor` | XALOC | source | - | yes |
| transmission | ALBATransmission (?) | `Transmission` | XALOC | source | - | yes |
| wavelength_motor | SardanaMotor (?) | `wavelength` | XALOC | source | - | yes |
| zoom | ALBAZoomMotor (?) | `Zoom` | XALOC | source | - | yes |
| zoom-auto-brightness | ALBAZoomMotorAutoBrightness (?) | - | XALOC | source | - | yes |

## Candidate enclosures

`XALOC` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **Qt4_graphics-manager** (`Qt4_GraphicsManager`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Qt4_GraphicsManager'; the CORA Family needs a human
    - MXCuBE object at 'Qt4_graphics-manager'; endstation to enclosure is a guess
- **Qt4_testvideo** (`Qt4_GraphicsManager`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Qt4_GraphicsManager'; the CORA Family needs a human
    - MXCuBE object at 'Qt4_testvideo'; endstation to enclosure is a guess
- **auto-processing** (`ALBAAutoProcessing`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBAAutoProcessing'; the CORA Family needs a human
    - MXCuBE object at 'auto-processing'; endstation to enclosure is a guess
- **backlight** (`ALBABackLight`)
    - family is the MXCuBE class 'ALBABackLight'; the CORA Family needs a human
    - MXCuBE object at 'backlight'; endstation to enclosure is a guess
- **beam-info** (`ALBABeamInfo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBABeamInfo'; the CORA Family needs a human
    - MXCuBE object at 'beam-info'; endstation to enclosure is a guess
- **blight** (`ALBAZoomMotor`)
    - family is the MXCuBE class 'ALBAZoomMotor'; the CORA Family needs a human
    - MXCuBE object at 'blight'; endstation to enclosure is a guess
- **bstopz** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'bstopz'; endstation to enclosure is a guess
- **calibration** (`ALBACalibration`)
    - family is the MXCuBE class 'ALBACalibration'; the CORA Family needs a human
    - MXCuBE object at 'calibration'; endstation to enclosure is a guess
- **cats** (`ALBACats`)
    - family is the MXCuBE class 'ALBACats'; the CORA Family needs a human
    - MXCuBE object at 'cats'; endstation to enclosure is a guess
- **catsmaint** (`ALBACatsMaint`)
    - family is the MXCuBE class 'ALBACatsMaint'; the CORA Family needs a human
    - MXCuBE object at 'catsmaint'; endstation to enclosure is a guess
- **centx** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'centx'; endstation to enclosure is a guess
- **centy** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'centy'; endstation to enclosure is a guess
- **data-analysis** (`ALBADataAnalysis`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBADataAnalysis'; the CORA Family needs a human
    - MXCuBE object at 'data-analysis'; endstation to enclosure is a guess
- **dbconnection** (`ALBAISPyBClient`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBAISPyBClient'; the CORA Family needs a human
    - MXCuBE object at 'dbconnection'; endstation to enclosure is a guess
- **detector-distance** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'detector-distance'; endstation to enclosure is a guess
- **energy** (`ALBAEnergy`)
    - family is the MXCuBE class 'ALBAEnergy'; the CORA Family needs a human
    - MXCuBE object at 'energy'; endstation to enclosure is a guess
- **energy_motor** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'energy_motor'; endstation to enclosure is a guess
- **fastshut** (`ALBAFastShutter`)
    - MXCuBE object at 'fastshut'; endstation to enclosure is a guess
- **flux** (`ALBAFlux`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'flux'; endstation to enclosure is a guess
- **frontend** (`ALBAFrontEnd`)
    - family is the MXCuBE class 'ALBAFrontEnd'; the CORA Family needs a human
    - MXCuBE object at 'frontend'; endstation to enclosure is a guess
- **frontlight** (`ALBAFrontLight`)
    - family is the MXCuBE class 'ALBAFrontLight'; the CORA Family needs a human
    - MXCuBE object at 'frontlight'; endstation to enclosure is a guess
- **kappa** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'kappa'; endstation to enclosure is a guess
- **kappaphi** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'kappaphi'; endstation to enclosure is a guess
- **limavideo** (`Qt4_TangoLimaVideo`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'Qt4_TangoLimaVideo'; the CORA Family needs a human
    - MXCuBE object at 'limavideo'; endstation to enclosure is a guess
- **mach-info** (`ALBAMachineInfo`)
    - family is the MXCuBE class 'ALBAMachineInfo'; the CORA Family needs a human
    - MXCuBE object at 'mach-info'; endstation to enclosure is a guess
- **mini-diff** (`ALBAMiniDiff`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - MXCuBE object at 'mini-diff'; endstation to enclosure is a guess
- **mxcollect** (`ALBACollect`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBACollect'; the CORA Family needs a human
    - MXCuBE object at 'mxcollect'; endstation to enclosure is a guess
- **omega** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'omega'; endstation to enclosure is a guess
- **omegax** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'omegax'; endstation to enclosure is a guess
- **omegay** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'omegay'; endstation to enclosure is a guess
- **omegaz** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'omegaz'; endstation to enclosure is a guess
- **parallel-processing** (`ParallelProcessing`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ParallelProcessing'; the CORA Family needs a human
    - MXCuBE object at 'parallel-processing'; endstation to enclosure is a guess
- **photonshut** (`ALBAEpsActuator`)
    - family is the MXCuBE class 'ALBAEpsActuator'; the CORA Family needs a human
    - MXCuBE object at 'photonshut'; endstation to enclosure is a guess
- **pilatus** (`ALBAPilatus`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBAPilatus'; the CORA Family needs a human
    - MXCuBE object at 'pilatus'; endstation to enclosure is a guess
    - vendor model '6M_F' read from the config; confirm against the floor
- **resolution** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'resolution'; endstation to enclosure is a guess
- **session** (`ALBASession`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBASession'; the CORA Family needs a human
    - MXCuBE object at 'session'; endstation to enclosure is a guess
- **slowshut** (`ALBAEpsActuator`)
    - family is the MXCuBE class 'ALBAEpsActuator'; the CORA Family needs a human
    - MXCuBE object at 'slowshut'; endstation to enclosure is a guess
- **supervisor** (`ALBASupervisor`)
    - family is the MXCuBE class 'ALBASupervisor'; the CORA Family needs a human
    - MXCuBE object at 'supervisor'; endstation to enclosure is a guess
- **transmission** (`ALBATransmission`)
    - family is the MXCuBE class 'ALBATransmission'; the CORA Family needs a human
    - MXCuBE object at 'transmission'; endstation to enclosure is a guess
- **wavelength_motor** (`SardanaMotor`)
    - family is the MXCuBE class 'SardanaMotor'; the CORA Family needs a human
    - MXCuBE object at 'wavelength_motor'; endstation to enclosure is a guess
- **zoom** (`ALBAZoomMotor`)
    - family is the MXCuBE class 'ALBAZoomMotor'; the CORA Family needs a human
    - MXCuBE object at 'zoom'; endstation to enclosure is a guess
- **zoom-auto-brightness** (`ALBAZoomMotorAutoBrightness`)
    - no Exporter / TINE handle in the config object; control handle needs confirm
    - family is the MXCuBE class 'ALBAZoomMotorAutoBrightness'; the CORA Family needs a human
    - MXCuBE object at 'zoom-auto-brightness'; endstation to enclosure is a guess
