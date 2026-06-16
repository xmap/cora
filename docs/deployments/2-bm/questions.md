# Open questions

*The open items CORA needs 2-BM staff to confirm. Only open items appear here.*

## What we need from you

Below are the facts we need you to confirm or correct about 2-BM hardware. Most you can answer from memory in a couple of minutes.

**How to reply:** open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one per answer or several together. Quote the item ID and write the answer in plain text, for example:

> HXP-1: m1 = X, m2 = Y, m3 = Z, m4 = Roll, m5 = Pitch, m6 = Yaw
> DET-1: sliding objective selector, positions in millimeters

You do not need to edit this file or know where it lives. If you do not use GitHub, just send the same thing (the item ID and your answer) to whoever shared this page with you.

**If you are not the beamline scientist:** a few rows name a different contact. Safety and interlocks: **PSS-1**. Facility utilities (gas, compressed air): **SUP-1**, **SUP-2**. If a row is really a controls/EPICS, network, or engineering question rather than yours, just route it to the right person or tell us who that is.

**Where to start:** the six `Blocks-build` items below help us most, because your answer changes how we have to describe the device, not just a value we fill in. They are `STAGE-1`, `DET-1`, `DET-2`, `DET-3`, `DET-4`, `DET-5`. If you only have five minutes, do these first. After that, `Blocks-go-live` items matter before CORA ever controls or observes hardware: notably the safety item `PSS-1`, and `DET-10` so CORA and the MCTOptics server do not end up commanding the focus motors at the same time.

## How this page works

CORA keeps a structured description of each device: its axes, its identity, and how the parts connect. Some of your answers just fill in a value, like a serial number. Others change the structure itself, like whether the objective selector rotates or slides. We mark the second kind `Blocks-build`.

Where we do not have your answer yet, CORA fills in a clearly-marked temporary guess so the description work can continue. We never use a guessed value to move or control any hardware. The one exception to "a guess is fine for now" is a `Blocks-build` item: if it is still open when we finalize the description it affects, that is a hard stop, and we have to wait for your answer before we can proceed.

**Priority** is one of:

- `Blocks-build`: CORA cannot describe the device correctly until we know this. Your answer changes the structure of the description.
- `Blocks-go-live`: a temporary guess is fine for the description, but the real value is needed before CORA controls or observes the hardware.
- `Nice-to-have`: extra detail for the record and for datasheets.

**The columns:**

- *CORA assumes* is our current temporary guess (or a note that nothing is recorded yet). Where it is a real guess, please confirm or correct it. Where it says something like `unknown-pending-confirmation` or `not yet registered`, it just means we have no value yet.
- *Resolves* is only for us: it shows where your answer gets recorded once confirmed. You do not need to click it to reply.

When an item is confirmed, we record the value, replace the temporary guess, and delete the row from this page. The deletion is intentional and is kept in our change history, along with who confirmed it and, if it overturned an earlier value, why. So this page always shows only what is still open; its length is just the count of things we are still waiting on. Each ID is permanent: once an item is removed, that ID is never reused for a different question. IDs run per section.

## Drives and controllers

CORA records each controller box's identity (serial, firmware) so it can later answer questions like "did the controller firmware change between Monday's scan and Friday's?". These are temporary guesses today.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | `Blocks-go-live` | Serial numbers for the five motion-controller boxes (drives for the rotary, the hexapod, the focus stage, and the two OMS VME58 crate cards)? | `unknown-pending-confirmation` | [Settings](assets.md#settings) |
| DRIVE-2 | `Blocks-go-live` | Firmware versions for those same five boxes? | `unknown-pending-confirmation` | [Settings](assets.md#settings) |
| DRIVE-3 | `Nice-to-have` | Are the Aerotech drives network-attached, and if so their IP addresses? | left blank (assumed not needed) | [Settings](assets.md#settings) |
| DRIVE-4 | `Nice-to-have` | Exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The source page says "native Aerotech Ensemble" but does not name the box. | `unknown-pending-confirmation`; vendor known to be Aerotech | [Vendor catalog](assets.md#vendor-catalog-models) |
| DRIVE-5 | `Nice-to-have` | Model and serial of the Nanotec ST4118 stepper driving the Microscope objective selector? CORA has no record of this controller class yet, so this answer is optional for now; send it when you can. | not yet registered | [Pending](assets.md#pending) |
| DRIVE-6 | `Nice-to-have` | Model and serial of the Schunk LPTM 30 stepper driving the Microscope camera selector? CORA has no record of this controller class yet, so this answer is optional for now; send it when you can. | not yet registered | [Pending](assets.md#pending) |

## The hexapod

CORA describes the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

### Can CORA move the hexapod yet?

Not the real stage yet, but closer than "wait for the beamline" suggests.

The hard part of moving a hexapod, turning one target position into six coordinated leg movements, is already done for us inside the Aerotech controller. CORA does not compute it and never will; its job is only to hand the controller a target and read back where the stage ended up.

Two things remain:

1. A small piece of CORA software (a connector) that hands the controller a target and reads the result. This is ours to build, and we can build and rehearse it against a simulated controller before the beamline is powered on. Rehearsed runs are tagged simulated, so their data can never be mistaken for real measurements.
2. A live link to the real controller, needed only for moving the real stage. That one comes with a running beamline.

`HXP-3` to `HXP-5` shape the connector; `HXP-1` (which channel is which axis) you can answer now.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| HXP-1 | `Blocks-go-live` | Which EPICS channel (`2bmHXP:m1` through `m6`) is which axis? The source page names two rotational channels (`m4`, `m5`); the full six-channel map is unconfirmed. | not asserted in the docs | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-3 | `Blocks-go-live` | What is the hexapod's motion solver called, and where does it run? | `2bmHXP`, an EPICS soft IOC | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-4 | `Blocks-go-live` | What version of that solver is in use? | `1.0.0` placeholder | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-5 | `Blocks-go-live` | What interface(s) does the solver expose for handing it a target pose and reading back where the stage ended up: an EPICS soft-IOC record set, a controller or vendor API, both, or something else? List what is available; CORA will choose how it connects. | an EPICS soft-IOC record set | [Hexapod DoF model](assets.md#hexapod-dof-model) |

## Sample stages

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | `Blocks-build` | Is `LaminographyPitch` (the Kohzu SA16A-RM goniometer in the source page) the SAME physical thing as the hexapod's Pitch axis, or a SEPARATE stage mounted on the hexapod? Your answer decides whether CORA describes one device or two. | treated as the hexapod's Pitch axis | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| STAGE-2 | `Nice-to-have` | Full part number and datasheet for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? | `Kohzu CYAT-070`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | Full part number and datasheet for the Aerotech ABS250MP-M-AS rotary stage (`Rotary`)? | `Aerotech ABS250MP-M-AS`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | [Procedures](procedures.md) |

## The Microscope detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | `Blocks-build` | Is the lens turret a rotating turret, or a sliding (translating) objective selector? This sets whether its positions are degrees or millimeters. | rotating (degrees) | [Microscope](equipment/microscope.md) |
| DET-2 | `Blocks-build` | How many focus motors does the microscope have, and how are they arranged: a single shared focus stage (we believe the `2bmbAERO:m1` Z rail), or one fine-focus motor per objective (we believe `2bmb:m2`, `m3`, `m4`) plus a shared coarse Z stage? Your answer decides whether CORA models one focus axis or a per-lens focus group. | single shared focus stage; per-lens differences held as software offsets | [Microscope](equipment/microscope.md) |
| DET-3 | `Blocks-build` | How are cameras selected: a single fixed bay, or is there a selection stage? | single bay, no selection stage | [Microscope](equipment/microscope.md) |
| DET-4 | `Blocks-build` | How does the camera bay move, if at all: fixed, or is there a rotation stage? | fixed, no rotation stage | [Microscope](equipment/microscope.md) |
| DET-5 | `Blocks-build` | Is there a second active FLIR Oryx camera bay (`2bmSP2:`), or is 2-BM genuinely single-camera? | single-camera; any second Oryx is offline | [Microscope](equipment/microscope.md) |
| DET-6 | `Nice-to-have` | Who actually makes the lens-turret motor (Optique Peter, or a third-party motor inside the housing), and its part number? | assumed Optique Peter | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-7 | `Nice-to-have` | The three distinct Mitutoyo part numbers, one per magnification (10x / 2x / 1.1x)? Today all three share one catalog row. | one `Plan-Apo-NIR` family row | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-8 | `Blocks-go-live` | The FLIR Oryx's max frame rate, sensor kind, and readout mode (rolling vs global), plus its part number for the datasheet? CORA needs these camera values and they are currently blank. | only sensor size / pixel / bit-depth recorded | [Settings](assets.md#settings) |
| DET-9 | `Nice-to-have` | The measured magnification of the 2x Mitutoyo objective at 25 keV? The current 2.0x is nominal, pending re-measurement. | 2.0x nominal (provisional) | [Microscope](equipment/microscope.md) |
| DET-10 | `Blocks-go-live` | When an objective is selected, does the MCTOptics server automatically move the focus to the stored position for that lens, or is focus set as a separate explicit step? And is focus ever moved mid-scan (continuous autofocus), or only at lens-change setup? CORA plans to drive focus itself with a full audit trail, so it needs to know what moves it today to avoid two systems commanding the same motor. | MCTOptics applies a stored focus per lens at lens change; focus is not moved mid-scan | [Microscope](equipment/microscope.md) |

## Timing

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq timing box's identity and gateware (bitstream) version, so we can finalize the list of settings CORA records for it? CORA has no record of this device yet, so this answer is optional for now. | draft schema, not yet registered | [Pending](assets.md#pending) |

## Beam path and front end

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BEAM-1 | `Blocks-go-live` | Is the beam shutter already open when a tomography run starts, or does the operator open it as part of run startup? | open before the run (handled by commissioning / a pre-run caution) | [Procedures](procedures.md) |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | The canonical APS drawing reference for the B-station safety shutter (`StationShutter`)? | shutter modelled; no drawing on file | [Engineering drawings](assets.md#engineering-drawings) |
| BEAM-4 | `Nice-to-have` | Is the beamline layout drawing `ICMS A342-RT1000` Rev 02 (May 2026) still the current revision? | assumed current | [2-BM index](index.md) |

## Safety interlocks

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | `Blocks-go-live` | Does the APS Personnel Safety System expose hutch-search and shutter-permit status as readable Channel Access PVs? If so, what are the PV names; if not, how is that status readable today by a read-only outside system: a different protocol (for example P4P or Tango), a relay or hardwired output, a gateway, or only by a request to PSS engineering? CORA needs this so it can decide whether to start its own data-collection run, by reading the hutch-permit status. To be clear: CORA only reads the permit. It never drives, holds, or releases the PSS permit or the beam; the PSS remains the sole interlock. Confirming the PV names does not put CORA into the safety chain. Confirmer: APS safety-systems / PSS contact. | no PV names known; confirmer: APS safety-systems / PSS contact | [Enclosures](enclosures.md) |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? Confirmer: facility utilities. | a gas supply exists; mixture unknown; confirmer: facility utilities | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? Confirmer: facility utilities. | air available; specs unknown; confirmer: facility utilities | [Supplies](supplies.md) |

## Data storage and transfer

CORA records where each dataset's bytes live and how they move between storage locations, so it can later answer "where is this scan's data now?" and verify that copies are intact. Our current guesses come from the existing DMagic setup; please confirm or correct. Confirmer: the beamline's data-management / controls contact, these may not be beamline-scientist questions.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DATA-1 | `Blocks-go-live` | Where does 2-BM data physically land, and through what stages, in order? For example local scratch on the acquisition / reconstruction host, then a DM / Sojourner archive, then tape. Please name the real systems and paths. | raw under `/data3/2BM/<experiment>/`, reconstructed under `<experiment>_rec/`, transferred to APS Data Management ("Sojourner"); the tiers and their order are unconfirmed | [Supplies](supplies.md) |
| DATA-2 | `Blocks-go-live` | For each storage location: is it operator-visible, and is it permanent or auto-deleted? In particular, when (if ever) is the local scratch purged, and on what policy? | retention unknown; scratch assumed transient, archive assumed durable | [Supplies](supplies.md) |
| DATA-3 | `Blocks-go-live` | Which Globus collection(s) or endpoints does the DAQ write to, and which do users pull from? Are they the same? | one Globus collection (Sojourner) for user pull; the DAQ write target is unconfirmed | [Supplies](supplies.md) |
| DATA-4 | `Blocks-go-live` | During and after a beamtime, does a dataset normally exist in several locations at once (for example scratch and archive simultaneously), or move from one to the next and get deleted from the source? | assumed multi-home: scratch and archive coexist for a while | [Datasets](datasets.md) |
| DATA-5 | `Blocks-go-live` | What kicks off a transfer between locations, and is it a continuous sync running for the whole beamtime or a one-shot per scan / per beamtime? At what granularity (per file, per scan, per proposal)? | assumed a continuous DAQ sync started at beamtime open (DMagic `daq-start`) | [Datasets](datasets.md) |
| DATA-6 | `Blocks-go-live` | Is there one canonical "home" storage location that a beamtime's data always goes to first, that everything else derives from? | assumed a single default archive (Sojourner) | [Supplies](supplies.md) |
| DATA-7 | `Nice-to-have` | Do raw and reconstructed data share the same location and lifecycle, or are they handled differently (different tiers, retention, or transfer paths)? | assumed same location, parallel `<experiment>` and `<experiment>_rec` folders | [Datasets](datasets.md) |

## Proposals, users and scheduling

CORA will later read proposal and user information from the APS scheduling system (the same `beam-api` / DMagic data the beamline already uses), so it can label each run with its proposal and notify the right people. None of these block today's work; they help us get the design right before we build it. Confirmer: the beamline scientist, except SCHED-3 (APS User Office / data-management contact).

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCHED-1 | `Nice-to-have` | Once a user group is on-site for their beamtime, does APS ever move their scheduled time window (earlier or later) before they start, or do time changes only happen before they arrive? | time changes happen only before arrival | [2-BM index](index.md) |
| SCHED-2 | `Nice-to-have` | Is the beamline staff contact (local contact) for a beamtime listed among that experiment's users in the scheduling system, or tracked separately as a beamline-side assignment? | listed as one of the beamtime's people | [2-BM index](index.md) |
| SCHED-3 | `Nice-to-have` | Are APS badge numbers ever reused or reassigned to a different person over time, or is a badge number stable for life per person? And under APS data governance, is a badge number classified as personal data subject to deletion on request? Confirmer: APS User Office / data-management contact. | badge stable per person; classified as deletable personal data | [2-BM index](index.md) |

## Not on this page

Hardware CORA has deliberately not described yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). Those raise their own questions here only once CORA starts describing them.
