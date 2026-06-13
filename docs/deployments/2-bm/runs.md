# Runs

*Run BC Runs registered at 2-BM.*

A Run is the operator-started execution of a Plan, typically against a Subject (calibration runs such as dark-field and flat-field execute without one). Runs are composed by [Campaigns](campaigns.md) and produce [Datasets](datasets.md). See [Model](../../architecture/model.md) for the aggregate shape.

| Run | Subject | Campaign |
| --- | --- | --- |
| `Proposal 2026-1234 sample A tomography (first proposal scan)` | [sample A](subjects.md) | [1234 beamtime](campaigns.md) |
| `Proposal 2026-1234 sample A tomography` | sample A | 1234 beamtime |
| `Proposal 2026-1234 sample A tomography (with reading logbook)` | sample A · readings | 1234 beamtime · readings |
| `Proposal 2026-1234 sample A tomography (with beam-trip pause)` | sample A · paused | 1234 beamtime · paused |
| `Proposal 2026-1234 sample A overnight tomography` | sample A · outage | 1234 beamtime · outage |
| `Proposal 2026-1234 sample A streaming tomography` | sample A | 1234 beamtime |
| `Proposal 2026-1234 sample A tomography (with intervention)` | sample A · degraded | 1234 beamtime · degraded |
| `Proposal 2026-1235 sample B tomography (aborted on hexapod fault)` | sample B · aborted | 1235 beamtime · aborted |
| `Sample-of-opportunity tomography (planning 1500 projections)` | leftover core | sample-of-opportunity scan |
| `mosaic tile {0..3}` (N=4) | [wide slab](subjects.md) | [1236 2x2 mosaic](campaigns.md) |
| `continuous-rotation child Run {1..3}/3` (N=3) | sample A · rotation | [1234 rotation series](campaigns.md) |
| `Proposal 2026-1237 low-energy tomography (25 keV)` | [iron-bearing core](subjects.md) | [1237 multi-energy](campaigns.md) |
| `Proposal 2026-1237 high-energy tomography (30 keV)` | iron-bearing core | 1237 multi-energy |

## Pending

| Run | Subject | Campaign |
| --- | --- | --- |
| Operator-decision `Aborted` Run | | |
| Alignment-chain composed Runs | | alignment-chain Coordinated Campaign |
| Energy-calibration Run | | |
| Vibration-baseline Run | | |
