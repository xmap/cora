# Sample

*The sample-stage and sample-environment Assets across P02's two diffraction endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P02 has two endstations sharing the OH1 optics: P02.1 (powder / total scattering) and P02.2 (extreme conditions, diamond-anvil cell). The sample positioning at each is exposed as generically-named motor banks (`eh1a / eh1b` for P02.1, `eh2a / eh2b` for P02.2), grouped as stage Assets carrying the bank prefix, per-axis roles pending (`GROUP-1`).

## P02.1: powder / total scattering

- `SampleStage` binds `LinearStage`: the P02.1 sample / instrument motor banks (`eh1a_mot01..48`, `eh1b_mot01..16`); per-axis roles grouped (`GROUP-1`).
- `SampleEnvironment` binds `TemperatureController`: the P02.1 in-situ sample environment, the Anton-Paar furnace (Eurotherm 2604), a Eurotherm 2408, and a Lakeshore 336 cryo controller, for parametric temperature studies (`TEMP-1`).

## P02.2: extreme conditions (diamond-anvil cell)

- `SampleStage` binds `LinearStage`: the P02.2 sample / instrument motor banks (`eh2a_mot01..76`, `eh2b_mot01..64`), including the diamond-anvil-cell positioning stages; per-axis roles grouped (`GROUP-1`).
- `PressureCell` binds the allowlisted-loose `PressureCell` Family: the P02.2 diamond-anvil-cell high-pressure environment. The membrane / gas-loading control is not separately labelled in the registry. This is the second consumer of the `PressureCell` Family (the 13-id-d precedent), crossing the rule-of-three promotion threshold (`PRESSURE-1`).
- `BeamMonitor` binds `FluxMonitor`: the P02.2 CAEN-ELS AH501D picoammeter; beam-intensity monitoring (`DET-1`).

## Families and confirmations

Every Asset here binds an existing Family: `LinearStage` for the sample banks, `TemperatureController` for the sample environment, `FluxMonitor` for the beam monitor, and the allowlisted-loose `PressureCell` for the diamond-anvil cell. P02 coins no new Family. The axis maps are read from the OnlineXML and carried confirm; the per-axis bank roles, the pressure-cell membrane / load control, and the sample-environment detail are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
