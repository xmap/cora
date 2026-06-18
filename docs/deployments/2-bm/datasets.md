# Datasets

*Data BC Datasets registered at 2-BM.*

A Dataset records an already-existing artifact (URI, checksum, byte size, encoding) plus optional cross-aggregate refs to producing Run, Subject, and a set of upstream Datasets it was derived from. See [Model](../../architecture/model.md) for the aggregate shape.

| Dataset | Producing Run | Subject |
| --- | --- | --- |
| `2BM_dark_baseline_2026-04-17` | | |
| `2BM_flat_baseline_2026-04-17` | | |
| `Proposal_2026-1234_sample_A_tomo` | 1234-A tomography | sample A |
| `Proposal_2026-1234_sample_A_rotation_{01..03}` | 1234-A rotation series (N=3) | sample A · rotation |
| `Proposal_2026-1236_mosaic_tile_{00..03}` | 1236 mosaic tiles (N=4) | wide slab |
| `Proposal_2026-1237_low_energy_25keV` / `..._high_energy_30keV` | 1237 multi-energy Runs (N=2) | iron-bearing core |
| `Proposal_2026-1234_sample_A_streaming_snapshot` | 1234-A streaming | sample A |
| `Sample_of_opportunity_partial_600proj` | sample-of-opportunity (partial) | leftover core |

## Pending

| Dataset | Producing Run | Subject |
| --- | --- | --- |
| Rocking curve | energy-characterization Procedure | channel-cut crystal |
| Vibration baseline ([item_070](https://docs2bm.readthedocs.io/en/latest/source/ops/item_070.html)) | vibration-baseline Run | |
| Reconstructed volume | | |
| Segmentation mask | | |
| Dark-subtracted flat | | |
