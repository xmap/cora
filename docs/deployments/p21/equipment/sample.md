# Sample

*The sample-stage Assets across P21's EH3 and LAB stations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P21's sample positioning is exposed as generically-named motor banks per station, grouped as stage Assets carrying the bank prefix, per-axis roles pending (`GROUP-1`).

## EH3 endstation

- `SampleStage` binds `LinearStage`: the EH3 sample / instrument motor bank (`eh3_u*` on the `hasep21eh3` host); per-axis roles grouped (`GROUP-1`).

## LAB station

- `SampleStage` binds `LinearStage`: the LAB sample / instrument motor bank (`lab*` on the `haspp21lab` host); per-axis roles grouped (`GROUP-1`).
- `DefiningSlits` binds `Slit`: the LAB beam-defining slits (`s1` / `s2`, vmexecutor virtual gap / offset axes) (`OPT-1`).

## Families and confirmations

Both stations bind existing catalog Families (`LinearStage`, `Slit`); P21 coins no new Family. The axis maps are read from the OnlineXML and carried confirm; the per-axis bank roles, the diffractometer / sample-environment detail, and the P21.1 station (not in this slice) are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
