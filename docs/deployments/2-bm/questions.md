# Open questions

*Facts CORA needs 2-BM staff to confirm or correct. Each row is a question about the real beamline; only open items appear here.*

## How to reply

Open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one answer or several together. Quote the item ID and write the answer in plain text:

> HXP-2: A = Roll, B = Pitch, C = Yaw
> DET-9: the installed middle objective is 5x

You do not need to edit this file or know where it lives. If you do not use GitHub, send the same thing (the item ID and your answer) to whoever shared this page. A few rows name a different contact: facility utilities (gas, compressed air) for **SUP-1**, **SUP-2**. If a row is really a controls/EPICS, network, or engineering question, route it to the right person or tell us who that is.

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
| DRIVE-1 | `Blocks-go-live` | Serial numbers for the two OMS VME58 crate cards (`SampleStageDrive`, `FrontEndDrive`)? The three Aerotech drives (rotary, hexapod, propagation-distance) are now confirmed and recorded; these two await a crate-access hardware visit. | `unknown-pending-confirmation` | not yet | [Settings](assets.md#settings) |
| DRIVE-2 | `Blocks-go-live` | Firmware versions for all five motion-controller boxes (the three Aerotech drives plus the two OMS VME58 cards)? | `unknown-pending-confirmation` | not yet | [Settings](assets.md#settings) |
| DRIVE-3 | `Nice-to-have` | Are the Aerotech drives network-attached, and if so their IP addresses? | left blank (assumed not needed) | not yet | [Settings](assets.md#settings) |
| DRIVE-5 | `Nice-to-have` | Serial number of the Nanotec `ST4118M1404-B` stepper driving the Microscope objective selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DRIVE-6 | `Nice-to-have` | Serial number of the Schunk `LPTM 30` stepper driving the Microscope camera selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Pending](assets.md#pending) |

## The hexapod

The sample hexapod's six degrees of freedom are described as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](computed-axes.md#hexapod-dof-model).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | yes | [Hexapod DoF model](computed-axes.md#hexapod-dof-model) |

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
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | A datasheet PDF for the Aerotech ABRS-250MP-M-AS rotary stage (`Rotary`)? The vendor engineering drawing (630C2125) is now on file (#156); a datasheet PDF would still be useful. | `Aerotech ABRS-250MP-M-AS`, vendor drawing on file, no datasheet PDF yet | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABRS-250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html), `item_050`). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABRS-250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) | one installed (`ABRS-250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-10 | `Nice-to-have` | Confirm the `Rotary` encoder resolution. `item_050`'s Ensemble encoder table gives 532800 pulses/rev (11840 lines/rev x 45 scale factor) = 0.000676 deg/count for the ABRS-250MP; CORA now records that, replacing an earlier unsourced `0.0001 deg`. Is 0.000676 deg/count the right operational resolution, or does the Ensemble apply further multiplication? | `0.000676 deg` from item_050 (was `0.0001 deg`, unsourced) | yes (corrected from item_050; awaiting confirmation) | [Settings](assets.md#settings) |

## The Microscope detector

Objectives and the turret selector on the Optique Peter microscope. Objectives are swappable, so several rows confirm what is mounted now.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). The field-tested staff `2bm-procedures` repo independently corroborates this: it hard-codes the middle objective (MCTOptics `LensSelect` index 1) as 5.0x. Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); the microscope lens table and the field-tested staff repo both indicate 5x installed | yes | [Microscope](equipment/microscope.md) |
| DET-11 | `Blocks-go-live` | The objective turret selector (`2bmb:m1`, Nanotec stepper): for each objective (10x, 2x, 1.1x), the physical slot order and the turret motor position that brings it into the beam? CORA models the selector as a discrete index axis (commanded slot index -> saved turret position), but the slot order and positions it carries today are placeholders. | placeholder slot order + positions; modelled as a discrete index axis | yes | [Microscope](equipment/microscope.md) |
| DET-12 | `Nice-to-have` | When the propagation-distance stage (`2bmbAERO:m1`, the sample-to-detector rail) moves, does the whole detector (the Optique Peter housing with its objectives, scintillator, and camera) travel along the beam as one unit, or does only part of it move while the rest stays fixed to the detector table? Put another way: is the microscope mounted on top of that stage, or are the stage and the microscope mounted side by side on the table? | the stage carries the whole microscope, so CORA models the rail as the support the housing rests on; please confirm the physical mounting | yes | [Microscope](equipment/microscope.md) |
| DET-13 | `Nice-to-have` | The FLIR Oryx 31 MP (`Camera_HighRes`, `2bmSP2:`) sensor specs to complete its `Camera` settings: sensor width and height (pixels), bit depth, max frame rate, sensor kind, and readout mode? Per-unit identity (model `ORX-10G-310S9M`, serial `22150530`, firmware `1904.0.72.0`) and the 3.45 um pixel pitch are already confirmed, so the Asset is registered identity-only until these land. | registered identity-only; sensor settings pending | yes | [Microscope](equipment/microscope.md) |

## Timing

The softGlueZynq box is registered and its trigger outputs are wired to the camera and the piezo (ports plus Plan wires). What stays open is the gateware (bitstream) version and two labels on the camera leg (the FPGA output channel and the `GateDly1` block name).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq's gateware (bitstream) version? The box itself is identified on the components page (a Xilinx Zynq SoC on a MicroZed carrier, EPICS prefix `2bmbMZ1:SG:`); only the bitstream version is missing. Optional for now. | registered as a `TimingController` Asset; bitstream version still a placeholder | yes | [Settings](assets.md#settings) |
| TIME-2 | `Nice-to-have` | Two labels on the camera trigger leg: (a) which FPGA output channel feeds the camera (the routing string ends at the camera's `Line2` input but names no box-side output), and (b) the `GateDly1` block name on that leg (the piezo legs use the source-grounded `GateDly-2`/`GateDly-3` from item_028; `GateDly1` is so far unconfirmed). | wired `Timing.camera_trigger_out -> Camera.trigger_in` with `camera_trigger_out` a placeholder port name pending the channel; `GateDly1` recorded but flagged | yes | [Camera trigger wiring](assets.md#camera-trigger-wiring) |

## Fine-positioning piezo controllers (Jena)

CORA has registered the two Piezosystem Jena piezo controllers (NV100D, item_027; NV200D/NET, item_028) as `MotionController` boxes, but the item pages describe how to operate them, not what each physically positions. These rows confirm that and the per-box detail; the function answer (PIEZO-1) is what lets CORA name and register the driven X/Y axes.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| PIEZO-1 | `Blocks-go-live` | What does each Jena piezo controller physically position, and in which hutch? The NV100D (`OpticsFineDrive`) is reached from the `mct_optics` screen, so CORA guesses it fine-positions a microscope optic; the NV200D (`SampleFineDrive`) is FPGA-stepped during tomography and "complements" the NV100D, so its X/Y could move an optics / detector element rather than the sample. The answer finalizes both provisional controller names and lets CORA register the driven axes. | provisional names `OpticsFineDrive` / `SampleFineDrive`, both placed in `2-BM-B`; driven element unconfirmed | yes | [Fine-positioning piezo controllers](assets.md#fine-positioning-piezo-controllers-jena-nv100d-nv200d) |
| PIEZO-2 | `Nice-to-have` | The piezo actuator / flexure-stage models and their travel for each controller's two axes (item_028 notes the NV200D stroke as 0 to 100 um)? CORA needs these to register the X/Y `LinearStage` axes once PIEZO-1 names them. | no actuator model or travel on file; axes not yet registered | not yet | [Fine-positioning piezo controllers](assets.md#fine-positioning-piezo-controllers-jena-nv100d-nv200d) |
| PIEZO-3 | `Nice-to-have` | Confirm the vendor (Piezosystem Jena) and the exact part numbers for the two controllers? CORA records `NV100D` and `NV200D/NET` as working values. | `Piezosystem Jena` `NV100D` / `NV200D/NET` (working values) | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| PIEZO-4 | `Nice-to-have` | The two static IP addresses per controller, to record alongside the EPICS IOC handles (host `arcturus`, IOCs `JenaNV100D` / `JenaNV200D`)? | IOC host / names known from the item pages; per-axis IPs not recorded | not yet | [Fine-positioning piezo controllers](assets.md#fine-positioning-piezo-controllers-jena-nv100d-nv200d) |
| PIEZO-5 | `Nice-to-have` | Confirm the NV200D FPGA trigger mapping and its purpose. item_028 routes the JenaX / JenaY cables to FPGA `out2` / `out3`, but labels the delay PVs `GateDly-3_DLY` = "X axis delay" and `GateDly-2_DLY` = "Y axis delay", which crosses that cable map; which axis is on which output? And what is the 1024-position triggered-step mode used for (interlaced / dithered tomographic sampling)? | wired `Timing.out2 -> X`, `Timing.out3 -> Y` per the cable map, with the delay-PV labels recorded as the apparent cross; step use-case assumed fine-sampling during tomography | yes | [NV200D trigger wiring](assets.md#nv200d-trigger-wiring) |

## Beam path and front end

Three rows cover the front-end windows, the B-station safety shutter, and the diagnostic flag.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | not yet | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | Is there a canonical APS drawing for the B-station safety shutter (`StationShutter`) beyond its RSS tag (`02-BM-A-P-01`)? | shutter modelled; only the RSS tag on file | not yet | [Engineering drawings](assets.md#engineering-drawings) |
| FLAG-1 | `Nice-to-have` | For the diagnostic flag (`DiagnosticFlag`, `2bma:m44`): its exact in-hutch location (which 2-BM-A position / z), and the energy-dependent vertical positions it takes in Mono (the staff `energy_move_flag` table) plus its parked Pink position? CORA registers it as a `Screen` Asset on `FrontEndDrive`, raised in Mono and parked in Pink, but does not yet carry its positions or model the Y as an energy-tracking axis. | registered as a `Screen` Asset; in-hutch position and energy-tracking Y curve pending | yes | [Beam modes](procedures.md#beam-modes-mono-pink) |

## Energy and the optics

On an energy change the DMM monochromator, its Bragg arms, and the tracking slits move together to saved per-energy positions. These items supply those saved values and confirm how they are driven.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ENERGY-1 | `Nice-to-have` | The real saved per-energy positions (the `store_0` table) for the energy-driven DMM axes: the Bragg arms (`dmm_us_arm` / `dmm_ds_arm` = `2bma:m30` / `2bma:m31`) and the M2 vertical offset (`dmm_m2_y` = `2bma:m32`)? CORA models each as a continuous curve, but the positions it carries today are placeholders. | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-2 | `Nice-to-have` | The matching per-energy saved positions for the B-station sample-slit vertical pair (`b_slit_top` / `b_slit_bot` = `2bma:m9` / `2bma:m10`) that tracks the beam walk? (The mirror is held constant in Mono mode, so it gets no Mono energy curve; in Pink the coating stripe IS swept per energy, see MODE-3.) | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-3 | `Nice-to-have` | Does the energy-change IOC drive the Bragg-arm angles from a saved per-energy table, or compute them from the Bragg geometry? This decides whether CORA keeps the arms as interpolated curves or models them as a computed relationship. | modelled as interpolated curves (provisional) | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-4 | `Nice-to-have` | We plan a "set energy" operation that accepts a free energy value (keV) and interpolates the saved per-energy curves, rather than only the exact configured energies, so an operator could request, say, 22 keV between two saved points. Is that acceptable and safe at 2-BM, i.e. is it OK to drive the optics to interpolated in-between positions that were not individually saved/validated, or must operation stay restricted to the exact configured energies? (Outside the saved range we refuse the move rather than clamp or extrapolate: the operator must request an in-range energy or extend the calibration.) | designed to accept free-keV with interpolation within the saved range, refusing out-of-range requests; pending your confirmation | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-5 | `Nice-to-have` | The DMM tank/alignment motors (`2bma:m25`-`m29`) are part of the energy-change coordinated move, but the components page does not say whether their saved positions actually differ per energy. Do they vary with energy, or are they re-asserted at fixed values? If they vary, CORA would add curves for them too. (The lateral X pair `2bma:m25` / `2bma:m28` may instead be the multilayer stripe selector rather than alignment; that distinction is `ENERGY-6`.) | in the coordinated move; per-energy variation unconfirmed; not modeled as curves | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-6 | `Nice-to-have` | Per the [DMM page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_021.html) the monochromator substrate carries two multilayer stripes with different periods (13.8 and 24 angstrom, 4 mm apart). Is the active stripe selected per energy by a lateral crystal translation (the upstream / downstream X motors `2bma:m25` / `2bma:m28`, today folded into `ENERGY-5`), and which stripe serves which energies in the Mono menu (13.374 to 25.584 keV)? If it is an operator-facing per-energy selection rather than a fixed setup, CORA would model it as a named DMM stripe selector, the monochromator counterpart of the mirror coating stripe (`MIRROR-1`). | two stripes exist; no DMM stripe / d-spacing selector modelled; `2bma:m25` / `2bma:m28` lateral X carried only as unframed alignment motors | not yet | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |
| ENERGY-7 | `Nice-to-have` | Is energy calibration via a channel-cut crystal current 2-BM practice, and which crystal (its lattice spacing 2d; the [calibration page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_022.html) lists 3.84 angstrom)? Is the crystal a removable reference standard (CORA models it as a calibration Subject, like the resolution phantom) or installed equipment, and on what rotation stage is it rocked? | modelled as the `energy_characterization` Procedure with the crystal as a calibration Subject; current practice, crystal, and 2d unconfirmed | yes | [Procedures](procedures.md) |
| ENERGY-8 | `Nice-to-have` | When the energy calibration finds an offset (true minus commanded energy), is it folded back into the saved `store_0` per-energy table (so the energy curves already deliver the corrected energy), or applied as a separate energy-axis correction at command time? This decides whether CORA's `energy_offset` Calibration stays independent of the energy curves (today's model) or is wired to correct them. | modelled as an independent `energy_offset` Calibration on the `Monochromator`, not folded into the curves | yes | [Energy-tracking optic axes](computed-axes.md#energy-tracking-optic-axes) |

## Filters and the mirror stripe

These rows cover the absorber-foil paddles and the mirror coating stripe.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| FOIL-1 | `Blocks-go-live` | We model the operational downstream absorber-foil paddle (`2bma:m18`) as a discrete selector with these slots and motor positions, read from the components page: `600 um Al` at 0, `150 um Al` at 26, `300 um C` at 53, `50 um C` at 80, `None` at 106. Are the slots, order, and positions correct, and is the position unit millimetres (the components page says the motor EGU is "consistent with mm" but does not state it outright)? | downstream paddle modelled with the positions above; unit assumed mm | yes | [Filter foil selection](computed-axes.md#filter-foil-selection) |
| FOIL-2 | `Nice-to-have` | We treat the upstream paddle (`2bma:m17`) as bound-in-software but not in service (selecting it has no beam effect), so CORA does not model it as a live selector. Is that right, and should we ever expect it to come back into service? | upstream paddle not modelled as a live selector | yes | [Filter foil selection](computed-axes.md#filter-foil-selection) |
| MIRROR-1 | `Nice-to-have` | We understand the mirror coating stripe (`2bma:m3`) is not a free discrete pick: in Mono mode it is held at one position, and in Pink mode it is swept per energy together with the optical-table X stages, managed by the energy-change IOC. We will model it with the beam-mode work, not as a filter-style index axis. Is that understanding correct, and is there a stripe-to-position mapping (which stripe sits at which `m3` position) we can record? | stripe selection deferred to the beam-mode work; energy/mode-dependent, no stripe->position map on file | not yet | [Beam modes](procedures.md#beam-modes-mono-pink) |

## Beam mode (Mono / Pink)

2-BM runs in two beam modes, and switching between them is a coordinated multi-device move CORA does not yet drive. These confirm the mode model and supply the values it would need.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| MODE-1 | `Nice-to-have` | We model 2-BM as running two beam modes: monochromatic (the DMM is inserted and Bragg-selects one energy: 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV) and pink (the DMM is driven out of the beam and the mirror coating stripe sets the high-energy cutoff: 30, 40, 50, 60 keV). Are the two modes and those two configured-energy menus correct and current? | two modes; Mono and Pink menus as listed | not yet | [Beam modes](procedures.md#beam-modes-mono-pink) |
| MODE-2 | `Blocks-go-live` | How is the DMM physically inserted (Mono) and bypassed (Pink)? The components page implies the DMM Y motors drive to about -10 (out) for pink and 0 (in) for mono, with the Bragg arms parked when out, but we have no exact positions, PVs, or required switching sequence or interlock on file. What moves, to what positions, and in what order? | DMM Y to about -10 out / 0 in, Bragg arms parked in pink; exact positions and sequence unknown | not yet | [Beam modes](procedures.md#beam-modes-mono-pink) |
| MODE-3 | `Blocks-go-live` | The pink-mode per-energy saved positions (the Pink half of `store_0`) for the swept mirror coating stripe (`2bma:m3`) and the mirror-table X stages (`2bma:m1` / `m4`)? The page gives a partial table (30 keV: m3 3.039, table X 8/8; 40: 13.0, 10/10; 50: 39.0, 10/10; 60: 49.0, 29/29 mm); please confirm and complete it, and (the data half of MIRROR-1) tell us which named stripe (a/b/c/d) sits at which `m3` position. | partial pink m3 and table-X positions from the page; stripe-to-label map not on file | not yet | [Beam modes](procedures.md#beam-modes-mono-pink) |

## Beamline alignment (item_012)

The [docs2bm beamline-alignment page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_012.html) is the staff routine for walking the beam through the front-end optics in three modes (white, then pink, then mono). CORA models the optics it touches (`Mirror`, `Monochromator`, in the [Inventory](assets.md#inventory)) and the act itself as a deferred `beam_alignment` [Procedure family](procedures.md#beam-alignment-item_012); two pieces the routine relies on are not yet on file. These rows confirm them. Source: the staff-authored item_012 page.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ALIGN-1 | `Nice-to-have` | The beam-alignment routine views the beam on a 2-BM-A camera (a vertical-stage view on motor `2bma:m21`), separate from the B-station microscope detector. Is that a standing diagnostic Asset CORA should register (like the front-end `BeamPositionMonitor`), or a temporary setup brought in only for alignment? If standing, its vendor / model and EPICS handle. | a-station alignment camera not registered; assumed a transient diagnostic, not a standing Asset | not yet | [Pending](assets.md#pending) |
| ALIGN-2 | `Nice-to-have` | The fixed front-end mask used to center the white beam: CORA carries it as a passive, water-cooled, beam-defining aperture (`Mask` Family, about 24 m from the source) but has not registered it as an Asset. item_012 cites a 50 x 3 mm (H x V) aperture. Confirm the aperture size and that it should be registered as a passive Asset. | `Mask` descriptor stub (`new: true`); item_012 cites 50 x 3 mm (H x V); not yet registered | not yet | [Pending](assets.md#pending) |

## Equipment protection (BLEPS)

BLEPS is the beamline equipment-protection interlock, separate from the PSS: BLEPS protects equipment, the PSS protects people. CORA does not model its logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset's condition. These items confirm that mapping before any BLEPS signal is ingested.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BLEPS-1 | `Nice-to-have` | Does this mapping match how 2-BM thinks about BLEPS faults: utility faults (vacuum via IP/IG/GV, cooling-water via the Flow channels) surface as Supply status (Degraded / Unavailable), and device faults (for example a mirror or optics trip) as that Asset's condition (Faulted / Degraded)? Which faults are utility-level versus tied to a specific device? | utility faults map to Supply, device faults to Asset condition; CORA never models the interlock matrix | not yet | [Supplies](supplies.md) |
| BLEPS-2 | `Nice-to-have` | Are the BLEPS fault / status signals readable as Channel Access PVs for an external observer (the BLEPS EPICS transfer table lists tags such as `A_Fault_Exists`, `GV1.Faulted`, the Flow channels, `FES.Permit` / `SBS.Permit`)? If readable, which PV maps to which utility or device; if not, the integration path. | readable via the BLEPS PLC EPICS interface; exact PV-to-Supply/Asset mapping unknown | not yet | [Supplies](supplies.md) |
| BLEPS-3 | `Nice-to-have` | Is there a beamline-level "BLEPS tripped / armed / recovering" state that operators act on as a whole, distinct from the individual utility and device faults, that should gate a run on its own? If yes, CORA adds a dedicated protection status; if no, CORA decomposes BLEPS onto Supply and Asset condition and adds no new aggregate. | no system-level state needed; decompose onto existing axes | not yet | [Supplies](supplies.md) |

## Supplies

Facility utilities confirm 2-BM's sample-environment gas and compressed air.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? Confirmer: facility utilities. | a gas supply exists; mixture unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? Confirmer: facility utilities. | air available; specs unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |

## Data storage and transfer

CORA records where each dataset's bytes live and how they move between locations, so it can later answer "where is this scan's data now?" and verify that copies are intact. The guesses below come from the existing DMagic setup. Confirmer: the beamline's data-management / controls contact, these may not be beamline-scientist questions.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DATA-1 | `Blocks-go-live` | Where does 2-BM data physically land, and through what stages, in order? For example local scratch on the acquisition / reconstruction host, then a DM / Sojourner archive, then tape. Please name the real systems and paths. | raw under `/data3/2BM/<experiment>/`, reconstructed under `<experiment>_rec/`, transferred to APS Data Management ("Sojourner"); the tiers and their order are unconfirmed | not yet | [Supplies](supplies.md) |
| DATA-2 | `Blocks-go-live` | For each storage location: is it operator-visible, and is it permanent or auto-deleted? In particular, when (if ever) is the local scratch purged, and on what policy? | retention unknown; scratch assumed transient, archive assumed durable | not yet | [Supplies](supplies.md) |
| DATA-3 | `Blocks-go-live` | Which Globus collection(s) or endpoints does the DAQ write to, and which do users pull from? Are they the same? | one Globus collection (Sojourner) for user pull; the DAQ write target is unconfirmed | not yet | [Supplies](supplies.md) |
| DATA-4 | `Blocks-go-live` | During and after a beamtime, does a dataset normally exist in several locations at once (for example scratch and archive simultaneously), or move from one to the next and get deleted from the source? | assumed multi-home: scratch and archive coexist for a while | not yet | [Datasets](datasets.md) |
| DATA-5 | `Blocks-go-live` | What kicks off a transfer between locations, and is it a continuous sync running for the whole beamtime or a one-shot per scan / per beamtime? At what granularity (per file, per scan, per proposal)? | assumed a continuous DAQ sync started at beamtime open (DMagic `daq-start`) | not yet | [Datasets](datasets.md) |
| DATA-6 | `Blocks-go-live` | Is there one canonical "home" storage location that a beamtime's data always goes to first, that everything else derives from? | assumed a single default archive (Sojourner) | not yet | [Supplies](supplies.md) |
| DATA-7 | `Nice-to-have` | Do raw and reconstructed data share the same location and lifecycle, or are they handled differently (different tiers, retention, or transfer paths)? | assumed same location, parallel `<experiment>` and `<experiment>_rec` folders | not yet | [Datasets](datasets.md) |

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
| VIB-1 | `Nice-to-have` | Confirm the camera used for the vibration and flat-field stability measurements is the same FLIR Oryx (`ORX-10G-51S5M`, serial `19173710`) that serves as the microscope detector, run at a high frame rate (about 99 fps), and not a separate high-speed camera. item_070 reports that exact serial, which is why CORA reads it as the same unit. | the active FLIR Oryx (serial `19173710`) run fast; no separate high-speed camera | yes | [Procedures](procedures.md) |
| VIB-2 | `Nice-to-have` | Is baseline vibration measurement (the high-speed image-shift method) current recurring 2-BM practice, for example run at shakedown or after maintenance, or was item_070 a one-off study? This decides whether CORA registers a standing `vibration_baseline` technique or keeps a single historical record plus a caution. | kept as a Pending Procedure / Run / Dataset; recurring-vs-one-off unconfirmed | not yet | [Procedures](procedures.md) |
| VIB-3 | `Nice-to-have` | Is the multi-hour flat-field stability measurement (item_070 ran about 8 hours, 471 sets at 60 s intervals) a recurring monitoring activity, for example to track DMM stripe drift periodically, or a one-off study? Its written conclusion reads as guidance rather than a repeated run. | treated as a one-off study informing a flat-timing caution; recurring use unconfirmed | not yet | [Procedures](procedures.md) |
| VIB-4 | `Nice-to-have` | Is the 100 mA storage-ring current threshold (the `S-DCCT:CurrentM` cutoff that stopped the stability acquisition) a standing 2-BM acquisition gate applied to ordinary scans too, or specific to this study? If it is standing, CORA would register beam current as a beamline Supply with an availability threshold that ordinary runs could also gate on. | no ring-current Supply registered; 100 mA read as study-specific | not yet | [Supplies](supplies.md) |
| VIB-5 | `Nice-to-have` | What vibration level (and on which measurement) counts as too much, behind the caution that vibration rises after an air-handler shutdown, and which air handler(s) dominate? Is the building HVAC the main vibration source operators should watch? CORA needs this to give the Pending air-handler [caution](cautions.md) a real severity and text. | a vibration-after-air-handler-shutdown caution filed as Pending, with no threshold or named unit | not yet | [Cautions](cautions.md) |
| VIB-6 | `Nice-to-have` | Confirm the operational takeaway from the flat-field stability study, that flats should be acquired as close to scan time as possible, and whether there is a usable timing window (for example, flats stay good for up to N minutes during quiet periods). CORA would record this as a caution surfaced at run start. | flat-timing guidance noted from item_070; no specific window on file | not yet | [Cautions](cautions.md) |
| VIB-7 | `Nice-to-have` | For a vibration or stability measurement, which artifacts does 2-BM keep as the data of record: the raw image stack, the derived results file (for example `stripe_motion_results.npz`), or only the scalar outcomes (dominant frequencies, total drift)? This sets how many Datasets CORA records and how they are linked as derived data. | raw stack recorded as the producing Dataset; derived products linked as derived data, exact set unconfirmed | not yet | [Datasets](datasets.md) |

## Not on this page

Hardware CORA has deliberately not described yet (the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). It raises questions here only once CORA starts describing it. The `Mirror` is the exception that proves the rule: it is now a registered Asset ([Inventory](assets.md#inventory)), so it already raises questions here (`MIRROR-1`, `MODE-1`, `MODE-3`) even though its coating-stripe physics stay deferred to the beam-mode work.
