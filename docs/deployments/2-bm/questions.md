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
| DRIVE-5 | `Nice-to-have` | Serial number of the Nanotec `ST4118M1404-B` stepper driving the Microscope objective selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Vendor catalog](microscope.md#vendor-catalog) |
| DRIVE-6 | `Nice-to-have` | Serial number of the Schunk `LPTM 30` stepper driving the Microscope camera selector? The model is now known from the components page; only the per-unit serial is missing. Optional for now. | model known; serial not recorded | not yet | [Microscope](microscope.md) |

## The hexapod

The sample hexapod's six degrees of freedom are described as named axes: three translations (X, Y, Z) and three rotations (Roll, Pitch, Yaw). See [Hexapod DoF model](inventory.md#hexapod-dof-model).

### Rebooting a stuck hexapod

Recovery from a controller lock-up is the [`hexapod_reboot` recipe](recipes.md), read from the authoritative script [`decarlof/2bmb-bin@372285c6`](https://github.com/decarlof/2bmb-bin/blob/372285c69492/hexapod_reboot.py). HXP-3 through HXP-8 are all answered: the script is confirmed as the current production copy, and with it the enable PVs, IOC scripts and host, PDU and outlet, and reboot timings. One question is left, and it is one the script cannot answer about itself.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HXP-9 | `Nice-to-have` | What actually re-homes the hexapod after a reboot? Your HXP-8 answer says the axes come back homed with Y at dial 350 and user 0, which we have recorded. We cannot see what performs it: `hexapod_reboot.py` has no homing step, and neither `hexapod_IOC.sh` nor `hexapod_IOC_stop.sh` does either, so it is happening in the IOC's `st.cmd`, in the Automation1 firmware on power-up, or by hand. Naming which one decides whether a reboot leaves a hexapod ready to move or still needs an operator, which is the difference between a recipe that finishes and one with a manual tail. | homing happens automatically, performed by the IOC startup or the controller firmware rather than by an operator | yes (the coordinate convention is recorded; the recipe claims no homing postcondition) | [Recipes](recipes.md) |

## Sample stages

These rows confirm vendor models, datasheets, and travel limits for the sample-side stages.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| STAGE-2 | `Nice-to-have` | A datasheet PDF for the Kohzu CYAT-070 alignment stages (`SampleTop_X` / `SampleTop_Z`)? The part number and key specs are on the components page; we just have no datasheet on file. Also: our docs quote 15 mm of travel each way, but CORA records 10 mm each way (`-10..10 mm`); which is right? | `Kohzu CYAT-070`, no datasheet on file; travel -10..10 mm (docs say 15 mm each way) | yes | [Engineering drawings](inventory.md#engineering-drawings) |
| STAGE-4 | `Nice-to-have` | The measured motor-sensitivity constants (K_roll, K_pitch) that link a hexapod tilt to the observed image-centroid shift? Today they are re-derived per alignment rather than stored. | derived in-procedure, not persisted | not yet | [Procedures](procedures.md) |
| STAGE-5 | `Nice-to-have` | The rotation stage belongs to a documented kit (`ABRS-250MP-M-AS` installed, plus `ABRS-150MP-M-AS` and the `ABS2000-1000AS-RU` spindle per the [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html), `item_050`). Is the rotary actually SWAPPED per experiment at 2-BM-B today, or is `ABRS-250MP-M-AS` the single installed stage with the others historical / per-station? And which mode label (`fast tomo` / `mona tomo` / `spindle`) maps to which stage in the current setup? (Source labels conflict pre vs post APS-U.) **New evidence to reconcile:** the ENERGY-7 channel-cut answer (#256) says its calibration crystal is rocked on an `ABRS-150MP`, while the installed sample rotary is the serial-numbered `ABRS-250MP-M-AS` (`S/N 146853-A-1-1-X`, STAGE-3 / #164). Is the 150MP genuinely mounted for energy calibration (a real kit swap), or is that a slip for the installed 250MP? | one installed (`ABRS-250MP-M-AS`); kit not actively swapped | yes | [Vendor catalog](inventory.md#vendor-catalog) |
| STAGE-6 | `Nice-to-have` | The exact Kohzu model of the laminography-pitch / swivel stage (`LaminographyPitch`, `2bmb:m49`)? CORA uses `SA16A-RM`; the source swivel kit also lists `SA16A-RS` and `SA07A-R2L`. | `Kohzu SA16A-RM` | yes | [Vendor catalog](inventory.md#vendor-catalog) |
| STAGE-10 | `Nice-to-have` | Confirm the `Rotary` encoder resolution. `item_050`'s Ensemble encoder table gives 532800 pulses/rev (11840 lines/rev x 45 scale factor) = 0.000676 deg/count for the ABRS-250MP; CORA now records that, replacing an earlier unsourced `0.0001 deg`. The 11840 lines/rev fundamental is confirmed by the ABRS datasheet (#164); still open is whether the Ensemble applies the x45 or a further electronic multiplication to reach the operational count. | `0.000676 deg` from item_050; 11840 lines/rev datasheet-confirmed (#164) | yes (awaiting Ensemble-multiplication confirmation) | [Settings](inventory.md#settings) |

## The Microscope detector

Objectives and the turret selector on the Optique Peter microscope. Objectives are swappable, so several rows confirm what is mounted now.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DET-7 | `Nice-to-have` | The Mitutoyo part number for the 1.1x objective? The 2x and 10x part numbers are on record; the 1.1x is the one still missing, and all three currently share one catalog row. | one `Plan-Apo-NIR` family row | yes | [Vendor catalog](microscope.md#vendor-catalog) |
| DET-9 | `Nice-to-have` | Which magnification is the middle objective physically at 2-BM, and its measured value at 25 keV? CORA records 2.0x (nominal), but the Microscope lens table lists the installed middle objective as 5x (measured about 4.93). The field-tested staff `2bm-procedures` repo independently corroborates this: it hard-codes the middle objective (MCTOptics `LensSelect` index 1) as 5.0x. Objectives are swappable, so please confirm what is installed now. | 2.0x nominal (provisional); the microscope lens table and the field-tested staff repo both indicate 5x installed | yes | [Microscope](microscope.md) |
| DET-14 | `Nice-to-have` | The focal length of each of the three objectives, and the tube-lens focal length the microscope uses? CORA published 20 / 100 / 200 mm for the 10x / 2x / 1.1x. Those values carry no external citation: they appear in CORA's own microscope scenario, which requires the field, and nowhere else. The descriptor, the vendor catalog row, and the staff pages are all silent on focal length, so they have been withdrawn from the published tables rather than left reading as recorded facts. Two of the three are what an F=200 mm tube lens would give for the nominal magnifications and the third is not, which is a reason to confirm them rather than to reconstruct them. | the scenario applies 20 / 100 / 200 mm to the three Assets; `magnification`, `numerical_aperture` and `working_distance` are separately recorded in the descriptor, focal length is not | partly | [Inventory](inventory.md#settings) |
| DET-12 | `Nice-to-have` | When the propagation-distance stage (`2bmbAERO:m1`, the sample-to-detector rail) moves, does the whole detector (the Optique Peter housing with its objectives, scintillator, and camera) travel along the beam as one unit, or does only part of it move while the rest stays fixed to the detector table? Put another way: is the microscope mounted on top of that stage, or are the stage and the microscope mounted side by side on the table? | the stage carries the whole microscope, so CORA models the rail as the support the housing rests on; please confirm the physical mounting | yes | [Microscope](microscope.md) |
| DET-13 | `Nice-to-have` | The remaining FLIR Oryx 31 MP (`Camera_HighRes`, `2bmSP2:`) `Camera`-schema fields: bit depth, sensor kind, and readout mode? The [Detection page (item_020)](https://docs2bm.readthedocs.io/en/latest/source/ops/item_020.html) now confirms the sensor as 6464 x 4852 px at 26 fps (3.45 um pitch, mono), and per-unit identity (model `ORX-10G-310S9M`, serial `22150530`, firmware `1904.0.72.0`) is on record, so only these three are missing; the `Camera` schema needs bit depth before the sensor group can be applied, so the Asset stays identity-only until then. | size + frame rate confirmed (item_020); bit depth / sensor kind / readout mode pending | partly | [Microscope](microscope.md) |

## Fine-positioning piezo controllers

The NV200D/NET piezo (now `ApertureFineDrive`) fine-positions the coded `Aperture` mask via FPGA-triggered stepping; the NV100D is present but not in operational use. The axis mapping is settled (PIEZO-5): your 2026-07-28 patch-panel trace confirmed `out2` = X and `out3` = Y, and the same trace corrected the delay-PV axis comments in `item_028`. One row is left, and it is about a screen rather than a cable.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| PIEZO-6 | `Nice-to-have` | The delay-PV axis comments in `item_028` were corrected on 2026-07-28 so that `GateDly-2` is X and `GateDly-3` is Y. Does the softGlueZynq operator screen (`softGlueZynqAll.adl`) carry its own axis annotation next to those two blocks, and if so does it now agree? We ask because the delay is set by hand per scan: a screen still reading the old way sends that edit to the other axis, and the scan still completes. | screen either carries no axis annotation or agrees with the corrected `item_028` | yes (the corrected mapping is recorded per axis) | [NV200D trigger wiring](inventory.md#nv200d-trigger-wiring) |

## Energy and the optics

On an energy change the DMM monochromator, its Bragg arms, and the tracking slits move together to saved per-energy positions (now recorded). The remaining item covers the channel-cut calibration crystal.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| ENERGY-7 | `Nice-to-have` | Channel-cut energy calibration is confirmed current practice (2d = 3.84 angstrom, 36 x 3 mm removable crystal, modelled as a calibration Subject). Residual confirms: explicit confirmation the crystal is **Si(220)** (only Si(220) matches 2d = 3.84) and how often calibration is re-run. (The rocking-stage model question, ABRS-150MP vs the installed 250MP, is folded into STAGE-5, the rotary-kit-swap question.) | calibration + 2d + removable confirmed (#256); Si(220) + re-run cadence open | partly | [Procedures](procedures.md) |

## Beam mode

2-BM runs in two beam modes, and switching between them is a coordinated multi-device move CORA does not yet drive. These confirm the mode model and supply the values it would need.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| MODE-3 | `Blocks-go-live` | The swept mirror coating stripe (`2bma:m3`) is now modelled as the `Mirror_StripeReachX` facet (held at stripe a in Mono, Pink curve 3.039 / 13 / 39 / 49 mm) with the named-stripe map recorded. What remains is the coordinated mirror-table X stages (`2bma:m1` / `m4`, Pink 8 / 10 / 10 / 29 mm): CORA recorded these as blocked by the `M1Y=2bma:m3` substitution error ([2bm-docs#171](https://github.com/xray-imaging/2bm-docs/issues/171)). That is now out of date, and not in the way CORA assumed: the issue closed as completed on 2026-06-16 having taken **Path C**, which dropped the `2bma:table1` virtual record entirely rather than correcting the substitution. The `dbLoadRecords` line for `table.db` was commented out in `iocBoot/ioc2bma/st.cmd`, so `2bma:table1` and its `.X / .Y / .Z / .AX / .AY / .AZ` composite axes no longer exist in Channel Access at all. Two things follow, and both need you. First, please confirm the record really is gone from the running `ioc2bma`. Second, CORA still models `MirrorTable` as a `virtual_pose` asset over that deleted record, which is now wrong: should it be re-modelled onto the raw motors, pitch and vertical through `2postMirror.db` and table X through the energy-change IOC, as item_020 describes? | `MirrorTable` still carries `axis_layout=virtual_pose` and `virtual_record=2bma:table1`, a record the published upstream source says was removed on 2026-06-15 | no | [Beam modes](procedures.md#beam-modes) |

## Proposals, users and scheduling

CORA will read proposal and user information from the APS scheduling system (the `beam-api` / DMagic data the beamline already uses) to label each run with its proposal and notify the right people. These help us get the design right before we build it.

Confirmed design basis (SCHED-1/2/3a, #269): a scheduled beamtime window is **immutable once users are on-site** (only pre-arrival shifts happen; mid-run beam outages are Run-level "beam unavailable T1-T2" annotations, not schedule changes). The **local contact is a beamline-side assignment, distinct from the proposal user list** (CORA's earlier "listed as one of the beamtime's people" assumption was wrong; model it as a separate beamline-assigned field). Per-person identity uses two stable, never-reused keys: **ORCID** (primary, cross-institution, already CORA's actor key) plus the **APS badge number** (APS-internal join key for `beam-api` / DMagic correlation). The 2-BM scheduling integration itself is a future slice; these facts are its inputs.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| SCHED-3b | `Nice-to-have` | Under APS data governance, is the APS badge number classified as personal data subject to deletion on request (so CORA scrubs it via the same forget-actor path as other PII)? The badge-reuse and identifier questions are settled (#269); only this classification routes to data-management. Confirmer: APS User Office / data-management contact. | treated as deletable personal data (PII-vault scrubbed), pending the governance ruling | not yet | [2-BM index](index.md) |

## Inside the scan file

The storage chain was settled by DATA-1 through DATA-7 (#270). What those answers did not cover, the file
itself, is now read from the upstream source instead of asked: tomoscan's 2-BM subclass and dmagic give the
Data Exchange layout, the file naming template, the end-of-scan ordering, and the experiment-folder
derivation. Those are recorded in [Operations](operations.md#inside-the-scan-file). DATA-9 and DATA-10 were
settled the same way, by a direct read against the live 2bmb deployment on 2026-08-11 rather than a staff
reply; see [Operations](operations.md#inside-the-scan-file) for the evidence. Only what neither source can
answer is left here.

DATA-11 is answered and closed (#655). It asked whether the detector IOC could be made to refresh its
timestamp attribute at file open; the answer is that it cannot, because an `EPICS_PV` NDAttribute is only
refreshed by a frame passing through the plugin and no frame of a new scan has passed at file-open time.
The write moved to the tomoscan client instead, and CORA now declares `captured_at_source: start_date`.
What the fix left behind is DATA-12: it overwrites the stale value rather than preserving it, so a file
gives a reader no way to tell which writer produced its own timestamp.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| DATA-8 | `Nice-to-have` | How often do scans finish with dropped frames? `add_theta()` compares written frames against commanded angles and logs a warning when they disagree, so the condition is detected but not fatal. Knowing whether this is rare-and-alarming or routine decides whether a record of the scan should refuse to be written, or carry the shortfall as an ordinary recorded fact. | rare enough to treat as an exception worth surfacing, not a routine outcome to normalise | not yet, but the question is now askable: CORA could not read the commanded counts at all until 2026-08-12 (2-BM writes them as one-element arrays and the reader understood only plain scalars), so every shortfall check silently compared against nothing. Two data points since: `test_000.h5`, an early smoke test, 3601 commanded and 1 captured with `theta` absent; and `test_005.h5`, the first production scan CORA read end to end, 1501 commanded and 1501 captured, nothing dropped | [Operations](operations.md) |
| DATA-12 | `Blocks-go-live` | From which date are 2-BM scan files written with the corrected `start_date`, and has the `2bmbSP2` IOC been restarted yet? A file gives no way to answer this from its own contents: the client fix overwrites the IOC's stale value instead of preserving it, so a pre-fix and a post-fix file are identical in shape. CORA now reads `start_date`, which is right for new files and silently wrong for old ones, and the ingest policy is that a parseable file timestamp beats an operator's, so a wrong value cannot be corrected after the fact. A date is a complete answer. A marker written into the file, even a one-line `start_date_writer` attribute, would retire the question permanently and would serve every other consumer of these files too. | the client fix (`decarlof/tomoscan@d0025a2`) went live 2026-08-13; the IOC restart that stops the stale write at file open has not happened yet | not yet (the descriptor declares `start_date`; no 2-BM file written after the fix has been read by CORA) | [Operations](operations.md#inside-the-scan-file) |

## Where CORA runs

CORA needs a machine at 2-BM to run on, and these are the facts about that machine that CORA cannot
choose for itself. None of them change how CORA describes the beamline, so none block the description;
all of them block pointing CORA at anything real. Whether the host is a virtual machine, a container, or
bare metal is CORA's problem to accommodate and not a question for this page. What the host can reach,
and what survives losing it, are not.

Decided 2026-08-11, internally rather than as a staff question: CORA runs on `arcturus` for now.
`arcturus` already carries a shared installation CORA can use, `conda activate cora` under the shared
`/home/beams/2BMB` home directory, confirmed directly reachable there with no extra hop. This is an
interim choice for testing and development while nothing structured is decided yet, and the host may
move later. Two consequences follow. `arcturus`'s own `EPICS_CA_ADDR_LIST` (an explicit address list,
not broadcast) is simply what CORA now uses, which is what the former HOST-1 asked. And read access to a
finished scan file is settled: CORA reads it in place on `tomdet` and never copies it.

Copying was the earlier posture, exercised end to end on 2026-08-12 by staging `test_005.h5` (24.5 GB) to
`/local/cora-scans` on `arcturus` and ingesting it there. That worked for one supervised scan and does not
survive a batch. Measured 2026-08-18 and 2026-08-19: a scan averages 24 GB, the link between the two hosts
is 1 GbE (about 105 MB/s in practice), so one file takes roughly 230 seconds to move against a scan cadence
near 120 seconds. Copying therefore falls permanently behind at about twice the rate it can keep up, and it
saturates the same link the run witness uses for its EPICS traffic. A mount of the detector tier would
inherit the same ceiling, because the constraint is the link rather than the protocol.

Reading in place inverts the cost. Digesting a file on `tomdet`'s own disk runs at about 920 MB/s, roughly
26 seconds per scan, and only a small verdict crosses the link. What travels to the detector host is a
request; what comes back is a description and a checksum. The beamline confirmed on 2026-08-19 that a
read-only reader may run there under the shared beamline account.

Two properties this places on CORA rather than on the beamline. The path CORA is handed originates in a PV
that anyone with Channel Access can write, so it is untrusted input: it never reaches a command line, and
it is confined to a declared list of permitted roots, checked on the host that actually holds the bytes.
And the write target is itself an operator-settable PV that has moved between tiers at least once, so the
permitted roots are a deployment setting to be re-read against `2bmb:TomoScan:DetectorTopDir`, not a
constant to be hard-coded.

These are likely controls, networking, or IT questions rather than floor questions. Routing them to the
right person, or naming who that person is, is a complete answer to any row here.

| ID | Priority | Question | CORA assumes | Already done? | Resolves |
| --- | --- | --- | --- | --- | --- |
| HOST-2 | `Blocks-go-live` | Can the host read the scan files directly, as a mount of the analysis tier (`/data2`, `/data3`) or of the Sojourner experiment tree, and read-only is sufficient? If no mount is possible, what is the supported way for an off-host reader to fetch a finished file? The answer decides whether CORA reads a dataset in place or has to copy it first, which is a different design and not a setting. | no mount, and none needed: CORA reads in place on `tomdet` over an SSH hop (confirmed 2026-08-11 that none of `/local1`, `/local2`, `/data2`, `/data3`, `/gdata/dm/2BM` are visible from `arcturus`, and measured 2026-08-19 that copying cannot keep pace with the scan cadence, so a mount would not have helped either). Finished files land on `tomdet` at `/local1/2BM/<experiment>/`; an earlier reading of `/local2` on 2026-08-11 was real, 66 older scans still sit there, so the tier is operator-settable rather than fixed | resolved 2026-08-19, read-only access confirmed by the beamline | [Operations](operations.md#inside-the-scan-file) |
| HOST-3 | `Blocks-go-live` | What durable storage can the host write backups to that is not the host's own disk, and does the host's own disk survive the host being lost or rebuilt? A backup written beside the database protects against operator error and corruption and against nothing else. This row also carries a deadline: backup-repository encryption is fixed when the repository is first created and cannot be added afterwards, so the target has to be known before that step, not after. | a facility share or object store is reachable; local disk is an interim posture only | not yet | [Deployment](../../stack/deployment.md) |
| HOST-4 | `Blocks-go-live` | Who needs to reach CORA's web interface, and from where: the beamline network only, anyone on the APS network, remote users over VPN, or remote users without one? This decides whether CORA sits behind an existing APS proxy or brings its own, and whether it needs a certificate and a resolvable name. | beamline and APS-network access, behind a facility-provided proxy that terminates TLS | not yet | [Deployment](../../stack/deployment.md) |
| HOST-5 | `Nice-to-have` | Who administers the host, and does the operating account have rights to install a scheduled system job? CORA needs a timer to run backups and expire old ones. If that is not permitted, the schedule has to live inside the application instead, which is a different and slightly worse design worth choosing deliberately. | beamline-administered, with rights to install a system timer | not yet | [Deployment](../../stack/deployment.md) |
| HOST-6 | `Blocks-go-live` | Is the APS Data Management tree (`/gdata/dm/2BM/`) readable from `tomdet`, using the same account CORA's scan probe already logs in with? The 2026-08-11 check covered `arcturus` only, and found `/gdata` invisible there; whether `tomdet` can see it was never tested. It matters because the DM copy is the one that outlives the beamtime, and every upstream tier is capacity-purged, so a record that names only `/local1` points at bytes that will be gone. If `tomdet` cannot read it either, naming the host that can, or the supported way to list and read an experiment folder there, is an equally complete answer. | readable on `tomdet` over the existing SSH account, read-only | not yet | [Operations](operations.md#supplies) |

## Not on this page

Hardware CORA has deliberately not described yet (the wider sample-stage motor band, IOC-hosted devices, past high-speed cameras) raises questions here only once CORA starts describing it. The `Mirror` is the exception that proves the rule: it is a registered Asset ([Inventory](inventory.md#inventory)) and its coating-stripe sweep is now modelled (`Mirror_StripeReachX`); only the coordinated mirror-table X binding stays open (`MODE-3`), now because the `2bma:table1` composite axes were removed upstream rather than repaired.
