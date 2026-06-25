# Controls

*The control stack and the metadata / Data Management seam. First cut; handles read from the beamline config, carried confirm.*

9-ID runs on the APS EPICS control stack, the same floor as the 2-BM pilot. CORA observes that floor and, where it replaces Bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own Bluesky instrument repo ([BCDA-APS/9id_bits](https://github.com/BCDA-APS/9id_bits)), so the descriptor carries the real PV prefixes and per-axis maps (`9ida:FMBO:`, `9idCSSI:mcs2-01:`, `9idPyCRL:CRL9ID:`, and so on). They remain confirm-pending: a value read from the operator's config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The metadata and Data Management seam

The instrument config carries a large set of metadata PVs (`experiment_name`, `sample_name`, `file_path`, `qmap_file`, `workflow_name`, `measurement_num`) and a `DM_WorkflowConnector` that hands data to APS Data Management workflows. These are not hardware: they are where the beamline records what an experiment is and routes its data downstream. That is the job CORA's event-sourced system of record does, so they are a seam, not Assets. CORA's Run and experiment record subsume the metadata bookkeeping, and the Data Management workflow trigger is the compute seam CORA's conduct path drives over (see [Model](../model.md#the-metadata-and-data-management-seam)).

## Fly-scan timing

The grazing-incidence fly scans are gated by a multi-channel scaler (`9idCSSI:mcs2-01`), modelled here as a single `GenericProbe`. The full pulse-routing and timing graph is not modelled (`CTRL-2`); it is the most likely first thing to firm up when CORA begins to conduct 9-ID acquisitions.

## Equipment protection

9-ID carries an equipment-protection interlock separate from the personnel PSS, as 2-BM does. CORA does not model the interlock logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
