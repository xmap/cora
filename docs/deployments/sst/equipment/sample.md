# Sample

*The RSoXS (soft) and HAXPES (tender) UHV sample manipulators. First cut; PVs read from the config-driven profile, carried confirm.*

SST has two sample endstations, one per branch: the RSoXS UHV manipulator on the SST-1 soft branch, and the HAXPES UHV manipulator and analyzed-spot slit on the SST-2 tender branch. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

Both manipulators reuse the catalog `Manipulator` Family (SST is the 3rd and 4th UHV manipulator after SIX + ESM); the HAXPES slit reuses `Slit`. No new family is introduced (see [Model](../model.md#what-this-deployment-graduates)).

## The RSoXS sample manipulator (SST-1)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `RSoXSManipulator` | `Manipulator` | RSoXS UHV sample manipulator (x/y/z + yaw); pseudo sample-frame axes on the Manipulator layer (`SAMPLE-1`) |

## The HAXPES sample manipulator (SST-2)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `HAXPESManipulator` | `Manipulator` | HAXPES UHV sample manipulator (x/y/z + theta) (`SAMPLE-1`) |
| `HAXPESSlit` | `Slit` | HAXPES quad slit defining the analyzed spot (`OPT-2`) |

Both manipulators are serial-stack UHV sample manipulators, the same role that graduated the `Manipulator` Family on SIX + ESM; their axis maps, base pressures, and any cryo or sample-transfer mechanisms are `SAMPLE-1`. The HAXPES sample orientation (theta) and the analyzed-spot slit together set what the [electron analyzer](detector.md) sees.

See [Open questions](../questions.md) for the sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
