# Sample

*The sample positioning table and the sample-environment translation stack at 10-ID-D. First cut; PVs read from the profile collection, carried confirm.*

The IXS sample side is a hard X-ray ambient endstation: pure-translation stacks set the sample position in front of the six-circle spectrometer, which swings about the sample to set the momentum transfer Q. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

Both stacks bind the catalog `LinearStage` Family (the fxi / hxn `SampleStage` precedent for a pure-translation stage). This is deliberately not SIX's loose `Manipulator`: that Family is a UHV cryostat multi-axis manipulator, and reusing it for an ambient hard X-ray endstation would mirror context, not anatomy.

## The sample stack (10-ID-D)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleTable` | `LinearStage` | sample positioning table (x/y/z) on the `Spec:1` PV root (`SAMPLE-1`) |
| `SampleEnvironment` | `LinearStage` | sample-environment translation stack (x/y/z) on its own `Env:1` PV root (`SAMPLE-1`) |

The sample table sets the sample position in the beam; the environment stack translates whatever sample environment is mounted, on its separate `Env:1` PV root. Together they place the sample at the centre of rotation the six-circle arm pivots about. The arm itself (the `Spectrometer` `Goniometer` and its reciprocal-space pseudo-axis) lives on the [Detector](detector.md) side, since at IXS the scattering geometry sets Q and the analyzed beam is point-detected there.

Whether the table and the environment translations are one fused Asset or two siblings on their separate PV roots, and what sample environment is mounted on them, is `SAMPLE-1`.

See [Open questions](../questions.md) for the sample-stage facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
