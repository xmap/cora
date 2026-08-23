# Operations

*The 2-BM runbook, by task: ready the beam, set energy, mount and align, scan, recover.*

The detail lives in the pages under this one: [Procedures](procedures.md), [Recipes](recipes.md),
[Enclosures](enclosures.md) (the hutch permits), and [Cautions](cautions.md). A run starts only when its hutches
are Permitted and its resources are available.

## The task flow

- Ready the beam: confirm the hutch permits, pick the beam mode (Mono or Pink), open the shutters.
- Set the energy: [`energy_setting`](recipes.md#energy_setting) drives the optic curves to a configured energy.
- Mount and align: `motor_homing` and the `*_alignment` [Procedures](procedures.md).
- Scan: capture [`dark_field`](recipes.md#dark_field) and [`flat_field`](recipes.md#flat_field),
  then run the tomography Plan.
- Recover: the [Cautions](cautions.md) name the fix (a locked hexapod clears with
  [`hexapod_reboot`](recipes.md#hexapod_reboot)).

## Supplies

A Supply is a continuously-available resource a run draws on. Beamline-scope Supplies are tracked here;
facility-scope utilities live at [APS](../aps/index.md#what-this-site-provides).

| Supply | Scope | Kind |
| --- | --- | --- |
| `2-BM detector LN2 dewar` | `Beamline` | `LiquidNitrogen` |
| `2-BM cooling water` | `Beamline` | `CoolingWater` |
| `2-BM beamline vacuum` | `Beamline` | `Vacuum` |

2-BM keeps no standing gas-mix or compressed-air Supply: sample gas is per-experiment and ESAF-gated (a
Run-level fact, not a beamline Supply), and compressed air is the APS facility shop-air line with no
beamline-local spec.

Cooling water and vacuum are beamline-scope here, not facility utilities. Both are cut into circuits that
belong to 2-BM and are named for the 2-BM optics they serve: eight cooling-water circuits and seven vacuum
sections along this beam path, observed through [BLEPS](#equipment-protection). Each is modelled as one
Supply rather than one per circuit, because a Supply exists to answer whether a run can draw on the
resource, and no run-readiness decision at 2-BM yet turns on which circuit failed. The per-circuit signals
name the failure inside that answer. The photon beam and electrical power stay facility-scope and are
recorded at the [APS](../aps/index.md#what-this-site-provides) level: the source is the storage ring and
the power is the site's, neither is cut to 2-BM's shape.

Beyond the physical utilities, a run also draws on a compute pool (for reconstruction) and on data-transfer and
storage tiers. These are modelled through the `ComputePort` and `TransferPort` (a Method plus a port, not a new
deployment aggregate). The confirmed pipeline (DATA-1 through DATA-7): the detector writes to fast local NVMe on
`tomdet` (`/local1`, re-measured 2026-08-19; the write target is an operator-settable PV that has moved at least
once, so treat any value on this page as a reading rather than a constant, and re-read
`2bmb:TomoScan:DetectorTopDir` before relying on it), tomoscan auto-uploads each scan to the analysis tier
(`/data2` or `/data3`), tomocupy reconstructs there (`..._rec/` beside the raw), and an operator copies the
experiment to its canonical home on APS Data Management
(`/gdata/dm/2BM/<yyyy-mm>/<exp>/{data,analysis,system}/`), shared to proposal and ESAF users through
the Globus collection `APS:DM:2BM` and archived to tape on a per-experiment timer (default one year). The
beamline names this tier two ways, DM on its current pages and Sojourner on older ones; both mean the same
`/gdata` mount, which is the stable thing to match on. The upstream tiers are transient, capacity-purged with
no fixed schedule, so a dataset is briefly multi-homed and then collapses to the DM copy; there is no
continuous beamtime-long sync. The DM tier is readable from `tomdet` over the same SSH hop CORA
already uses to read a finished scan file, measured 2026-08-21 from `arcturus` as the beamline account:
the month directories run back to `2020-11`, and an experiment folder carries the documented
`{data,analysis,system}` split. The earlier reading behind HOST-2 covered `arcturus` only, where none of
the tiers are visible, so this is a different host and not a re-test. An experiment folder is also
locatable from its GUP number alone (`2026-08/*-1015116` resolved to exactly one directory), which is what
lets a reader find the durable copy without being told the PI surname the folder name carries. The reconstruction compute resource itself is not yet pinned to a specific
host or pool.

Transient understates what can happen upstream. On 2026-08-14 the `tomodata2` array failed and `/data2` was
lost outright, taking every dataset on it that DM did not already hold; the beamline's
[archival status page](https://docs2bm.readthedocs.io/en/latest/source/data_management.html) records "DM is
authoritative" against the rows that survived, and clearing a local copy DM already holds is gated on an
emailed approval rather than a schedule. The tiers are therefore not equally durable, which matters to CORA
more than the copy order does: a location on `/local1`, `/local2`, `/data2` or `/data3` is a reading of where
the bytes are today, while the DM path is the one that outlives the beamtime. `2026-08-Haridy-1015116` is
already past that transition and is held only under `/gdata/dm/2BM/2026-08/`.

### Inside the scan file

Read from the upstream source rather than assumed: [tomoscan](https://github.com/decarlof/tomoscan)'s
2-BM subclass and [dmagic](https://github.com/decarlof/dmagic). Every scan product is HDF5; no
acquisition path writes TIFF.

Confirmed 2026-08-11 against the live 2bmb deployment (DATA-9): the deployed `tomoscan_2bm.py`
and its siblings (`tomoscan_2bm_step.py`, `tomoscan_stream_2bm.py`, `tomoscan_fpga_2bm.py`, both
`.template` files) are byte-identical to `decarlof/tomoscan@ce86818`. The shared `tomoscan.py` base
class carries one uncommitted local edit, a camera-readout-timing tweak for one pixel format, nowhere
near `add_theta()` or the `ScanStatus` literals below.

The layout is Data Exchange. `tomoscan_2bm.py` addresses the datasets by name when it post-processes a
finished scan: `/exchange/data` (projections), `/exchange/data_white` (flats), `/exchange/data_dark`
(darks), and `/exchange/theta` (rotation angles). Frame bookkeeping lives in `/defaults/NDArrayUniqueId`
and `/defaults/HDF5FrameLocation`. Per-scan files follow the areaDetector template `%s%s_%3.3d.h5`, so a
scan basename carries a three-digit counter, and `..._rec/` reconstruction directories are named from it.

The file has a second author besides tomoscan: the areaDetector layout XML configured in the detector
IOC writes everything under `/process`, `/measurement`, and `/defaults` (public copy:
[`data-exchange/dxfile/doc/demo/areadetector/2-BM/`](https://github.com/data-exchange/dxfile/tree/master/doc/demo/areadetector/2-BM)).
The deployed file has no name match in that public tree (it lives on `tomdet` as `TomoScanLayout.xml`
at a beamline-local path, not one of the `2bma*` / `adimec2bmb*` names dxfile ships), so DATA-9 was
confirmed by reading its content on 2026-08-11 rather than by matching a filename: it writes the same
dataset paths and lifecycle timing this section assumes. Two of its facts matter to a reader. The
commanded scan geometry (`/process/acquisition/rotation/num_angles`, the flat and dark field
mode-and-count groups) is written `OnFileClose`, so it exists only in cleanly closed files, and it is
what a shortfall check compares captured frames against; the `/defaults` frame ids alone can never show
tail truncation, because a missed trigger never receives an id. `end_date`
(`/process/acquisition/end_date`, from the PV `S:IOC:timeOfDayISO8601`) is written `OnFileClose`. That PV
carries an explicit UTC offset (confirmed 2026-08-11, DATA-10: `2026-08-11T12:01:05-0500`), not naive
local time, so a reader parses it as an unambiguous instant with no site timezone rule needed.
`start_date` used to be written the same way at `OnFileOpen`, and the section below is about why it is
not written that way any more.

**`start_date` was the previous scan's `end_date`, and it is now fixed at the source.** Measured
2026-08-12 across the six files in `2026-08-DeCarlo-1015116`: every file's `end_date` falls within five
seconds of its own close, and in three consecutive cases the `start_date` is the PREVIOUS file's
`end_date` to the second (`test_003` carries `test_002`'s, `test_004` carries `test_003`'s, `test_005`
carries `test_004`'s). `test_005` ran on the morning of 2026-08-12 and claims a start on the evening of
2026-08-11, wrong by about twelve hours and across a day boundary. Two early smoke tests carry a value
five days older than the file. One file, `test_002`, does look correct, which is part of why the defect
is easy to miss. CORA asked about it as DATA-11 and the reply was three upstream commits rather than a
confirmation: the mechanism inferred from the measurements is the one that was there.

An `EPICS_PV` NDAttribute is snapshotted onto each frame as that frame passes the areaDetector
NDAttributes plugin. Between scans no frame flows, so the cached value stays frozen where the previous
scan's last frame left it, and `when="OnFileOpen"` fires before any frame of the new scan has arrived.
`end_date` escaped because by `when="OnFileClose"` this scan's own final frame has already refreshed the
cache. The general form outlives this beamline: `when="OnFileOpen"` cannot carry an `EPICS_PV`
NDAttribute that has to mean *now, at file open*, because the IOC-side pipeline cannot observe a scan
boundary. Only the client can.

So the write moved to the client. `tomoscan_2bm.py` captures the instant in Python at the top of
`begin_scan()` and, once the HDF5 plugin has closed the file, reopens it with `h5py` and writes
`/process/acquisition/start_date` itself
([`decarlof/tomoscan@d0025a2`](https://github.com/decarlof/tomoscan/commit/d0025a2)). The
`DateTimeStart` attribute and its `start_date` layout line were deleted from the areaDetector XML so the
IOC stops writing the stale value at all
([`data-exchange/dxfile@de33f3a`](https://github.com/data-exchange/dxfile/commit/de33f3a)), and `meta
show` marks a pre-fix file's stale value `[derived]` without altering anything on disk
([`xray-imaging/meta-cli@29a56bc`](https://github.com/xray-imaging/meta-cli/commit/29a56bc)). The
canonical bug ticket is `tomography/tomoscan#180`.

The descriptor now declares `captured_at_source: start_date`, and three things follow that a reader
should not have to rediscover. The two timestamps no longer bracket the acquisition from two different
moments: both are written after the file closes, so `start_date` inherited the fragility `end_date`
always had, and a scan that dies before `end_scan()` runs leaves no client-written start time at all,
where before it carried one that was at least wrong in a predictable direction. Nothing in a file names
the writer that produced its `start_date`, because the committed fix overwrites the IOC's value rather
than preserving it under the companion `start_date_from_ioc` that `tomoscan#180` had suggested, so a
pre-fix and a post-fix file are identical in shape and the only discriminator is a deployment date the
file does not carry. That is DATA-12, and until it is answered CORA must not ingest a 2-BM file older
than the fix under this declaration, because the ingest policy is that a parseable file timestamp beats
an operator's and a wrong one could not be corrected afterwards.

The IOC half is also not finished. `dxfile@de33f3a` is deployed into the working tree at
`/home/beams/2BMB/conda/dxfile/`, which the `2bmbSP2` boot directory symlinks into, so the corrected
files already sit on the paths the IOC opens. Until that IOC is restarted it holds the old CA monitor
and the old parsed layout and keeps writing the stale value at file open, and the client's post-close
overwrite is the only thing making new files right.

**A finished capture is not a finished file, and this is the fact an ingest reader must respect.** The
end-of-scan sequence stops the file plugin (`FPCapture` to `Done`, then waits for `Capture_RBV` to reach
0), and only *then* calls `add_theta()`, which REOPENS the file in append mode and creates
`/exchange/theta`. A checksum taken when capture completes describes a file that is about to change.
The `ScanStatus` transfer messages (`fdt file transfer complete`, `scp file transfer complete`) mark the
point at which the transfer is *started*, not finished: both paths are fire-and-forget (the scp path is
backgrounded, the FDT path runs in a daemon thread), so the signal says nothing about whether the copy
on the analysis tier exists yet, and a copy in flight dies silently if the tomoscan process exits.
Anything that needs the file to have *arrived* must verify arrival independently, by size or checksum,
rather than trust the status message.

`add_theta()` also compares the frames actually written against the angles commanded, and logs a warning
naming the missing ones when they disagree. Dropped frames are therefore a known, detected, and
non-fatal condition: a reader that records only what landed will silently under-describe such a scan.
A genuine instance was found 2026-08-11 reading a real file from the beamline (`test_000.h5`, an early
smoke test rather than a production scan): 3601 angles commanded, one frame captured, `theta` absent.
`DataExchangeScanReader` handled it exactly as designed.

The first production scan CORA read end to end (`test_005.h5`, 2026-08-12) dropped nothing: 1501
commanded, 1501 captured, 40 flats, 20 darks, angles 0 to 180.013. That is one scan, so it does not
settle DATA-8's frequency question, but it is the first data point and it comes from the record rather
than from a log line. Until 2026-08-12 the question could not be asked at all: the reader could not read
the commanded counts, because 2-BM writes them as one-element arrays and the reader only understood
plain scalars, so every shortfall check compared against nothing.

The experiment folder is computed, not conventional, which is what makes it derivable rather than
guessable. `dmagic`'s `dm.py` formats it as `{year_month}-{pi_last_name}-{gup_number}` from APS
scheduling data, and normalises the surname through `clean_entry()`: NFKD normalise, encode to ASCII
discarding what will not encode, then keep only letters, digits, hyphen and underscore. Anything
deriving that folder name independently must reproduce that normalisation exactly or it will miss on
accented and punctuated surnames.

## Equipment protection

BLEPS is the beamline equipment-protection interlock, separate from the PSS: BLEPS protects equipment,
the PSS protects people. CORA holds the same posture toward both, the one described for the
[hutch permits](enclosures.md): it reads outcomes, never drives the chain, and never models the
interlock matrix. BLEPS decides; CORA records what BLEPS decided.

Every signal is readable over Channel Access under the prefix `2bmBLEPS:BLEPS:`. The PLC's tag names use
dots and the EPICS names replace them with underscores, so the PLC tag `GV1.Faulted` is the PV
`2bmBLEPS:BLEPS:GV1_FAULTED`.

### Two questions, not one severity scale

BLEPS sorts its signals into warnings, trips and faults, and the PLC ranks them in that order of
loudness. That ranking is not a single scale, which the flow channels show plainly: each of the eight
publishes all three at once. `Flow2.Under_Range_Warning`, `Flow2.Below_Set_Point_Trip` and
`Flow2.Over_Range_Fault` are the same sensor answering different questions.

What separates them is direction. Cooling water is dangerous when it runs low, so a reading off-scale low
is a warning, because it might be true. A reading off-scale high is a fault, because it cannot be: the
transducer is lying. Temperature is the mirror image. Danger is high, so off-scale high warns and
off-scale low faults, since a water-cooled optic cannot read colder than its sensor's span and an
open thermocouple is the likelier explanation.

So the signals answer two separate questions:

| The question | BLEPS classes | Where it lands in CORA |
| --- | --- | --- |
| How bad is the thing being measured? | warning, then trip | a status. For a Supply that is `Degraded`, then `Unavailable`; for an Asset's condition it is `Degraded`, then `Faulted`. The two vocabularies are separate, and no Supply is ever `Faulted` |
| Can the reading be believed at all? | fault, on an instrument | not a status. The reading is set aside, and CORA declines to claim anything |

The reader is warning-aware, mapping a believable warning to `Degraded`
by the same one-is-enough-to-degrade / all-must-clear rule it already
applies to trips, but ships that axis off by default. Nobody has
measured how often BLEPS warnings actually latch at 2-BM, and a channel
that warns routinely would still park its Supply in `Degraded`
semi-permanently, which fails the run-start supply gate. A deployment
flag turns warnings on so that base rate can be observed directly
instead of guessed at.

The second question is why no new status was added to match BLEPS's three classes. A broken flow sensor
is not a worse version of low flow. During an instrumentation fault the honest answer about the cooling
water is that CORA does not know, and "I do not know" is not a rung on a scale that runs from fine to
failed. It is the same fail-closed posture the run pre-flight check already takes when a PV reads back
with bad quality.

### What reads as what

| BLEPS channels | What they observe | CORA reads them as |
| --- | --- | --- |
| `Flow1..8.Below_Set_Point_Trip`, `Flow1..8.Under_Range_Warning` | Cooling water, one circuit each: the filter and upstream slits, M1 and the DMM, the three window groups, the white-beam mask and SBS, the Station B slits, the Station B photon stop | `2-BM cooling water` [Supply](#supplies) status |
| `VS1..7.Trip`, the seven ion-pump and eight ion-gauge warnings | Vacuum, by section and by the instrument reading it | `2-BM beamline vacuum` [Supply](#supplies) status |
| `BIV.Fail_to_Close`, `GV1..3.Faulted` and their nine per-cause flags each | The isolation valve and the three gate valves failing to obey | `2-BM beamline vacuum` [Supply](#supplies) status |
| `Temp1..3.Above_Set_Point_Trip`, `Temp1..3.Over_Range_Warning` | The M1 mirror tank running hot, at its lower, middle and upper thermocouples | `Mirror` Asset condition |
| `FES.Fail_to_Close`, `SBS.Fail_to_Close` | Whether each shutter obeyed its close command | that shutter Asset's condition. BLEPS also publishes their open or closed state, but CORA reads that from the PSS, on [Enclosures](enclosures.md), so one fact keeps one source |
| `Flow1..8.Over_Range_Fault`, `Temp1..3.Under_Range_Fault` | That sensor has stopped making sense | nothing, on purpose. That channel's readings are set aside while the fault stands. A dead tank thermocouple does not mean the mirror is faulty; it means the mirror has lost its over-temperature protection, which is a fact about the sensor |
| `Communications_Fault`, the PLC power and redundancy warnings | The BLEPS system's own health | nothing about the beamline. Every BLEPS reading is set aside while this stands |

Four of those rows are decisions rather than transcriptions, and each follows from what a CORA state is
for rather than from where the PLC draws its own boundary.

The valves are read as vacuum, not as devices of their own. BLEPS owns each valve fault unambiguously, but
CORA registers a thing as an Asset when someone needs its identity: its serial, its history, the record
that it was replaced. Nobody has needed a gate valve's identity here yet, and what a run does need, whether
the vacuum path is intact, is exactly what the valve states say. So `GV2` failing to open degrades the
vacuum Supply and names `GV2` and the cause in doing so. Promote the valves to Assets the first time a
question is asked about one of them across time rather than right now.

The mirror-tank thermocouples go the other way and sit with the device, because three thermocouples on one
tank describe one Asset, not a resource that many Assets draw on. Reading a tank over-temperature as the
`Mirror`'s condition keeps the causal chain legible: `Flow2` is the cooling circuit that serves M1 and the
DMM, so a cooling failure appears as a Supply falling and then, separately, as the mirror it was cooling
running hot. Those are two true facts at two layers, and collapsing them into one would lose which came
first.

Their fault channel is a third fact again, and not a fact about the mirror. `Temp2.Under_Range_Fault` says
the middle thermocouple has stopped reporting a believable number, which usually means an open circuit.
The mirror may be perfectly cold. What has actually happened is that this tank has lost one of its three
over-temperature guards, so CORA sets that channel's readings aside rather than claiming anything about
the optic.

A valve's nine per-cause flags are diagnostics, not states. The overall faulted flag moves the status; the
sub-flag that latched, whether a limit switch disagreed with its twin or the valve never reached its stop,
is the reason recorded with that move. Status vocabularies stay small enough to hold in the head, and the
specifics travel as the reason on the transition.

### The beamline-level state

There is a state operators act on as a whole, and it latches. Three aggregates, `A_FAULT_EXISTS`,
`A_TRIP_EXISTS` and `WARNING_EXISTS`, each go high when anything of that severity latches anywhere in
BLEPS, and the warning stays high after its cause clears until someone resets it. They are the top row of
the operator screen and the glance that decides whether it is worth opening a shutter.

CORA reads them where it already asks that question: the pre-flight check a run makes before it starts.
That check already folds BLEPS, through the composite upstream permit described on
[Enclosures](enclosures.md), and the three aggregates refine it below the permit's threshold. A latched
warning does not withdraw the permit, but it is the difference between a beamline that is ready and one
that is merely allowed to run. The aggregates are read at that instant rather than kept as a state of
their own, for the same reason the shutter states are: they change often, they are always re-readable,
and a history of them would record the interlock's life rather than the experiment's.

The reset commands stay on the floor. They are writes into the interlock, and CORA does not write there.
What CORA does hold is the acknowledgement the reset stands for: a Supply that an observation drove down
does not return to Available on its own, even once the signal reads clear. It waits in `Recovering` for a
person to say it is back. That is the same gesture as the reset button, one layer up, and it is CORA's
record of who accepted the recovery rather than the interlock's record of who cleared the latch.
