# Open questions

*What CORA needs the I13-1 team to confirm before the model can be trusted.*

I13-1 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal), `src/dodal/beamlines/i13_1.py`), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. This is a **deliberately partial** first cut: dodal currently exposes only the coherence-branch endstation, so the shared I13 source and optics are deferred, not invented. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Is I13-1 its own experiment hutch, and how does it relate to the I13-2 imaging branch and the shared I13 source? | One `i13-1` experiment hutch on the `BL13J` prefix. | The Enclosure grouping. |
| SRC-1 | Blocks-go-live | The shared I13 undulator source, absent from the i13_1 dodal module. | An undulator upstream, not modelled in this partial cut. | The source Asset. |
| OPT-1 | Blocks-go-live | The shared I13 optics (monochromator, mirrors, slits), absent from the i13_1 dodal module. | Shared optics upstream, not modelled in this partial cut. | The optics Assets. |

## Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The piezo sample-scanning stage axes, and the fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`): one stage with two reference frames or two stages? | One `LinearStage` (the ptychography raster); the fixed-angle frame a setting on the same stage. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The Merlin (Medipix3) detector configuration and the side viewing camera role. | The Merlin and the side camera bind `Camera`; the Merlin is the coherent-diffraction science detector. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the i13_1 dodal module). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| MACHINE-1 | Nice-to-have | The storage-ring state I13-1 reads. | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| SUP-1 | Nice-to-have | The vacuum extent of the coherent-beam path. | Photon beam, cooling water, and vacuum on the flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does ptychography / coherent diffraction imaging enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice; the fleet's first coherent diffractive imaging, no `cora.capability.ptychography` coined. | The ptychography Capability. |
