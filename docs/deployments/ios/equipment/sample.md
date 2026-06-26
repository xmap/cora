# Sample

*The IOS sample side at the 23-ID-2 endstation: the AP-PES manipulator, the XAS sample stage, the surface-prep ion gun, and the deferred ambient-pressure reaction cell. First cut; PVs read from the profile collection, carried confirm.*

The IOS sample side places the specimen in the focus of the SPECS analyzer for ambient-pressure photoemission, and on the XAS stage for absorption. The positioning that is in the profile collection is modelled as sample-stage groups in the [descriptor](../inventory.md); the ambient-pressure reaction cell that makes IOS operando is not in the profile and is carried as the headline open question (`INSITU-1`).

The manipulator binds the catalog `Manipulator` Family (a further consumer after SIX / ESM / SST / I06); the XAS-endstation translation reuses `LinearStage`; the surface-prep ion gun reuses `GenericProbe`. No new family is introduced (see [Model](../model.md#no-new-families)).

## The sample side at a glance

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleManipulator` | `Manipulator` | AP-PES four-axis stage, x / y / z / rotation (`SAMPLE-1`) |
| `XasSampleStage` | `LinearStage` | single-axis XAS-endstation translation (`SAMPLE-1`) |
| `SputterGun` | `GenericProbe` | SPECS power-supply surface-prep sputter / ion gun (`SAMPLE-2`) |

## The AP-PES manipulator

The APPES manipulator (`XF:23ID2-ES{APPES:1-Ax:{X,Y,Z,R}}Mtr`) carries the sample on three translations plus a rotation, placing it in the analyzer focus. It is the same multi-axis UHV sample-positioning role as the SIX, ESM, and SST manipulators, which is why it reuses the `Manipulator` Family rather than earning a new shape; the axis roles are `SAMPLE-1`. The IOXAS stage (`XF:23ID2-BI{IOXAS:1-Ax:X}Mtr`) is a single-axis translation for the XAS endstation, modelled as `LinearStage`.

## The surface-prep ion gun

The SPECS power supply (`XF:23ID2-ES{SPECS-PS1}`) drives the surface-preparation sputter / ion gun (its mode and degas commands are in the profile). It is an auxiliary that conditions the sample surface, not the analyzer, so it is modelled as a `GenericProbe` rather than folded into the detector (`SAMPLE-2`).

## The ambient-pressure reaction cell (deferred)

What makes IOS operando is measuring under a working gas atmosphere: a reaction cell, gas dosing and mixing, pressure control, and sample heating. The profile collection exposes none of that hardware (no gas, pressure, or temperature PVs), so CORA does not invent it. The ambient-pressure sample environment is carried as the headline open question (`INSITU-1`), to be modelled when the hardware and its PVs are provided. A load-lock gate valve (`IOXAS-GV:4`) is in the profile, but no sample-transfer motor PVs are, so the transfer mechanism is deferred too (`SAMPLE-1`). This is the same discipline the fleet's other in-situ accessories follow: the positioning that exists is modelled, and the sample-environment hardware that is not in the public source is deferred to an open question, not invented.

## Why no new Family here

The sample side is reinforcement, not novelty: the manipulator, the translation stage, and the ion gun all reuse existing catalog Families, and the one genuinely new thing, the ambient-pressure cell, is deferred rather than coined (`INSITU-1`). See [Open questions](../questions.md) for the sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
