# Sample

*The TXM sample stage in 32-ID-C. Design-phase; values are published-doc values carried as confirm.*

The sample stage modelled here is the transmission X-ray microscope (TXM) endstation in `32-ID-C`: a granite-supported stack carrying the tomographic rotation axis and the zone-plate optics that form the magnified image. It is modelled as one sample-stage group in the [descriptor](../inventory.md). The published TXM component list mixes pre-APS-U and current hardware, so every device is carried confirm (`TXM-1`).

Unlike a composed `Microscope` Assembly, the TXM optics are modelled here as a plain device group: the condenser, zone plate, and phase ring are bound to loose Family strings, not catalog Families, because they are device classes CORA has not earned yet and no Asset is registered to earn them (see [Model](../model.md#deliberately-not-here-yet)).

## The model in one picture

The stack, base to sample (containment, `Asset.parent_id`). The precise sub-order firms with the confirmed mechanical layout (`TXM-1`); the tree below is the published-layout intent.

```
32-ID  (Unit, Asset)
└── TXMGranite  (Component, Family Table; granite sample-and-optic support, 32-ID-C)
    ├── Condenser  (Device, loose Family CondenserOptic; conditions the beam onto the sample)
    ├── TXMRotary  (Device, RotaryStage; tomographic rotation)
    │   └── TXMSamplePositioning  (Device, LinearStage; sample centring, co-rotates)
    ├── ZonePlate  (Device, loose Family ZonePlate; objective, forms the magnified image)
    └── PhaseRing  (Device, loose Family PhaseRing; inserted for Zernike phase contrast)
```

## TXM endstation (32-ID-C)

The in-house nano-tomography instrument: a Fresnel zone plate magnifies the transmitted beam onto the [detector](detector.md) while the sample rotates. The condenser shapes the beam onto the sample; the phase ring is inserted for phase contrast.

| Device | Family | Design spec / note |
| --- | --- | --- |
| `TXMGranite` | `Table` | granite stage support carrying the TXM sample system and optics |
| `TXMRotary` | `RotaryStage` | tomographic rotation axis; model and encoder unconfirmed (`TXM-1`) |
| `TXMSamplePositioning` | `LinearStage` | sample centring and alignment stack; axes and travel unconfirmed (`TXM-1`) |
| `Condenser` | `CondenserOptic` (loose) | beam-condensing optic; capillary or condenser zone plate, unconfirmed (`OPTICS-1`) |
| `ZonePlate` | `ZonePlate` (loose) | objective Fresnel zone plate; outermost-zone width and diameter unconfirmed (`OPTICS-2`) |
| `PhaseRing` | `PhaseRing` (loose) | Zernike phase ring; inserted or retracted, details unconfirmed (`OPTICS-3`) |

In-situ environments the published docs anticipate (a furnace, a nano-indenter) are not modelled yet; they join as confirmed equipment, as Fixtures or sample environments once the design firms.

See [Open questions](../questions.md) for the optics and stage facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
