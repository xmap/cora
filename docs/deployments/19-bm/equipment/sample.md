# Sample

*The 19-BM-FACT in-air endstation. Design-phase; values are FDR design targets, and the manipulator design was out of FDR scope.*

The sample stage sits in air in 19-BM-D. The beamline vacuum terminates at a water-cooled beryllium window (~50 m); a short rough-vacuum section protects that window from oxidation, then a Kapton window transitions to air. In the air gap the sample stage places the specimen in the white beam in front of the [Detector](detector.md).

Unlike the [Detector](detector.md), the sample stage is **not modelled as a catalog Assembly** here: it is a device group, not a composed blueprint. (2-BM models its sample positioning as a `SampleTower` Assembly + Fixture; 19-BM could earn the same once the manipulator firms and a scenario registers it.)

## The model in one picture

The transition to air and the kinematic stack, base to sample (containment, `Asset.parent_id`). The precise sub-order firms with the mechanical design; the tree below is the design-layout intent.

```
19-BM  (Unit, Asset)
└── DEntryWindow  (Device, Window; water-cooled Be, 250 um, ~50 m; vacuum terminus)
    └── KaptonWindow  (Device, Window; transition to air)
        └── SampleRotary  (Device, RotaryStage; tomographic rotation, candidate trigger master)
            └── SamplePositioning  (Device, LinearStage; sample centring; hosts the robotic changer)
```

## Endstation

The workhorse stack: a rotary stage carries the sample for tomographic rotation, with a linear positioning stage for centring. Both are in air. The `SampleRotary` is the candidate trigger master clock (see [Controls](controls.md)). The manipulator design and its model bindings were out of FDR scope and are carried as questions.

| Device | Family | Design spec (FDR) |
| --- | --- | --- |
| `SampleRotary` | `RotaryStage` | tomographic rotation in air; candidate master clock for high-throughput triggering (STAGE-1, TRIG-1) |
| `SamplePositioning` | `LinearStage` | sample centring on the rotation stack; designed to host the robotic sample changer (STAGE-1, ROBOT-1) |

## Robotic sample changer

The endstation is designed to host a robotic sample-changing system: this is what makes 19-BM "Fast Autonomous CT", swapping samples without an operator so the beamline can run a high scan cadence. The detailed design is out of FDR scope, and the FDR records that the changer will undergo a **separate safety review before implementation**.

CORA models this when the design lands (ROBOT-1): the natural shape is one Positioner Asset that loads and unloads `Subject`s (a sample queue), with each load a mount rather than a new Fixture, gated by a Clearance that must be Active, issued after the safety review. None of that is built yet; the seam is reserved, not invented.

See [Open questions](../questions.md) for the stage and changer items still to confirm, and [Inventory](../inventory.md) for the Asset tree.
