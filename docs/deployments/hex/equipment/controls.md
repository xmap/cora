# Controls

*The control stack and the bluesky-orchestration seam. First cut; the endstation detector handles are read from the profile collection, the FOE-optics handles are pending, all carried confirm.*

HEX runs on the NSLS-II EPICS / ophyd control stack, the same floor as the other NSLS-II beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The endstation detector handles are filled from the beamline's own bluesky profile collection ([NSLS2/hex-profile-collection](https://github.com/NSLS2/hex-profile-collection), the `startup/*.py` files, with the detector helpers in [NSLS2/hextools](https://github.com/NSLS2/hextools)): the Kinetix sCMOS cameras (`XF:27ID1-BI{Kinetix-Det:N}`, from `10-kinetix.py`), the PerkinElmer flat panel (`XF:27ID1-ES{PE-Det:1}`, from `11-perkin-elmer.py`), and the GeRM germanium strip detector (`XF:27ID1-ES{GeRM-Det:1}`). The FOE-optics PVs (the wiggler, the filters, the monochromator, the slits) are not in the profile collection and are carried as `{confirm: ...}` pending staff (`CTRL-1`). All handles remain confirm-pending: a value read from public config is evidence to verify with staff, not a CORA-owned fact.

The motion layer (Phytron and Delta Tau PowerBrick controllers) and the fly-scan triggering that gates tomography (`tomo_flyscan`) are observed but not modelled as device instances in this cut: their per-axis functional map is not in the public config, and CORA does not invent a controller instance from the vendor names alone (vendor identity belongs on a bound Model, not an instance label). When the functional map is confirmed, each controller would be named by what it drives, the sibling `<Function>MotionController` pattern, and bound to the beamline-path Assets by `controller_id` (`CTRL-1`). The Moxa ioLogik relays seen in the public config are discrete I/O, observed not modelled.

## The orchestration seam

The HEX acquisition runs through bluesky plans driven from a queue server (`run-qserver-gui`): the tomography plans (`tomo_flyscan`, `tomo_dark_flat`, `tomo_loop`, `tomo_y_scan_loop`), the diffraction acquisition, and the technique switch that repositions detectors and optics. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The tomography and area-detector file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

What CORA conducts over the floor, by leg:

| Floor activity (bluesky today) | CORA leg | Devices conducted |
| --- | --- | --- |
| Fly-scan tomography / CT | acquisition over `ControlPort` | `SampleRotation`, `ImagingCamera` + `ImagingScintillator` (position-triggered) |
| Time-resolved radiography | acquisition over `ControlPort` | `HighSpeedCamera`, `SampleStage` |
| Energy-dispersive diffraction (EDXD) | acquisition over `ControlPort` | `SampleStage` (gauge volume), `EnergyDispersiveDetector` |
| Angle-dispersive diffraction (ADXD) | acquisition over `ControlPort` | `SampleRotation` / `SampleStage`, `FlatPanelDetector` |
| Technique switch (detector / optics into beam) | positioning over `ControlPort` | `DetectorStage` |
| Frames to the NSLS-II filestore | observed plumbing | none owned; CORA moves frames into its own Dataset of record |

### The technique switch specifically

The one leg worth spelling out is the technique switch, because it is what makes HEX's single-endstation, multi-technique experiment work. The same sample mounting can be measured by tomography, then by energy-dispersive diffraction, then by angle-dispersive diffraction, with the detectors and optics moved into the beam remotely between modes. CORA conducts that as a positioning leg over the `ControlPort`: the `DetectorStage` moves the chosen detector or optic into place, and then the technique's acquisition runs. CORA does not treat the multi-technique endstation as one fused instrument; it treats technique selection as a conducted positioning step ahead of a single-technique acquisition (`TECH-1`). No new hardware is invoked by the switch beyond the positioning stage.

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the profile collection and are not invented here (`PSS-1`). HEX's source is a superconducting wiggler, whose gap / field handle is not in the profile collection either and is carried confirm (`SCW-1`). At HEX's photon energies (white beam to 250 keV) the shielding burden is heavier than the fleet's lower-energy beamlines, which the safety tier would reflect once confirmed. If CORA later models the protection tier, it would not model the interlock logic itself; it would only observe outcomes, mapping the in-situ environments and the vacuum optics to Supply and Asset condition. That mapping is not modelled in this cut.
