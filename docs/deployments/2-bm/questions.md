# Open questions

*Facts CORA needs 2-BM staff to confirm or correct. Each row is a question about the real beamline; only open items appear here.*

## How to reply

Open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one answer or several together. Quote the item ID and write the answer in plain text:

> STAGE-6: the laminography-pitch stage is a Kohzu SA16A-RM
> DET-9: the installed middle objective is 5x

You do not need to edit this file or know where it lives. If you do not use GitHub, send the same thing (the item ID and your answer) to whoever shared this page. If a row is really a controls/EPICS, network, or engineering question, route it to the right person or tell us who that is.

## How to read a row

A *CORA assumes* value is only ever a placeholder for the description; CORA never uses a guessed value to move or observe hardware. No `Blocks-build` items are open right now, so start with the `Blocks-go-live` rows.

**Priority:**

- `Blocks-build`: your answer changes the structure of the description, so CORA cannot finalize it until you reply. None are open right now.
- `Blocks-go-live`: a guess is fine for the description, but the real value is needed before CORA controls or observes the hardware.
- `Nice-to-have`: extra detail for the record and for datasheets.

**Columns:**

- *CORA assumes*: the current placeholder, or a note that nothing is recorded yet. Confirm or correct it where it is a real guess; `unknown-pending-confirmation` or `not yet registered` just means we have no value yet.
- *Already done?*: **yes** means the guess is live in CORA now, so your answer confirms it or tells us to change it; **not yet** means CORA is holding a blank and waiting for yours.
- *Resolves*: where the answer gets recorded once confirmed. This is for us, not something you click to reply.

Once an item is confirmed we record the value, replace the guess, and delete the row, noting who confirmed it and, if it overturned an earlier value, why. This page always shows only what is still open. Each ID is permanent and never reused, and IDs run per section.

## Drives and controllers

CORA records each controller box's identity (serial, firmware) so it can later tell whether the firmware changed between two scans. These are placeholders today.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DRIVE-1 | `Blocks-go-live` | Serial numbers for the two OMS VME58 crate cards (`SampleStageDrive`, `FrontEndDrive`)? The three Aerotech drives (rotary, hexapod, propagation-distance) are now confirmed and recorded; these two await a crate-access hardware visit. | `unknown-pending-confirmation` | not yet | [Settings](inventory.md#settings) |
| DRIVE-2 | `Blocks-go-live` | Firmware versions for all five motion-controller boxes (the three Aerotech drives plus the two OMS VME58 cards)? | `unknown-pending-confirmation` | not yet | [Settings](inventory.md#settings) |
| DRIVE-3 | `Nice-to-have` | Are the Aerotech drives network-attached, and if so their IP addresses? | left blank (assumed not needed) | not yet | [Settings](inventory.md#settings) |
| DRIVE-5 | `Nice-to-have` | Serial number of the Nanotec `ST4118M1404-B` stepper driving the Microscope objective selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Vendor catalog](equipment/microscope.md#vendor-catalog) |
| DRIVE-6 | `Nice-to-have` | Serial number of the Schunk `LPTM 30` stepper driving the Microscope camera selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Microscope](equipment/microscope.md) |

## The hexapod

The sample hexapod's six degrees of freedom are described as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](inventory.md#hexapod-dof-model).

### Rebooting a stuck hexapod

Recovery from a controller lock-up is the [`hexapod_reboot` recipe](recipes.md), read from the authoritative script [`decarlof/2bmb-bin/hexapod_reboot.py`](https://github.com/decarlof/2bmb-bin/blob/HEAD/hexapod_reboot.py). Confirming that script is the current production copy (HXP-7) settles HXP-3, HXP-4, and HXP-6 at once; the only value not in the repo is the deployment PDU secret (HXP-5).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-3 | `Nice-to-have` | Confirm the enable / force-enable PVs are still current. | `2bmHXP:HexapodAllEnabled.VAL` (read), `2bmHXP:EnableWork.PROC` (force-enable) | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-4 | `Nice-to-have` | Confirm the IOC stop / start scripts and host. | `hexapod_IOC_stop.sh` / `hexapod_IOC.sh`, IOC host `arcturus` (user `2bmb`) | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-5 | `Blocks-go-live` | Which of the two PDUs (`a` default, or `b`) powers the hexapod, and its IP address? The script's `--pdu a/b` is the same box `item_050` calls "PDU 1" on the Tomo control screen; please confirm PDU 1 maps to `pdu_a`. The outlet is the operator-facing number 5 (the NetBooter relay index is zero-based, so the wire call is `rly=4`); only the PDU choice and IP live in `~/access.json`, not the repo. | NetBooter over HTTP (`/cmd.cgi?rly=N`, `/status.xml`), operator outlet 5 = wire `rly=4`; PDU `a` assumed = item_050 "PDU 1"; IP unknown | partly (type / endpoints / outlet known; PDU choice + IP not) | [Recipes](recipes.md) |
| HXP-6 | `Nice-to-have` | Confirm the reboot timings are the current operating values. item_050 says to "wait about 2 minutes" before restarting the IOC; the script's per-phase defaults sum to roughly that, so CORA records the script's values. | 10 s off-wait, 30 s on-wait, 10 s IOC settle, 180 s enable poll at 1 s intervals (script defaults); item_050 quotes "~2 min" overall | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-7 | `Blocks-go-live` | Is the public [`decarlof/2bmb-bin`](https://github.com/decarlof/2bmb-bin) repo (and specifically `hexapod_reboot.py`) the current production version, or is there a newer or internal copy we should track instead? CORA read the reboot records from it, so a yes resolves the "confirm current" on HXP-3, HXP-4, and HXP-6 at once; it is also the operational-scripts source for the IOC start/stop and energy scripts. | `decarlof/2bmb-bin` is current and authoritative | not yet | [Recipes](recipes.md) |
| HXP-8 | `Nice-to-have` | Confirm two `item_050` facts are still current: (a) the over-travel drive error (driving the hexapod past its travel range disconnects the axis drivers and turns off the Enable/Fault indicator), cleared by the same reboot; and (b) the post-reboot Y-stage dial misreset (the Y dial resets to 0 while the encoder reads 350, so the operator must set the Y dial to 350 before any Y move, or the first move faults). | both modelled as Cautions: over-travel folded into the controller-lockup Caution, the Y-dial misreset as a stage Caution | yes (modelled from item_050; awaiting staff confirmation) | [Cautions](cautions.md) |

## Sample stages

These rows confirm vendor models, datasheets, and travel limits for the sample-side stages.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](inventory.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABRS-250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html), `item_050`). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABRS-250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) | one installed (`ABRS-250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](inventory.md#vendor-catalog) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](inventory.md#vendor-catalog) |
| STAGE-10 | `Nice-to-have` | Confirm the `Rotary` encoder resolution. `item_050`'s Ensemble encoder table gives 532800 pulses/rev (11840 lines/rev x 45 scale factor) = 0.000676 deg/count for the ABRS-250MP; CORA now records that, replacing an earlier unsourced `0.0001 deg`. The 11840 lines/rev fundamental is confirmed by the ABRS datasheet (#164); still open is whether the Ensemble applies the x45 or a further electronic multiplication to reach the operational count. | `0.000676 deg` from item_050; 11840 lines/rev datasheet-confirmed (#164) | yes (awaiting Ensemble-multiplication confirmation) | [Settings](inventory.md#settings) |

## The Microscope detector

Objectives and the turret selector on the Optique Peter microscope. Objectives are swappable, so several rows confirm what is mounted now.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](equipment/microscope.md#vendor-catalog) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). The field-tested staff `2bm-procedures` repo independently corroborates this: it hard-codes the middle objective (MCTOptics `LensSelect` index 1) as 5.0x. Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); the microscope lens table and the field-tested staff repo both indicate 5x installed | yes | [Microscope](equipment/microscope.md) |
| DET-12 | `Nice-to-have` | When the propagation-distance stage (`2bmbAERO:m1`, the sample-to-detector rail) moves, does the whole detector (the Optique Peter housing with its objectives, scintillator, and camera) travel along the beam as one unit, or does only part of it move while the rest stays fixed to the detector table? Put another way: is the microscope mounted on top of that stage, or are the stage and the microscope mounted side by side on the table? | the stage carries the whole microscope, so CORA models the rail as the support the housing rests on; please confirm the physical mounting | yes | [Microscope](equipment/microscope.md) |
| DET-13 | `Nice-to-have` | The remaining FLIR Oryx 31 MP (`Camera_HighRes`, `2bmSP2:`) `Camera`-schema fields: bit depth, sensor kind, and readout mode? The [Detection page (item_020)](https://docs2bm.readthedocs.io/en/latest/source/ops/item_020.html) now confirms the sensor as 6464 x 4852 px at 26 fps (3.45 um pitch, mono), and per-unit identity (model `ORX-10G-310S9M`, serial `22150530`, firmware `1904.0.72.0`) is on record, so only these three are missing; the `Camera` schema needs bit depth before the sensor group can be applied, so the Asset stays identity-only until then. | size + frame rate confirmed (item_020); bit depth / sensor kind / readout mode pending | partly | [Microscope](equipment/microscope.md) |

## Timing

The softGlueZynq box is registered and its trigger outputs are wired to the camera and the piezo (ports plus Plan wires). What stays open is two labels on the camera leg (the FPGA output channel and the `GateDly1` block name).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- || TIME-2 | `Nice-to-have` | Two labels on the camera trigger leg: (a) which FPGA output channel feeds the camera (the routing string ends at the camera's `Line2` input but names no box-side output), and (b) the `GateDly1` block name on that leg (the piezo legs use the source-grounded `GateDly-2`/`GateDly-3` from item_028; `GateDly1` is so far unconfirmed). | wired `Timing.camera_trigger_out -> Camera.trigger_in` with `camera_trigger_out` a placeholder port name pending the channel; `GateDly1` recorded but flagged | yes | [Camera trigger wiring](inventory.md#camera-trigger-wiring) |

## Fine-positioning piezo controllers

The NV200D/NET piezo (now `ApertureFineDrive`) fine-positions the coded `Aperture` mask via FPGA-triggered stepping; the NV100D is present but not in operational use. One row remains: confirming which FPGA output drives which axis.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| PIEZO-5 | `Nice-to-have` | Confirm the NV200D FPGA trigger mapping and its purpose. item_028 routes the JenaX / JenaY cables to FPGA `out2` / `out3`, but labels the delay PVs `GateDly-3_DLY` = "X axis delay" and `GateDly-2_DLY` = "Y axis delay", which crosses that cable map; which axis is on which output? And what is the 1024-position triggered-step mode used for (interlaced / dithered tomographic sampling)? | wired `Timing.out2 -> X`, `Timing.out3 -> Y` per the cable map, with the delay-PV labels recorded as the apparent cross; step use-case assumed fine-sampling during tomography | yes | [NV200D trigger wiring](inventory.md#nv200d-trigger-wiring) |

## Energy and the optics

On an energy change the DMM monochromator, its Bragg arms, and the tracking slits move together to saved per-energy positions (now recorded). The remaining items cover the multilayer stripe selection and the channel-cut calibration crystal.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ENERGY-6 | `Nice-to-have` | Per the [DMM page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_021.html) the monochromator substrate carries two multilayer stripes with different periods (13.8 and 24 angstrom, 4 mm apart). Is the active stripe selected per energy by a lateral crystal translation (the upstream / downstream X motors `2bma:m25` / `2bma:m28`, today folded into `ENERGY-5`), and which stripe serves which energies in the Mono menu (13.374 to 25.584 keV)? If it is an operator-facing per-energy selection rather than a fixed setup, CORA would model it as a named DMM stripe selector, the monochromator counterpart of the mirror coating stripe (`MIRROR-1`). | two stripes exist; no DMM stripe / d-spacing selector modelled; `2bma:m25` / `2bma:m28` lateral X carried only as unframed alignment motors | not yet | [Energy-tracking optic axes](inventory.md#energy-tracking-optic-axes) |
| ENERGY-7 | `Nice-to-have` | Is energy calibration via a channel-cut crystal current 2-BM practice, and which crystal (its lattice spacing 2d; the [calibration page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_022.html) lists 3.84 angstrom)? Is the crystal a removable reference standard (CORA models it as a calibration Subject, like the resolution phantom) or installed equipment, and on what rotation stage is it rocked? | modelled as the `energy_characterization` Procedure with the crystal as a calibration Subject; current practice, crystal, and 2d unconfirmed | yes | [Procedures](procedures.md) |

## Filters and the mirror stripe

This row covers the mirror coating stripe.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| MIRROR-1 | `Nice-to-have` | Is the mirror coating stripe (`2bma:m3`) held at one fixed position in Mono mode and swept per energy in Pink mode (together with the optical-table X stages, driven by the energy-change IOC), rather than a freely-selectable discrete pick? And is there a stripe-to-position mapping (which stripe sits at which `m3` position) we can record? | energy/mode-dependent stripe; held in Mono, swept in Pink; no stripe->position map on file | not yet | [Beam modes](procedures.md#beam-modes) |

## Beam mode

2-BM runs in two beam modes, and switching between them is a coordinated multi-device move CORA does not yet drive. These confirm the mode model and supply the values it would need.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| MODE-3 | `Blocks-go-live` | The pink-mode per-energy saved positions (the Pink half of `store_0`) for the swept mirror coating stripe (`2bma:m3`) and the mirror-table X stages (`2bma:m1` / `m4`)? The page gives a partial table (30 keV: m3 3.039, table X 8/8; 40: 13.0, 10/10; 50: 39.0, 10/10; 60: 49.0, 29/29 mm); please confirm and complete it, and (the data half of MIRROR-1) tell us which named stripe (a/b/c/d) sits at which `m3` position. | partial pink m3 and table-X positions from the page; stripe-to-label map not on file | not yet | [Beam modes](procedures.md#beam-modes) |

## Equipment protection

BLEPS is the beamline equipment-protection interlock, separate from the PSS: BLEPS protects equipment, the PSS protects people. CORA does not model its logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset's condition. These items confirm that mapping before any BLEPS signal is ingested.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BLEPS-1 | `Nice-to-have` | Which BLEPS faults are utility-level (vacuum via IP/IG/GV, cooling-water via the Flow channels) versus tied to a specific device (for example a mirror or optics trip)? | utility faults map to Supply, device faults to Asset condition; CORA never models the interlock matrix | not yet | [Supplies](operations.md#supplies) |
| BLEPS-2 | `Nice-to-have` | Are the BLEPS fault / status signals readable as Channel Access PVs for an external observer (the BLEPS EPICS transfer table lists tags such as `A_Fault_Exists`, `GV1.Faulted`, the Flow channels, `FES.Permit` / `SBS.Permit`)? If readable, which PV maps to which utility or device; if not, the integration path. | readable via the BLEPS PLC EPICS interface; exact PV-to-Supply/Asset mapping unknown | not yet | [Supplies](operations.md#supplies) |
| BLEPS-3 | `Nice-to-have` | Is there a beamline-level "BLEPS tripped / armed / recovering" state that operators act on as a whole, distinct from the individual utility and device faults, that gates a run on its own? | no system-level state needed; decompose onto existing axes | not yet | [Supplies](operations.md#supplies) |
## Proposals, users and scheduling

CORA will read proposal and user information from the APS scheduling system (the `beam-api` / DMagic data the beamline already uses) to label each run with its proposal and notify the right people. These help us get the design right before we build it. Confirmer: the beamline scientist, except SCHED-3 (APS User Office / data-management contact).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SCHED-1 | `Nice-to-have` | Once a user group is on-site for their beamtime, does APS ever move their scheduled time window (earlier or later) before they start, or do time changes only happen before they arrive? | time changes happen only before arrival | not yet | [2-BM index](index.md) |
| SCHED-2 | `Nice-to-have` | Is the beamline staff contact (local contact) for a beamtime listed among that experiment's users in the scheduling system, or tracked separately as a beamline-side assignment? | listed as one of the beamtime's people | not yet | [2-BM index](index.md) |
| SCHED-3 | `Nice-to-have` | Are APS badge numbers ever reused or reassigned to a different person over time, or is a badge number stable for life per person? And under APS data governance, is a badge number classified as personal data subject to deletion on request? Confirmer: APS User Office / data-management contact. | badge stable per person; classified as deletable personal data | not yet | [2-BM index](index.md) |

## Vibration and beam stability

The [docs2bm item_070 page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_070.html) documents three characterization measurements of the beamline itself: a high-speed vibration baseline, an air-handler shutdown test, and a multi-hour flat-field stability run. CORA models these as subject-less characterization captures, the Pending [`vibration_baseline`](procedures.md) Procedure / Run / Dataset and two operator [Cautions](cautions.md); the FFT and stripe-motion analysis stays downstream. These rows confirm the real-beamline facts that turn those stubs into records. Source: the staff-authored item_070 page.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |

## Not on this page

Hardware CORA has deliberately not described yet (the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) raises questions here only once CORA starts describing it. The `Mirror` is the exception that proves the rule: it is now a registered Asset ([Inventory](inventory.md#inventory)), so it already raises questions here (`MIRROR-1`, `MODE-3`) even though its coating-stripe physics stay deferred to the beam-mode work.
