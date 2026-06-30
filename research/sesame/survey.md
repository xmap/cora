# SESAME (Synchrotron-light for Experimental Science and Applications in the Middle East) research brief

*Research seed for future CORA deployment pages. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about SESAME, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. CORA is not connected to SESAME; the seam section is an initial read, not a commitment. Compiled 2026-06-30 from the SESAME facility pages plus a direct read of the public per-beamline EPICS DAQ repos on GitHub.*

!!! note "Reading posture"
    Public facility pages (`sesame.org.jo`) are the source of HARDWARE FACTS (ring, beamline roster, techniques). The public `github.com/SESAME-Synchrotron` org is the source of CONTROL-SOFTWARE FACTS (device topology, EPICS PVs, IOC configs). Confidence is flagged inline as **[verified]**, **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6). SESAME is unusual in a good way: the device source is the **facility's own GitHub org** (not a staff personal account), so provenance is strong, but every value is still carried `confirm` until SESAME staff verify it, since a public DAQ repo is a snapshot, not a live-floor guarantee.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | SESAME, an independent intergovernmental storage-ring light source | [SESAME](https://www.sesame.org.jo/) |
| Location / operator | Allan, Jordan; an intergovernmental members organization (modeled on CERN) | [SESAME](https://www.sesame.org.jo/) |
| Storage ring | 2.5 GeV storage ring (first light 2017; the first synchrotron in the Middle East) | facility docs, **[partly verified]** |
| Beamline roster (operating / commissioning) | XAFS/XRF (BM08), MS/XPD (ID09 powder diffraction), HESEB (ID11L soft X-ray), BEATS (tomography), IR (BM02 spectromicroscopy) | facility + DAQ repos, **[verified for the named set]** |

SESAME is a smaller, younger facility than the APS/Diamond/NSLS-II tier, with a handful of operating beamlines. Its distinguishing value for CORA is provenance: the control system is published openly by the facility org itself, down to the EPICS IOC substitutions layer, so the dry-fact seed is unusually authoritative. The governance / provenance / recipe spine CORA adds is absent from the DAQ repos (they are scan tools + IOC configs), which is the usual gap that justifies the spine.

---

## 2. Candidate beamlines

SESAME publishes a per-beamline **EPICS DAQ / ScanTool repository** for each instrumented beamline in the `SESAME-Synchrotron` org. Each carries an `IOCs/<BL>_DAQ/.../`<BL>`.substitutions` + `st.cmd` (the real EPICS device wiring, with a clean `P` prefix) plus a Python scan tool (`Mono.py`, `detectors/`, `common.py`) that names device PVs. This is the modellable set, and it is richer than a bluesky profile: it is the IOC layer.

| Beamline | ID | Technique | DAQ repo(s) | EPICS prefix (P) | Source |
| --- | --- | --- | --- | --- | --- |
| XAFS/XRF | BM08 | X-ray absorption fine structure / fluorescence spectroscopy | `XAFSScanTool`, `xafs-dt8824-daq` | `XAFS:` | [XAFSScanTool](https://github.com/SESAME-Synchrotron/XAFSScanTool) |
| MS/XPD | ID09 | materials science / X-ray powder diffraction | `MS-XPD-ScanTool` | `MS:` | [MS-XPD-ScanTool](https://github.com/SESAME-Synchrotron/MS-XPD-ScanTool) |
| HESEB | ID11L | Helmholtz-SESAME soft X-ray beamline | `HESEBScanTool`, `heseb-pico-6487` | `HESEB:` | [HESEBScanTool](https://github.com/SESAME-Synchrotron/HESEBScanTool) |
| BEATS | tomography | full-field X-ray tomography (CT) | `BEATS_tomoscan`, `BEATS_Dashboard`, `BEATS_recon` | `tomoscanBEATS:` / `BEATS:` | [BEATS_tomoscan](https://github.com/SESAME-Synchrotron/BEATS_tomoscan) |
| IR | BM02 | infrared spectromicroscopy | `IR-Docs` (docs only, no DAQ) | (none public) | [IR-Docs](https://github.com/SESAME-Synchrotron/IR-Docs) |

The first four are device-modellable from source. IR (BM02) publishes only documentation (no DAQ repo), so it is a survey-only beamline (out of scope for a device pass until staff provide facts). Technique labels are from the repo descriptions and facility pages. **[verified for the named beamlines]**

**Identifier scheme:** SESAME uses beamline names (XAFS, MS/XPD, HESEB, BEATS) and `ID##` / `BM##` source IDs (ID09, ID11L, BM02, BM08). EPICS PVs use a per-beamline `P` macro prefix (`XAFS:`, `MS:`, `HESEB:`, `tomoscanBEATS:`) plus structured device records, e.g. motion controllers `MC1:ES-DIFF-STP-ROTX1` (MS), `ACS:EH-TMO-SRV-ROT:m1` (BEATS rotation), `MC2:EH-TMO-STP-TRSX1` (BEATS translation), sample `SMP:X/Y` (XAFS), cameras `CAM1:` / `FLIR:` / PCO. The naming carries a readable location/function code (`ES-DIFF`, `EH-TMO`, endstation-technique-devicetype). **[verified]**

---

## 3. Control-system stack, by layer

SESAME is an **EPICS** facility with a strongly standardized, openly-published controls house-style.

### Device IO (the floor)

EPICS Channel Access, with IOCs built from a shared set of facility drivers, all public: `galil-ioc` (Galil motion), `stream-device-ioc` (generic serial/TCP), `caen-ioc` / `psc-asyn-driver` (power supplies), `libera-spark-epics` (BPMs), `epics-gamma` (vacuum), `heseb-pico-6487` / `xafs-dt8824-daq` (ammeters / DAQ). Per-beamline IOC boot configs (`.substitutions` + `st.cmd`) wire real device records. This is below CORA's seam; CORA's ControlPort actuates through the EPICS floor exactly as at the 2-BM pilot and the NSLS-II / SSRL fleets. **[verified]**

### Scan orchestration (the seam layer)

A per-beamline **ScanTool** (Python over the EPICS PVs: `Mono.py`, `detectors/`, `common.py`, `H5Writer.py` / `ZMQWriter.py` / `SEDWriter.py`) plus an EPICS-Qt operator GUI stack (`qeframework`, `custom-widgets`, the `qt` clients). This is the layer CORA's EdgeConductor would conduct over / replace. It is a home-grown scan-tool house-style (not bluesky, not BLISS, not GDA), distinct from the other reverse-engineered fleets. **[verified]**

### Fast paths and exceptions

BEATS tomography carries continuous (fly) and step scan IOCs (`iocTomoScan_BEATS_FLIR_ACS_Cont` / `_Step`) over an ACS motion controller and FLIR / PCO cameras; the ACS controller drives the continuous rotation (`ACS:EH-TMO-SRV-ROT:m1`). Confirm whether the fly path is pure EPICS or an ACS-direct trigger (FLY-1). **[partly verified]**

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| `github.com/SESAME-Synchrotron` (facility org, ~38 repos) | per-beamline DAQ / ScanTools, shared EPICS drivers + IOCs, Qt GUI framework, accelerator (orbit feedback), reconstruction (tomopy/dxchange) | [SESAME-Synchrotron](https://github.com/SESAME-Synchrotron) |
| EPICS community | the upstream EPICS base / asyn / areaDetector / StreamDevice SESAME builds on | epics-controls.org |

**Why a per-beamline device model IS buildable from public source.** Each beamline's `IOCs/<BL>_DAQ/iocBoot/.../<BL>.substitutions` carries the literal device records and the `st.cmd` sets the `P` prefix; the ScanTool Python names the mono, detectors, and sample stages with their PVs (verified: `MC1:ES-DIFF-STP-ROTX1`, `ACS:EH-TMO-SRV-ROT:m1`, `SMP:X`, `ENGCAL:RealFoilEng`, `BLSetup:Crystal`). This is the IOC layer, more authoritative than a bluesky profile, and published by the facility itself.

---

## 5. Data management

The ScanTools write HDF5 (`H5Writer.py`), a SESAME SED format (`SEDWriter.py`, `SEDSS`), and stream over ZMQ (`ZMQWriter.py`); BEATS uses DXchange / tomopy for tomography reconstruction. No public facility-wide data catalog / archive was established in this pass (DATA-1). **[partly verified]**

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility data layer is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** SESAME device IO is EPICS Channel Access (Galil / ACS motion, FLIR/PCO cameras, ammeters, BPMs). CORA's ControlPort actuates through it exactly as at the APS / NSLS-II / SSRL EPICS beamlines. The APS-pilot ControlPort model carries over with no new control substrate to build.

**What CORA replaces (edge orchestration).** The per-beamline ScanTool (the `Mono.py` energy scan, the BEATS tomoscan continuous/step engine, the MS two-theta scan) is the scan-orchestration layer the 2-BM seam designates as CORA's. CORA's EdgeConductor would conduct routines over the EPICS floor where the ScanTools sit today. Treat the ScanTool as DATA to learn from (device topology, scan structure), NOT a spec to mirror; pitch CORA on governance, replayability, recipe-binding, never on out-executing the ScanTool.

**Source-of-truth contest (data).** The HDF5 / SED / ZMQ writers and the tomopy reconstruction are the produced records CORA subsumes; CORA stays the system of record for the experiment. Decision deferred until a specific SESAME deployment is in scope.

**Coexist.** SESAME facility scheduling / identity (read, do not replace), the reconstruction compute (a port roundtrip CORA governs but does not own), any data archive (an egress destination).

---

## 7. Open questions (for SESAME staff)

1. **Technique / beamline confirm:** confirm the science + status of XAFS (BM08), MS/XPD (ID09), HESEB (ID11L), BEATS, IR (BM02), and whether other beamlines (e.g. a future MX or SAXS) exist.
2. **PV namespaces:** confirm the per-beamline `P` prefixes (`XAFS:`, `MS:`, `HESEB:`, `tomoscanBEATS:`) and the optics/mono device records not exposed in the ScanTool.
3. **Fast-path (FLY-1):** is the BEATS continuous-rotation path pure EPICS (ACS over Channel Access) or an ACS-direct hardware trigger?
4. **Optics floor:** the DCM / mirrors / slits per beamline are only partly in the ScanTools (mostly endstation devices); is there a public optics IOC config, or is that staff-only?
5. **Data catalog (DATA-1):** what is SESAME's data-policy / catalog / archive chain?
6. **Ring parameters:** confirm SPEAR-equivalent ring facts (2.5 GeV, current, emittance) from the machine design report.

---

## 8. Source list

**Facility (hardware facts):**
- SESAME: https://www.sesame.org.jo/

**Control system / device topology (public facility org):**
- SESAME-Synchrotron org: https://github.com/SESAME-Synchrotron
- XAFS/XRF (BM08): https://github.com/SESAME-Synchrotron/XAFSScanTool
- MS/XPD (ID09): https://github.com/SESAME-Synchrotron/MS-XPD-ScanTool
- HESEB (ID11L): https://github.com/SESAME-Synchrotron/HESEBScanTool
- BEATS (tomography): https://github.com/SESAME-Synchrotron/BEATS_tomoscan
- shared EPICS drivers/IOCs: galil-ioc, stream-device-ioc, caen-ioc, libera-spark-epics, epics-gamma
- Qt GUI framework: qeframework, custom-widgets

**Docs-only (no public DAQ):** IR (BM02) IR-Docs.
