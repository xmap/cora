# Fleet recurrence: SESAME

Cross-fleet device-class frequency across the beamlines surveyed under `research/sesame/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables. **Scope: the 4 device-passed SESAME beamlines** with a public EPICS DAQ repo (XAFS/BM08, MS-XPD/ID09, HESEB/ID11L, BEATS/ID10). The IR beamline (BM02) publishes docs only (no DAQ) and is survey-only. Every PV was verified verbatim against the facility's own GitHub org (`SESAME-Synchrotron`) at pass time, with dynamically-built / indirect PVs flagged confirm in the per-beamline facts.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| LinearStage | 3 (xafs, heseb, beats) | graduated |
| Shutter | 2 (ms-xpd, beats) | graduated |
| RotaryStage | 2 (ms-xpd, beats) | graduated |
| EnergyDispersiveSpectrometer | 2 (xafs, heseb) | graduated |
| Camera | 2 (ms-xpd, beats) | graduated |
| FluxMonitor | 2 (xafs, heseb) | graduated |
| GenericProbe | 2 (ms-xpd, beats) | graduated |
| Monochromator | 1 (xafs) | graduated |
| GratingMonochromator | 1 (heseb) | graduated |
| Diffractometer | 1 (ms-xpd) | LOOSE / Assembly (fleet-wide question) |
| Filter | 1 (heseb) | graduated |
| PseudoAxis | 1 (xafs ENGCAL) | graduated |

## Graduation shortlist (the actionable output)

SESAME is a small fleet (4 modellable beamlines) on a home-grown EPICS ScanTool stack. Result: **zero new families; every recurring class is already graduated.** The signals:

| Family | Distinct beamlines | What SESAME adds | Verdict |
| --- | --- | --- | --- |
| EnergyDispersiveSpectrometer | 2 (xafs FICUS/SDD, heseb MCA) | SDD + MCA fluorescence/spectroscopy detectors | ALREADY graduated. Reuse. No action. |
| Camera | 2 (ms CAM1, beats FLIR/PCO) | powder + tomography area detectors | ALREADY graduated. Reuse. No action. |
| Rotary/LinearStage | 2/3 | diffractometer + tomography + sample stages | ALREADY graduated. Reuse. No action. |
| Diffractometer | 1 (ms-xpd) | a theta/2theta powder diffractometer | LOOSE / modeled as Assembly elsewhere. ONE consumer here; folds into the fleet-wide Diffractometer question (NSLS-II n=6 contested, Diamond i07/i16 absent). SESAME MS leans toward the RotaryStage-composition / Assembly reading (powder theta/2theta, not a full multi-circle). Do NOT coin. |
| GratingMonochromator | 1 (heseb) | a soft X-ray PGM | ALREADY graduated; another cross-facility consumer (NSLS-II csx, Diamond i05/i09/i21/b07). No action. |

**Net over the 4:** zero new families. The fleet stresses the existing vocabulary on a *new controls house-style* (a home-grown Python ScanTool over EPICS, with the IOC-substitutions layer as the extraction surface, distinct from bluesky/dodal/BLISS) and it holds. That is the meaningful result: CORA's families generalize not just across facilities but across controls *idioms*.

## Notable for the cross-facility picture

- **energy_scan Capability:** TWO SESAME beamlines run live scanning-energy modes whose energy path is in public source, XAFS (hard X-ray DCM via `Mono.py` + `ENGCAL`) and HESEB (soft X-ray PGM via `PGM:getEnergy`). With SSRL 2-2, these add to the set of facilities where the scanning-energy trajectory is publicly instantiated (unlike Diamond b18's stub). Flagged for the pending energy_scan graduation review.
- **BEATS tomoscan** is the APS `tomoscan` lineage, the same family as CORA's 2-BM / FXI / TomoWise tomography deployments, confirming that tomography stack at a 5th facility.
- **New controls idiom:** SESAME is the first fleet whose device source is read at the **EPICS IOC substitutions** layer (the facility publishes `.substitutions` + `st.cmd`), more authoritative than a bluesky profile and a useful stress of the facts-template on a non-Python-framework source.

## Provenance

Compiled from the device tables of the 4 device-passed SESAME beamlines (every literal PV verified verbatim against the `SESAME-Synchrotron` org at pass time; dynamic/indirect PVs flagged confirm). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. The durable result: CORA's families hold at SESAME with zero new families, on a controls house-style not previously stressed (home-grown EPICS ScanTool, facility-published IOC layer).
