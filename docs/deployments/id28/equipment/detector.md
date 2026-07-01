# Detector

*The multi-analyzer IXS spectrometer arm and the counting detectors. First cut; handles read from the BLISS Beacon config, carried confirm.*

ID28 detection is energy-dispersive and arm-borne: a two-theta arm carries an array of inclined analyzer crystals that Bragg-reflect the scattered beam in backscattering to select a fixed analyzed energy, and the energy-analyzed photons are counted per analyzer while the incident energy is scanned. The arm sets the momentum transfer Q, the analyzers fix the analyzed energy, and the incident-energy scan (the [backscattering monochromator](../beamline.md)) reads out the energy loss. They are modelled in the detection stage of the [descriptor](../inventory.md).

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SpectrometerArm` | `SpectrometerArm` | the IXS multi-analyzer spectrometer: a two-theta arm (BLISS `tth_multilayer`, `TwoThetaMultilayer`, `tth` over the `tthm` rail) carrying an array of inclined analyzer crystals (`inca` controllers `a2_inca` / `a3_inca` / `a4_inca`, each chi / th, with analyzer cylinder slits `a1h..a9h` / `a1v..a9v`); a further consumer of the graduated family (`RIXS-1`, `IXS-1`) |
| `Detector` | `Camera` | the Basler / PCO counting and imaging detectors at the spectrometer endstation (BLISS lima `basler_ixs` / `pco`); the per-analyzer photon counters `deta1..deta9` and the `izero` / `ione` beam monitors are on the P201 CT2 cards (`DET-1`) |

The chain reads outward from the sample. The two-theta arm points the analyzer crystals at the scattered beam and sets the magnitude of the momentum transfer through its scattering angle; the inclined analyzer crystals Bragg-reflect a fixed analyzed energy in backscattering and focus the energy-selected photons onto the detectors. Detection is energy-dispersive: the energy-loss axis is built by scanning the incident energy against the fixed-angle analyzers, not by dispersing the beam across a single sensor.

## The spectrometer arm: a further SpectrometerArm consumer

The multi-analyzer arm is the signature ID28 instrument, and it binds the catalog `SpectrometerArm` Family. This is a **further consumer** of the family SIX coined and ID32 brought to a rule-of-three (SIX RIXS arm + ID32 RIXS arm + ID32 XES arm): ID28's arm is the same anatomy, an arm that **positions** an energy-dispersing element (here a crystal array, at SIX / ID32 a grating) and **carries** detectors, presenting the `Positioner` Role, which is why it never fit the point-Sensor families. That sighting reinforced the graduation (`RIXS-1`), which has since landed as a catalog Family; ID28's arm binds it directly.

The arm carries an array of inclined analyzer crystals, each with its own chi / th and its own cylinder slit. The config provisions analyzer slits `a1h..a9h` / `a1v..a9v` (nine positions) and inclined-analyzer (`inca`) controllers for `a2` / `a3` / `a4`; how many crystals are populated is `IXS-1`. The first cut carries the array as a per-Asset setting on the one `SpectrometerArm` Asset; promoting each crystal to a child Asset via `parent_id` is the nested-component-identity convention (the IXS 10-ID diced-crystal question is the sibling), so ID28 flags `IXS-1` rather than asserting it.

## Why no new family

The detection side coins no new Family. The arm reuses the catalog `SpectrometerArm`; the Basler / PCO detectors reuse the catalog `Camera`. The genuinely new modelling at ID28 is not a device class but the further sighting of `SpectrometerArm`, which reinforced the graduation that has since landed.

## Families

Reused from the catalog: `SpectrometerArm` (the multi-analyzer arm, graduated across SIX + ID32 RIXS/XES + ID28, `RIXS-1`, `IXS-1`) and `Camera` (the Basler / PCO detectors). The backscattering monochromator and incident-energy axis the arm reads against live on the [Source](../beamline.md) walk; the sample stage and cryostats on the [Sample](sample.md) side. See [Inventory](../inventory.md) for the Asset tree and [Model](../model.md) for the graduation plan.
