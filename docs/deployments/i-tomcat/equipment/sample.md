# Sample

*The I-TOMCAT endstation. Modelling exercise; values are read from PSI's public pages.*

The sample stage is the I-TOMCAT endstation (ES2), about 33 m from the source, in the experiment hutch. It is modelled as one sample-stage group in the [descriptor](../inventory.md): an air-bearing rotation stage carrying the sample, a continuous-rotation slip ring, and a sample-side fast shutter. The maximum field of view is about 1.5 x 1.5 mm2. Models named "(target)" are read from the public endstations page, carried unbound until staff confirm them.

Like [TomoWise](../../tomowise/equipment/sample.md) and unlike 2-BM, the sample stage is **not modelled as a catalog Assembly** here: it is a device group, not a composed blueprint. (2-BM models its sample positioning as a `SampleTower` Assembly + Fixture; I-TOMCAT could earn the same once the manipulator firms and a scenario registers it.) So this page carries the containment tree but no Assembly-to-Fixture composition diagram.

## The model in one picture

The kinematic stack, base to sample (containment, `Asset.parent_id`). The precise sub-order firms with staff confirmation (SAMPLE-1); the tree below is the design-layout intent.

```
I-TOMCAT  (Unit, Asset)
└── Rotary  (Device, RotaryStage; air-bearing rotation at ~33 m, master rotation + trigger clock)
    ├── SamplePositioning  (Device, LinearStage; sample centring, co-rotates)
    ├── SlipRing  (Device, SlipRing; continuous-rotation feedthrough)
    └── FastShutter  (Device, Shutter; sample-side, dose limiting)
```

## Endstation (ES2, ~33 m)

The air-bearing rotation stage is the heart of the endstation and the trigger master clock (see [Controls](controls.md)). I-TOMCAT's fast and dynamic 4D tomography depends on continuous rotation through the slip ring paired with the streaming camera.

| Device | Family | Target model | Design spec (public pages) |
| --- | --- | --- | --- |
| `Rotary` | `RotaryStage` | Aerotech ABRX150 (STAGE-1) | air-bearing rotation at ES2 (~33 m), up to ~1500 deg/s; trigger master clock |
| `SamplePositioning` | `LinearStage` | (target) | sample centring / translation on the rotation stage; axis set is SAMPLE-1 |
| `SlipRing` | `SlipRing` | (target) | continuous-rotation feedthrough for endless tomographic acquisition; channel count is SAMPLE-1 |
| `FastShutter` | `Shutter` | (target) | sample-side fast shutter limiting dose between projections |

The legacy TOMCAT offered in-situ sample-conditioning rigs (load frames, furnaces); whether the rebuilt I-TOMCAT carries them is not yet modelled and joins as confirmed (SAMPLE-1).

See [Open questions](../questions.md) for the model bindings still to confirm and [Inventory](../inventory.md) for the Asset tree.
