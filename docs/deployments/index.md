# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

A beamline is never standalone: it sits inside a Site, a Federation `Facility` that owns the clearances, principals, practices, and facility-scope supplies the beamline inherits but does not own. The deployments below are grouped by that Site; each beamline page links up to its Site rather than restating it. CORA's operational pilot is 2-BM; the rest are in the design phase, modelled from a design report ahead of construction or recommissioning, so their pages describe an intended shape, not a running instrument.

## [APS](aps/index.md)

CORA's first multi-beamline Site: four beamlines share one APS envelope, which is reused rather than re-created per beamline.

| Beamline | Status | What it is |
| --- | --- | --- |
| [2-BM](2-bm/index.md) | Pilot | bending-magnet micro-CT, the operational pilot |
| [7-BM](7-bm/index.md) | In design | multi-technique flow and combustion imaging, recommissioned for APS-U |
| [19-BM](19-bm/index.md) | In design | bending-magnet autonomous high-throughput tomography |
| [32-ID](32-id/index.md) | In design (partial) | canted multi-instrument: optics spine and transmission X-ray microscope |

## [MAX IV](maxiv/index.md)

The second Site CORA models; thin while its beamline is in design.

| Beamline | Status | What it is |
| --- | --- | --- |
| [TomoWise](tomowise/index.md) | In design | micro- and nano-tomography, Technical Design Report phase |

## [Diamond Light Source](diamond/index.md)

The third Site CORA models, and a deliberate off-roadmap exercise: a real, operating beamline modelled from Diamond's open `dodal` controls library to test that the dry-fact seed feeds CORA's intentional model, and that the model generalizes beyond tomography (SCOPE-1).

| Beamline | Status | What it is |
| --- | --- | --- |
| [I22](i22/index.md) | Modelling exercise | small- and wide-angle X-ray scattering (SAXS/WAXS), reverse-engineered from dodal |

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
