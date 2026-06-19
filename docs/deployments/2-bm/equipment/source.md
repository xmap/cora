# Source

*The 2-BM beam-delivery side: the front-end optics that take the bending-magnet beam and condition it for the experiment. A concept page; the detailed model lives in the Reference tables until the source model settles.*

The source area covers everything between the bending magnet and the sample: the white-beam mirror, the monochromator, the conditioning and sample slits, the absorber-foil filter, and the diagnostic flag. At 2-BM these sit in the optics hutch `2-BM-A` (the sample slits in `2-BM-B`), and all of them are driven by the `FrontEndDrive` controller.

## Why this is not a Fixture page

The [Sample](sample_tower.md) and [Detector](microscope.md) pages each document a Fixture: a cross-facility Assembly that presents a functional Role (`Positioner`, `Detector`). The source side has no such Assembly. Its devices are modelled as a flat set of `Device` Assets hanging off the `2-BM` Unit, each driven by `FrontEndDrive`, not as a cluster that presents a Role.

The reason is in the Role model. The candidate `Conditioner` Role (attenuators, shutters, mirrors) was deferred because no affordance is universally required across those Families, so the contract would be empty (see [the Catalog](../../../catalog/index.md)). A mirror, a slit, and a filter share no common primitive verb, so there is no Role to present and no Fixture to build.

What the source *does* is modelled where it belongs instead: setting energy and switching beam mode are coordinated moves on the [Procedures](../procedures.md) page, and the energy-tracking optic positions are virtual axes on the [Computed axes](../computed-axes.md) page.

## Where the source is documented today

- [Layout](../beamline.md): the source-to-detector walk, generated from the descriptor.
- [Assets](../assets.md): the front-end optics in the inventory, with their Families, Models, and settings.
- [Computed axes](../computed-axes.md): the energy-tracking optic axes (the Bragg arms, the beam-offset compensator, and slit tracking).
- [Procedures](../procedures.md): beam modes (Mono and Pink) and the set-energy coordinated move.

## Open items

The source model is still settling; the [Open questions](../questions.md) page tracks the energy, mirror-stripe, filter-foil, and monochromator-stripe items. This page becomes a full model walk, like the Sample and Detector pages, once those resolve and a beam-delivery Assembly or `Conditioner` Role earns its place.
