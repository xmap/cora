# Detector

*The 19-BM-FACT indirect-detection imaging system, and the downstream beam stops. Design-phase; the detector hardware is procured after the FDR.*

19-BM records 2-D projections with an indirect-detection system: a scintillator converts the transmitted X-ray image to visible light, visible-light microscope optics relay it, and a camera captures the frames, which are reconstructed off-line into 3-D micron-resolution tomograms. The system sits in air, downstream of the sample in 19-BM-D.

The specific scintillator, microscope optics, and camera are chosen after the FDR (DET-1); the shapes below are the design intent.

## The model in one picture

What holds what, downstream of the sample (containment, `Asset.parent_id`):

```
19-BM  (Unit, Asset)
└── DetectorStage  (Component, Family Table; positions the system in air)
    └── Microscope  (Component, Family Housing; anchors the Microscope Assembly, presents the Detector Role)
        ├── Scintillator  (Device, Scintillator; X-ray to visible)
        └── Camera        (Device, Camera; records projections)
```

The microscope chassis is a `Housing` that anchors the cross-facility `Microscope` Assembly, the same blueprint 2-BM uses: a scintillator and visible-light optics presenting the Detector Role. The `Microscope` itself is an Assembly, not a Family, so the chassis binds the `Housing` Family (matching 2-BM and TomoWISE). No Fixture is registered yet (19-BM is design-phase, and no scenario binds Assets to slots), so this is the planned composition, not a materialized Fixture.

## Detector

| Device | Family | Design spec (FDR) |
| --- | --- | --- |
| `DetectorStage` | `Table` | positions the indirect-detection system in air, downstream of the sample; axis layout TBD |
| `Scintillator` | `Scintillator` | converts the X-ray projection to a visible-light image; selection TBD (DET-1) |
| `Microscope` | `Housing` (Microscope Assembly) | visible-light relay optics chassis presenting the Detector Role; selection TBD (DET-1) |
| `Camera` | `Camera` | records 2-D projections for off-line reconstruction; selection TBD (DET-1) |

## Downstream beam stops

At the downstream wall of 19-BM-D, the white beam is absorbed and the station is shielded to the standard required for a white-beam BM station.

| Device | Family | Design spec (FDR) |
| --- | --- | --- |
| `PhotonStop` | `BeamStop` | A359-M100, water-cooled copper; water in series with the upstream Be window, BLEPS-monitored |
| `BremsstrahlungStop` | `BeamStop` | A359-K3, chevron stack of lead bricks, behind the photon stop |
| `DownstreamGuillotines` | `Shielding` | two movable Pb guillotines (>= 12 mm each), the 1 x 1 m2 extra-lead area required by APS TB-44; one held open during operation |

## Families

The active detector families are reused, none new: `Table` (the detector stage), `Housing` (the microscope chassis), `Scintillator`, and `Camera`, composed through the cross-facility `Microscope` Assembly. The beam stops reuse the catalog `BeamStop` Family (graduated under the passive beam-path tier); the guillotines bind the loose `Shielding` family, which renders as plain text (not yet in the catalog).

The detector hardware selections and the trigger path are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
