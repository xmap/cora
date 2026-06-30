# Extracted facts: NanoMAX (B303A)

Candidate device facts for `nanomax` (MAX IV B303A, hard X-ray nanoprobe: scanning coherent diffraction / ptychography, nano-XRF, nano-diffraction, nano-imaging). Candidates only; confirm every row before modeling. Source: the public `maxiv-science/contrast` DAQ framework (`beamlines/nanomax/diffraction.py` + `imaging.py`, read at commit `8e787ac`, 2026-01). Every value is carried `confirm` until NanoMAX staff verify it: the contrast beamline files are strong evidence, not a CORA-owned fact. Handles are Tango device addresses (`domain/family/member`) and Tango-pool device names, carried in the descriptor `pv` slot; MAX IV runs Tango + Sardana, not EPICS.

!!! note "Source idiom and the active-vs-commented rule"
    Unlike the ESRF Beacon YAML, MAX IV's `contrast` declares devices as Python objects: `TangoMotor(device='b303a-o/opt/mono-xml', name='mono_x', ...)`, `EigerTango('b303a/dia/eiger-1m', ...)`, `SmaractLinearMotor(device='B303A-EH/CTL/PZCU-04', axis=N, ...)`. Many lines are commented out (dev variants, retired stages); ONLY active (uncommented, not-in-docstring) device handles are recorded here, extracted by stripping triple-quoted blocks and `#` lines. The Tango address case is preserved verbatim as it appears (the config mixes `b303a-o/...` and `B303A-O/...` for the same domain).

!!! note "Two endstations, one optics train"
    NanoMAX has two experimental endstations that share one optics / source train: the **diffraction endstation** (`diffraction.py`, B303A-E02, a goniometer + KB-focus + nPoint sample piezos) and the **imaging endstation** (`imaging.py`, B303A-E01, a zone-plate / coarse+fine sample stack). The shared optics block (undulator, mono, mirrors, SSA) is declared in full in `diffraction.py` and commented out in `imaging.py` (it is the same hardware), the SRX two-endstation precedent. Both stations are modeled below; the optics/source rows belong to both.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level handle the descriptor binds, component axes as sub-detail read verbatim from source. Multi-axis Smaract / E727 / LC400 / PiezoLegs controllers host many named axes on ONE Tango device address (e.g. `B303A-EH/CTL/PZCU-04` carries 15 axes); these are grouped into the physical assembly the axes form (a slit, an attenuator bank, the KB, the sample stack), NOT one row per controller and NOT one row per axis. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

### Source + shared optics (B303A-O / front end; both endstations)

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Undulator | InsertionDevice | `motor/ivu_gap_ctrl/1` (pool proxy) | ivu_gap=`motor/ivu_gap_ctrl/1` (4.5-25); ivu_taper=`motor/ivu_taper_ctrl/1` | B303A | source | yes |
| BeamlineFilters | Filter | `b303a-o/opt/flt-01-yml` | bl_filter_1=`flt-01-yml`; bl_filter_2=`b303a-o/opt/flt-02-yml` (diamond filters, diagnostics module 1) | B303A-O | optics | yes |
| VerticalFocusingMirror | Mirror | `b303a-o/opt/mir-01-xml` | x=`mir-01-xml`; y=`mir-01-yml`; pit=`mir-01-pitml`; yaw=`mir-01-yawml` (VFM) | B303A-O | optics | yes |
| HorizontalFocusingMirror | Mirror | `b303a-o/opt/mir-02-xml` | x=`mir-02-xml`; y=`mir-02-yml`; pit=`mir-02-pitml`; bend=`mir-02-bendml` (HFM) | B303A-O | optics | yes |
| Monochromator | Monochromator | `b303a-o/opt/mono-xml` | x=`mono-xml`; bragg=`MONO-BRAGML` (4.0-27.46); x2per=`mono-perml`; x2pit=`mono-pitml`; x2rol=`mono-rolml`; fine x2fpit=`B303A-O/CTL/PZCU-01`; fine x2frol=`B303A-O/CTL/PZCU-02` | B303A-O | optics | yes |
| SecondarySourceAperture | Slit | `B303A-O/opt/SLIT-01-GAPXPM` | gapx=`SLIT-01-GAPXPM`; gapy=`SLIT-01-GAPYPM`; posx=`SLIT-01-POSXPM`; posy=`SLIT-01-POSYPM` (SSA, pool pseudo-motors) | B303A-O | optics | yes |
| NanoBPM | BeamPositionMonitor | `b303a-o/dia/bpx-01` | y=`bpx-01` (nano beam-position monitor vertical stage) | B303A-O | diagnostics | yes |
| BeamEnergy | PseudoAxis | `pseudomotor/nanomaxenergy_ctrl/1` | energy_raw=`nanomaxenergy_ctrl/1`; energy (corrected)=`pseudomotor/nanomaxenergy_corr_ctrl/1` (Sardana energy pseudo) | B303A-O | optics | yes |

### Diffraction endstation (B303A-E02 / B303A-EH)

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| DiagnosticsSlitAttenuatorStack | Slit | `B303A-EH/CTL/PZCU-04` (Smaract MCS, 15 axes) | dbpm2_x/y (axis 0/1); SEH slit seh_top/bottom/left/right (axis 2-5) -> gap/pos pseudos; attenuator1-4_x (axis 6-9); diode1_x (11); polarizer pol_x/pol_y/pol_rot (axis 12-14) | B303A-EH | optics | yes |
| FastShutterDBPM1Stack | LinearStage | `B303A-EH/CTL/PZCU-07` (Smaract, 3 axes) | fastshutter_y (axis 0); dbpm1_x (1); dbpm1_y (2) (OH2 fast shutter + first diamond BPM) | B303A-EH | optics | yes |
| SampleStage | LinearStage | `B303A/CTL/PZCU-LC400B` (nPoint LC400, 3 axes) | sx=axis 2; sy=axis 3; sz=axis 1 (sample scanning piezos, +/-50 um) | B303A-E02 | sample | yes |
| SampleBaseStage | LinearStage | `B303A-EH/CTL/PZCU-08` (PiezoLegs, 3 axes) | basex=axis 0; basey=axis 1; basez=axis 2 (coarse sample positioning) | B303A-E02 | sample | yes |
| SampleKBSlit | Slit | `B303A-EH/CTL/PZCU-03` (Smaract, used axes) | skb_top/bottom/left/right (axis 0-3) -> gap/pos pseudos; pinhole_x/y/z (axis 6-8) | B303A-EH | optics | yes |
| KBMirrorPiezo | Mirror | `B303A-EH/CTL/PZCU-01` (PI E727, 3 axes) | m1froll=axis 1; m1fpitch=axis 2; m2fpitch=axis 3 (KB mirror fine pitch/roll piezos) | B303A-EH | optics | yes |
| OpticalMicroscopes | Camera (?) | `b303a-e02/dia/om-01-x` (on-axis) + `b303a-e02/dia/om-02-x` (top) | oam x/y/z/zoom=`om-01-{x,y,z,zoom}`; topm x/y/z/zoom=`om-02-{x,y,z,zoom}` (sample-viewing microscopes) | B303A-E02 | sample | yes |
| Goniometer | Goniometer | `b303a-e02/dia/gon-01-theta` | theta=`gon-01-theta`; phi=`gon-01-phi`; x1/x2/x3=`gon-01-x{1,2,3}`; y1/y2=`gon-01-y{1,2}`; z=`gon-01-z` | B303A-E02 | sample | yes |
| Beamstop | LinearStage | `B303A-E02/DIA/SAMS-01-X` | x=`SAMS-01-X`; y=`SAMS-01-Y` | B303A-E02 | detection | yes |
| XRFDetectorStage | LinearStage | `B303A-E02/DIA/DMA-01-X` | xrf_x=`DMA-01-X` (fluorescence detector linear motion) | B303A-E02 | detection | yes |
| DetectorTable | LinearStage | `b303a-e02/dia/tab-01-x1` | front_x=`tab-01-x1`; back_x=`tab-01-x2`; front_y=`tab-01-y1`; back_y=`tab-01-y2` | B303A-E02 | detection | yes |
| AreaDetectorPilatus | Camera | `b303a/dia/pilatus` (Pilatus3, hw_trig) | (2D photon-counting area detector) | B303A-E02 | detection | yes |
| AreaDetectorEiger1M | Camera | `b303a/dia/eiger-1m` (EigerTango) | (Eiger 1M area detector) | B303A-E02 | detection | yes |
| AreaDetectorEiger500k | Camera | `b303a/dia/eiger-500k` (EigerTango) | (Eiger 500k area detector) | B303A-E02 | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `xspress3ds/xspress3/mini-temp` (Xspress3) | (SDD fluorescence MCA, x3mini) | B303A-E02 | detection | yes |
| IonChamberElectrometer | FluxMonitor | `b-nanomax-em2-2` (AlbaEM, host) | alba2: ion chamber at KB (Ch1), PIN diodes (Ch3/Ch4) | B303A-E02 | detection | yes |
| TimingController | TimingController | `b-nanomax-pandabox-0` (PandaBox, host) | panda0: encoder capture (INENC1-3), fast-scan trigger distribution | B303A-EH | detection | yes |
| EnergyScanTiming | TimingController | `b303a-a100380cab03/dia/panda-01` (PandaBoxPCAP) | panda1: continuous energy-scan PCAP capture | B303A | detection | yes |

### Imaging endstation (B303A-E01)

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| KBMirrorPiezo | Mirror | `B303A-E01/CTL/PZCU-04` (PI E727, 3 axes) | m1pitch=axis 1; m2pitch=axis 2; m1roll=axis 3 (imaging KB fine pitch/roll) | B303A-E01 | optics | yes |
| SampleStage | LinearStage | `B303A/CTL/IMG-02` (NI-DAC, 3 axes) | sx=axis 0; sy=axis 1; sz=axis 2 (sample scanning piezos, +/-50 um) | B303A-E01 | sample | yes |
| SampleBaseStage | LinearStage | `B303A-E01/CTL/PZCU-02` (PiezoLegs ImgSampleStage, 3 axes) | basex/basey/basez (coarse sample positioning) | B303A-E01 | sample | yes |
| SampleOpticsStage | LinearStage | `B303A-E01/CTL/MCS2-01` (Smaract MCS2, 11 axes) | sample tilt slt/slr/sll/slb (axis 0-3); zone-plate / grating grx/gry/grz/grip (axis 4-7); sr rotation (axis 8); aperture apx/apy (axis 9-10) | B303A-E01 | sample | yes |
| XRFDetectorStage | LinearStage | `B303A-E01/DIA/XRF-01-X` | xrf1_x=`XRF-01-X`; xrf2_x=`B303A-E01/DIA/XRF-02-X` | B303A-E01 | detection | yes |
| PixelDetectorStage | LinearStage | `B303A-E01/DIA/PIXDET-X` | pixdet_x=`PIXDET-X`; pixdet_y=`PIXDET-Y` | B303A-E01 | detection | yes |
| OpticalScreenMicroscope | Camera (?) | `B303A-E01/DIA/OPT-SCR` | screen=`OPT-SCR`; mic=`B303A-E01/DIA/OPT-MIC` (optical screen + microscope) | B303A-E01 | sample | yes |
| AreaDetectorEiger4M | Camera | `b303a/dia/eiger-4m` (EigerTango) | (Eiger 4M area detector) | B303A-E01 | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `staff/alebjo/xspress3mini` (Xspress3) | (SDD fluorescence MCA, x3mini; staff dev device name) | B303A-E01 | detection | yes |
| IonChamberElectrometer | FluxMonitor | `b-nanomax-em2-1` (AlbaEM, host) | alba1: DBPM in DM4 | B303A-E01 | detection | yes |
| TimingController | TimingController | `b-nanomax-pandabox-2` (PandaBox, host) | panda2: LC400 encoder capture + fast-shutter control | B303A-E01 | detection | yes |

The device-level handles above are read verbatim from `diffraction.py` and `imaging.py` (active lines only). The multi-axis controller addresses (`B303A-EH/CTL/PZCU-0{1,3,4,7,8}`, `B303A-E01/CTL/MCS2-01`, `B303A/CTL/PZCU-LC400B`, `B303A/CTL/IMG-02`) each host the several named axes shown; the descriptor binds the controller address once per physical assembly. Detector hosts (`b-nanomax-em2-*`, `b-nanomax-pandabox-*`) are AlbaEM / PandaBox network hosts, not Tango `domain/family/member` addresses; recorded verbatim as they appear (`host=`).

## Role hints

- **Positioner**: the mono, both KB mirrors (VFM/HFM coarse + the E727 fine-pitch piezos), the SSA + SEH + SKB slits, the nPoint LC400 / NI-DAC sample scanning piezos, the PiezoLegs coarse base, the MCS2 sample-optics stack, the goniometer, and all detector / XRF / table stages. Constructor classes are explicit (`TangoMotor`, `SmaractLinearMotor`, `E727Motor`, `LC400Motor`, `PiezoLegsMotor`, `DacMotor`, `SmaractLinearMotor_MCS2`).
- **Sensor**: the AlbaEM electrometers (ion chamber + PIN diodes, the I0 / flux chain), the NanoBPM, the PandaBox encoder/ADC pseudo-detectors.
- **Detector**: the area detectors (Pilatus3, Eiger 1M / 500k / 4M) and the Xspress3 fluorescence SDD.
- **Controller / timing**: the PandaBox units (`panda0/1/2`) are the fast-scan / fly-scan trigger + encoder-capture timing masters (the contrast `NpointFlyscan` / `EnergyFlyscan` / `WFtrigscan` macros bind them); a TimingController-role hint, the same role as the NSLS-II Zebra.
- **No Regulator / settable-setpoint actuator** is active in either file. A Eurotherm heater is present but commented out (`EuroThermDSMotor`, "20240520 heater"); not modeled (see deferred).

## Trust hints

The contrast files carry no queue-server / user-group-permissions artifact (contrast is a DAQ framework, not the authorization layer; MAX IV authorization is a Tango / DUO concern). The files reference a `MaxivScheduler` (pauses scans on shutter close / injection) and a `ScicatRecorder` (writes to SciCat), both consistent with the survey's seam read: the BLISS-style orchestration CORA's edge would conduct over is contrast itself (`SoftwareScan`, the flyscan macros), and SciCat is the data-of-record contest. The `userLevel` scheme (1 simple user, 2 power user, 3 optics, 4 dangerous) is a contrast-side access gradient, an input to the Trust seam read, not a binding.

## New-family watch

Nothing to coin from NanoMAX. All bindings map to existing catalog families:

- **Mirror, Monochromator, Slit, InsertionDevice, Filter, Camera, LinearStage, Goniometer, PseudoAxis, FluxMonitor, EnergyDispersiveSpectrometer, TimingController (all graduated).** NanoMAX is a further consumer of each.
- **KB mirrors -> Mirror (not a new KB family).** Each KB mirror (VFM, HFM, plus the E727 fine-pitch piezos at each endstation) binds the graduated `Mirror`; the KB pair is two Mirror Assets, no Kirkpatrick-Baez family (the catalog has no KB family and the rule-of-three is not met from NanoMAX alone).
- **PandaBox -> TimingController (?).** The fast-scan trigger / encoder-capture unit; `TimingController` is the catalog Family (confirm vs a bare GenericProbe, the same question as the NSLS-II Zebra). PandaBox recurs across MAX IV beamlines (CoSAXS also), a graduation-reinforcement watch, not coined here.
- **OpticalMicroscopes / OpticalScreenMicroscope -> Camera (?).** On-axis / top sample-viewing visible-light microscopes; bind `Camera` by role (a viewing camera + stage), NOT the X-ray `Microscope` Family (which is the scintillator-relay full-field detector). Confirm; likely a Camera + LinearStage composition.
- **NanoBPM -> BeamPositionMonitor (loose, DIAG-1).** The nano beam-position monitor binds the loose `BeamPositionMonitor` held fleet-wide under `DIAG-1`; do not coin.
- **AlbaEM -> FluxMonitor.** The electrometer reads ion-chamber / PIN-diode current (flux); binds the graduated `FluxMonitor` by what it measures. AlbaEM recurs across MAX IV (CoSAXS too), reinforcing, not coined.

## Deferred / absent

- **PSS permit signals and shutters (`PSS-1`).** The commented-out `MaxivScheduler` block names the real shutter devices (`B303A-FE/VAC/HA-01`, `B303A-FE/PSS/BS-01`, `B303A-O/PSS/BS-01`, `B303A-E/PSS/BS-01`), but they are not instantiated as live contrast objects; recorded as the personnel-safety / shutter handles to confirm, not modeled as Assets here. The fast shutter (`fsopen`/`fsclose` runCommands) is driven via PandaBox, not a standalone device.
- **Zone plate / OSA / central stop (`ZP-1`).** The imaging endstation's zone-plate, order-sorting-aperture, and central-stop positioners (the `osax`/`osay`/`zpx`/`zpy`/`csx` Nanos block) are present in source but commented out; the live MCS2 `grx/gry/grz` axes are the operative zone-plate-region stage. No `ZonePlate` Asset is instantiated live; carry as `ZP-1` (the FXI / 32-ID ZonePlate precedent would apply once confirmed).
- **Sample temperature (Eurotherm heater) (`TEMP-1`).** A `EuroThermDSMotor` / `EuroThermDSDetector` on `B303A/DIA/TRC-01` is imported but commented out ("20240520 heater"); a Regulator-presenting TemperatureController candidate if instantiated, but absent from the active config.
- **Robot (`ROBOT-1`).** A `KukaRobot` (`B303-EH2/CTL/DM-02-ROBOT`, gamma/delta/radius) is present but commented out in the diffraction file; a diffractometer-arm robot, not live.
- **Merlin / Andor3 / Basler cameras.** Imported and partly instantiated-then-commented (Merlin `host='localhost'`, Andor3 `b303a-e01/dia/zyla`, several `basler/e0*-cam-*`); not in the active detector set, deferred as `DET-2`.
- **Dev / scratch beamline files.** `diff_develop.py`, `julio.py`, `test_selun_img.py`, `dummy_keysight.py` are developer variants of the two canonical endstation files; not read as the source of record (the operative files are `diffraction.py` + `imaging.py`).
