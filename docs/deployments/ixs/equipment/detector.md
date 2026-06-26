# Detector

*The six-circle spectrometer arm, the diced crystal energy analyzer, its thermal stabilization, and the counting detectors. First cut; PVs read from the profile collection, carried confirm.*

IXS detection is momentum-resolved and energy-analyzed, not imaging: a six-circle scattering arm carries a fixed diced crystal analyzer that Bragg-reflects the scattered beam to select a single final energy, focusing the energy-selected photons onto point detectors that integrate the current. The arm sets the momentum transfer Q, the analyzer fixes the final energy, and the incident energy is scanned upstream (the DCM and the high-resolution monochromator) to build I(Q, energy-loss). They are modelled in the detection stage of the [descriptor](../inventory.md).

The spectrometer arm reuses the catalog `Goniometer` Family (the 8-ID / 4-ID six-circle diffractometer anatomy, driven by the reciprocal-space `PseudoAxis`); the crystal analyzer binds a loose `EnergyAnalyzer` Family (no catalog or loose Family fits a driven diced-crystal Bragg analyzer, see [Model](../model.md#new-loose-families)); its thermal stabilization reuses the catalog `TemperatureController`; and the counting detectors reuse `FluxMonitor`.

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Spectrometer` | `Goniometer` | six-circle scattering arm (`2Th` / `Th` / `ChiA` / `PhiA`); the scattering angle `two_theta` sets `\|Q\|`, driven by the reciprocal-space pseudo-axis (`ANALYZER-1` for the Assembly question) |
| `ReciprocalSpace` | `PseudoAxis` | six-circle H / K / L reciprocal-space axis over the arm via the SixCircle kinematics; the derived angles present a Sensor read-back facet (`ENERGY-1`) |
| `EnergyAnalyzer` | `EnergyAnalyzer` (loose) | diced crystal Bragg energy analyzer, six diced crystals d1-d6, each with theta / phi and PID temperature; selects a fixed final energy (`ANALYZER-1`, `XTAL-1`) |
| `AnalyzerSlit` | `Slit` | analyzer-chamber beam-defining slit (top / bottom / inboard / outboard) (`OPT-2`) |
| `AnalyzerThermalControl` | `TemperatureController` | per-crystal PID thermal stabilization for energy stability, six PID channels (`TEMP-1`, `XTAL-1`) |
| `AnalyzerElectrometers` | `FluxMonitor` | quad electrometers reading the energy-analyzed scattered signal as a scalar current, the science point detector (`DET-1`) |
| `IncidentScaler` | `FluxMonitor` | counting scaler; the I0 channel is the incident-flux monitor for normalization (`DET-1`) |

The chain reads outward from the sample. The six-circle arm points the analyzer at the scattered beam and sets the magnitude of the momentum transfer through its scattering angle, with the reciprocal-space pseudo-axis driving the four angles together so a run can step in H / K / L. The analyzer then selects one final energy and focuses the energy-selected photons onto photodiodes, which the quad electrometers read as a current; the scaler I0 channel records the incident flux for normalization. Detection is point and current-integrating, so there is no area detector and no per-pixel readout: the energy axis is built by scanning the incident energy, not by dispersing the beam across a sensor. The channel map, and whether the analyzer-focus photodiode is a separate Asset or just an electrometer channel, is `DET-1` (default: a channel).

## The crystal energy analyzer

The energy analyzer is the signature IXS instrument and the one device class no existing Family covers. It is a diced multi-crystal Bragg analyzer: six diced crystals, each carrying its own theta / phi orientation and PID temperature stabilization, that reflect the scattered beam to a fixed final energy. No catalog or loose Family fits this anatomy. It is not the catalog `EnergyDispersiveSpectrometer` (a per-event point Sensor that reads energy, where here the analyzer positions crystals and the reading happens downstream at the electrometers), nor the catalog `Monochromator` (an upstream incident-beam optic), nor SIX's loose `SpectrometerArm` (a soft X-ray energy-dispersive arm, where IXS uses a driven scanning crystal analyzer rather than a dispersive one).

So it is coined as one loose `EnergyAnalyzer` Family, held **at n=1** and graduating nothing: a second independent hard crystal-analyzer beamline must earn the abstraction before any catalog change. The name was cleared by the naming-r3 gate as the `<Quantity>Analyzer` sibling of 4-ID's loose `PolarizationAnalyzer` (the qualifier names the analyzed quantity), avoiding the `CrystalAnalyzer` / `AnalyzerCrystal` read-aloud homograph. Whether `EnergyAnalyzer` and `PolarizationAnalyzer` later merge into one `Analyzer` Family differentiated by a setting is the open `ANALYZER-1`, a gate decision at the second sighting.

The six diced crystals are carried as settings on the one `EnergyAnalyzer` Asset for this first cut, even though each is identity-bearing (its own theta / phi and its own temperature loop). Promoting each crystal to a child Asset via `parent_id` is exactly the nested-component-identity convention, which is itself at a rule-of-three gate, so IXS flags `XTAL-1` as a candidate trigger rather than asserting it. The six crystal-temperature PID loops are carried as one `TemperatureController` Asset for the same reason (`TEMP-1`). Whether the arm plus the analyzer compose an `Assembly(Diffractometer)`-style Fixture is `ANALYZER-1`, named as the follow-on the way 8-ID and 4-ID deferred their diffractometer Assemblies.

## Families

Reused from the catalog: `Goniometer` (the six-circle arm), `PseudoAxis` (the reciprocal-space axis), `Slit` (the analyzer slit), `TemperatureController` (the per-crystal thermal stabilization), and `FluxMonitor` (the quad electrometers and the I0 scaler). New at n=1: the `EnergyAnalyzer` Family for the diced crystal analyzer, held loose until a second hard crystal-analyzer / IXS beamline earns it (`ANALYZER-1`). The diced-crystal child-Asset identity is `XTAL-1` and the electrometer / scaler channel map is `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
