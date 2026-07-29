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
`tomdet` (`/local1`), tomoscan auto-uploads each scan to the analysis tier (`/data2` or `/data3`), tomocupy
reconstructs there (`..._rec/` beside the raw), and an operator copies the experiment to its canonical home on
Sojourner (`/gdata/dm/2BM/<yyyy-mm>/<exp>/{data,analysis,system}/`), shared to proposal and ESAF users through
the Globus collection `APS:DM:2BM` and archived to tape on a per-experiment timer (default one year). The
upstream tiers are transient, capacity-purged with no fixed schedule, so a dataset is briefly multi-homed and
then collapses to the Sojourner copy; there is no continuous beamtime-long sync. The reconstruction compute
resource itself is not yet pinned to a specific host or pool.

### Inside the scan file

Read from the upstream source rather than assumed: [tomoscan](https://github.com/decarlof/tomoscan)'s
2-BM subclass and [dmagic](https://github.com/decarlof/dmagic). Every scan product is HDF5; no
acquisition path writes TIFF.

The layout is Data Exchange. `tomoscan_2bm.py` addresses the datasets by name when it post-processes a
finished scan: `/exchange/data` (projections), `/exchange/data_white` (flats), `/exchange/data_dark`
(darks), and `/exchange/theta` (rotation angles). Frame bookkeeping lives in `/defaults/NDArrayUniqueId`
and `/defaults/HDF5FrameLocation`. Per-scan files follow the areaDetector template `%s%s_%3.3d.h5`, so a
scan basename carries a three-digit counter, and `..._rec/` reconstruction directories are named from it.

The file has a second author besides tomoscan: the areaDetector layout XML configured in the detector
IOC writes everything under `/process`, `/measurement`, and `/defaults` (public copy:
[`data-exchange/dxfile/doc/demo/areadetector/2-BM/`](https://github.com/data-exchange/dxfile/tree/master/doc/demo/areadetector/2-BM)).
Two of its facts matter to a reader. The commanded scan geometry
(`/process/acquisition/rotation/num_angles`, the flat and dark field mode-and-count groups) is written
`OnFileClose`, so it exists only in cleanly closed files, and it is what a shortfall check compares
captured frames against; the `/defaults` frame ids alone can never show tail truncation, because a
missed trigger never receives an id. The acquisition timestamp (`/process/acquisition/start_date`, from
the PV `S:IOC:timeOfDayISO8601`) is written `OnFileOpen`, so a crashed file keeps its timestamp while
losing its geometry.

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

Every latching fault names either a shared utility or one device, which is the boundary CORA reads them
across:

| BLEPS channels | What they observe | CORA reads them as |
| --- | --- | --- |
| `FLOW1_TRIP` to `FLOW8_TRIP` | Cooling water, one circuit each: the filter and upstream slits, M1 and the DMM, the three window groups, the white-beam mask and SBS, the Station B slits, the Station B photon stop | `2-BM cooling water` [Supply](#supplies) status |
| `VS1_TRIP` to `VS7_TRIP`, the seven ion-pump and eight ion-gauge channels | Vacuum, by section and by the instrument reading it | `2-BM beamline vacuum` [Supply](#supplies) status |
| `BIV_*`, `GV1_*`, `GV2_*`, `GV3_*` | The isolation valve and the three gate valves, each with an overall faulted flag and nine per-cause flags | `2-BM beamline vacuum` [Supply](#supplies) status |
| `TEMP1_TRIP` to `TEMP3_TRIP` | The M1 mirror tank running hot, at its lower, middle and upper thermocouples | `Mirror` Asset condition |
| `FES_*`, `SBS_*` | The front-end and station shutters: whether each obeyed its close command, and its interlock permit | that shutter Asset's condition. BLEPS also publishes their open or closed state, but CORA reads that from the PSS, on [Enclosures](enclosures.md), so one fact keeps one source |
| `COMMUNICATIONS_FAULT`, the PLC power and redundancy warnings | The BLEPS system's own health | evidence that a BLEPS reading cannot be trusted, not a fault of the beamline |

Three of those rows are decisions rather than transcriptions, and each follows from what a CORA state is
for rather than from where the PLC draws its own boundary.

The valves are read as vacuum, not as devices of their own. BLEPS owns each valve fault unambiguously, but
CORA registers a thing as an Asset when someone needs its identity: its serial, its history, the record
that it was replaced. Nobody has needed a gate valve's identity here yet, and what a run does need, whether
the vacuum path is intact, is exactly what the valve states say. So `GV2` failing to open degrades the
vacuum Supply and names `GV2` and the cause in doing so. Promote the valves to Assets the first time a
question is asked about one of them across time rather than right now.

The mirror-tank thermocouples go the other way and sit with the device, because three thermocouples on one
tank describe one Asset, not a resource that many Assets draw on. Reading them as the `Mirror`'s condition
keeps the causal chain legible: `FLOW2` is the cooling circuit that serves M1 and the DMM, so a cooling
failure appears as a Supply falling and then, separately, as the mirror it was cooling running hot. Those
are two true facts at two layers, and collapsing them into one would lose which came first.

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
