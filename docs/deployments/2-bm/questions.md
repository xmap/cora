# Open questions

*The open items CORA needs 2-BM staff to confirm. Only open items appear here.*

## What we need from you

Below are the facts we need you to confirm or correct about 2-BM hardware. Most you can answer from memory in a couple of minutes.

**How to reply:** open a short issue at [github.com/xmap/cora/issues](https://github.com/xmap/cora/issues), one per answer or several together. Quote the item ID and write the answer in plain text, for example:

> HXP-2: A = Roll, B = Pitch, C = Yaw
> DET-2: CORA drives the focus stage directly

You do not need to edit this file or know where it lives. If you do not use GitHub, just send the same thing (the item ID and your answer) to whoever shared this page with you.

**If you are not the beamline scientist:** a few rows name a different contact. Safety and interlocks: **PSS-1**. Facility utilities (gas, compressed air): **SUP-1**, **SUP-2**. If a row is really a controls/EPICS, network, or engineering question rather than yours, just route it to the right person or tell us who that is.

**Where to start:** one `Blocks-build` item is left, `DET-2`, because your answer changes how we have to describe the device, not just a value we fill in. If you only have a couple of minutes, do that one first. After that, the `Blocks-go-live` items (including the safety item `PSS-1`) matter before CORA ever controls or observes hardware.

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
| DRIVE-4 | `Nice-to-have` | Exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The rotary drive is named (Aerotech Ensemble HLE10-40-A-MXH); these two boxes are not. | `unknown-pending-confirmation`; vendor known to be Aerotech | [Vendor catalog](assets.md#vendor-catalog-models) |
| DRIVE-5 | `Nice-to-have` | Serial number of the Nanotec `ST4118M1404-B` stepper driving the Microscope objective selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DRIVE-6 | `Nice-to-have` | Serial number of the Schunk `LPTM 30` stepper driving the Microscope camera selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | [Pending](assets.md#pending) |

## The hexapod

CORA describes the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

### Can CORA move the hexapod yet?

Short answer: not yet, and that is expected.

CORA can describe the hexapod's six axes and how they connect, and it checks that those connections are valid. What it cannot do yet is send a "move the sample to this position" command. Moving a hexapod means turning one target pose into six coordinated leg movements, and that math (the kinematics solver) runs inside the hexapod's own Aerotech controller, reached through the `2bmHXP:` EPICS interface. CORA just needs a live connection to that controller so it can hand over a pose and read back where the stage ended up. That connection comes with a running beamline, so it is deferred until the system is stood up. Until then the six axes are described and the wiring is validated, but no motion command will execute. The channel map, the solver location, and how to talk to it are all now known from the beamline components page; the controller's firmware version comes in with the controller serial/firmware items (`DRIVE-2`). Only one hexapod question is left below.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| HXP-2 | `Nice-to-have` | Do our rotation names match yours? We used Roll = about X, Pitch = about Y, Yaw = about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw | [Hexapod DoF model](assets.md#hexapod-dof-model) |

## Sample stages

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. | `Kohzu CYAT-070`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-3 | `Nice-to-have` | A datasheet PDF for the Aerotech ABS250MP-M-AS rotary stage (`Rotary`)? The part number and key specs are on the components page; we just have no datasheet on file. | `Aerotech ABS250MP-M-AS`, no datasheet on file | [Engineering drawings](assets.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | [Procedures](procedures.md) |

## The Microscope detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-2 | `Blocks-build` | Does CORA drive the focus stage directly, or does the detector's own IOC move it behind the scenes? This decides which side owns that control path. The motors are now mapped (shared Z rail `2bmbAERO:m1`, per-lens fine focus `2bmb:m2/m3/m4`); what we still need is who owns the control path. | CORA drives it | [Microscope](equipment/microscope.md) |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | [Vendor catalog](equipment/microscope.md#vendor-catalog-models) |
| DET-8 | `Blocks-go-live` | The FLIR Oryx's max frame rate, sensor kind, and readout mode (rolling vs global), plus its part number for the datasheet? CORA needs these camera values and they are currently blank. | only sensor size / pixel / bit-depth recorded | [Settings](assets.md#settings) |
| DET-9 | `Nice-to-have` | The measured magnification of the 2x Mitutoyo objective at 25 keV? The current 2.0x is nominal, pending re-measurement. | 2.0x nominal (provisional) | [Microscope](equipment/microscope.md) |

## Timing

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIME-1 | `Nice-to-have` | The softGlueZynq's gateware (bitstream) version? The box itself is identified on the components page (a Xilinx Zynq SoC on a MicroZed carrier, EPICS prefix `2bmbMZ1:SG:`); only the bitstream version is missing. Optional for now. | identity known; bitstream version not recorded | [Pending](assets.md#pending) |

## Beam path and front end

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BEAM-1 | `Blocks-go-live` | Is the beam shutter already open when a tomography run starts, or does the operator open it as part of run startup? The TomoScan sequence does open and close the fast shutter during a scan; we want to confirm the state CORA's run-start should assume. | open before the run (handled by commissioning / a pre-run caution) | [Procedures](procedures.md) |
| BEAM-2 | `Nice-to-have` | How many front-end Be windows are in the stack, and what is their total thickness? | windows exist; count and thickness unconfirmed | [Pending](assets.md#pending) |
| BEAM-3 | `Nice-to-have` | Is there a canonical APS drawing for the B-station safety shutter (`StationShutter`) beyond its RSS tag (`02-BM-A-P-01`)? | shutter modelled; only the RSS tag on file | [Engineering drawings](assets.md#engineering-drawings) |

## Safety interlocks

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | `Blocks-go-live` | Does the APS Personnel Safety System expose hutch-search and shutter-permit status as readable Channel Access PVs? If so, what are the PV names; if not, what is the integration path for an external observer? CORA needs this so it can decide whether to start its own data-collection run, by reading the hutch-permit status. To be clear: CORA only reads the permit. It never drives, holds, or releases the PSS permit or the beam; the PSS remains the sole interlock. Confirming the PV names does not put CORA into the safety chain. Confirmer: APS safety-systems / PSS contact. | no PV names known; confirmer: APS safety-systems / PSS contact | [Enclosures](enclosures.md) |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | `Nice-to-have` | The sample-environment gas-mix composition available at 2-BM? Confirmer: facility utilities. | a gas supply exists; mixture unknown; confirmer: facility utilities | [Supplies](supplies.md) |
| SUP-2 | `Nice-to-have` | The compressed-air spec at 2-BM (line pressure, flow, quality class)? Confirmer: facility utilities. | air available; specs unknown; confirmer: facility utilities | [Supplies](supplies.md) |

## Not on this page

Hardware CORA has deliberately not described yet (the mirror, the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) lives in [assets.md Pending](assets.md#pending) and [Decommissioned](assets.md#decommissioned-provenance-only). Those raise their own questions here only once CORA starts describing them.
