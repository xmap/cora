# Open questions

*The open items CORA needs 2-BM staff to confirm. Only open items appear here.*

Nothing on this page blocks the model, with one exception. Where an answer is missing, CORA holds a clearly-marked placeholder and runs on it. The exception is a `Blocks-build` item: if one is still open when CORA locks the affected aggregate or descriptor, that is a gate failure, not a placeholder to run on. Each row is one question, what CORA assumed in the meantime, and where the answer will land once confirmed.

**To answer:** reply with the item ID (for example `HXP-3`) to the 2-BM beamline scientist (the default confirmer; a few rows name a more specific contact), or edit the row. When an item is confirmed, the value goes into the linked model doc (replacing its placeholder) and the row is deleted from this page; the commit that deletes it records who confirmed it and, if it overturned an earlier value, why. So this page always shows only what is still open, and its length is just the count of things we are still waiting on; git history is the record of what was settled and why.

**Priority** is one of: `Blocks-build` (CORA cannot model the device correctly until we know this), `Blocks-go-live` (a placeholder is fine for modelling, but the real value is needed before CORA controls hardware), `Nice-to-have` (provenance and datasheet enrichment). IDs are per-section and append-only: a retired ID is never reused.

**Start here (the `Blocks-build` items):** `STAGE-1`, `DET-1`, `DET-2`, `DET-3`, `DET-4`, `DET-5`. Each of these changes *what* CORA models, so an answer reshapes the model rather than just filling a blank.

## Drives and controllers

CORA records each controller box's identity (serial, firmware) so it can later answer questions like "did the controller firmware change between Monday's scan and Friday's?". These are placeholders today.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | `Blocks-go-live` | Serial numbers for the five motion-controller boxes (drives for the rotary, the hexapod, the focus stage, and the two OMS VME58 crate cards)? | `unknown-pending-confirmation` | [Settings](assets.md#settings) |
| DRIVE-2 | `Blocks-go-live` | Firmware versions for those same five boxes? | `unknown-pending-confirmation` | [Settings](assets.md#settings) |
| DRIVE-3 | `Nice-to-have` | Are the Aerotech drives network-attached, and if so their IP addresses? | left blank (assumed not needed) | [Settings](assets.md#settings) |
| DRIVE-4 | `Nice-to-have` | Exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The source page says "native Aerotech Ensemble" but does not name the box. | `unknown-pending-confirmation`; vendor known to be Aerotech | [Vendor catalog](assets.md#vendor-catalog-models) |
| DRIVE-5 | `Nice-to-have` | Model and serial of the Nanotec ST4118 stepper driving the MCTOptics objective selector? (6th controller class, not yet modelled.) | not yet registered | [Pending](assets.md#pending) |
| DRIVE-6 | `Nice-to-have` | Model and serial of the Schunk LPTM 30 stepper driving the MCTOptics camera selector? (7th controller class, not yet modelled.) | not yet registered | [Pending](assets.md#pending) |

## The hexapod

CORA models the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

### Can CORA move the hexapod yet?

Short answer: not yet, and that is expected.

CORA can describe the hexapod's six axes and how they connect, and it checks that those connections are valid. What it cannot do yet is send a "move the sample to this position" command. Moving a hexapod means turning one target pose into six coordinated leg movements, and that math (the kinematics solver) already runs inside the hexapod's own controller. CORA just needs a live connection to that controller so it can hand over a pose and read back where the stage ended up. That connection comes with a running beamline, so it is deferred until the system is stood up. Until then the six axes are modelled and the wiring is validated, but no motion command will execute. `HXP-3` to `HXP-5` are what that connection needs.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| HXP-1 | `Blocks-go-live` | Which EPICS channel (`2bmHXP:m1` through `m6`) is which axis? The source page names two rotational channels (`m4`, `m5`); the full six-channel map is unconfirmed. | not asserted in the docs | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-3 | `Blocks-go-live` | What is the hexapod's motion solver called, and where does it run? | `2bmHXP`, an EPICS soft IOC | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-4 | `Blocks-go-live` | What version of that solver is in use? | `1.0.0` placeholder | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| HXP-5 | `Blocks-go-live` | How should CORA talk to it (an EPICS soft-IOC record, a controller API, or something else)? | EPICS soft-IOC record | [Hexapod DoF model](assets.md#hexapod-dof-model) |

## Sample stages

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | `Blocks-build` | Is `Sample_pitch_lam` (the Kohzu SA16A-RM goniometer in the source page) the SAME physical thing as the hexapod's Pitch axis, or a SEPARATE stage mounted on the hexapod? This decides whether CORA models one device or two. | treated as the hexapod's Pitch axis | [Hexapod DoF model](assets.md#hexapod-dof-model) |
| STAGE-2 | `Nice-to-have` | Full part number and datasheet for the Kohzu CYAT-070 alignment stages (`Sample_top_X` / `Sample_top_Z`)? | `Kohzu CYAT-070`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | Full part number and datasheet for the Aerotech ABS250MP-M-AS rotary stage (`Rotary`)? | `Aerotech ABS250MP-M-AS`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | [Procedures](procedures.md) |

## The MCTOptics detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | `Blocks-build` | Is the lens turret a rotating turret, or a sliding (translating) selector? This sets whether its positions are degrees or millimeters. | rotating (degrees) | [MCTOptics](equipment/mctoptics.md) |
| DET-2 | `Blocks-build` | Does CORA drive the focus stage directly, or does the detector's own IOC move it behind the scenes? This decides whether CORA owns that control path. | CORA drives it | [MCTOptics](equipment/mctoptics.md) |
| DET-3 | `Blocks-build` | How are cameras selected: a single fixed bay, or is there a selection stage? | single bay, no selection stage | [MCTOptics](equipment/mctoptics.md) |
| DET-4 | `Blocks-build` | How does the camera bay move, if at all: fixed, or is there a rotation stage? | fixed, no rotation stage | [MCTOptics](equipment/mctoptics.md) |
| DET-5 | `Blocks-build` | Is there a second active FLIR Oryx camera bay (`2bmSP2:`), or is 2-BM genuinely single-camera? | single-camera; any second Oryx is offline | [MCTOptics](equipment/mctoptics.md) |
| DET-6 | `Nice-to-have` | Who actually makes the lens-turret motor (Optique Peter, or a third-party motor inside the housing), and its part number? | assumed Optique Peter | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-7 | `Nice-to-have` | The three distinct Mitutoyo part numbers, one per magnification (10x / 2x / 1.1x)? Today all three share one catalog row. | one `Plan-Apo-NIR` family row | [Vendor catalog](assets.md#vendor-catalog-models) |
| DET-8 | `Blocks-go-live` | The FLIR Oryx's max frame rate, sensor kind, and readout mode (rolling vs global)? The Camera schema requires these and they are currently blank, plus its part number for the datasheet. | only sensor size / pixel / bit-depth recorded | [Settings](assets.md#settings) |
| DET-9 | `Nice-to-have` | The measured magnification of the 2x Mitutoyo objective at 25 keV? The current 2.0x is nominal, pending re-measurement. | 2.0x nominal (provisional) | [MCTOptics](equipment/mctoptics.md) |

## Timing

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq timing box's identity and gateware (bitstream) version, so we can finalize its settings schema? (Not yet modelled.) | draft schema, not yet registered | [Pending](assets.md#pending) |

## Beam path and front end

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BEAM-1 | `Blocks-go-live` | Is the beam shutter already open when a tomography run starts, or does the operator open it as part of run startup? | open before the run (handled by commissioning / a pre-run caution) | [Procedures](procedures.md) |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | The canonical APS drawing reference for the B-station safety shutter (`Shutter`)? | shutter modelled; no drawing on file | [Engineering drawings](assets.md#engineering-drawings) |
| BEAM-4 | `Nice-to-have` | Is the beamline layout drawing `ICMS A342-RT1000` Rev 02 (May 2026) still the current revision? | assumed current | [2-BM index](index.md) |

## Safety interlocks

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | `Blocks-go-live` | Does the APS Personnel Safety System expose hutch-search and shutter-permit status as readable Channel Access PVs? If so, what are the PV names; if not, what is the integration path for an external observer? This is the one piece missing for CORA to gate runs on the hutch permit. | no PV names known; confirmer: APS safety-systems / PSS contact | [Enclosures](enclosures.md) |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? | a gas supply exists; mixture unknown; confirmer: facility utilities | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? | air available; specs unknown; confirmer: facility utilities | [Supplies](supplies.md) |

## Not on this page

Hardware CORA has deliberately not modelled yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). Those raise their own questions here only once CORA starts modelling them.
