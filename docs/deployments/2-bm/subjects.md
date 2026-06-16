# Subjects

*Subject BC Subjects registered at 2-BM.*

A Subject is the sample-or-thing being measured, proposal-anchored at operations phase and kinematic-mounted at acquisition time. See [Model](../../architecture/model.md) for the aggregate shape.

Each Subject runs a custody lifecycle from intake (`Received`) through mount and measurement to a terminal disposition: `Returned` to the PI, `Stored` for a follow-up beamtime, or `Discarded` with an audited reason. The three terminal transitions are exercised by the `test_2bm_subject_returned` / `_stored` / `_discarded` scenarios.

- `porous sandstone core (Proposal 2026-1234, sample A)`
- `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)`
- `porous sandstone core (Proposal 2026-1234, sample A, degraded run)`
- `porous sandstone core (Proposal 2026-1234, sample A, with readings)`
- `porous sandstone core (Proposal 2026-1234, sample A, beam-trip pause)`
- `porous sandstone core (Proposal 2026-1234, sample A, overnight outage)`
- `porous sandstone core (Proposal 2026-1235, sample B, aborted run)`
- `leftover sandstone core (sample-of-opportunity)`
- `wide sandstone slab (Proposal 2026-1236, mosaic acquisition)`
- `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)`

## Pending

- Proposal co-I sample roster
- Calibration phantom (Siemens star, USAF 1951, sphere)
