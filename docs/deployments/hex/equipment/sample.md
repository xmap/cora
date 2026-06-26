# Sample

*The endstation sample side: the reconfigurable heavy-sample tower, the tomographic rotation, and the sample translations. First cut; the endstation detector PVs are read from the `NSLS2/hex-profile-collection` startup files, the sample-stage PVs are pending, all carried confirm.*

HEX places an engineering component, a working battery, or a bulk sample in the beam in the `hex-endstation` enclosure (the F-hutch, in a satellite building adjacent to Bldg. 742, `ENC-1`, `SAT-1`): for a tomographic scan of its microstructure, an energy-dispersive map of its internal strain and phase, or a powder pattern. The sample side is what makes HEX distinct on the floor: the tower carries up to 500 kg and is fully removable for custom in-situ / operando environments. Every axis here reuses a catalog [Family](../../../catalog/families.md), and nothing on this page coins a new one. They are modelled in the sample stage of the [descriptor](../inventory.md).

## The sample side at a glance

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleTower` | `Table` | the modular sample tower (configs A to D) | carries the specimen, up to 500 kg, fully removable for in-situ environments (`STAGE-1`) |
| `SampleRotation` | `RotaryStage` | the tomographic rotation axis | rotates the sample for tomography (continuous fly) and diffraction (stepped) (`STAGE-1`) |
| `SampleStage` | `LinearStage` | the sample x / y / z translations | positions the specimen and the gauge volume in the beam (`STAGE-1`) |

## The heavy reconfigurable tower

The `SampleTower` is the heart of the HEX sample side, and the place HEX most stresses CORA's model. It is a modular support fixture that carries up to 500 kg and is fully removable, so a user can lift the whole tower out and install a custom in-situ rig in its place. It is configurable, with several documented configurations (configs A to D) and interface plates that adapt it to different loads. This is not a precision goniometer; it is a heavy stage.

CORA holds the line on reuse: the tower binds the catalog `Table` Family (the support-table anatomy the fleet already uses for hutch tables), and its load capacity and configuration set are carried as settings on the Asset, not as a new `HeavyStage` Family. A single fleet beamline with a heavy removable tower does not earn an abstraction; a second one would be the rule-of-three trigger (`STAGE-1`). The tower is named here so the reader knows the heavy-sample affordance is acknowledged and modelled by reuse, not drawn as new structure.

## Rotating and translating the sample

The `SampleRotation` binds the catalog `RotaryStage` Family: it is the tomographic rotation axis, swept continuously for fly-scan computed tomography (the `tomo_flyscan` plan) and stepped for diffraction. The `SampleStage` binds the catalog `LinearStage` Family: the x / y / z translations that position the specimen and, for energy-dispersive diffraction, set where the gauge volume sits inside a bulky sample. The vertical translation is what the `tomo_y_scan_loop` plan steps to stitch a tall sample across several tomographic fields. Which physical axes are motorized and how they map to the logical roles is `STAGE-1`.

## Sample environment

HEX's science is operando: following a working battery or a loaded engineering component in real time. The endstation is described as capable of housing complex sample environments, and the area behind the instrumentation accommodates large processing equipment for custom in-situ work. No specific rig (a load frame, a furnace, a cryostat, a battery cycler) is source-confirmed as installed, however, so in this cut CORA models no in-situ rig as an Asset (`INSITU-1`). When a specific environment is confirmed installed, it lands with the equipment that brings it, and an experiment Clearance would carry its hazard class (see [Governance](../governance.md)). If a second fleet beamline brings a comparable in-situ rig, that is the trigger to consider a sample-environment Family.

## Why no new Family here

The sample side reuses the catalog throughout: `Table` for the tower, `RotaryStage` for the tomographic rotation, and `LinearStage` for the translations. This is reinforcement, not novelty: HEX's tomography is the same shape the 2-BM pilot and the NSLS-II FXI already speak. The one thing that is genuinely distinct, the 500 kg removable tower, is modelled by reuse with capacity as a setting, and the family decision is deliberately held at n=1 (`STAGE-1`). Nothing here graduates and the catalog is unchanged.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family-reuse rationale, and [the source walk](../beamline.md) for the optics that condition the beam onto the sample.
