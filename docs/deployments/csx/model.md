# Model

*The developer's by-kind index: where each CORA aggregate's CSX content lives, the `GratingMonochromator` graduation this deployment earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CSX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the TARDIS hkl `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates

CSX is the **consolidation** deployment for soft X-ray. SIX (NSLS-II 2-ID) introduced `GratingMonochromator` as a loose family at n=1; CSX's VLS-PGM (`XF:23ID1-OP{Mono`, 200-2200 eV) is the **second** independent soft X-ray plane-grating monochromator, which earns the rule-of-three. So `GratingMonochromator` **graduates into the catalog** with this deployment: it becomes a catalog Family that both SIX and CSX bind, with the grating line density and energy range carried as a per-Asset settings difference (the `InsertionDevice` / `Monochromator` precedent), not a Family split. The SIX deployment's references are swept from loose to graduated in the same change. The catalog `Monochromator` (a crystal / multilayer Bragg optic) is deliberately not stretched to cover the grating mono; they are distinct optics. Its naming-r3 review is done.

CSX also **reinforces** an existing abstraction rather than adding one: its TARDIS endstation is an in-vacuum hkl E6C diffractometer whose circles bind the catalog `Goniometer` Family and the composed `Assembly(Diffractometer)`, a third hkl diffractometer after 4-ID and 8-ID (and the first in a soft X-ray, in-vacuum context). No new family is introduced.

## Deliberately not here yet

- **The fine piezo nanopositioner.** CSX carries a piezo nanopositioner for sample / lens fine-positioning; it is deferred (it would fold to `Hexapod` or stay a loose nanopositioner family, an owner call at the point it is modelled).

- **The reciprocal-space solver.** The TARDIS hkl pseudo-axis is modelled as a `PseudoAxis` device; the inverse-kinematics partition rule is `DIFF-2`, deferred (as on 4-ID / 8-ID).

- **The coherent / holography Method.** CSX's defining coherence (the FastCCD coherent-scattering and holography) is carried as a beam-quality enabler and settings on the existing scattering Methods, not coined as its own Method; whether coherent soft X-ray scattering enters the catalog is an owner decision (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_csx_*.py` registers the CSX asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
