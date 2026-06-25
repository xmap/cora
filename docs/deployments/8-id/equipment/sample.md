# Sample

*The 8-ID-E six-circle diffractometer and the 8-ID-I XPCS sample endstation. First cut; PVs read from the beamline config, carried confirm.*

8-ID has two sample-side endstations: the six-circle Huber diffractometer at `8-ID-E`, and the XPCS sample stack at `8-ID-I` (Aerotech translation, a rheometer shear-cell, and temperature-controlled holders). They are modelled as sample-stage groups in the [descriptor](../inventory.md).

The diffractometer device binds the catalog `Goniometer` Family for its sample circles; the composed `Assembly(Diffractometer)` is in the catalog and materialized by the integration scenario (see [Model](../model.md#the-diffractometer-assembly-landed)). The temperature controllers and the beam-position monitor bind loose Families held for gate-review (8-ID is the second independent beamline to use them, but the abstraction is open); the rheometer binds a loose `Rheometer` Family.

## The six-circle diffractometer (8-ID-E)

A Huber six-circle diffractometer orients a single crystal through six rotation circles and scans reciprocal space via hklpy2.

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Diffractometer_SixCircle` | `Goniometer` | six circles mu / eta / chi / phi / nu / delta + x/y/z; bound as the goniometer of the Diffractometer Assembly (`DIFF-1`) |
| `ReciprocalSpace` | `PseudoAxis` | hklpy2 reciprocal-space layer (psic); partition rule is `DIFF-2` |
| `TemperatureController_1/2` | `TemperatureController` | LakeShore 336 controllers (`TEMP-1`) |
| `BeamPositionMonitor_E` | `BeamPositionMonitor` | Sydor TetrAMM monitor (`BPM-1`) |
| `FastShutter` | `Shutter` | gates the exposure (`XPCS-1`) |

The six circles (mu, eta, chi, phi, nu, delta) are the strongest evidence for the `Assembly(Diffractometer)` slot shape; together with 4-ID's diffractometers they set `sample_circles` at cardinality `OneOrMore` (see [Model](../model.md#deliberately-not-here-yet)).

## The XPCS sample endstation (8-ID-I)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleStage` | `LinearStage` | Aerotech three-axis sample positioning |
| `Rheometer` | `Rheometer` (loose) | six-axis shear-cell sample environment (`SAMPLE-1`) |
| `SampleHolder_QNW` | `TemperatureController` | Quantum Northwest temperature-controlled holders, three units (`TEMP-1`) |
| `SampleSlit` | `Slit` | sample-defining slit |

The UR5 robotic sample changer is present in the beamline config but not modelled in this cut (`SAMPLE-2`); CORA has no sample-changer shape yet.

See [Open questions](../questions.md) for the diffractometer and sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
