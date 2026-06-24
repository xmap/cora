# Sample

*The sample-scanning stack in the 2-ID-D hutch. Design-phase; values are EAA-corpus inferences carried as confirm.*

The sample stage modelled here is the moving heart of the microprobe: the sample is rastered through the focused spot while the [detector](detector.md) reads a fluorescence spectrum at each point. It is modelled as one sample-stage group in the [descriptor](../inventory.md). EAA's `aps_mic` integration evidences a vertical raster axis (`samy`) and a standoff axis (`samz`); the full axis complement is carried coarse and confirm (`AXIS-1`).

Unlike the 2-BM sample tower or a composed Assembly, the stack is modelled here as a single coarse positioning device, because the EAA corpus does not give the axis-by-axis breakdown a real microprobe carries (typically a coarse XYZ stage plus a fine piezo raster stage). The fine-versus-coarse split firms with the confirmed mechanical layout.

## The model in one picture

The stack, base to sample (containment, `Asset.parent_id`). The precise sub-order and the coarse/fine split firm with the confirmed layout (`AXIS-1`); the tree below is the EAA-evidenced intent.

```
2-ID  (Unit, Asset)
└── SamplePositioning  (Device, LinearStage; sample-scanning stack in 2-ID-D)
        samy  (vertical raster axis, evidenced)
        samz  (standoff axis, evidenced)
        horizontal scan axis  (inferred, AXIS-1)
```

The probe-forming zone plate that the sample scans beneath is modelled on the [Source](../beamline.md) walk (it conditions the beam), not here, even though it sits in the same hutch.

## Sample-scanning stack (2-ID-D)

The sample moves through the focused spot in a 2D fly raster (`fly2d`) or a 1D step scan (`step1d`); dwell per point is short (EAA carries 0.05 to 0.2 s defaults). The stage is what CORA's Conductor drives during a scan, taking the sequencing EAA's `scan_control` holds today.

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SamplePositioning` | `LinearStage` | sample-scanning stack; vertical raster (`samy`) and standoff (`samz`) evidenced, horizontal scan axis and coarse/fine piezo split unconfirmed (`AXIS-1`) |

A sample environment (an in-situ cryo or heating stage) and a rotation axis are not modelled: EAA evidences neither, and the rotation axis that scanning fluorescence tomography would need is carried as `ENV-1`. They join as confirmed equipment, as Fixtures or sample environments, once the design firms.

See [Open questions](../questions.md) for the axis and sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
