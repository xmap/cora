# Open questions

*The open items CORA needs 2-BM staff to confirm. Only open items appear here.*

## What we need from you

Below are the facts we need you to confirm or correct about 2-BM hardware. Most you can answer from memory in a couple of minutes.

**How to reply:** open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one per answer or several together. Quote the item ID and write the answer in plain text, for example:

> HXP-2: A = Roll, B = Pitch, C = Yaw
> DET-2: CORA drives the focus stage directly

You do not need to edit this file or know where it lives. If you do not use GitHub, just send the same thing (the item ID and your answer) to whoever shared this page with you.

**If you are not the beamline scientist:** a few rows name a different contact. Safety and interlocks: **PSS-1**. Facility utilities (gas, compressed air): **SUP-1**, **SUP-2**. If a row is really a controls/EPICS, network, or engineering question rather than yours, just route it to the right person or tell us who that is.

**Where to start:** the `Blocks-build` items below help us most, because your answer changes how we have to describe the device, not just a value we fill in. They are `DET-2`, `DET-10`, `STAGE-7`, and `STAGE-8`. If you only have a few minutes, do these first. After that, the `Blocks-go-live` items (including the safety item `PSS-1`) matter before CORA ever controls or observes hardware.

## How this page works

CORA keeps a structured description of each device: its axes, its identity, and how the parts connect. Some of your answers just fill in a value, like a serial number. Others change the structure itself, like whether the objective selector rotates or slides. We mark the second kind `Blocks-build`.

Where we do not have your answer yet, CORA fills in a clearly-marked temporary guess so the description work can continue. Sometimes that guess is already built into CORA's model (for example, we have described the optical tables as best we understand them); other times CORA is just holding a blank. The *Already done?* column tells you which. Either way, it is still an open question until you confirm, and we never use a guessed value to move or control any hardware. The one exception to "a guess is fine for now" is a `Blocks-build` item: if it is still open when we finalize the description it affects, that is a hard stop, and we have to wait for your answer before we can proceed.

**Priority** is one of:

- `Blocks-build`: CORA cannot describe the device correctly until we know this. Your answer changes the structure of the description.
- `Blocks-go-live`: a temporary guess is fine for the description, but the real value is needed before CORA controls or observes the hardware.
- `Nice-to-have`: extra detail for the record and for datasheets.

**The columns:**

- *CORA assumes* is our current temporary guess (or a note that nothing is recorded yet). Where it is a real guess, please confirm or correct it. Where it says something like `unknown-pending-confirmation` or `not yet registered`, it just means we have no value yet.
- *Already done?* tells you whether CORA has already built this guess into its model. **yes** means we made a best guess and it is live in CORA now, so your answer either confirms it or tells us to change something already there; **not yet** means CORA has no value recorded and is simply waiting for yours.
- *Resolves* is only for us: it shows where your answer gets recorded once confirmed. You do not need to click it to reply.

When an item is confirmed, we record the value, replace the temporary guess, and delete the row from this page. The deletion is intentional and is kept in our change history, along with who confirmed it and, if it overturned an earlier value, why. So this page always shows only what is still open; its length is just the count of things we are still waiting on. Each ID is permanent: once an item is removed, that ID is never reused for a different question. IDs run per section.

## Drives and controllers

CORA records each controller box's identity (serial, firmware) so it can later answer questions like "did the controller firmware change between Monday's scan and Friday's?". These are temporary guesses today.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DRIVE-1 | `Blocks-go-live` | Serial numbers for the five motion-controller boxes (drives for the rotary, the hexapod, the focus stage, and the two OMS VME58 crate cards)? | `unknown-pending-confirmation` | not yet | [Settings](assets.md#settings) |
| DRIVE-2 | `Blocks-go-live` | Firmware versions for those same five boxes? | `unknown-pending-confirmation` | not yet | [Settings](assets.md#settings) |
| DRIVE-3 | `Nice-to-have` | Are the Aerotech drives network-attached, and if so their IP addresses? | left blank (assumed not needed) | not yet | [Settings](assets.md#settings) |
| DRIVE-4 | `Nice-to-have` | Exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The rotary drive is named (Aerotech Ensemble HLE10-40-A-MXH); these two boxes are not. | `unknown-pending-confirmation`; vendor known to be Aerotech | not yet | [Vendor catalog](assets.md#vendor-catalog-models) |
| DRIVE-5 | `Nice-to-have` | Serial number of the Nanotec `ST4118M1404-B` stepper driving the Microscope objective selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DRIVE-6 | `Nice-to-have` | Serial number of the Schunk `LPTM 30` stepper driving the Microscope camera selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | [Pending](assets.md#pending) |

## The hexapod

CORA describes the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

### Can CORA move the hexapod yet?

Short answer: not yet, and that is expected.

CORA can describe the hexapod's six axes and how they connect, and it checks that those connections are valid. What it cannot do yet is send a "move the sample to this position" command. Moving a hexapod means turning one target pose into six coordinated leg movements, and that math (the kinematics solver) runs inside the hexapod's own Aerotech controller, reached through the `2bmHXP:` EPICS interface. CORA just needs a live connection to that controller so it can hand over a pose and read back where the stage ended up. That connection comes with a running beamline, so it is deferred until the system is stood up. Until then the six axes are described and the wiring is validated, but no motion command will execute. The channel map, the solver location, and how to talk to it are all now known from the beamline components page; the controller's firmware version comes in with the controller serial/firmware items (`DRIVE-2`). The rotation-name confirmation is below, followed by the reboot records the [`hexapod_reboot` recipe](recipes.md) needs.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |

### Rebooting a stuck hexapod

When the hexapod controller locks up, the recovery is a power-cycle ceremony: stop the IOC, power-cycle the controller's PDU outlet, restart the IOC, then confirm the axes re-enable. CORA has modelled it as the [`hexapod_reboot` recipe](recipes.md). The records below come from the external `2bmb-bin/hexapod_reboot.py` script (not in CORA, and not in the beamline descriptor or the published 2-BM procedures), so they need confirming before the recipe can run. CORA's assumed values are the script's; we just need a yes/no or a correction on each.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-3 | `Blocks-go-live` | The exact EPICS PVs the reboot uses to (a) read whether all hexapod axes are enabled and (b) force-enable them. Are these current? | `2bmHXP:HexapodAllEnabled.VAL` (read), `2bmHXP:EnableWork.PROC` (force-enable) | not yet | [Recipes](recipes.md) |
| HXP-4 | `Blocks-go-live` | How the hexapod IOC is stopped and restarted: which host runs it, and the exact stop / start commands. | scripts `hexapod_IOC_stop.sh` / `hexapod_IOC.sh` on host `arcturus` | not yet | [Recipes](recipes.md) |
| HXP-5 | `Blocks-go-live` | Which PDU powers the hexapod controller, how CORA talks to it, and which outlet is the hexapod. | NetBooter-style PDU over HTTP (`/cmd.cgi` to switch, `/status.xml` to read), outlet 4 | not yet | [Recipes](recipes.md) |
| HXP-6 | `Nice-to-have` | The reboot timings: how long to wait after powering the controller off, after powering it on, and how long to poll for "all enabled" before giving up. | 10 s off-settle, 10 s boot-settle, 180 s enable poll at 2 s intervals | not yet | [Recipes](recipes.md) |

## Sample stages

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | A datasheet PDF for the Aerotech ABS250MP-M-AS rotary stage (`Rotary`)? The part number and key specs are on the components page; we just have no datasheet on file. | `Aerotech ABS250MP-M-AS`, no datasheet on file | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABS250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the source). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABS250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) | one installed (`ABS250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-7 | `Blocks-build` | We are describing the optical tables (the heavy support tables the equipment sits on). Is it right to describe all three: the sample table (the four motors `2bmb:m24` Y, `2bmb:m20` Z, `2bmb:m21` upstream-X, `2bmb:m22` downstream-X under the hexapod), the detector optical table (six axes on record `2bmb:table3`: three linear X/Y/Z plus three tilts), and the mirror optical table (record `Dma:table1`)? Or should the mirror table, which you flagged as present but not used, be left out for now? | all three tables described, as a best guess | yes | [Inventory](assets.md#inventory) |
| STAGE-8 | `Blocks-build` | Those tables have different axes (the sample table is plain motion with four motors; the detector table is six axes including tilts on a combined `table3` record). We are treating them as one kind of device where the axis list is just a per-table detail. Is that right, or are they different enough to be separate kinds? (You raised this as "two tables with a different degree of freedom".) | one kind of device (`Table` family); the axis list is a per-table detail | yes | [Family settings schemas](assets.md#family-settings-schemas) |
| STAGE-9 | `Blocks-go-live` | On the detector optical table's three tilt axes (`2bmb:table3.AX` / `.AY` / `.AZ`): which is roll, which is pitch, which is yaw? The components-page legend and the detector Z-rail alignment procedure disagree, so CORA has left the naming open and uses the raw `AX` / `AY` / `AZ` labels for now. | left unmapped; raw `AX` / `AY` / `AZ` | not yet | [Pending](assets.md#pending) |

## The Microscope detector

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-2 | `Blocks-build` | Does CORA drive the focus stage directly, or does the detector's own IOC move it behind the scenes? This decides which side owns that control path. The motors are now mapped (shared Z rail `2bmbAERO:m1`, per-lens fine focus `2bmb:m2/m3/m4`); what we still need is who owns the control path. | CORA drives it | yes | [Microscope](equipment/microscope.md) |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DET-8 | `Blocks-go-live` | The FLIR Oryx's max frame rate, sensor kind, and readout mode (rolling vs global), plus its part number for the datasheet? Our docs give part number ORX-10G-51S5M-C and a max frame rate of about 162 fps; please confirm those and add the sensor kind (CMOS?) and readout mode. | sensor size / pixel / bit-depth recorded; docs suggest ORX-10G-51S5M-C, about 162 fps | not yet | [Settings](assets.md#settings) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); docs suggest 5x installed | yes | [Microscope](equipment/microscope.md) |
| DET-10 | `Blocks-build` | The Aerotech PRO225SL-1000 stage on `2bmbAERO:m1`: CORA currently describes it as the microscope focus stage (`Focus`). The components page calls it the detector Z stage, the sample-to-detector throw (propagation distance). Is that one stage or two, and which job does `2bmbAERO:m1` do? This decides what the detector Z-rail alignment procedure targets. | one stage, described as the microscope focus (`Focus`) | yes | [Microscope](equipment/microscope.md) |

## Timing

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq's gateware (bitstream) version? The box itself is identified on the components page (a Xilinx Zynq SoC on a MicroZed carrier, EPICS prefix `2bmbMZ1:SG:`); only the bitstream version is missing. Optional for now. | registered as a `TimingController` Asset; bitstream version still a placeholder | yes | [Settings](assets.md#settings) |

## Beam path and front end

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BEAM-1 | `Blocks-go-live` | Is the beam shutter already open when a tomography run starts, or does the operator open it as part of run startup? The TomoScan sequence does open and close the fast shutter during a scan; we want to confirm the state CORA's run-start should assume. | open before the run (handled by commissioning / a pre-run caution) | yes | [Procedures](procedures.md) |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | not yet | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | Is there a canonical APS drawing for the B-station safety shutter (`StationShutter`) beyond its RSS tag (`02-BM-A-P-01`)? | shutter modelled; only the RSS tag on file | not yet | [Engineering drawings](assets.md#engineering-drawings) |
| BEAM-5 | `Blocks-go-live` | We propose two names for the front-end slits: `ConditioningSlit` for the A-station L3 four-blade slit (`2bma:m13`-`m16`), and `SampleSlit` for the B-station slit (`2bma:m9`-`m12`). Do those names match how you refer to them, and is the four-blade aperture (H size and centre, V size and centre) structure right? If you have them: the A-station position along the beam, and the slit-position tolerances. | names `ConditioningSlit` and `SampleSlit`, both four-blade slits; B-station at z = 50500 mm | yes | [Inventory](assets.md#inventory) |

## Energy and the optics

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ENERGY-1 | `Nice-to-have` | The real saved per-energy positions (the `store_0` table) for the energy-driven DMM axes: the Bragg arms (`dmm_us_arm` / `dmm_ds_arm` = `2bma:m30` / `2bma:m31`) and the M2 vertical offset (`dmm_m2_y` = `2bma:m32`)? CORA models each as a continuous curve, but the positions it carries today are placeholders. | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-2 | `Nice-to-have` | The matching per-energy saved positions for the B-station sample-slit vertical pair (`b_slit_top` / `b_slit_bot` = `2bma:m9` / `2bma:m10`) that tracks the beam walk? (The mirror is held constant per the components page, so it gets no energy curve.) | provisional placeholder curves; real saved points not on file | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-3 | `Nice-to-have` | Does the energy-change IOC drive the Bragg-arm angles from a saved per-energy table, or compute them from the Bragg geometry? This decides whether CORA keeps the arms as interpolated curves or models them as a computed relationship. | modelled as interpolated curves (provisional) | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-4 | `Nice-to-have` | We plan a "set energy" operation that accepts a free energy value (keV) and interpolates the saved per-energy curves, rather than only the exact configured energies, so an operator could request, say, 22 keV between two saved points. Is that acceptable and safe at 2-BM, i.e. is it OK to drive the optics to interpolated in-between positions that were not individually saved/validated, or must operation stay restricted to the exact configured energies? (Outside the saved range we refuse the move rather than clamp or extrapolate: the operator must request an in-range energy or extend the calibration.) | designed to accept free-keV with interpolation within the saved range, refusing out-of-range requests; pending your confirmation | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |
| ENERGY-5 | `Nice-to-have` | The DMM tank/alignment motors (`2bma:m25`-`m29`) are part of the energy-change coordinated move, but the components page does not say whether their saved positions actually differ per energy. Do they vary with energy, or are they re-asserted at fixed values? If they vary, CORA would add curves for them too. | in the coordinated move; per-energy variation unconfirmed; not modeled as curves | not yet | [Energy-tracking optic axes](assets.md#energy-tracking-optic-axes) |

## Safety interlocks

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| PSS-1 | `Blocks-go-live` | Does the APS Personnel Safety System expose hutch-search and shutter-permit status as readable Channel Access PVs? We found candidate PVs in an APS 2-BM status screen: hutch searched `PA:02BM:STA_A_SRCHD_TO_B` and `PA:02BM:STA_B_SRCHD_TO_B`, beam permission `PA:02BM:STA_A_BEAMREADY_PL`, front-end shutter `PA:02BM:STA_A_FES_OPEN_PL`, B-station shutter `PA:02BM:STA_B_SBS_OPEN_PL`. Are these the right PVs for an external read-only observer (the people-interlock `PA:` reflections, as opposed to BLEPS equipment-protection tags)? CORA needs this so it can decide whether to start its own data-collection run, by reading the hutch-permit status. To be clear: CORA only reads the permit. It never drives, holds, or releases the PSS permit or the beam; the PSS remains the sole interlock. Confirming the PV names does not put CORA into the safety chain. Confirmer: APS safety-systems / PSS contact. | candidate `PA:02BM:` PVs identified (listed at left); names unconfirmed; confirmer: APS safety-systems / PSS contact | not yet | [Enclosures](enclosures.md) |

## Equipment protection (BLEPS)

BLEPS is the beamline equipment-protection interlock, and it is a different system from the PSS: BLEPS protects equipment, the PSS protects people. CORA does not model the BLEPS PLC logic. Following the same observation-only stance it uses for the PSS, CORA would observe BLEPS outcomes on axes it already has: utility faults become Supply status, device faults become an Asset's condition. None of these block today's model (CORA does not model BLEPS yet); they confirm the mapping before CORA ingests any BLEPS signal.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BLEPS-1 | `Nice-to-have` | Does this mapping match how 2-BM thinks about BLEPS faults: utility faults (vacuum via IP/IG/GV, cooling-water via the Flow channels) surface as Supply status (Degraded / Unavailable), and device faults (for example a mirror or optics trip) as that Asset's condition (Faulted / Degraded)? Which faults are utility-level versus tied to a specific device? | utility faults map to Supply, device faults to Asset condition; CORA never models the interlock matrix | not yet | [Supplies](supplies.md) |
| BLEPS-2 | `Nice-to-have` | Are the BLEPS fault / status signals readable as Channel Access PVs for an external observer (the BLEPS EPICS transfer table lists tags such as `A_Fault_Exists`, `GV1.Faulted`, the Flow channels, `FES.Permit` / `SBS.Permit`)? If readable, which PV maps to which utility or device; if not, the integration path. | readable via the BLEPS PLC EPICS interface; exact PV-to-Supply/Asset mapping unknown | not yet | [Supplies](supplies.md) |
| BLEPS-3 | `Nice-to-have` | Is there a beamline-level "BLEPS tripped / armed / recovering" state that operators act on as a whole, distinct from the individual utility and device faults, that should gate a run on its own? If yes, CORA adds a dedicated protection status; if no, CORA decomposes BLEPS onto Supply and Asset condition and adds no new aggregate. | no system-level state needed; decompose onto existing axes | not yet | [Supplies](supplies.md) |

## Supplies

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? Confirmer: facility utilities. | a gas supply exists; mixture unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? Confirmer: facility utilities. | air available; specs unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |

## Data storage and transfer

CORA records where each dataset's bytes live and how they move between storage locations, so it can later answer "where is this scan's data now?" and verify that copies are intact. Our current guesses come from the existing DMagic setup; please confirm or correct. Confirmer: the beamline's data-management / controls contact, these may not be beamline-scientist questions.

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

CORA will later read proposal and user information from the APS scheduling system (the same `beam-api` / DMagic data the beamline already uses), so it can label each run with its proposal and notify the right people. None of these block today's work; they help us get the design right before we build it. Confirmer: the beamline scientist, except SCHED-3 (APS User Office / data-management contact).

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SCHED-1 | `Nice-to-have` | Once a user group is on-site for their beamtime, does APS ever move their scheduled time window (earlier or later) before they start, or do time changes only happen before they arrive? | time changes happen only before arrival | not yet | [2-BM index](index.md) |
| SCHED-2 | `Nice-to-have` | Is the beamline staff contact (local contact) for a beamtime listed among that experiment's users in the scheduling system, or tracked separately as a beamline-side assignment? | listed as one of the beamtime's people | not yet | [2-BM index](index.md) |
| SCHED-3 | `Nice-to-have` | Are APS badge numbers ever reused or reassigned to a different person over time, or is a badge number stable for life per person? And under APS data governance, is a badge number classified as personal data subject to deletion on request? Confirmer: APS User Office / data-management contact. | badge stable per person; classified as deletable personal data | not yet | [2-BM index](index.md) |

## Not on this page

Hardware CORA has deliberately not described yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). Those raise their own questions here only once CORA starts describing them.
