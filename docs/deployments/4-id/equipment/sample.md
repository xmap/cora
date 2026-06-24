# Sample

*The diffractometers and sample environment across 4-ID-B / G / H. First cut; PVs read from the beamline config, carried confirm.*

The sample stage at POLAR is not a single endstation but a set of per-station systems: the Huber diffractometers at 4-ID-G that orient a crystal and scan reciprocal space, the polarization analyzer at 4-ID-B, and the sample environment (superconducting magnets, temperature controllers, positioning tables, a pump-probe laser) spread across the experiment stations. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

The diffractometer devices bind the catalog `Goniometer` Family for their sample circles; the composed `Assembly(Diffractometer)` is in the catalog (materialized by the 8-ID Fixture scenario), and a 4-ID Fixture is the follow-on (see [Model](../model.md#deliberately-not-here-yet)). The polarization, magnet, temperature, and laser device classes are bound to loose Family strings, not catalog Families, pending graduation.

## The diffractometers (4-ID-G)

POLAR's diffraction core: a Huber Eulerian-cradle diffractometer and a high-pressure diffractometer. Each orients a single crystal through its circles while the detector records the scattered intensity; the reciprocal-space (h, k, l) coordination runs through hklpy2.

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Diffractometer_Euler` | `Goniometer` | Huber Eulerian cradle; sample x/y/z mapped, circle roles partial (`DIFF-1`) |
| `Diffractometer_HighPressure` | `Goniometer` | high-pressure diffractometer; chi/phi/sample-tilt + x/y/z mapped (`DIFF-1`) |
| `PolarizationAnalyzer` | `PolarizationAnalyzer` (loose) | analyzer crystal stage (th/y) at 4-ID-B; resolves scattered polarization (`POL-2`) |

The circle geometry (4-circle Eulerian versus 6-circle, and which motor is which circle) is `DIFF-1`; it decides the `Assembly(Diffractometer)` slot shape. The reciprocal-space pseudo-axis is `DIFF-2`.

## Sample environment

POLAR's magnetic-scattering signature: applied field and low temperature at the sample, plus a pump-probe laser.

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Magnet_2T_B`, `Magnet_2T_E` | `Magnet` (loose) | 2 T sample magnets at 4-ID-B; control PVs not in the config (`MAG-1`) |
| `Magnet_9T_H` | `Magnet` (loose) | high-field magnet at 4-ID-H (`MAG-1`) |
| `Magnet_Kepco_G` | `Magnet` (loose) | Kepco-driven electromagnet; station a guess (`TOPO-3`, `MAG-1`) |
| `TemperatureController_336/340` | `TemperatureController` (loose) | LakeShore 336 / 340 controllers at 4-ID-G (`TEMP-1`) |
| `SampleTable_B`, `SampleTable_H` | `Table` | per-station sample positioning tables |
| `PumpProbeLaser` | `Laser` (loose) | Ventus laser at 4-ID-H; model-versus-hazard open (`SAMPLE-1`) |
| `SampleSlit_B/G/H` | `Slit` | per-station sample-defining slits |

The high-pressure cell controllers and the preamplifiers that read the sample signal are present in the config but not modelled in this cut (`SAMPLE-2`).

See [Open questions](../questions.md) for the diffractometer, magnet, and laser facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
