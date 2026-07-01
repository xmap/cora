# Sample

*The IXS sample-positioning stage and the sample-temperature environments. First cut; handles read from the BLISS Beacon config, carried confirm.*

The ID28 sample side places the specimen in the meV-resolution beam at the eh1 spectrometer endstation and conditions its temperature, typically deep cryogenic for phonon studies. It is modelled in the sample stage of the [descriptor](../inventory.md); the multi-analyzer spectrometer arm that energy-analyzes the scattered beam lives on the [Detector](detector.md) side.

## The sample stack (id28-eh1)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleStage` | `LinearStage` | the IXS scattering-geometry sample stage (BLISS `sax` / `say` / `saz` translations, `th` / `sphi` / `chi` rotations, the eh1_ss IcePAP `iceid285` `phi` / `omega` / `sz`, and the SmarAct MCS2 fine stage); the precise axis-to-Asset map is `SAMPLE-1` |
| `SampleSlit` | `Slit` | the sample-defining slits (BLISS `slits_sh` / `slits_sv`, horizontal + vertical gap and offset) (`OPT-2`) |
| `SampleTemperatureController` | `TemperatureController` | the 10 K displex cryostat LakeShore 340 (BLISS `lakeshore340_10kdiplex`); the Oxford 700 cryostream and the nanodac gas blower are the alternative environments (`TEMP-1`) |

The sample stage binds the catalog `LinearStage` Family, the positioning anatomy the fleet's sample stacks reuse; the config exposes the scattering-geometry translations and rotations on the main goniometer, a side-station IcePAP, and a SmarAct fine stage, so the precise axis-to-Asset map is `SAMPLE-1`. The sample-defining slits bind the catalog `Slit` Family (`OPT-2`). The sample temperature is regulated by one of three environments, all binding the graduated `TemperatureController` Family (presenting the `Regulator` Role): the 10 K displex closed-cycle cryostat (the deep-cryogenic default for phonon work), the Oxford 700 cryostream, and the nanodac gas blower for elevated temperatures. Which is mounted for a given experiment, and the displex base temperature, is `TEMP-1`.

## Why no new family here

The sample side coins no new Family. The positioning stage is an ordinary `LinearStage`, the sample slits are catalog `Slit` Assets, and the three temperature environments are settable thermal regulators (`TemperatureController`), the same shapes the fleet already carries. The genuinely distinct instrument at ID28, the multi-analyzer spectrometer arm, is a detection device on the [Detector](detector.md) side, where it binds the catalog `SpectrometerArm` family (graduated).

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, and [Model](../model.md) for the modelling decisions.
