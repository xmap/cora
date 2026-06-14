# Open questions

*A running list of things CORA needs 2-BM staff to confirm.*

Nothing on this page blocks the model. Where an answer is missing, CORA holds a clearly-marked placeholder and runs on it; confirming an item simply replaces a placeholder with the real value. Each item gives the question, why it matters, and what CORA assumed in the meantime.

To answer, reply against the question number (Q1, Q2, ...) in a comment, a message, or a quick edit here. When an item is answered, move it to [Resolved](#resolved) with the answer and the date.

## Device identities

CORA records each controller box's serial number and firmware version so it can later answer questions like "did the controller firmware change between Monday's scan and Friday's?". These are placeholders today.

| # | Question | Assumed for now |
| --- | --- | --- |
| Q1 | Serial numbers for the five motion-controller boxes (the drives for the rotary stage, the hexapod, the focus stage, and the two OMS VME58 crate cards)? | `unknown-pending-confirmation` |
| Q2 | Firmware versions for those same five boxes? | `unknown-pending-confirmation` |
| Q3 | Are the Aerotech drives network-attached, and if so what are their IP addresses? | left blank (assumed not needed) |
| Q4 | The exact Aerotech model / part number for the hexapod drive and the focus-stage drive? The source page says "native Aerotech Ensemble" but does not name the box. | recorded as `unknown-pending-confirmation`; vendor known to be Aerotech |

## The hexapod axes

CORA now models the sample hexapod's six degrees of freedom as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](assets.md#hexapod-dof-model).

| # | Question | Assumed for now |
| --- | --- | --- |
| Q5 | Which EPICS channel (`2bmHXP:m1` through `m6`) is which axis? The source page names two rotational channels (`m4`, `m5`); the full six-channel map is unconfirmed. | not asserted in the docs |
| Q6 | Do our rotation names match yours? We used Roll = rotation about X, Pitch = rotation about Y, Yaw = rotation about Z (matching the vendor datasheet's A/B/C envelope). | A = Roll, B = Pitch, C = Yaw |

### Can CORA move the hexapod yet?

Short answer: not yet, and that is expected.

CORA can now describe the hexapod's six axes and how they connect, and it checks that those connections are valid. What it cannot do yet is send a "move the sample to this position" command. Moving a hexapod means turning one target pose into six coordinated leg movements, and that math (the kinematics solver) already runs inside the hexapod's own controller. CORA just needs a live connection to that controller so it can hand over a pose and read back where the stage ended up. That connection comes with a running beamline, so it is deferred until the system is stood up. Until then the six axes are modelled and the wiring is validated, but no motion command will execute.

| # | Question | Assumed for now |
| --- | --- | --- |
| Q7 | What is the hexapod's motion solver called, and where does it run? | assumed `2bmHXP`, running as an EPICS soft IOC |
| Q8 | What version of that solver is in use? | `1.0.0` placeholder |
| Q9 | How should CORA talk to it (an EPICS soft-IOC record, a controller API, or something else)? | assumed EPICS soft-IOC record |

## The sample pitch stage

| # | Question | Assumed for now |
| --- | --- | --- |
| Q10 | Is `Sample_pitch_lam` (the Kohzu SA16A-RM goniometer named in the source page) the SAME physical thing as the hexapod's Pitch axis, or a SEPARATE stage mounted on the hexapod? This decides whether CORA models one device or two. | treated as the hexapod's Pitch axis |

## The MCTOptics detector

| # | Question | Assumed for now |
| --- | --- | --- |
| Q11 | Is the lens turret a rotating turret, or a sliding (translating) selector? This sets whether its positions are in degrees or millimeters. | assumed rotating (degrees) |
| Q12 | Does CORA drive the focus stage directly, or does the detector's own software move it behind the scenes? This decides whether CORA owns that control path. | assumed CORA drives it |
| Q13 | Is there a stage that selects between cameras? | assumed none (single camera bay) |
| Q14 | Does the camera bay rotate? | assumed fixed |
| Q15 | Part numbers for the three Mitutoyo objectives and the FLIR Oryx camera, so we can attach the right vendor datasheets? | pending |

## Timing box

| # | Question | Assumed for now |
| --- | --- | --- |
| Q16 | The softGlueZynq timing box's identity and gateware (bitstream) version, so we can finalize how CORA records it? | draft schema, pending |

## Hardware not modelled yet

For awareness, not action. CORA deliberately has not modelled these yet and will raise specific questions when it does: the mirror (`Y3-30_mirror`), the wider sample-stage motor band, other IOC-hosted devices, and the past high-speed cameras (PCO Dimax, Adimec), which are kept for provenance only.

## Resolved

*(none yet)* When an item above is answered, move it here with the answer and date, for example: "Q5 (2026-06-20, J. Smith): m1 = X, m2 = Y, m3 = Z, m4 = Pitch, m5 = Roll, m6 = Yaw."
