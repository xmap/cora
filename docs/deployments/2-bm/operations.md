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

2-BM keeps no standing gas-mix or compressed-air Supply: sample gas is per-experiment and ESAF-gated (a
Run-level fact, not a beamline Supply), and compressed air is the APS facility shop-air line with no
beamline-local spec.

The photon beam, cooling water, vacuum, and electrical power are facility-scope utilities, observed through
BLEPS and recorded at the [APS](../aps/index.md#what-this-site-provides) level rather than as beamline
Supplies; the BLEPS-to-Supply mapping is tracked on
[Open questions](questions.md#equipment-protection-bleps).

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

**A finished capture is not a finished file, and this is the fact an ingest reader must respect.** The
end-of-scan sequence stops the file plugin (`FPCapture` to `Done`, then waits for `Capture_RBV` to reach
0), and only *then* calls `add_theta()`, which REOPENS the file in append mode and creates
`/exchange/theta`. A checksum taken when capture completes describes a file that is about to change.
The file is final after the transfer step reports through `ScanStatus` (`fdt file transfer complete` or
`scp file transfer complete`), which is also the point at which the copy on the analysis tier exists.

`add_theta()` also compares the frames actually written against the angles commanded, and logs a warning
naming the missing ones when they disagree. Dropped frames are therefore a known, detected, and
non-fatal condition: a reader that records only what landed will silently under-describe such a scan.

The experiment folder is computed, not conventional, which is what makes it derivable rather than
guessable. `dmagic`'s `dm.py` formats it as `{year_month}-{pi_last_name}-{gup_number}` from APS
scheduling data, and normalises the surname through `clean_entry()`: NFKD normalise, encode to ASCII
discarding what will not encode, then keep only letters, digits, hyphen and underscore. Anything
deriving that folder name independently must reproduce that normalisation exactly or it will miss on
accented and punctuated surnames.
