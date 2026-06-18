# As-built

*The equipment actually installed at 2-BM: what is on the floor, how it is composed, and its measured state,
distinct from the cross-facility types it instantiates.*

This is where the deployment carries its densest, most beamline-specific content: which vendor Model and serial is
installed, the measured calibration values with their source and status, the containment tree, and any deviation
from the catalog type. Each thing here names the reusable [Catalog](../../catalog/index.md) type it instantiates
and records only this beamline's specifics, so the catalog stays the single source of the generic shape and this
zone stays the single source of the as-built fact. An Asset binds a vendor [Model](../../catalog/models.md) to
fill a [Family](../../catalog/families.md); a Fixture materializes an [Assembly](../../catalog/assemblies.md)
blueprint into specific Assets, the same portable-to-bound move as a Recipe materializing a Method.

## The walk

- [Layout](beamline.md): the equipment walk source to detector, every device with its calibration and condition,
  generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml)
  descriptor so the as-built facts cannot drift from the source.

## The composed fixtures

A Fixture is a composed unit materializing a catalog Assembly into this beamline's hardware:

- [Microscope](equipment/microscope.md): the Optique Peter detector, a `Microscope` Assembly over a reusable
  `Optics` sub-assembly, presenting the `Detector` Role.
- [Sample tower](equipment/sample_tower.md): the sample positioning stack, a `SampleTower` Assembly presenting
  the `Positioner` Role, with the stages held in a containment chain.

## The model view

- [Assets](assets.md): the CORA Asset model view, the flat tree by `parent_id` with each Asset's installed
  settings, vendor Model, and engineering drawings.
- [Computed axes](computed-axes.md): the virtual and derived axes configured on this beamline (the hexapod
  degrees of freedom, the detector-table axes, the energy-tracking optic axes, and the filter-foil selector).
