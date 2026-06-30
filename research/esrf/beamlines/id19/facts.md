# Extracted facts: ID19

Device facts for `ID19` (facility `esrf`), read from the public ID19 BLISS Beacon config
(`gitlab.esrf.fr/id19/beamline_configuration`, commit `b78389a`). Candidates: confirm every row
with ID19 staff before treating as a CORA-owned fact (a config snapshot is strong evidence, not a
guarantee against the live system). Handles are BLISS object names and Tango device names, carried
in the descriptor `pv` field (the opaque control-handle slot); ESRF runs BLISS / Tango, not EPICS.

This cut models the source, the optics, and the MR (micro-resolution) and HR (high-resolution)
tomography endstations. The MH / MED / laminography / radiography / PCO endstations are present in
the config (their own BLISS sessions) but noted, not modelled in this cut.

## Source (insertion devices)

From `devices/insertion_devices.yml` (`ESRF_Undulator`, Tango `//acs.esrf.fr:10000/ID/MASTER/ID19`):

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| InsertionDevices | InsertionDevice | `u13a_gap`, `u32a_gap`, `u17_6c_gap`, `u32c_gap` (undulators); `w150b_gap` + `w150b_taper` (wiggler) | the ID19 straight-section source set; the wiggler drives white-beam tomography |

## Optics

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| Monochromator | Monochromator | `TripleMono` (`Id19Mono`); axes `vmx2/vmy1/vmy2/vmz1/vmz2/thy1/thy2` | triple monochromator, three crystal pairs, Bragg 17-99 keV plus Laue and multilayer modes (`mono/id19mono.yml`) |
| PrimarySlits | Slit | `psu/psd/psf/psb` (blades), `psvg/psvo/pshg/psho` (gap/offset) | primary white-beam slits (`iceid193`) |
| SecondarySlits | Slit | `ssu/ssd/ssf/ssb` | secondary slits (`iceid192`) |
| Transfocator | Transfocator | `id19wbtfctrl` (`ID19Transfocator`), 8 Be lenses + pinhole | white-beam compound refractive lens transfocator (`transfocators/id19transfocator.yml`) |
| Attenuators | Filter | `wba1`/`wba2` (`WhiteBeamAttenuator`), positions `wba11..wba25` (`MultiplePositions`), axes `att11..att25` | white-beam attenuator banks (Cu/Al foils); folds into Filter (i03 precedent), not a new Attenuator Family |

## Shutters

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| FrontEndShutter | Shutter | `frontend` (`//acs.esrf.fr:10000/fe/master/id19`) | front-end shutter |
| BeamShutter1 | Shutter | `bsh1` (`TangoShutter id19/bsh/1`) | main beam shutter |
| BeamShutter2 | Shutter | `bsh2` (`TangoShutter id19/bsh/2`) | second beam shutter |

## MR endstation (micro-resolution tomography; BLISS session MRTOMO)

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| MR_RotationStage | RotaryStage | `mrsrot` (Elmo, `rfc2217://lid192:28319`) | micro-res tomographic rotation; 900 deg/s ceiling |
| MR_SampleStage | LinearStage | `mrsx`/`mrsy` (`iceid191`), `mrxc`/`mryc` (centring, `iceid192`), `XYOnRotation` `mrxyonsrot` | sample centring + CoR alignment |
| MR_YRot / MR_SZ | LinearStage | `mryrot`, `mrsz` (Elmo) | sample translation under rotation |
| MR_Detector | Camera | Lima `frelon1`/`frelon2`/`pco4k`/`dimax_lid19det1..3` (`id19/limaccd/*`) | indirect-detection area detector(s); Frelon / PCO Dimax lineage |
| MR_DetectorStage | LinearStage | `hdx`/`hdy`/`hdz`/`hdthz` (detector hutch stages, `iceid191`) | detector positioning / propagation distance (phase contrast) |
| MR_Optic | (microscope optics) | `mrtriplemic` (`TripleMicOptic`), `mrhasselblad` (`RevolvedHasselbladOptic`) | objective + scintillator selection (`tomo_config/`) |

## HR endstation (high-resolution tomography; BLISS session HRTOMO)

| Device | Family | Handle | Note |
| --- | --- | --- | --- |
| HR_RotationStage | RotaryStage | `hrsrot` (Elmo_whistle, `rfc2217://lid192:28300`) | high-res tomographic rotation; 900 deg/s ceiling |
| HR_SampleStage | LinearStage | `hrsx`/`hrsy` (`iceid192`), `hrsz`/`hrz0` (`iceid191`), `hryrot`, `XYOnRotation` `hrxyonsrot` | sample centring + CoR alignment; session aliases srot/sz/sx/sy/yrot |
| HR_Detector | Camera | Lima `frelon1`/`frelon2`/`pco4k`/`dimax_*`/`basler1`/`basler2` | indirect-detection area detector(s) |
| HR_DetectorStage | LinearStage | `hrxc`/`hryc`/`hrzc` (detector carriage, `iceid191`) | detector positioning / propagation distance |
| HR_Optic | (microscope optics) | `hrhasselblad` (`RevolvedHasselbladOptic`); objective/scintillator turret motors | objective + scintillator selection |

## Other endstations in the config (noted, not modelled in this cut)

- `MHTOMO` (`mhsrot/mhyrot/mhsz`, `iceid191/iceid195`), `MEDTOMO` (`medsrot/medsz/medtilt/...`,
  `iceid195`), `LATOMO` laminography (`micos_anka` MicosAnka over TCP `wid19lamino1.esrf.fr`,
  tilt-transformation `Pusher`), `RADIO`, `PCOTOMO`. Plus the SmarAct multi-tower stack
  (`towerA..E`, `smaractid191/192`) and fluorescence MCAs (`fxid19` FalconX, `fluodet` Mercury).

## Open confirms

- **CTRL-1** -- the BLISS / Tango handles are read from the public config and carried `confirm`;
  verify they are current against the live system.
- **SRC-1** -- which insertion device(s) feed which endstation / mode, and the energy reach.
- **OPT-1** -- the TripleMono crystal-pair / Laue / multilayer mode mapping and the transfocator
  lens recipe per energy.
- **SAMPLE-1 / DET-1** -- the exact stage and detector roster per endstation (the config carries
  many spare / commented axes); confirm the operative set.
- **PSS-1** -- the personnel-safety permit signals behind the `frontend` / `bsh` shutters.
