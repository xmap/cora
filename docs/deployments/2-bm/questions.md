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

The sample hexapod's six degrees of freedom are described as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |

### Rebooting a stuck hexapod

Recovery from a controller lock-up is the [`hexapod_reboot` recipe](recipes.md), read from the authoritative script [`decarlof/2bmb-bin/hexapod_reboot.py`](https://github.com/decarlof/2bmb-bin/blob/HEAD/hexapod_reboot.py). Confirming that script is the current production copy (HXP-7) settles HXP-3, HXP-4, and HXP-6 at once; the only value not in the repo is the deployment PDU secret (HXP-5).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-3 | `Nice-to-have` | Confirm the enable / force-enable PVs are still current. | `2bmHXP:HexapodAllEnabled.VAL` (read), `2bmHXP:EnableWork.PROC` (force-enable) | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-4 | `Nice-to-have` | Confirm the IOC stop / start scripts and host. | `hexapod_IOC_stop.sh` / `hexapod_IOC.sh`, IOC host `arcturus` (user `2bmb`) | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-5 | `Blocks-go-live` | Which of the two PDUs (`a` default, or `b`) powers the hexapod, and its IP address? The PDU type, the HTTP endpoints, and the outlet are known from the script; only the choice and IP live in `~/access.json`, not the repo. | NetBooter over HTTP (`/cmd.cgi?rly=N`, `/status.xml`), outlet 5; PDU `a`, IP unknown | partly (type / endpoints / outlet known; PDU choice + IP not) | [Recipes](recipes.md) |
| HXP-6 | `Nice-to-have` | Confirm the reboot timings are the current operating values. | 10 s off-wait, 30 s on-wait, 10 s IOC settle, 180 s enable poll at 1 s intervals (script defaults) | yes, from the reboot script | [Recipes](recipes.md) |
| HXP-7 | `Blocks-go-live` | Is the public [`decarlof/2bmb-bin`](https://github.com/decarlof/2bmb-bin) repo (and specifically `hexapod_reboot.py`) the current production version, or is there a newer or internal copy we should track instead? CORA read the reboot records from it, so a yes resolves the "confirm current" on HXP-3, HXP-4, and HXP-6 at once; it is also the operational-scripts source for the IOC start/stop and energy scripts. | `decarlof/2bmb-bin` is current and authoritative | not yet | [Recipes](recipes.md) |

## Sample stages

These rows confirm vendor models, datasheets, and travel limits for the sample-side stages.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | A datasheet PDF for the Aerotech ABRS-250MP-M-AS rotary stage (`Rotary`)? The vendor engineering drawing (630C2125) is now on file (#156); a datasheet PDF would still be useful. | `Aerotech ABRS-250MP-M-AS`, vendor drawing on file, no datasheet PDF yet | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABRS-250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the source). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABRS-250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) | one installed (`ABRS-250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](assets.md#vendor-catalog-models) |

## The Microscope detector

Objectives and the turret selector on the Optique Peter microscope. Objectives are swappable, so several rows confirm what is mounted now.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); docs suggest 5x installed | yes | [Microscope](equipment/microscope.md) |
| DET-11 | `Blocks-go-live` | The objective turret selector (`2bmb:m1`, Nanotec stepper): for each objective (10x, 2x, 1.1x), the physical slot order and the turret motor position that brings it into the beam? CORA models the selector as a discrete index axis (commanded slot index -> saved turret position), but the slot order and positions it carries today are placeholders. | placeholder slot order + positions; modelled as a discrete index axis | yes | [Microscope](equipment/microscope.md) |

## Timing

Only the softGlueZynq timing box's gateware (bitstream) version is still open.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq's gateware (bitstream) version? The box itself is identified on the components page (a Xilinx Zynq SoC on a MicroZed carrier, EPICS prefix `2bmbMZ1:SG:`); only the bitstream version is missing. Optional for now. | registered as a `TimingController` Asset; bitstream version still a placeholder | yes | [Settings](assets.md#settings) |

## Beam path and front end

Two rows cover the front-end windows and the B-station safety shutter.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | not yet | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | Is there a canonical APS drawing for the B-station safety shutter (`StationShutter`) beyond its RSS tag (`02-BM-A-P-01`)? | shutter modelled; only the RSS tag on file | not yet | [Engineering drawings](assets.md#engineering-drawings) |

## Energy and the optics

On an energy change the DMM monochromator, its Bragg arms, and the tracking slits move together to saved per-energy positions. These items supply those saved values and confirm how they are driven.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ENERGY-1 | `Nice-to-have` | The real saved per-energy positions (the `store_0` table) for the energy-driven DMM axes: the Bragg arms (`dmm_us_arm` / `dmm_ds_arm` = `2bma:m30` / `2bma:m31`) and the M2 vertical offset (`dmm_m2_y` = `2bma:m32`)? CORA models each as a continuous curve, but the positions it carries today are placeholders. | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-2 | `Nice-to-have` | The matching per-energy saved positions for the B-station sample-slit vertical pair (`b_slit_top` / `b_slit_bot` = `2bma:m9` / `2bma:m10`) that tracks the beam walk? (The mirror is held constant in Mono mode, so it gets no Mono energy curve; in Pink the coating stripe IS swept per energy, see MODE-3.) | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-3 | `Nice-to-have` | Does the energy-change IOC drive the Bragg-arm angles from a saved per-energy table, or compute them from the Bragg geometry? This decides whether CORA keeps the arms as interpolated curves or models them as a computed relationship. | modelled as interpolated curves (provisional) | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-4 | `Nice-to-have` | We plan a "set energy" operation that accepts a free energy value (keV) and interpolates the saved per-energy curves, rather than only the exact configured energies, so an operator could request, say, 22 keV between two saved points. Is that acceptable and safe at 2-BM, i.e. is it OK to drive the optics to interpolated in-between positions that were not individually saved/validated, or must operation stay restricted to the exact configured energies? (Outside the saved range we refuse the move rather than clamp or extrapolate: the operator must request an in-range energy or extend the calibration.) | designed to accept free-keV with interpolation within the saved range, refusing out-of-range requests; pending your confirmation | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-5 | `Nice-to-have` | The DMM tank/alignment motors (`2bma:m25`-`m29`) are part of the energy-change coordinated move, but the components page does not say whether their saved positions actually differ per energy. Do they vary with energy, or are they re-asserted at fixed values? If they vary, CORA would add curves for them too. | in the coordinated move; per-energy variation unconfirmed; not modeled as curves | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |

## Filters and the mirror stripe

These rows cover the absorber-foil paddles and the mirror coating stripe.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| FOIL-1 | `Blocks-go-live` | We model the operational downstream absorber-foil paddle (`2bma:m18`) as a discrete selector with these slots and motor positions, read from the components page: `600 um Al` at 0, `150 um Al` at 26, `300 um C` at 53, `50 um C` at 80, `None` at 106. Are the slots, order, and positions correct, and is the position unit millimetres (the components page says the motor EGU is "consistent with mm" but does not state it outright)? | downstream paddle modelled with the positions above; unit assumed mm | yes | [Filter foil selection](assets.md#filter-foil-selection) |
| FOIL-2 | `Nice-to-have` | We treat the upstream paddle (`2bma:m17`) as bound-in-software but not in service (selecting it has no beam effect), so CORA does not model it as a live selector. Is that right, and should we ever expect it to come back into service? | upstream paddle not modelled as a live selector | yes | [Filter foil selection](assets.md#filter-foil-selection) |
| MIRROR-1 | `Nice-to-have` | We understand the mirror coating stripe (`2bma:m3`) is not a free discrete pick: in Mono mode it is held at one position, and in Pink mode it is swept per energy together with the optical-table X stages, managed by the energy-change IOC. We will model it with the beam-mode work, not as a filter-style index axis. Is that understanding correct, and is there a stripe-to-position mapping (which stripe sits at which `m3` position) we can record? | stripe selection deferred to the beam-mode work; energy/mode-dependent, no stripe->position map on file | not yet | [Filter foil selection](assets.md#filter-foil-selection) |

## Beam mode (Mono / Pink)

2-BM runs in two beam modes, and switching between them is a coordinated multi-device move CORA does not yet drive. These confirm the mode model and supply the values it would need.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| MODE-1 | `Nice-to-have` | We model 2-BM as running two beam modes: monochromatic (the DMM is inserted and Bragg-selects one energy: 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV) and pink (the DMM is driven out of the beam and the mirror coating stripe sets the high-energy cutoff: 30, 40, 50, 60 keV). Are the two modes and those two configured-energy menus correct and current? | two modes; Mono and Pink menus as listed | not yet | [Beam modes](assets.md#beam-modes-mono-pink) |
| MODE-2 | `Blocks-go-live` | How is the DMM physically inserted (Mono) and bypassed (Pink)? The components page implies the DMM Y motors drive to about -10 (out) for pink and 0 (in) for mono, with the Bragg arms parked when out, but we have no exact positions, PVs, or required switching sequence or interlock on file. What moves, to what positions, and in what order? | DMM Y to about -10 out / 0 in, Bragg arms parked in pink; exact positions and sequence unknown | not yet | [Beam modes](assets.md#beam-modes-mono-pink) |
| MODE-3 | `Blocks-go-live` | The pink-mode per-energy saved positions (the Pink half of `store_0`) for the swept mirror coating stripe (`2bma:m3`) and the mirror-table X stages (`2bma:m1` / `m4`)? The page gives a partial table (30 keV: m3 3.039, table X 8/8; 40: 13.0, 10/10; 50: 39.0, 10/10; 60: 49.0, 29/29 mm); please confirm and complete it, and (the data half of MIRROR-1) tell us which named stripe (a/b/c/d) sits at which `m3` position. | partial pink m3 and table-X positions from the page; stripe-to-label map not on file | not yet | [Beam modes](assets.md#beam-modes-mono-pink) |

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

## Not on this page

Hardware CORA has deliberately not described yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). It raises questions here only once CORA starts describing it.
