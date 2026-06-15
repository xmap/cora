# Open questions

*The open items CORA needs 2-BM staff to confirm. Only open items appear here.*

## What we need from you

Below are the facts we need you to confirm or correct about 2-BM hardware. Most you can answer from memory in a couple of minutes.

**How to reply:** open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one per answer or several together. Quote the item ID and write the answer in plain text, for example:

> HXP-1: m1 = X, m2 = Y, m3 = Z, m4 = Roll, m5 = Pitch, m6 = Yaw
> DET-1: sliding objective selector, positions in millimeters

You do not need to edit this file or know where it lives. If you do not use GitHub, just send the same thing (the item ID and your answer) to whoever shared this page with you.

**If you are not the beamline scientist:** a few rows name a different contact. Safety and interlocks: **PSS-1**. Facility utilities (gas, compressed air): **SUP-1**, **SUP-2**. If a row is really a controls/EPICS, network, or engineering question rather than yours, just route it to the right person or tell us who that is.

**Where to start:** the `Blocks-build` items below help us most, because your answer changes how we have to describe the device, not just a value we fill in. They are `STAGE-1`, `STAGE-7`, `STAGE-8`, `DET-1` through `DET-5`, and `DET-10`. If you only have five minutes, do these first. After that, `Blocks-go-live` items (including the safety item `PSS-1`) matter before CORA ever controls or observes hardware.

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
| DRIVE-4 | `Nice-to-have` | Exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The source page says "native Aerotech Ensemble" but does not name the box. | `unknown-pending-confirmation`; vendor known to be Aerotech | not yet | [Vendor catalog](assets.md#vendor-catalog-models) |
| DRIVE-5 | `Nice-to-have` | Model and serial of the stepper driving the Microscope objective selector? Our beamline docs name a Nanotec ST4118M1404-B (1.8 deg/step, 1.7 VDC, 1.4 A/phase) with a Heidenhain ERO 1420 encoder; please confirm and add the serial. CORA has no record of this controller yet, so this is optional for now. | likely Nanotec ST4118M1404-B; not yet registered | not yet | [Pending](assets.md#pending) |
| DRIVE-6 | `Nice-to-have` | Model and serial of the stepper driving the Microscope camera selector? Our docs name a Schunk LPTM 30 (200 steps/rev, 0.5 mm pitch); please confirm and add the serial. CORA has no record of this controller yet, so this is optional for now. | likely Schunk LPTM 30; not yet registered | not yet | [Pending](assets.md#pending) |

## The hexapod

CORA describes the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

### Can CORA move the hexapod yet?

Short answer: not yet, and that is expected.

CORA can describe the hexapod's six axes and how they connect, and it checks that those connections are valid. What it cannot do yet is send a "move the sample to this position" command. Moving a hexapod means turning one target pose into six coordinated leg movements, and that math (the kinematics solver) already runs inside the hexapod's own controller. CORA just needs a live connection to that controller so it can hand over a pose and read back where the stage ended up. That connection comes with a running beamline, so it is deferred until the system is stood up. Until then the six axes are described and the wiring is validated, but no motion command will execute. The questions below (`HXP-3` to `HXP-5`) are what that connection needs, and `HXP-1` is a question you can answer right now.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-1 | `Blocks-go-live` | Which EPICS channel (`2bmHXP:m1` through `m6`) is which axis? Our docs suggest `m1` = X, `m2` = Y, `m3` = Z (translations) and `m4`, `m5`, `m6` are the three rotations (`m3` and `m6` not user-exposed). Please confirm each channel, and which rotation (Roll, Pitch, Yaw) each of `m4` / `m5` / `m6` is (see HXP-2 for the naming). | suggested: m1=X, m2=Y, m3=Z, m4/m5/m6 the rotations | not yet | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-3 | `Blocks-go-live` | What is the hexapod's motion solver called, and where does it run? | `2bmHXP`, an EPICS soft IOC | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-4 | `Blocks-go-live` | What version of that solver is in use? | `1.0.0` placeholder | not yet | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-5 | `Blocks-go-live` | How should CORA talk to it (an EPICS soft-IOC record, a controller API, or something else)? | EPICS soft-IOC record | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |

## Sample stages

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| STAGE-1 | `Blocks-build` | Is `LaminographyPitch` (the Kohzu SA16A-RM goniometer in the source page) the SAME physical thing as the hexapod's Pitch axis, or a SEPARATE stage mounted on the hexapod? Your answer decides whether CORA describes one device or two. | treated as the hexapod's Pitch axis | yes | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| STAGE-2 | `Nice-to-have` | Full part number and datasheet for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | Full part number and datasheet for the Aerotech ABS250MP-M-AS rotary stage (`Rotary`)? | `Aerotech ABS250MP-M-AS`, no datasheet on file | yes | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABS250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the source). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABS250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) | one installed (`ABS250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| STAGE-7 | `Blocks-build` | We are describing the optical tables (the heavy support tables the equipment sits on). Is it right to describe all three: the sample table (the four motors `2bmb:m24` Y, `2bmb:m20` Z, `2bmb:m21` upstream-X, `2bmb:m22` downstream-X under the hexapod), the detector optical table (six axes on record `2bmb:table3`: three linear X/Y/Z plus three tilts), and the mirror optical table (record `Dma:table1`)? Or should the mirror table, which you flagged as present but not used, be left out for now? | all three tables described, as a best guess | yes | [Inventory](assets.md#inventory) |
| STAGE-8 | `Blocks-build` | Those tables have different axes (the sample table is plain motion with four motors; the detector table is six axes including tilts on a combined `table3` record). We are treating them as one kind of device where the axis list is just a per-table detail. Is that right, or are they different enough to be separate kinds? (You raised this as "two tables with a different degree of freedom".) | one kind of device (`Table` family); the axis list is a per-table detail | yes | [Family settings schemas](assets.md#family-settings-schemas) |
| STAGE-9 | `Blocks-go-live` | On the detector optical table's three tilt axes (`2bmb:table3.AX` / `.AY` / `.AZ`): which is roll, which is pitch, which is yaw? The components-page legend and the detector Z-rail alignment procedure disagree, so CORA has left the naming open and uses the raw `AX` / `AY` / `AZ` labels for now. | left unmapped; raw `AX` / `AY` / `AZ` | not yet | [Pending](assets.md#pending) |

## The Microscope detector

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-1 | `Blocks-build` | Is the objective changer a rotating turret, or a sliding (translating) selector? This sets whether its positions are degrees or millimeters. Our control software and beamline docs describe a ball-screw selector that translates the chosen lens onto the beam (about 2 mm/rev, about 60 mm of travel, positions in mm), which would make it a sliding selector. Please confirm rotating or sliding. | rotating (degrees) | yes | [Microscope](equipment/microscope.md) |
| DET-2 | `Blocks-build` | Does CORA drive the focus stage directly, or does the detector's own IOC move it behind the scenes? Our reading of the Microscope IOC code is that the IOC sets focus per objective and stores/restores focus on each camera switch, which would put the focus path on the IOC side. There also appear to be three per-objective focus motors (`2bmb:m2` / `m3` / `m4`) separate from the `2bmbAERO:m1` microscope-body Z stage. Please confirm who owns focus and how many focus motors there are. | CORA drives it | yes | [Microscope](equipment/microscope.md) |
| DET-3 | `Blocks-build` | How are cameras selected: a single fixed bay, or is there a selection stage? Our docs show a Schunk LPTM 30 folding-mirror selector on `2bmb:m5` with two positions (`CameraSelect` Pos. 0 / Pos. 1), which would mean a two-position selection stage. Please confirm. | single bay, no selection stage | yes | [Microscope](equipment/microscope.md) |
| DET-4 | `Blocks-build` | How does the camera bay move, if at all: fixed, or is there a rotation stage? We looked and found only per-camera calibration offsets, not a rotation-stage channel, which is consistent with "fixed." Please confirm there is no camera-rotation stage. | fixed, no rotation stage | yes | [Microscope](equipment/microscope.md) |
| DET-5 | `Blocks-build` | Is there a second active FLIR Oryx camera bay (`2bmSP2:`), or is 2-BM genuinely single-camera? Our docs show a second FLIR Oryx (31 MP, `2bmSP2:`) as camera 1 on a dual-port system, but CORA describes single-camera for now. Is the second bay live at 2-BM, or offline? | single-camera; any second Oryx is offline | yes | [Microscope](equipment/microscope.md) |
| DET-6 | `Nice-to-have` | Who actually makes the objective-selector motor, and its part number? Our docs point to a third-party Nanotec ST4118M1404-B stepper (with a Heidenhain ERO 1420 encoder) inside the Optique Peter housing, rather than an Optique Peter motor. Please confirm. | assumed Optique Peter; docs suggest Nanotec ST4118M1404-B | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-7 | `Nice-to-have` | The exact part number for each installed objective (with NA, focal length, working distance)? Our docs call the family Mitutoyo MPLAPO (not Plan-Apo-NIR) and the installed set 10x / 5x or 2x / 1.1x; please give one part number per magnification, and confirm the middle magnification (see DET-9). | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-8 | `Blocks-go-live` | The FLIR Oryx's max frame rate, sensor kind, and readout mode (rolling vs global), plus its part number for the datasheet? Our docs give part number ORX-10G-51S5M-C and a max frame rate of about 162 fps; please confirm those and add the sensor kind (CMOS?) and readout mode. | sensor size / pixel / bit-depth recorded; docs suggest ORX-10G-51S5M-C, about 162 fps | not yet | [Settings](assets.md#settings) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); docs suggest 5x installed | yes | [Microscope](equipment/microscope.md) |
| DET-10 | `Blocks-build` | The Aerotech PRO225SL-1000 stage on `2bmbAERO:m1`: CORA currently describes it as the microscope focus stage (`Focus`). The components page calls it the detector Z stage, the sample-to-detector throw (propagation distance). Is that one stage or two, and which job does `2bmbAERO:m1` do? This decides what the detector Z-rail alignment procedure targets. | one stage, described as the microscope focus (`Focus`) | yes | [Microscope](equipment/microscope.md) |

## Timing

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq timing box's gateware (bitstream) version and serial number? CORA already has its identity (a Xilinx Zynq board on the `2bmbMZ1:SG:` IOC); we just need the loaded gateware version to finalize what CORA records. Optional for now. | identity known (`2bmbMZ1:SG:`); gateware version not yet recorded | not yet | [Pending](assets.md#pending) |

## Beam path and front end

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| BEAM-1 | `Blocks-go-live` | Is the beam shutter already open when a tomography run starts, or does the operator (or the scan software) open it as part of run startup? Our reading of the 2-BM tomoscan code is that the scan opens the front-end shutter at the start of each run; please confirm whether that, an operator step, or a pre-run caution is the real sequence. | open before the run (handled by commissioning / a pre-run caution) | yes | [Procedures](procedures.md) |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | not yet | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | The canonical APS drawing reference for the B-station safety shutter (`StationShutter`)? | shutter modelled; no drawing on file | not yet | [Engineering drawings](assets.md#engineering-drawings) |
| BEAM-4 | `Nice-to-have` | Is the beamline layout drawing `ICMS A342-RT1000` Rev 02 still the current revision? Our docs show Rev 02 dated 27 May 2026; please confirm it has not been superseded. | Rev 02 (27 May 2026) assumed current | yes | [2-BM index](index.md) |
| BEAM-5 | `Blocks-go-live` | We propose two names for the front-end slits: `ConditioningSlit` for the A-station L3 four-blade slit (`2bma:m13`-`m16`), and `SampleSlit` for the B-station slit (`2bma:m9`-`m12`). Do those names match how you refer to them, and is the four-blade aperture (H size and centre, V size and centre) structure right? If you have them: the A-station position along the beam, and the slit-position tolerances. | names `ConditioningSlit` and `SampleSlit`, both four-blade slits; B-station at z = 50500 mm | yes | [Pending](assets.md#pending) |

## Safety interlocks

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| PSS-1 | `Blocks-go-live` | Does the APS Personnel Safety System expose hutch-search and shutter-permit status as readable Channel Access PVs? We found candidate PVs in an APS 2-BM status screen: hutch searched `PA:02BM:STA_A_SRCHD_TO_B` and `PA:02BM:STA_B_SRCHD_TO_B`, beam permission `PA:02BM:STA_A_BEAMREADY_PL`, front-end shutter `PA:02BM:STA_A_FES_OPEN_PL`, B-station shutter `PA:02BM:STA_B_SBS_OPEN_PL`. Are these the right PVs for an external read-only observer (the people-interlock `PA:` reflections, as opposed to BLEPS equipment-protection tags)? CORA needs this so it can decide whether to start its own data-collection run, by reading the hutch-permit status. To be clear: CORA only reads the permit. It never drives, holds, or releases the PSS permit or the beam; the PSS remains the sole interlock. Confirming the PV names does not put CORA into the safety chain. Confirmer: APS safety-systems / PSS contact. | candidate `PA:02BM:` PVs identified (listed at left); names unconfirmed; confirmer: APS safety-systems / PSS contact | not yet | [Enclosures](enclosures.md) |

## Supplies

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? Confirmer: facility utilities. | a gas supply exists; mixture unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? Confirmer: facility utilities. | air available; specs unknown; confirmer: facility utilities | not yet | [Supplies](supplies.md) |

## Not on this page

Hardware CORA has deliberately not described yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). Those raise their own questions here only once CORA starts describing them.
