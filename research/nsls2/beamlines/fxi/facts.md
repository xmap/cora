# Extracted facts: FXI (18-ID)

Candidate device facts for `fxi` (NSLS-II 18-ID, full-field transmission X-ray microscopy and tomography). Candidates only; confirm every row before modeling. Source: the public `NSLS2/fxi-profile-collection` (`startup/*.py`, read 2026-06; modules `05-ion-chamber`, `10-area-detector`, `11-txm_motor`, `12-optics_motor`, `14-ic`, `17-temperature_controllers`, `18-zebra`). Every value is carried `confirm` until FXI staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Full-field TXM optics chain"
    FXI is a transmission X-ray microscope: the imaging optics (condenser, zone plate, phase ring, Bertrand lens) form a magnified full-field image on an area detector, distinct from a scanning probe. These optics are the beamline's signature and are modeled as Assets below; many share the `XF:18IDB-OP` endstation-optics prefix with per-class leaves.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:18IDA-PPS{PSh}` | Opn/Cls-Cmd, Pos-Sts (TwoButtonShutter) | 18-ID-A | source | yes |
| Monochromator | Monochromator | `XF:18IDA-OP{Mono:DCM` | energy=`-Ax:En}Mtr`; th2=`-Ax:Th2}Mtr` (+PID); chi2=`-Ax:Chi2}Mtr` (+PID) | 18-ID-A | optics | yes |
| CollimatingMirror | Mirror | `XF:18IDA-OP{Mir:CM` | jacks (Mir:CM) | 18-ID-A | optics | yes |
| ToroidalMirror | Mirror | `XF:18IDA-OP{Mir:TM` | jacks (Mir:TM) | 18-ID-A | optics | yes |
| PinkBeamSlit | Slit | `XF:18IDA-OP{PBSL:1` | blade axes | 18-ID-A | optics | yes |
| Filters | Filter | `XF:18IDB-ES{IOLOGIK5:E1211}` | DO1-DO7 digital filter inserts (filter1-7) | 18-ID-B | optics | yes |
| Condenser | Condenser | `XF:18IDB-OP` | condenser optic (class Condenser) | 18-ID-B | optics | yes |
| Zoneplate | ZonePlate | `XF:18IDB-OP` | zone-plate objective (class Zoneplate) | 18-ID-B | optics | yes |
| Aperture | Aperture | `XF:18IDB-OP` | order-sorting aperture (class Aperture) | 18-ID-B | optics | yes |
| PhaseRing | PhaseRing | `XF:18IDB-OP` | Zernike phase ring (class PhaseRing) | 18-ID-B | optics | yes |
| BertrandLens | BetrandLens | `XF:18IDB-OP` | Bertrand lens (class BetrandLens, loose) | 18-ID-B | optics | yes |
| Scintillator | Scintillator | `XF:18IDB-OP{Det:Lens` | scintillator + lens (class Scint) | 18-ID-B | detection | yes |
| SSASlit | Slit | `XF:18IDB-OP{SSA:1` | secondary source aperture (TXM_SSA) | 18-ID-B | optics | yes |
| TXMSampleStage | LinearStage | `XF:18IDB-OP` | sample positioning (class TXMSampleStage, zps) | 18-ID-B | sample | yes |
| DetectorSupportU | LinearStage | `XF:18IDB-OP{DetS:U` | upstream detector support (DetSupport) | 18-ID-B | detection | yes |
| DetectorSupportD | LinearStage | `XF:18IDB-OP{DetS:D` | downstream detector support (DetSupport) | 18-ID-B | detection | yes |
| MaranaCamera | Camera | `XF:18IDB-ES{Det:Marana1}` | Andor Marana sCMOS (full-field) | 18-ID-B | detection | yes |
| OryxCamera | Camera | `XF:18IDB-ES{Det:Oryx1}` | Oryx camera | 18-ID-B | detection | yes |
| NeoCamera | Camera | `XF:18IDB-BI{Det:Neo}` | Andor Neo sCMOS | 18-ID-B | detection | yes |
| KinetixCamera | Camera | `XF:18ID1-ES{Kinetix-Det:1}` | Kinetix sCMOS (async) | 18-ID-B | detection | yes |
| VisualLightMicroscope | GenericProbe (?) | `XF:18IDB-BI{VLM:1}` | on-axis visual microscope | 18-ID-B | sample | yes |
| IonChamber | FluxMonitor | `XF:18IDB-BI{i404:1}` | I:R1-R4 currents (i404 4-channel) | 18-ID-B | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:18IDB-ES{Sclr:1}` | scaler channels | 18-ID-B | detection | yes |
| Zebra1 | TimingController (?) | `XF:18ID-ES:1{Dev:Zebra1}` | fly-scan tomography gating | 18-ID-B | detection | yes |
| Zebra2 | TimingController (?) | `XF:18ID-ES:1{Dev:Zebra2}` | second Zebra | 18-ID-B | detection | yes |
| TemperatureController | TemperatureController (?) | `XF:18ID-ES{Env:01` | sample environment temperature (17-temperature_controllers) | 18-ID-B | sample | yes |
| MetalFoilShutter | Shutter (?) | `XF:18IDA-BI{MFS:1}` | metal foil shutter (MFS/PMFS/WPFS triad) | 18-ID-A | source | yes |

Device-level prefixes read verbatim from source: `XEng = MyEpicsMotor("XF:18IDA-OP{Mono:DCM-Ax:En}Mtr")`, the TXM optics classes (`clens`/`zp`/`aper`/`phase_ring`/`betr`/`zps` all on `XF:18IDB-OP`), `shutter = TwoButtonShutter("XF:18IDA-PPS{PSh}")`, the i404 ion chamber, the Marana/Oryx/Neo/Kinetix cameras.

## Role hints

- **Positioner**: DCM (energy + th2/chi2 with PID feedback), both mirrors, slits, all TXM optics (condenser/zoneplate/aperture/phase-ring/Bertrand), sample stage, detector supports.
- **Sensor**: i404 ion chamber (flux), scaler, VLM.
- **Detector**: Marana, Oryx, Neo, Kinetix (all full-field sCMOS cameras).
- **Regulator**: the `Env:01` temperature controller (in-situ sample environment) is a candidate settable-setpoint actuator.
- **Timing**: two Zebras gate fly-scan tomography.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace. FXI is CORA's first NSLS-II deployment (shipped), so this aligns with the existing `deployments/fxi/` model.

## New-family watch

No new coining. Notes:
- **Condenser / ZonePlate / Aperture / PhaseRing** are catalog Families (the TXM optics chain); bind directly. This is the canonical full-field TXM optics set.
- **BetrandLens (loose)**: the Bertrand lens is a loose family already in the deployment set (note the source spelling `BetrandLens`); keep loose, single use.
- **TemperatureController (?)**: confirm the `Env:01` device presents Regulator (settable setpoint) vs read-only; if settable it is another TemperatureController consumer.
- **Zebra -> TimingController (?)**: the recurring fleet-wide fly-scan gating question; FXI has two. Graduation watch.
- **MetalFoilShutter -> Shutter (?)**: the MFS/PMFS/WPFS triad are foil-based fast shutters; confirm Shutter vs Filter binding.

## Deferred / absent

- **PZT** (`13-pzt.py`) fine-positioning and **DCM pump/valve** (`15-DCM_pumpValve.py`) vacuum devices not fully mapped; deferred `MISC-1`.
- **tomo_recon** (`94-tomo_recon.py`) is the reconstruction pipeline (compute, not a device); out of scope for facts.
- The **insertion-device source** referenced via `02-accelerator.py`; no standalone InsertionDevice instantiated; carry `SRC-1`.
