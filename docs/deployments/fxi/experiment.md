# Experiment

*CORA's Experiment model landing on FXI: the subjects, runs, campaigns, datasets, and decisions CORA would record for a beamtime. Described here as shape; CORA is not yet running FXI, so there are no live instances.*

At an operating beamline this page is served by the running app from the live read-API. For FXI it describes what CORA's Experiment BC would capture.

## Subjects

The specimen under study, recorded as a CORA Subject with its custody and history. The sample identity per run is carried on the Run.

## Runs

A scan session is a CORA Run. CORA records the conduct (what was run, by whom, against which Assets) and the provenance, with terminal states `Completed`, `Truncated`, or `Held`. The Assets a Run snapshots at start and end are the source-stage and sample-stage devices in the [Inventory](inventory.md) (the beam delivery, the sample stage and rotary, the optics, and the detector).

## Campaigns

A multi-run initiative. CORA maps this to the NSLS-II proposal and cycle (the facility's beamtime unit), so a proposal/cycle is one Campaign envelope over its Runs.

## Datasets

The data of record. CORA records its own Dataset for each Run within its Experiment model; the data-of-record store is CORA's, not the facility's. The raw frames the detector produces land on the facility filestore (floor); CORA's Porter (the TransferPort edge runtime) handles egress from there into the CORA Dataset and its lineage. CORA references where the frames physically sit; it does not depend on the facility's catalog as its own system of record.

## Decisions

Provenance of the choices made during a beamtime: energy, technique, reconstruction parameters, and any alignment or center-finding outcome. For an autonomous or adaptive run, these are the agent's recorded inferences, governed by the [trust boundary](governance.md#the-trust-boundary). FXI has no standing autonomous agent today, so this is the shape, not an instance.
