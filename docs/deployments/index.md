# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

A beamline is never standalone: it sits inside a Site, a Federation `Facility` that owns the clearances, principals, practices, and facility-scope supplies the beamline inherits but does not own. 2-BM's Site is APS; each beamline page links up to it rather than restating it.

Each beamline carries three independent badges, so the one word "status" no longer has to mean three things at once:

- **Maturity** is CORA's relationship to the beamline. `Pilot` means CORA drives it live.
- **Evidence** is where the facts came from, strongest first. `Live` is verified against the running instrument.
- **Coverage** is whether the modelled slice is the whole operational core (`Full`) or a deliberately partial cut (`Partial`).

The badges are read from the descriptor, so the table cannot drift from the model.

CORA has also modeled further beamlines at APS and at other facilities worldwide, from public source, to test that the domain model generalizes: those are not deployments (CORA has no operational relationship with them), so they are not presented here. That corpus lives in the private `xmap/descriptors` repo.

## [APS](aps/index.md)

The Advanced Photon Source (Argonne National Laboratory, near Chicago) is CORA's operational pilot Site. Control plane: EPICS / ophyd.

| Beamline | Maturity | Evidence | Coverage | What it is |
| --- | --- | --- | --- | --- |
| [2-BM](2-bm/index.md) | Pilot | Live | Full | bending-magnet micro-CT, the operational pilot |

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
