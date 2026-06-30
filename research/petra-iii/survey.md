# PETRA III (DESY) research brief

*Research seed for future CORA deployment pages. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the DESY PETRA III facility, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. CORA is not connected to PETRA III; the seam section is an initial read, not a commitment. Compiled 2026-06-29 from a deep-research workflow (5 angles, 17 sources, 25 adversarially verified claims) plus a direct gitlab.desy.de API probe that overturned the workflow's "device topology is firewalled" finding.*

!!! note "Reading posture"
    Public facility pages (photon-science.desy.de) are treated as the source of HARDWARE FACTS (beamline IDs, techniques, energies, beam sizes). Public GitLab source (gitlab.desy.de) and GitHub mirrors are treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices, which Tango device addresses each beamline binds). Confidence is flagged inline as **[verified]** (a decisive primary source or multiple corroborating sources), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | PETRA III, 3rd-generation hard X-ray synchrotron, ~2.3 km storage ring | [PETRA III](https://photon-science.desy.de/facilities/petra_iii/index_eng.html) |
| Operator | Deutsches Elektronen-Synchrotron (DESY), Hamburg-Bahrenfeld, Germany | [DESY](https://www.desy.de/) |
| Beamline count | ~25 beamlines operational for users; 27 designations enumerated (incl. P63 OperandoCat under construction) | [Beamlines](https://photon-science.desy.de/facilities/petra_iii/beamlines/index_eng.html) |
| Experimental halls | Max von Laue, Ada Yonath, Paul P. Ewald (three halls) | [Beamlines](https://photon-science.desy.de/facilities/petra_iii/beamlines/index_eng.html) |
| External operators | P05 (IBL) + P07 (HEMS, joint 2/3 Hereon + 1/3 DESY) by Helmholtz-Zentrum Hereon; P12/P13/P14 by EMBL | [Beamlines](https://photon-science.desy.de/facilities/petra_iii/beamlines/index_eng.html) |
| Upgrade | PETRA IV: the existing 2300 m ring will be modernised, instruments and infrastructure partially recycled; positioned as an "ultimate 4D X-ray microscope" | [PETRA IV](https://www.desy.de/research/facilities__projects/petra_iv/index_eng.html) |

**[verified]** PETRA III is a DESY hard X-ray storage-ring source running ~25 user beamlines across three halls, mid-planning for the PETRA IV upgrade that rebuilds the same ring.

**Upgrade is material to any deployment page.** PETRA IV will reshape beamline topology; the dedicated FPGA-firmware project `fpgafw/projects/petra/petra_motion_control` is described as "Motion Control project that will be used on PETRA IV photon beamlines." Any device inventory captured now is a PETRA-III-era snapshot and should be timestamped. **[verified]**

---

## 2. Beamline roster and techniques

DESY's beamline catalog is the authoritative roster. It exposes techniques, energy ranges, and beam sizes only: no device topology, no Tango/Sardana references, no PV inventories. Device topology comes from the controls source (section 4), not this catalog. **[verified]**

Designations: P01, P02.1, P02.2, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P21.1, P21.2, P22, P23, P24, P25, P61, P62, P63, P64, P65, P66.

Technique anchors confirmed against the catalog **[verified]**:

| Beamline | Technique | Notes |
| --- | --- | --- |
| P01 | Nuclear resonant scattering, IXS / RIXS (2.5-80 keV) | Dynamics; IRIXS spectrometer |
| P02.1 | Powder diffraction / total scattering / PDF | High-energy |
| P02.2 | Extreme conditions (diamond anvil cell) | |
| P03 | SAXS / WAXS (MiNaXS), 9-23 keV | Micro/nano-focus small-angle |
| P04 | Soft X-ray spectroscopy (250-3000 eV) | Variable-polarization undulator |
| P05 | Imaging Beamline (IBL): micro/nano-tomography (5-50 keV) | Hereon-operated |
| P06 | Hard X-ray micro/nano-probe (PETRA III nano) | Largest public config set |
| P07 | High-Energy Materials Science (HEMS) | Joint Hereon + DESY |
| P08 | High-resolution diffraction | |
| P09 | Resonant scattering and diffraction (+ HAXPES, + magnetism) | dif / mag endstations |
| P10 | Coherence Applications (XPCS, coherent imaging) | |
| P11 | Bio-imaging and diffraction (macromolecular crystallography, high throughput) | |
| P12/P13/P14 | EMBL beamlines: BioSAXS (P12), MX (P13/P14) | EMBL-operated |
| P21.1/P21.2 | Swedish Materials Science (high-energy diffraction/scattering) | |
| P22 | Hard X-ray photoelectron spectroscopy (HAXPES) | |
| P23 | In situ X-ray diffraction | |
| P24 | Chemical crystallography | |
| P61 | High-energy white-beam (Large Volume Press) | |
| P62 | SAXS / soft-matter (under earlier development) | |
| P63 | OperandoCat | under construction |
| P64/P65 | X-ray absorption spectroscopy (EXAFS/XANES) | |

Caveat: P02.1/P02.2 and P21.1/P21.2 are split stations under one designation, which is part of the 25-vs-27 spread (beamline-vs-station distinction). **[verified]**

---

## 3. Control-system stack, by layer

PETRA III beamlines run a **Tango + Sardana** stack, NOT EPICS. This is the opposite control substrate from the APS 2-BM / FXI (EPICS) and PSI TOMCAT (EPICS) pilots, and the same family as ESRF (Tango, via BLISS) and MAX IV. DESY is a Tango consortium member and a named Sardana supporting institution. **[verified]**

> Layer scope: PETRA III's accelerator/machine controls run on DESY's own **TINE / DOOCS** (the `doocs` group is public on gitlab.desy.de), not Tango. That is out of scope for beamline device topology but relevant if a deployment page reaches into machine status. **[verified]**

### Device IO / Tango (the floor)

- **Tango is the device floor.** Each device (motor, counter, detector, mono) is a Tango device with a `domain/family/member` address (e.g. `p01/timer/eh1.01`), hosted by a Tango device server, registered in a per-host Tango database (`haspp01eh1:10000`). **[verified]** [tango-ds source tree](https://gitlab.desy.de/tango-ds)
- **The device-server source lives in `gitlab.desy.de/tango-ds/deviceclasses`** (~251 repos), organized as a topology taxonomy: `acquisition/{1d,2d}` (detectors), `beamlinecomponents` (monos, mirrors, diffractometers, CRLs, analyzers), `motion/motorcontrollers` (Aerotech, ACS, Smaract, Kohzu, Micos, PhyMotion, piezo), `magneticdevices` (petra3undulator, petra3shutter), `countertimer`, `temperature`, `vacuum`, `powersupply`, `sampleenvironment`. **[verified]**
- **Motion (PETRA IV):** `gitlab.desy.de/fpgafw/projects/petra/petra_motion_control`, an FPGA-firmware motion-control project explicitly for PETRA IV photon beamlines. **[verified]**

### Scan orchestration (the seam layer)

- **Sardana is the scan/motion SCADA layer over Tango** (Pools, MeasurementGroups, MacroServer, Spock CLI, Taurus UIs). DESY maintains its own Sardana fork and controller set. **[verified]** [fsec-sardana](https://gitlab.desy.de/fsec-sardana)
  - `fsec-sardana/sardana` (DESY fork), `sardana-controllers`, `sardana-macros`, `sardana-tango`, `sardana-redis`, `taurus`.
  - `sardana-controllers/python/` holds the per-instrument controller code: `motor/` (HasyMotorCtrl, HKLMotorCtrl), `twod/` (EigerDectris, Lambda, Pilatus, PCO, PerkinElmer, MarCCD, ...), `countertimer/`, `triggergate/` (PiLC time/ZMQ-based gating). **[verified]**
- **Newer experiment-control efforts coexist:** `fs-ec/desy-bluesky` (Bluesky at DESY, incl. a `p65` package), `fs-ec/daiquiri` (+ `daiquiri-sardana`, `daiquiri-bluesky`), `fs-ec/blissengine` / `blissdataplugins`, `fs-ec/ewoks`. This is a live multi-stack picture: Sardana is the incumbent, Bluesky/BLISS/Daiquiri are being explored. **[partly verified]** (relative production share per beamline unconfirmed.)

### Data writing (NeXus)

- **NeXus/HDF5 via the DESY-grown `nexdatas` stack**, present both on GitHub (`github.com/nexdatas`) and on gitlab.desy.de (`tango-ds/deviceclasses/acquisition/nexdatas/`): `nxsdatawriter` (Tango server writing NeXus/HDF5), `nxsconfigserver` (Tango front-end to a NeXus component DB), `nxsrecselector` (record selector), plus client tools `nxstools`, `nxscompdesigner`. **[verified]**

---

## 4. Where the code lives, and the device topology

**gitlab.desy.de is fully public via its REST API** (the deep-research workflow's "auth-gated" claim was wrong: the web UI renders client-side so a plain fetch sees nothing, but `https://gitlab.desy.de/api/v4/` serves public projects with no token). ~1,900 public projects; ~600 controls-relevant. This is the source of record for PETRA III device topology, and it is browsable, unlike PSI's firewalled gitea. **[verified]**

| Group (gitlab.desy.de) | Role |
| --- | --- |
| [`tango-ds`](https://gitlab.desy.de/tango-ds) (~251 repos) | Tango device-server source: detectors, monos, mirrors, diffractometers, motor controllers, undulators, shutters, sample environment, vacuum, temperature, power |
| [`fsec-sardana`](https://gitlab.desy.de/fsec-sardana) (6 repos) | DESY Sardana fork + `sardana-controllers` (per-instrument scan/motion controller code) + taurus |
| [`petra-iii-debian-packages`](https://gitlab.desy.de/petra-iii-debian-packages) (~184 repos) | The packaged runtime, incl. the per-beamline NeXus config packages and pytango/sardana/taurus/lavue/blissdata/asapo/frappy |
| [`fs-ec`](https://gitlab.desy.de/fs-ec) | Newer experiment-control: desy-bluesky, daiquiri, blissengine, ewoks |
| [`doocs`](https://gitlab.desy.de/doocs) | Accelerator/machine control (out of beamline scope) |
| [`fpgafw`](https://gitlab.desy.de/fpgafw) | FPGA firmware incl. PETRA IV motion control |

GitHub mirrors of the same data stack: [`github.com/nexdatas`](https://github.com/nexdatas), [`github.com/syncope/lavue`](https://github.com/syncope/lavue) (live detector viewer; an inventory of PETRA III endstation detectors: Pilatus, Lambda, Eiger, PerkinElmer, PCO, LimaCCD), [`github.com/djlns/irixs`](https://github.com/djlns/irixs) (P01 RIXS analysis, not controls).

### The device topology source: OnlineXML

The decisive find for CORA deployment pages. Each beamline has a `python-nxstools-extras-pNN` package under `petra-iii-debian-packages`, and inside it `xml/online_hasp*.xml` is a **complete machine-readable device registry per endstation**. Each `<device>` entry carries: logical name, role `type`, `module` (the Tango device class), the Tango device address, the Tango DB hostname, and control protocol. Example, P01 EH1 (`online_haspp01eh1.xml`, **296 device entries**) **[verified]**:

```xml
<device>
   <name>eh1_t01</name>
   <type>timer</type>
   <module>dgg2</module>
   <device>p01/timer/eh1.01</device>
   <hostname>haspp01eh1:10000</hostname>
   <control>tango</control>
</device>
```

This is name -> Tango class -> Tango address -> host -> protocol for every motor, counter, detector, mono, etc. Each `module` value maps directly to a `tango-ds/deviceclasses/.../<Module>` source repo. The sibling per-beamline `.xml` files (e.g. P01: `nrsdiffractometer`, `rixsdet`, `kbmirror`, `crl`, `cryostage`, `samplestage`) are the NeXus component definitions. The default branches are deployment-packaging branches (mostly `debian/jessie`, P61 `debian/stretch`, P62 `main`), so the configs reflect real installed systems, with the age caveat that some entries may lag the live floor. **[verified]**

### OnlineXML coverage map (directly ingestible)

| Beamline | OnlineXML (endstation files) | NeXus components | Branch |
| --- | --- | --- | --- |
| P01 | 3 (eh1/eh2/eh3) | 21 | debian/jessie |
| P02 | 3 (ch1/ch1a/ch2) | 37 | debian/jessie |
| P03 | 2 (main/nano) | 29 | debian/jessie |
| P04 | 2 (exp1/exp2) | 18 | debian/jessie |
| P06 | 3 | 44 | debian/jessie |
| P07 | 1 (eh2) | 14 | debian/jessie |
| P08 | 1 | 18 | debian/jessie |
| P09 | 3 (main/dif/mag) | 21 | debian/jessie |
| P10 | 3 (e1/e2/lab) | 18 | debian/jessie |
| P11 | 1 (sardana) | 0 | debian/jessie |
| P21 | 4 (211eh/212oh/21eh3/lab) | 0 | debian/jessie |
| P22 | 2 | 3 | debian/jessie |
| P23 | 2 (dev/eh) | 0 | debian/jessie |
| P24 | 2 | 0 | debian/jessie |
| P61 | 1 | 0 | debian/stretch |
| P62 | 0 | 0 | main |
| P64 | 1 | 12 | debian/jessie |
| P65 | 1 | 12 | debian/jessie |

18 beamlines with public configs. Absent: P05, P12/P13/P14, P25, P63, P66 (P05/P07 Hereon; P12/P13/P14 EMBL run their own stacks; P63 under construction). Richest component sets: P06 (44), P02 (37), P03 (29). Cleanest single-endstation starting page: **P01 EH1** (296 devices, 21 components, full NRS/RIXS instrument). **[verified]**

### Extraction note

`scripts/reverse_engineer/` has an OnlineXML path (`--source onlinexml`) that pulls each `python-nxstools-extras-pNN` package's `xml/online_*.xml` from `gitlab.desy.de` and emits per-beamline `facts.md` + `beamline.candidate.yaml`. The underlying pull is a plain unauthenticated GitLab API call:

```
GET https://gitlab.desy.de/api/v4/projects/<url-encoded path>/repository/files/<url-encoded xml/online_*.xml>/raw?ref=<default_branch>
```

The parse maps each `<device>` to a CORA Family at Asset granularity (the stage, not the per-axis tuning), carrying the Tango address / logical name in the descriptor `pv` field (the opaque control-handle slot), every value `confirm` until DESY staff verify it. A config snapshot is strong evidence, not a CORA-owned fact.

Beamline directories under `beamlines/` are named by beamline ID (`p01`, `p10`, the EMBL MX beamlines `p13` / `p14` / `pe2`), not by source-package name; the OnlineXML enclosures do not encode the beamline, so the extractor is run with `--name python-nxstools-extras-pNN=PNN` to set the directory. Multi-endstation beamlines (p04 = EXP1/EXP2, p10 = E1/E2/LAB/...) are one directory per beamline with the endstations as enclosure rows inside, the same convention the EMBL beamlines use (p13 holds P13-EH1 + P13-OH1). The cross-beamline Family-frequency fold is in [`recurrence.md`](recurrence.md); its standing verdict is that PETRA III earns no new catalog Family (all recurring Families are already graduated, and the OnlineXML / MXCuBE class-name fallbacks are a curation backlog, not graduation signal).

---

## 5. Data management

**[partly verified]** PETRA III's data ecosystem surfaces in the public packaging: `asapo` (DESY's high-throughput data-streaming framework, `python-asapo-consumer`/`-producer`), `scingestor` + `pyscicat`/`pyicat-plus` (SciCat/ICAT catalog ingestion), `nxsconfigserver-db` (the NeXus component database), and the `nexdatas` writer chain. NeXus/HDF5 is the output format. The detailed data-policy, catalog-of-record, and DOI-minting chain were not researched in depth and are an open item; the presence of SciCat ingestion tooling (`pyscicat`, `scingestor`) signals a SciCat-family catalog seam similar to PSI's, to be confirmed.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI / TOMCAT lens: device IO is the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency.

**Where Tango stays the floor (drive through, never CORA).** PETRA III device IO is Tango (device servers in `tango-ds`, addressed as `domain/family/member` on per-host Tango DBs). CORA's ControlPort would actuate **through** this Tango floor, the same way it actuates through EPICS at 2-BM/FXI/TOMCAT, only over a Tango adapter rather than a Channel Access one. CORA never owns Tango devices, device servers, or the Tango DB. The DOOCS/TINE accelerator stack and the ASAPO fast-data transport are out of scope. **This is the first Tango floor in the fleet's EPICS-heavy pilot set (ESRF BLISS is the only sibling), so it is the trigger for a Tango ControlPort adapter** alongside the existing EPICS one.

**What CORA replaces (edge orchestration).** The scan/alignment orchestration role is held today by **Sardana** (Pool / MacroServer / MeasurementGroup), with Bluesky/Daiquiri/BLISS being explored. This is the layer the 2-BM seam designates as CORA's: CORA's EdgeConductor would conduct routines over the Tango floor where Sardana's MacroServer sits today, incrementally and routine-by-routine. A Sardana-deployed beamline is the "replacing a solid existing implementation" case: treat Sardana as DATA to learn from (its Pool/MeasurementGroup decomposition, its controller abstraction, the OnlineXML device model), NOT a spec to mirror. Pitch CORA conducting on governance, replayability, recipe-binding, provenance, never on out-executing Sardana on speed.

**Source-of-truth contest (data).** The SciCat-family ingestion tooling (`pyscicat`, `scingestor`) plus `nxsconfigserver-db` is the data seam. As at PSI, CORA stays the system of record for the experiment and either inverts source-of-truth (feeding the catalog downstream) or projects its event-sourced record into the facility catalog at the publish seam. CORA owns its own data-of-record (PG event store); NeXus/HDF5 output and the catalog are a source to subsume, not a dependency. Decision deferred until a PETRA III deployment is actually in scope.

**Coexist.** The DESY user office / proposal system (identity and scheduling, read via an ACL adapter, not replaced), ASAPO (a data-transport channel CORA observes, not owns), the NeXus writer chain (output CORA governs the production of), and any ELOG-style logbook (record-keeping overlap CORA subsumes at the debrief layer).

---

## 7. Open questions (for DESY staff)

These could not be settled from public sources and need operator confirmation before any seam lock.

1. **Per-beamline orchestration today:** which beamlines run Sardana vs Bluesky vs Daiquiri vs BLISS in production? The public source shows all four; the live split is unknown.
2. **OnlineXML freshness:** the `debian/jessie` branch age suggests these configs may lag the live floor. How current is each `online_*.xml` versus the running Tango DB?
3. **Tango DB as live source:** is the per-host Tango database (`haspp01eh1:10000` etc.) queryable for a live device list, so CORA reads current topology rather than a packaged snapshot?
4. **Detector control contract per endstation:** which detectors per beamline, and which driver path (Tango device class in `acquisition/2d`, LimaCCD, ASAPO)?
5. **Data catalog seam:** is SciCat (or ICAT) the mandated catalog, at what ingestion point (ASAPO? `scingestor`?), and is ingestion mandatory per proposal? This decides invert-vs-project.
6. **PETRA IV timeline + per-beamline migration:** which PETRA III beamline topologies are stable vs slated for imminent change under PETRA IV? `petra_motion_control` signals a new motion substrate.
7. **Identity chain:** what is the DESY proposal -> user-group -> data-access chain CORA must read, and via which API?
8. **Identifier mapping:** confirm how `pNN` + endstation host (`haspp01eh1`, `haspp01eh2`, ...) map to CORA's run/acquisition-context identifiers.

---

## 8. Source list

**Facility (hardware facts):**
- PETRA III: https://photon-science.desy.de/facilities/petra_iii/index_eng.html
- Beamlines overview: https://photon-science.desy.de/facilities/petra_iii/beamlines/index_eng.html
- PETRA IV upgrade: https://www.desy.de/research/facilities__projects/petra_iv/index_eng.html
- PETRA IV project site: https://petra4.desy.de/

**Controls source (device topology, gitlab.desy.de, public API):**
- API root (no auth): https://gitlab.desy.de/api/v4/projects?visibility=public
- tango-ds device servers: https://gitlab.desy.de/tango-ds
- fsec-sardana (DESY Sardana fork + controllers): https://gitlab.desy.de/fsec-sardana
- petra-iii-debian-packages (runtime + per-beamline NeXus configs): https://gitlab.desy.de/petra-iii-debian-packages
- fs-ec (Bluesky/Daiquiri/BLISS/ewoks): https://gitlab.desy.de/fs-ec
- doocs (accelerator control, out of scope): https://gitlab.desy.de/doocs
- fpgafw (PETRA IV motion control): https://gitlab.desy.de/fpgafw

**Controls / data stack (GitHub mirrors + ecosystem):**
- nexdatas (NeXus/Tango data writer chain): https://github.com/nexdatas
- LaVue live detector viewer: https://github.com/syncope/lavue
- IRIXS (P01 RIXS analysis): https://github.com/djlns/irixs
- Sardana: https://gitlab.com/sardana-org/sardana
- Tango Controls: https://www.tango-controls.org/
- Tango device class catalogue: https://www.tango-controls.org/developers/dsc/
- Sardana Controls: https://www.sardana-controls.org/
