# Fleet recurrence: SSRL

Cross-fleet device-class frequency across the beamlines surveyed under `research/ssrl/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables. **Scope: the 4 device-passed SSRL beamlines** with a public bluesky profile (2-1 diffraction, 2-2 continuous XAS, 1-5 scattering, DeNovX transmission XRD). The other ~21 of SSRL's 25 beamlines do not publish a public device manifest (staff-only); they are out of scope until staff provide facts.

!!! note "Profile customization varies"
    Every PV was verified verbatim against the public `tangkong/SSRL-*` profiles at pass time. Two profiles are properly customized with real beamline PVs (2-2 = `BL22:`, DeNovX = `TXRD:`); two (2-1, 1-5) are template-derived and carry `BL00:` placeholder motor PVs with shared `BL15:`/`SSRL:` detector roots (PV-1). The family mapping is unaffected (the device classes are real), but the namespaces need staff confirmation.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| LinearStage | 4 | graduated |
| GenericProbe | 4 | graduated |
| EnergyDispersiveSpectrometer | 3 (2-1, 2-2, 1-5) | graduated |
| Camera | 3 (2-1, 1-5, DeNovX) | graduated |
| TimingController | 1 (2-2) | graduated |

## Graduation shortlist (the actionable output)

SSRL is a small, EPICS-floor / bluesky-orchestrated fleet, and the 4 public beamlines are device-light (endstation profiles: sample stages + area detectors + spectroscopy, no mono/optics in source). Result: **zero new families; every recurring class is already graduated.**

| Family | Distinct beamlines | What SSRL adds | Verdict |
| --- | --- | --- | --- |
| Camera | 3 | Pilatus / MarCCD / Dexela area detectors for diffraction/scattering/transmission-XRD | ALREADY graduated. Reuse. No action. |
| EnergyDispersiveSpectrometer | 3 | Xspress3 (all) + three XIA DXP channels (2-2) | ALREADY graduated. 2-2's three-DXP continuous-XAS spectroscopy strongly reinforces. No action. |
| LinearStage | 4 | HiTp combinatorial sample stages + cassette / detector-Z stages | ALREADY graduated. Reuse. No action. |
| TimingController | 1 (2-2) | SCAN:MASTER + FPGA box (the continuous-XAS fly-scan engine) | ALREADY graduated. n=1 at SSRL but reinforces the fleet-wide fly-scan-gating question (Zebra/PandA/AnalogPizzaBox/SCAN:MASTER all bind TimingController). No action. |

**Net over the 4:** zero new families. The fleet is pure reuse. The one notable cross-facility signal is **2-2's continuous-XAS fly-scan engine** (SCAN:MASTER + FPGA box + DXP), which is the SSRL counterpart of NSLS-II ISS/QAS quick-EXAFS, reinforcing the TimingController + EnergyDispersiveSpectrometer fly-scan pattern across a third facility.

## Notable for the cross-facility picture

- **energy_scan Capability candidate:** SSRL 2-2 is a LIVE continuous-XAS beamline whose scanning-mono path is exposed (via `BL22:SCAN:MASTER`), unlike Diamond b18 (stub) and i18/i20-1 (skip/dispersive). If the pending `energy_scan` Capability graduation wants a beamline whose scanning-energy trajectory is actually instantiated in public source, SSRL 2-2 is a candidate, though the mono is an energy-trajectory abstraction (SCAN:MASTER) rather than a named DCM device (MONO-1). Flagged for that graduation review.
- **Shared HiTp tooling:** the `HITP:RIO` crate and `SSRL:DEX2923:` Dexela recur across 2-1 / 1-5 / DeNovX, real cross-beamline device sharing in the high-throughput combinatorial program (not a modelling artifact).

## Provenance

Compiled from the device tables of the 4 device-passed SSRL beamlines (every PV verified verbatim against the public `tangkong/SSRL-*` bluesky profiles; template-derived placeholder PVs flagged PV-1). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. The durable result: CORA's families hold at SSRL with zero new families, a small reuse-only fleet on an EPICS/bluesky stack.
