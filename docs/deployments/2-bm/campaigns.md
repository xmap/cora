# Campaigns

*Campaign BC Campaigns registered at 2-BM.*

A Campaign composes Runs under a coordinated study, proposal-scoped and technique-tagged. See [Model](../../architecture/model.md) for the aggregate shape.

| Campaign | Intent | Runs |
| --- | --- | --- |
| `Proposal 2026-1234 beamtime` | `Coordination` | 1234-A tomography |
| `Proposal 2026-1234 beamtime (degraded)` | `Coordination` | 1234-A tomography (with intervention) |
| `Proposal 2026-1234 continuous-rotation series` | `Series` | continuous-rotation child Run {1..3}/3 |
| `Proposal 2026-1235 beamtime (aborted)` | `Coordination` | 1235-B tomography (aborted) |
| `Proposal 2026-1236 2x2 tile mosaic` | `Coordination` | mosaic tile {0..3} |
| `Proposal 2026-1237 multi-energy contrast study` | `Coordination` | low-energy 25 keV, high-energy 30 keV |

## Pending

| Campaign | Intent | Runs |
| --- | --- | --- |
| Alignment-chain orchestration | `Coordination` | alignment + characterization + Step-1 re-run |
| In-situ / operando study | `Coordination` | |
| Energy sweep (N-point) | `Sweep` | |
| Block-design experiment | `Block` | |
