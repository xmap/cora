# The beamline

*The 2-BM beamline as five areas you can jump to: the three stations the beam passes through, plus the controls that drive them and the resources they draw on.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stations**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample_tower.md) stack that places the specimen in it, and the [Detector](microscope.md) that records what comes through. Cutting across all three are the two shared concerns: the [Controls](controls.md) that drive the hardware, and the [Resources](../operations.md#supplies) the beamline draws on.

The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right. So the list reads as one row of peers, but the first three share an axis the last two cross.

## Stations

- [Source](../beamline.md): the front-end optics that deliver and condition the beam, mirror through monochromator, slits, and filters.
- [Sample](sample_tower.md): the positioning stack that places and rotates the specimen, a `SampleTower` Assembly presenting the `Positioner` Role.
- [Detector](microscope.md): the imaging system that records the beam, a `Microscope` Assembly presenting the `Detector` Role.

## Shared

- [Controls](controls.md): the controllers and drive crates, and the trigger wiring that links them across stations.
- [Resources](../operations.md#supplies): the continuously-available supplies a run needs, beam, cooling, and vacuum among them.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full CORA Asset model view (every device as a flat tree by `parent_id`, with settings, vendor Models, drawings, and signal wiring) and the computed axes.
