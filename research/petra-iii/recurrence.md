# Fleet recurrence: PETRA III

Cross-fleet device-class frequency across the beamlines surveyed under `research/petra-iii/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` "Suggested family" columns (deduplicated within each beamline). **Scope: 21 device-passed PETRA III beamlines.** Eighteen are extracted from the DESY OnlineXML Tango registry (`python-nxstools-extras-pNN`): p01, p02, p03, p04, p06, p07, p08, p09, p10, p11, p21, p22, p23, p24, p61, p62, p64, p65. Three are extracted from MXCuBE HardwareObjects (the EMBL Hamburg MX beamlines): p13, p14, pe2.

!!! warning "Source-class noise, not Family noise"
    OnlineXML lists one Tango `<device>` per axis or channel, and MXCuBE lists one HardwareObject per device, so the "Suggested family" column is dominated by class-name fallbacks (`oms58`, `motor_tango`, `module_tango`, `spk`, `TINEMotor`, `ExporterMotor`, `EMBLEnergy`, `EMBLBeam*`, `Backlight`) where the extractor could not map the class to a CORA Family. These are NOT graduation candidates: they are unresolved bindings pending human Asset-granularity curation, the same `confirm` posture every row carries. Only the rows that map to a real CORA Family are counted below; the class-name fallbacks are recorded as the curation backlog, not as recurrence signal.

## Suggested CORA families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| Camera | 12 (p02, p03, p06, p07, p08, p09, p10, p11, p13, p14, p64, pe2) | graduated |
| GenericProbe | 10 | graduated (the unresolved-sensor sink; see DIAG note) |
| Diffractometer | 4 (p07, p08, p09, p10) | Assembly (see below) |
| Objective | 3 (p13, p14, pe2) | graduated |
| Aperture | 3 (p13, p14, pe2) | graduated |
| BeamStop | 3 (p13, p14, pe2) | graduated |
| Shutter | 3 (p13, p14, pe2) | graduated |
| Transfocator | 2 (p14, pe2) | graduated |
| Monochromator | 2 (p03, p08) | graduated |
| LinearStage | 2 (p14, pe2) | graduated |
| Goniometer | 2 (p13, p14) | graduated |
| FluxMonitor | 2 (p13, p14) | graduated |
| EnergyDispersiveSpectrometer | 2 (p13, p14) | graduated |
| Slit | 1 (p01) | graduated |
| Mirror | 1 | graduated |

## Graduation shortlist (the actionable output)

**No new Family is earned by the 21-beamline PETRA III pass.** Every recurring class that maps to a CORA Family is already graduated, and the one Assembly-shaped recurrence (Diffractometer) is already an Assembly in the catalog. This matches the other reverse-engineered facilities: the fleet stresses the existing vocabulary and it holds.

| Candidate | Distinct beamlines | CORA status (per catalog) | Decision |
| --- | --- | --- | --- |
| Camera | 12 | GRADUATED | reinforce only; the fleet-wide detector binding |
| Diffractometer | 4 (p07, p08, p09, p10) | ASSEMBLY (Goniometer + RotaryStage arms + PseudoAxis) | model as Assembly, not a Family; same call as APS / NSLS-II. The OnlineXML "Diffractometer" rows are class-fallback and may be plain stages; confirm the multi-circle contract per beamline before binding, do NOT coin |
| Goniometer | 2 (p13, p14) | GRADUATED | reinforce; the EMBL MX goniometers |
| Transfocator | 2 (p14, pe2) | GRADUATED | reinforce |
| Objective / Aperture / BeamStop / Shutter | 3 each (p13, p14, pe2) | GRADUATED | reinforce; the shared EMBL MX endstation vocabulary |
| Monochromator, LinearStage, FluxMonitor, EnergyDispersiveSpectrometer | 2 each | GRADUATED | reinforce |

## Curation backlog (class-name fallbacks, NOT recurrence signal)

These recur as Tango / MXCuBE class strings but are unresolved bindings, held pending Asset-granularity curation; do not coin from them:

- **OnlineXML motion/channel classes**: `oms58` (17 beamlines), `motor_tango` (15), `module_tango`, `spk`, `absbox`, `limaccd`, `TINEMotor`, `TINEEnergy`, `ExporterMotor`. These are the per-axis Tango device classes; one CORA Asset groups many of them. The `module_tango` / `spk` / `absbox` rows in particular need a human to decide what Asset they belong to.
- **MXCuBE EMBL classes** (p13, p14, pe2): `EMBLEnergy`, `EMBLBeam`, `EMBLBeamInfo`, `EMBLBeamCentring`, `EMBLPiezoMotor`, `Backlight`. These are EMBL HardwareObject wrappers; they map to existing Families (energy -> PseudoAxis, backlight -> a Camera-adjacent illumination) on curation, but are not their own Families.

## Recurring loose-family / DIAG notes

- **GenericProbe (10 beamlines)** absorbs the fleet-wide unresolved sensors (BPMs, counters, intensity monitors, gauges), the same `DIAG-1` cluster held across APS, ESRF, and NSLS-II. Held by design pending the cross-facility DIAG abstraction review; do not graduate piecemeal.

## Provenance

Compiled from the 21 per-beamline `facts.md` device tables. OnlineXML beamlines: PVs (Tango `domain/family/member` addresses) read verbatim from each `python-nxstools-extras-pNN` package's `xml/online_*.xml` on `gitlab.desy.de/petra-iii-debian-packages` at pass time. MXCuBE beamlines: device objects read from the EMBL beamline `configuration/*.xml`. Counts are distinct physical beamlines (a multi-endstation beamline like p04 / p10 counts once). Method: per-beamline distinct "Suggested family" values mapping to a CORA Family, `(?)` class-fallbacks separated into the curation backlog above.
