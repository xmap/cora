# Sample

*The endstation sample side: the cleanup slit, the fast shutter, the capillary spinner, the sample-environment stage, and the thermal-environment cluster. PVs verified against `startup/12-optics.py`, `11-motors.py`, the temperature-controller startup files, and `pdftools/sample_environment.py`.*

PDF positions a powder or capillary sample in the high-energy beam and records the total-scattering pattern on the area detectors. The sample side conditions the beam at the endstation, spins the capillary to average the powder texture, and carries the rich thermal environment that variable-temperature total scattering needs.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `CleanupSlit` | Slit | `XF:28ID1B-OP{Slt:AS}` | trims parasitic scatter ahead of the sample |
| `FastShutter` | Shutter | `XF:28ID1B-OP{PSh:1}` | gates the detector exposure |
| `SpinnerGoniohead` | Goniometer | `XF:28ID1B-ES{Stg:Smpl}` | spins and positions the capillary sample |
| `SampleEnvironmentStage` | LinearStage | `XF:28ID1B-ES{Env:1}` | presents the sample-environment cell to the beam |
| `SampleTemperature` | TemperatureController | `XF:28ID1-ES:1{Env:01}` | cryostream / cryostat / furnace cluster |

## Conditioning and spinning

The `CleanupSlit` (the endstation `cleanup_slits`) trims the parasitic scatter the upstream optics throw before the beam reaches the sample; an optics-cabin slit (`OCM_slits`) sits further upstream. The `FastShutter` (the `PDFFastShutter`) gates the detector exposure, with a slower photon shutter alongside. Both reuse existing families (`Slit`, `Shutter`).

The `SpinnerGoniohead` is the capillary-spinner goniohead: sample X / Y / Z plus a spin axis that rotates the capillary so the area detector sees a smooth powder ring rather than individual crystallite spots. An analyzer goniohead sits alongside. It reuses the `Goniometer` family; the full axis set, and whether the orientation warrants a `Goniometer` plus an Assembly (the i11 precedent), are STAGE-1.

## The sample environment

The `SampleEnvironmentStage` (the `Grid` X / Y / Z stage) presents the sample-environment cell to the beam. The `SampleTemperature` is the thermal-environment cluster: a cs800 cryostream controller (understood to be an Oxford Cryostream, an inference, TEMP-1), a Lakeshore 336 cryostat, and a Linkam T96 furnace. CORA models one thermal-environment Asset, reusing the `TemperatureController` family (graduated in #350, the same Family Diamond i11 graduated for variable-temperature powder diffraction); which units are live is TEMP-1.

A gas-handling and humidity rig (flow valves, a residual-gas analyzer, a humidity readout) is present in the profile collection. It is the settable in-situ environment, but CORA carries it deferred (ENV-1): a design-phase scaffold models the thermal environment that is settled and defers the gas / humidity actuators until they earn modelling, where they would likely bind the loose `FlowController` family other deployments use.
