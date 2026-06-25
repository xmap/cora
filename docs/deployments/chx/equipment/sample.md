# Sample

*The endstation sample side: the grazing-incidence mirror, the sample stack in the coherent focus, and the sample environment. PVs verified against `startup/10-optics.py`, `80-pseudomotors.py`, `51_Linkam.py`.*

CHX places the sample in a coherent focused spot and records how its speckle pattern changes over time. The sample side is deliberately light: the dynamics live in the time series the detector records, not in elaborate sample motion. What matters most here is conditioning the beam to its coherent core just before the sample.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `BeamDefiningSlit` | Slit | `XF:11IDB-OP{Slt:BDS}` | trims the beam to its coherent core at the sample |
| `GuardSlit` | Slit | `XF:11IDB-OP{Slt:Guard}` | cleans up parasitic scatter from the beam-defining slit |
| `GrazingIncidenceMirror` | Mirror | `XF:11IDB-OP{Mir:GI}` | steers the beam onto a surface for GISAXS |
| `SampleStage` | LinearStage | `XF:11IDB-ES{Dif-Ax:}` | positions the sample in the coherent focus |
| `SampleTemperature` | TemperatureController | `XF:11ID-ES{LINKAM}:` | in-situ thermal and tensile environment |

## Conditioning the coherent beam

For a coherence beamline the endstation slits are not an afterthought, they are the coherence-defining hardware. The `BeamDefiningSlit` (a SmarAct slit that replaced an older large-aperture JJ slit) trims the beam to the coherent core that produces a clean speckle pattern; the `GuardSlit` just downstream cleans up the parasitic scatter the defining slit throws. Both reuse the `Slit` family. This is why CHX models endstation slits as first-class Assets where an imaging beamline might fold them into settings.

## The sample stack

The `SampleStage` is the sample stack on the diffractometer base (`diff`, at `XF:11IDB-ES{Dif`), driven through the `SamplePositioner` pseudomotor (the physical sample holder is `XF:11IDB-ES{Dif-Ax:XH}Mtr`). CORA binds it to `LinearStage` as a design-phase placeholder; the diffractometer also carries goniometric (rotation) axes, so whether its sample orientation is modelled as a `Goniometer` plus a Diffractometer Assembly, the shape APS [8-ID](../../8-id/equipment/sample.md) uses, is folded into STAGE-1.

The `GrazingIncidenceMirror` steers the beam at a shallow angle onto a film or interface for grazing-incidence small-angle scattering (GISAXS), reusing the `Mirror` family. Whether GISAXS is a live routine is GI-1.

## Sample environment

The `SampleTemperature` Linkam stage reuses the `TemperatureController` family (graduated in #350). Source carries both a thermal form (`LThermal`) and a tensile form (`LTensile`) on the same PV namespace, so CORA models one thermal-environment Asset; the tensile mode is a setting, not a second Asset. This is the reuse point: the sample-environment thermal control that serves a spectroscopy beamline (BMM) or a powder-diffraction beamline serves a coherence beamline unchanged.
