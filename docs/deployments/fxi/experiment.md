# Experiment

*The live per-experiment view: subjects, runs, campaigns, datasets, decisions. Described here as the shape CORA would record from FXI's run metadata. CORA is not connected to FXI, so there are no live instances.*

At an operating beamline this page is served by the running app from the live read-API. For FXI it describes the shape, read from the run-metadata header (`RE.md`) and the data layout in the profile collection.

## Subjects

The specimen under study. FXI's run metadata is keyed to a proposal and a data session, not a standing sample registry; the sample identity per run is carried in the run header.

## Runs

A scan session. FXI's `RE.md` (a Redis-backed JSON document) carries, per run: `plan_name`, `plan_args`, the energy `XEng`, `scan_id`, the operator, the zone-plate identity, the storage-ring current `sr_current`, and the proposal / cycle / `data_session`. The run's `exit_status` (`success` / `abort` / `fail`) maps to the CORA Run terminal state (`Completed` / `Truncated` / `Held`, per the run-lifecycle model). The baseline device set recorded at run start and end is `[zp, aper, clens, zps, DetU, XEng, dcm, tm, pbsl, V4, V5, filter1-4]` (`startup/45-baseline.py`): these are the Assets a CORA Run snapshots.

## Campaigns

A multi-run initiative. At NSLS-II this aligns with a proposal and cycle (`data_session = pass-<proposal>`), validated against `api.nsls2.bnl.gov`. CORA would model the proposal/cycle as the Campaign envelope.

## Datasets

The data of record. FXI writes through Tiled (`tiled.nsls2.bnl.gov`, catalog `fxi`, stream `raw`) to `/nsls2/data/fxi-new/proposals/{cycle}/{data_session}/assets/...` (with a legacy `/nsls2/data/fxi-new/legacy/{Andor,Oryx}/...` path also present). CORA references the Tiled resource as the Dataset source-of-record; it does not own the archive. Checksum/integrity is not in the resource docs (DATA-1).

## Decisions

Provenance of choices made during a beamtime (energy, technique, reconstruction parameters). For an autonomous or adaptive run these would be the agent's recorded inferences; FXI's profile collection does not expose a standing autonomous agent, so this is the shape, not an instance.
