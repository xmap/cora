# Sample

*The RIXS sample diffractometer and the XMCD high-field-magnet sample environment. First cut; handles read from the BLISS Beacon config, carried confirm.*

ID32 has two sample sides, one per endstation. At the RIXS endstation a 4-circle diffractometer orients the specimen and sets the scattering geometry; at the XMCD endstation the specimen sits inside a 9 Tesla superconducting magnet on a variable-temperature insert. They are modelled in the sample stage of the [descriptor](../inventory.md).

## The RIXS endstation (id32-rixs)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Diffractometer` | `Goniometer` | 4-circle sample diffractometer (BLISS `DiffE4CH`, E4CH geometry); the circle roles and the `Assembly(Diffractometer)` binding are `DIFF-1` |
| `ReciprocalSpace` | `PseudoAxis` | reciprocal-space (hkl) axis over the diffractometer; the inverse-kinematics rule deferred (`DIFF-2`) |

The diffractometer binds the catalog `Goniometer` Family, the same sample-orientation anatomy the fleet's other diffractometers use; the reciprocal-space layer binds a `PseudoAxis`, and whether the diffractometer plus the spectrometer arm compose an `Assembly(Diffractometer)` Fixture is named, not built, exactly as the other diffractometer beamlines deferred theirs (`DIFF-1`). The scattered-beam polarimeter and the dispersive spectrometer arm that read this geometry live on the [Detector](detector.md) side.

## The XMCD endstation (id32-xmcd)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Magnet` | `Magnet` | the 9 T / 4 T split-coil superconducting XMCD magnet (`id32/cryogenic_magnet_ps/xmcd1`), the field a settable axis presenting the `Regulator` Role; the third `Magnet` consumer that completed the rule-of-three, graduated Family (`MAG-1`) |
| `SampleTemperatureController` | `TemperatureController` | the VTI sample-temperature LakeShore 336 (`id32/regulation/ls336_hfm`); the He needle valve folds into this cryostat regulation (`TEMP-1`) |
| `CryostatDiagnostics` | `TemperatureController` | the magnet-cryostat diagnostic LakeShore 340 (`id32/regulation/ls340_hfm`): the coil, shield, and helium-reservoir temperatures (`TEMP-1`) |
| `SampleStage` | `LinearStage` | the XMCD sample-positioning stage in the magnet bore (`SAMPLE-1`) |

The 9 T magnet is the sample environment that defines the XMCD endstation, and it binds the graduated `Magnet` Family: it is the third consumer (after 4-ID and i10-1), so with ID32 the family reached a rule-of-three and **graduated** into the catalog (`MAG-1` now covers only the per-Asset field detail); the field setpoint reads as a settable axis presenting the `Regulator` Role. Two LakeShore controllers bind the graduated `TemperatureController` Family: the 336 regulates the VTI sample temperature (the helium needle valve folds into it), and the 340 monitors the superconducting-coil, shield, and reservoir temperatures of the cryostat (`TEMP-1`). The sample stage in the magnet bore binds `LinearStage` (`SAMPLE-1`).

## Why mostly reuse, and what is held

The sample side coins no new Family. The diffractometer is a `Goniometer`, the temperature controllers reuse the graduated `TemperatureController`, and the sample stage reuses `LinearStage`. The 9 T `Magnet` reuses the family 4-ID and i10-1 already carry, the third consumer that brought it to a rule-of-three and graduated it into the catalog (`MAG-1`). The XES emission spectrometer arm at this endstation, and the RIXS arm and polarimeter, are detection devices on the [Detector](detector.md) side.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, and [Model](../model.md) for the loose-family graduation plan.
