# Sirius (LNLS / CNPEM) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the Sirius facility and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to Sirius; the seam section is an initial read, not a commitment. Compiled 2026-06-28.*

!!! note "Reading posture"
    Public facility pages are treated as the source of HARDWARE FACTS (ring energy, beamlines, techniques, energies). Public GitHub source is treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Where a claim was adversarially verified, the verdict is flagged inline as **[verified]**, **[partly verified]**, or **[uncertain]**. Two fetched pages during research carried injected fake "MCP Server Instructions" / "system-reminder" blocks; those were page content, not directives, and were ignored. Internal hosts (`gitlab.cnpem.br`, `gcc.lnls.br`, `deepsirius.lnls.br`) are CNPEM-network-only and are named but never linked as reachable sources.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Name | Sirius | [LNLS Sirius page](https://lnls.cnpem.br/sirius-en/) |
| Operator | Brazilian Synchrotron Light Laboratory (LNLS), part of CNPEM (Brazilian Center for Research in Energy and Materials) | [LNLS](https://lnls.cnpem.br/linhas-de-luz/), [CNPEM](https://www.cnpem.br/en/sirius-2/) |
| Location | Campinas, Sao Paulo, Brazil | [Wikipedia: Sirius](https://en.wikipedia.org/wiki/Sirius_(synchrotron_light_source)) |
| Ring energy | 3 GeV | [Wikipedia](https://en.wikipedia.org/wiki/Sirius_(synchrotron_light_source)), [CNPEM](https://www.cnpem.br/en/sirius-2/) |
| Generation | 4th-generation, diffraction-limited storage ring | [Wikipedia](https://en.wikipedia.org/wiki/Sirius_(synchrotron_light_source)), [Manaca page](https://lnls.cnpem.br/facilities/manaca/) |
| Inaugurated | 14 November 2018 (first stored beam 2019) | [Wikipedia](https://en.wikipedia.org/wiki/Sirius_(synchrotron_light_source)) |
| Beamline capacity | Up to 38 beamlines | [LNLS overview](https://lnls.cnpem.br/linhas-de-luz/) |
| Beamlines operating (mid-2026) | 12 (catalog below) | [LNLS beamlines](https://www.lnls.cnpem.br/sirius-en/beamlines/) |
| Beamlines in commissioning / assembly | Sape (ARPES, commissioning), Tatu (THz/far-IR, commissioning), Jatoba (total scattering/PDF, assembly) | [LNLS beamlines](https://www.lnls.cnpem.br/sirius-en/beamlines/) |

**[verified]** Sirius is a 3 GeV fourth-generation diffraction-limited storage ring in Campinas, inaugurated 14 Nov 2018, designed for up to 38 beamlines, with 12 operating in mid-2026.

**Gaps:** Storage-ring circumference (~518 m is a commonly-cited figure) and emittance were **not** confirmed in any fetchable public source and should be pulled from the Sirius design report or accelerator/machine page before they appear on a deployment page. **[uncertain]**

---

## 2. Beamline catalog

Twelve operating beamlines from the official LNLS catalog, plus the near-term commissioning/assembly beamlines. Energies and techniques are from each beamline's official facility page. No beamlines invented; all trace to `lnls.cnpem.br`.

| Name | Technique | Energy | Status | Source |
| --- | --- | --- | --- | --- |
| Carnauba | Coherent X-ray nanoprobe: XRF, XRD, XAS, ptychography, BCDI, XEOL, STXM, tomography | 2.05-15 keV (std 3-15) | Operating (TARUMA station since Nov 2020; SAPOTI in commissioning) | [page](https://lnls.cnpem.br/facilities/carnauba/) |
| Caterete | Coherent X-ray scattering: CXDI, XPCS, SAXS/USAXS, ptychographic nanotomography | 3-24 keV | Operating | [page](https://lnls.cnpem.br/facilities/caterete/) |
| Cedro | Synchrotron-radiation circular dichroism (SRCD), UV/VUV | ~5-8 eV (160-240 nm) | Operating (fast-track / hybrid lamp+synchrotron) | [page](https://lnls.cnpem.br/facilities/cedro/) |
| Ema | Extreme-condition XRD, XAS (XANES/EXAFS); XMCD/CDI/ptychography in commissioning | 5-32 keV (planned 2.7-30) | Operating (microfocus since Nov 2020; nanofocus in design) | [page](https://lnls.cnpem.br/facilities/ema/) |
| Imbuia | IR nano/microspectroscopy: s-SNOM + synchrotron IR, micro-FTIR, QCL | mid-far IR ~105-520 meV | Operating | [page](https://lnls.cnpem.br/facilities/imbuia/) |
| Ipe | Inelastic scattering + photoelectron spectroscopy: RIXS, XAS, XPS (soft X-ray) | 100-2000 eV | Operating | [page](https://lnls.cnpem.br/facilities/ipe/) |
| Manaca | Macromolecular crystallography (MX); serial + room-temperature; 48-pin auto changer; MXCuBE3 | 5-20 keV | Operating | [page](https://lnls.cnpem.br/facilities/manaca/) |
| Mogno | X-ray micro/nanotomography; phase-contrast, 4D time-resolved | 22, 39 keV (tender), 67.5 keV (hard) | Operating | [page](https://lnls.cnpem.br/facilities/mogno/) |
| Paineira | Powder XRD (PXRD), in situ/operando | 16-30 keV (currently fixed ~19.5) | Operating (temp wiggler; undulator planned) | [page](https://lnls.cnpem.br/facilities/paineira/) |
| Quati | Quick-XAS (XANES/EXAFS), time/space-resolved | 4.5-35 keV | Operating (advanced commissioning, accepting proposals) | [page](https://lnls.cnpem.br/facilities/quati/) |
| Sabia | Soft X-ray absorption + imaging: XAS, PEEM, XLD, XMLD, XMCD | 200-1600 eV | Operating | [page](https://lnls.cnpem.br/facilities/sabia/) |
| Sapucaia | SAXS / USAXS | 5-20 keV (commissioned at 8) | Operating (time-resolved to 1 ms) | [page](https://lnls.cnpem.br/facilities/sapucaia/) |
| Sape | ARPES | ~8-70 eV | Commissioning | [page](https://lnls.cnpem.br/facilities/sape/) |
| Tatu | THz / far-IR tip-enhanced nanospectroscopy (s-SNOM) | far-IR / THz | Commissioning / construction | [page](https://lnls.cnpem.br/facilities/tatu/) |
| Jatoba | Total X-ray scattering + PDF; WAXS, GIWAXS, GIPDF, CT | 41-68 keV | Assembly (test experiments expected H1 2026) | [page](https://lnls.cnpem.br/facilities/jatoba/) |

Ten further beamlines (Ariranha, Hibisco, Pitanga, Quiriquiri, Sibipiruna, Sussuarana, Teiu, Timbo, and others) are named at project stage on the [overview](https://lnls.cnpem.br/linhas-de-luz/); they are not catalogued here because they have no public technique/energy facts yet.

**Status-count caveat [uncertain]:** the LNLS overview text says "10 delivered and open" while the beamlines page lists 12 operating; the discrepancy is a snapshot-date artifact (Quati and Sapucaia moved from assembly to open). Treat 12 as the current figure and re-confirm with staff.

---

## 3. Control-system stack, by layer

Sirius runs **two distinct EPICS-based ecosystems split by layer**: an accelerator/machine stack (`lnls-sirius` org) and a beamline stack (`cnpem` org, the Bluesky-based "sophys" family). The beamline stack is the one a CORA deployment touches.

### Device IO / EPICS (the floor)

- **EPICS** is the control-system foundation at both accelerator and beamline level. **[verified]**
- Machine-level device IO: soft IOCs in [`lnls-sirius/machine-applications`](https://github.com/lnls-sirius/machine-applications) ("Soft IOCs for Sirius Control System"); device classes and the naming system in the `siriuspy` package ([`lnls-sirius/dev-packages`](https://github.com/lnls-sirius/dev-packages)). Custom low-level IO uses BeagleBone-based IOCs (BSMP/PRU-RS485), StreamDevice, and an EtherIP IOC for Allen-Bradley PLCs ([`lnls-sirius/etherip-ioc`](https://github.com/lnls-sirius/etherip-ioc)).
- Beamline-level device IO: **Ophyd over EPICS PVs**. `ExtendedEpicsMotor` subclasses Ophyd `EpicsMotor` with EPICS record fields (`.MRES`, `.VMAX`, `.CNEN`) and PV prefixes; a mnemonic-to-EPICS-prefix map gives users shorthand names ([`cnpem/sophys-common`](https://github.com/cnpem/sophys-common), [`cnpem/sophys-cli-extensions`](https://github.com/cnpem/sophys-cli-extensions)). **[verified]**
- Detectors: EPICS **areaDetector** drivers, including the in-house [`cnpem/ADPimega`](https://github.com/cnpem/ADPimega) (PiMega detectors) plus ADEiger, ADAravis, ADSimDetector IOCs; motion via [`cnpem/pmac`](https://github.com/cnpem/pmac) (Delta Tau PMAC). EPICS deployment is containerized via [`cnpem/epics-in-docker`](https://github.com/cnpem/epics-in-docker).

### Orchestration + scan engine (the seam layer)

- The current beamline scan/orchestration layer is the **Bluesky/Ophyd-based "sophys" family** ("Sirius Ophyd and Bluesky utilitieS"), built by the LNLS/CNPEM Control Software Group. **[verified]**
- Architecture is the standard NSLS-II Bluesky pattern, localized: **Bluesky RunEngine** fronted by **bluesky-queueserver** (RE Manager) and **bluesky-httpserver**. Clients submit plans as queue items over the HTTP API. **[verified]**
- [`cnpem/sophys-common`](https://github.com/cnpem/sophys-common): shared Ophyd device classes + Bluesky plans; per-beamline `sophys-<beamline>` packages import from it and supply hardware instantiation via an `instantiate_devices()` contract.
- [`cnpem/sophys-cli-core`](https://github.com/cnpem/sophys-cli-core) + [`cnpem/sophys-cli-extensions`](https://github.com/cnpem/sophys-cli-extensions): an IPython-based orchestration CLI (plans as `%scan`/`%grid_scan` magics); `--local` runs an in-process RunEngine, default mode drives the queueserver over HTTP. Extensions hold SIRIUS beamline-specific plans (EMA, IPE named).
- CNPEM maintains forks of [`cnpem/bluesky`](https://github.com/cnpem/bluesky) and [`cnpem/bluesky-httpserver`](https://github.com/cnpem/bluesky-httpserver).
- The older framework **py4syn** ([`lnls-sol/py4syn`](https://github.com/lnls-sol/py4syn), last push 2022, last code commit 2019) is dormant and superseded for new beamlines by sophys, though no source explicitly labels it deprecated and its repo is not archived. **[partly verified]**

### GUI

- Desktop: [`cnpem/sophys-gui`](https://github.com/cnpem/sophys-gui), a Qt/PyQt client controlling/monitoring a Bluesky instance over HTTP Server + Kafka (queue management, dynamic plan forms, login/permission tiers, live plotting via Kafka Bluesky Live). **[verified]**
- Web: [`cnpem/sophys-web`](https://github.com/cnpem/sophys-web), a Next.js/React/TypeScript monorepo of beamline web apps over bluesky-httpserver (named apps: `spu-ui` for Sapucaia, `qua-ui` for Quati). **[verified]**
- Accelerator GUI: PyDM + PyQt (`SiriusHLA` apps in [`lnls-sirius/hla`](https://github.com/lnls-sirius/hla)). A PyDM widget library, `sirius-widgets-case`, is reused in the beamline stack specifically for AreaDetector ROI configuration. **[verified]**
- MX beamlines (Manaca): **MXCuBE Web** ([`cnpem/mxcubeweb-lnls`](https://github.com/cnpem/mxcubeweb-lnls), Manaca page cites MXCuBE3). This repo's per-device MXCuBE HardwareObjects config is public and carries real EPICS handles (`MNC:` prefix), so it is the one exception to the firewalled device source: it unlocks Manaca's device pass (see `beamlines/manaca/facts.md` and `recurrence.md`). The config is the newer per-device YAML HardwareObjects format, not the classic XML that ALBA / SOLEIL use.

### Data acquisition

- Run documents (start/descriptor/event/stop) are **streamed over Kafka** (msgpack-encoded) via `make_kafka_callback`; consumers (sophys-cli monitor, [`cnpem/sophys-live-view`](https://github.com/cnpem/sophys-live-view)) reconstruct runs from the Kafka stream. **[verified]**
- A **databroker** Broker is wired in as a document sink (default `temp` broker in sophys-cli); it is present but not established in source as the single canonical persistent store. **[partly verified]**
- **Redis** appears in the web client as a versioned (ETag) hash store for client-side UI/application state, and in the EMA CLI extension for detector/metadata selection state; it is not on the run-document data path. **[partly verified]**

---

## 4. Where the code lives

All public LNLS/Sirius/CNPEM source is on **GitHub** across five orgs. Repo health from live GitHub API (2026-06-28).

| Org | Repos | Role | Health |
| --- | --- | --- | --- |
| [`cnpem`](https://github.com/cnpem) | ~79 | **Modern beamline stack** (sophys), ssc-* scientific computing, EPICS areaDetector IOCs | Very active; sophys-web/-common pushed within days of survey |
| [`lnls-sirius`](https://github.com/lnls-sirius) | ~177 | Accelerator/machine control: soft IOCs, HLA, archiver, dev-packages | Very active (multiple pushes June 2026) |
| [`lnls-dig`](https://github.com/lnls-dig) | ~154 | FPGA/gateware, BPM electronics, timing (openMMC, general-cores) | Active; low-level, not scan orchestration |
| [`lnls-fac`](https://github.com/lnls-fac) | ~51 | Accelerator physics modeling (pyaccel, trackcpp, pymodels) | Active to 2026-06 |
| [`lnls-sol`](https://github.com/lnls-sol) | ~43 | Beamline Operation Software Group; **legacy** (py4syn, mxcube fork) | Mostly pre-2022; superseded by cnpem/sophys |

**Self-hosted GitLab:** `gitlab.cnpem.br` exists and is the canonical upstream for the SOL/sophys beamline stack (the `sophys-common` `pyproject.toml` homepage/issues point there, with GitHub as a copy; `ADPimega` depends on `pimega-api` hosted there). It is **internal-only** (returns NXDOMAIN in public DNS) and cannot be linked or read. **[verified]** Whether GitHub is org-wide a mirror of GitLab is **not** established; verified only for SOL/sophys via pyproject metadata. The accelerator orgs may be GitHub-native. **[partly verified]**

**PyPI:** seven genuine LNLS/Sirius packages published, all by the `lnls-sirius` / `lnls-fac` users with GitHub homepages: [`siriuspy`](https://pypi.org/project/siriuspy/), [`mathphys`](https://pypi.org/project/mathphys/), `pydrs`, `siriushlacon`, `siriuscommon`, `conscommon`. The sophys beamline packages are **not** on public PyPI (install from git / internal index), consistent with internal GitLab hosting. py4syn is GitHub-only with docs on [ReadTheDocs](https://py4syn.readthedocs.io/).

**Docs sites:** [`cnpem.github.io/sophys-common`](https://cnpem.github.io/sophys-common/) (public), [`cnpem.github.io/iguape`](https://cnpem.github.io/iguape/) (public); `gcc.lnls.br` (Sirius Scientific Computing / GCC group) and `deepsirius.lnls.br` are CNPEM-internal.

**No public non-GitHub VCS** (SourceForge/Bitbucket) was found; the one SourceForge hit (LNLS-MML lattice files) is dead and says "moved to GitHub." **[partly verified]** as an absolute universal.

---

## 5. Data management + processing

- **Formats:** HDF5 is the working format across the processing stack (ssc-raft and ssc-cdi read/write HDF5 via h5py, with flat/dark fields and embedded software+version metadata; Mogno tomography uses DXchange-style `exchange/data`, `exchange/data_white_pre/post`, `exchange/data_dark` layout). The control layer is moving to **NeXus**: sophys-gui's Bluesky autosave writes "metadata inside the NeXus file" with **JSON** as the default sidecar format (enum JSON/NEXUS/SPEC). NeXus here is a metadata serialization option, not yet the universal raw-data container. **[verified]**
- **Data standardization engine:** **Assonant** ("a beamline-agnostic event processing engine for data collection and standardization", [ICALEPCS 2023 WE3BCO06](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO06.html)) applies a **NeXus-compliant, technique-centric data standard** transparently for beamline teams, channeling data into an event-driven infrastructure of streaming + microservices (MX and imaging named). This is the named layer behind the NeXus direction noted above. **[verified]**
- **Catalog / portal:** No public facility-wide data portal was found via direct survey, BUT LNLS is a named collaborator on the **ICAT** metadata catalogue effort ([ICALEPCS 2023 WE3BCO07](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO07.html), ESRF-led, with DataGateway / DataHub UIs, e-logbooks, sample tracking). LNLS is an adopter, not the lead, so the deployment status at Sirius is unconfirmed; this revises the earlier "no catalog" read toward "a catalogue direction exists, status unknown." The user-facing proposal system (SAU, Sistema de Atendimento ao Usuario) and any ELN were not surfaced publicly. **[partly verified]**
- **HPC:** the imaging/data-processing cluster is **TEPUI** ([Furusato et al. 2022, doi:10.1007/978-3-031-04209-6_1](https://doi.org/10.1007/978-3-031-04209-6_1)): SLURM-scheduled GPU cluster, LDAP auth, SSH job submission, GPU partitions (`--gres=gpu:`), shared storage mounted at **`/ibira`**. Web tools (deepsirius-ui, launch3d, the Mogno reconstruction GUI) submit SLURM jobs to it. **[verified]** Note CNPEM also runs a separate cluster ("Marvin" at LNBio), so name TEPUI specifically.
- **Reconstruction / analysis software** (GCC "Sirius Scientific Computing" ssc-* family):
  - [`cnpem/ssc-raft`](https://github.com/cnpem/ssc-raft): fast tomographic reconstruction, C/CUDA, parallel (FBP/EM) + conebeam (FDK/EM); Zenodo [10.5281/zenodo.10988342](https://doi.org/10.5281/zenodo.10988342).
  - [`cnpem/ssc-cdi`](https://github.com/cnpem/ssc-cdi): multi-GPU ptychography/CDI; published [J. Imaging 10(11):286, 2024](https://doi.org/10.3390/jimaging10110286).
  - `ssc-pimega` (detector geometric restoration), `ssc-deepsirius` / [`deepsirius-ui`](https://github.com/cnpem/deepsirius-ui) (DL tomographic segmentation), [`harpia`](https://github.com/cnpem/harpia) + [`annotat3d`](https://github.com/cnpem/annotat3d) (GPU volumetric segmentation).
  - Beamline analysis GUIs: [`iguape`](https://github.com/cnpem/iguape) (Paineira XRD), `s4ci` (Sapucaia SAXS), [`arara`](https://github.com/cnpem/arara) (X-ray reflection analyzer).

---

## 6. The CORA seam (initial read)

This is a first pass, not a committed seam. It applies the same 2-BM/FXI lens: EPICS and device IO are the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through.

**Where EPICS stays the floor.** Sirius beamline device IO is Ophyd-over-EPICS, with areaDetector IOCs (ADPimega, ADEiger, ADAravis), PMAC motion, and a mnemonic-to-PV map. CORA's ControlPort would actuate **through** this EPICS floor exactly as it does at 2-BM and FXI; CORA never owns PVs, IOCs, or the device layer. The accelerator-side EPICS stack (`lnls-sirius`, soft IOCs, timing, PSS/PLC) is entirely out of scope.

**What CORA would replace or drive through.** The orchestration layer at Sirius is **Bluesky RunEngine + bluesky-queueserver + bluesky-httpserver**, with sophys plans on top. This is the layer the 2-BM seam designates as CORA's: CORA's EdgeConductor replaces the scan/alignment orchestration that the queueserver+plans layer performs today, conducting over the EPICS floor. Two seam shapes are possible and the choice is the central design question:

1. **Replace** the sophys/queueserver orchestration with CORA's Conductor, driving Ophyd/EPICS directly (the 2-BM "edge promoted to intended" posture).
2. **Drive through** the existing Bluesky httpserver as an actuation port, treating queueserver as the floor below CORA's conduct path (lighter, leaves sophys in place).

The Kafka run-document stream and databroker are the existing data-acquisition path; CORA brings its own data of record (PG event store), so these become a **source to subsume**, not a system CORA depends on, mirroring the "we do our own data of record" stance.

**Open design questions.**
- Replace vs drive-through at the queueserver boundary: which beamlines justify which? sophys is uniform facility-wide, so the decision likely generalizes rather than going per-beamline.
- Does CORA subsume the NeXus/JSON autosave metadata layer, or write alongside it during transition?
- The internal `gitlab.cnpem.br` holds production deployment configs not visible publicly; the true device inventory per beamline (PVs, controller boxes, axes) is not in public GitHub and must come from staff or descriptors.
- Proposal/governance: with no public SAU/ISPyB surface, how CORA's Trust/governance maps to Sirius's user-office and LDAP/role model is unknown.

---

## 7. Confidence + gaps

**Well-corroborated (multiple primary sources or verified):**
- Facility identity: 3 GeV, 4th-gen, Campinas, 2018, up to 38 beamlines. **[verified]**
- EPICS as the device-IO floor at both accelerator and beamline levels. **[verified]**
- sophys (Bluesky RunEngine + queueserver + httpserver + Ophyd) as the current beamline orchestration layer. **[verified]**
- Qt (sophys-gui) + Next.js/React (sophys-web) GUI tiers over httpserver. **[verified]**
- HDF5 working format, NeXus/JSON metadata direction. **[verified]**
- TEPUI HPC: SLURM + GPU + LDAP + SSH + `/ibira`. **[verified]**
- The five GitHub orgs and the cnpem-org location of the modern stack. **[verified]**

**Uncertain or single-source:**
- Ring circumference (~518 m) and emittance: **not confirmed**; pull from machine page / design report. **[uncertain]**
- Exact operating beamline count (10 vs 12, snapshot-dependent). **[uncertain]**
- py4syn formal deprecation status (inferred from activity contrast, not stated). **[partly verified]**
- GitHub-mirrors-GitLab org-wide (verified only for SOL/sophys). **[partly verified]**
- databroker as canonical persistent store; Redis role on the data path. **[partly verified]**
- "Facility-wide standardization" on sophys (plausible, no explicit source). **[partly verified]**
- No public data catalog: revised: a catalogue direction exists (LNLS on ICAT; Assonant standardizes to NeXus), but Sirius deployment status is unconfirmed. **[partly verified]**
- No public non-GitHub VCS (absolute universal; evidence consistent but not proof). **[uncertain]**

**What to ask facility staff:**
1. Storage-ring circumference, emittance, and current bunch/fill parameters.
2. Authoritative operating-beamline list and per-beamline orchestration: does every beamline use shared sophys, or are there private `sophys-<beamline>` repos / holdouts on py4syn?
3. Per-beamline device inventory (PV namespaces, controller boxes, motion axes, detectors) that lives on internal GitLab.
4. Data of record: is databroker/Tiled the persistent store, what NeXus application definitions (NXtomo?) are written, and where does raw data land relative to `/ibira`.
5. Proposal/user-office system (SAU), role/permission model (LDAP), and any ELN, for the governance seam.
6. TEPUI specifics (node/GPU count, storage capacity) and whether reconstruction is expected inline with acquisition.
7. PSS/interlock implementation (EPICS soft IOC vs Allen-Bradley PLC via EtherIP) at beamline endstations.

---

## 8. Key papers and proceedings

Sirius control/beamline software is documented mainly in **JACoW ICALEPCS proceedings**; the modern `sophys` orchestration stack and `siriuspy`/`sirius-hla` have **no peer-reviewed write-up** (source code only). Most relevant to a deployment page:

| Paper | Venue | Why it matters | DOI / URL |
| --- | --- | --- | --- |
| Assonant: A Beamline-Agnostic Event Processing Engine for Data Collection and Standardization | ICALEPCS 2023 | The named NeXus-compliant data-standardization layer; streaming + microservices | [10.18429/JACoW-ICALEPCS2023-WE3BCO06](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO06.html) |
| Extending the ICAT Metadata Catalogue to New Scientific Use Cases | ICALEPCS 2023 | LNLS as collaborator on a Photon/Neutron metadata catalogue (data-of-record seam) | [10.18429/JACoW-ICALEPCS2023-WE3BCO07](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO07.html) |
| Supervisory System for the Sirius Scientific Facilities | ICALEPCS 2021 | Facility-wide aggregation over EPICS + OPC-UA (safety, utilities, beamline components) | [10.18429/JACoW-ICALEPCS2021-THPV001](https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-THPV001.html) |
| TATU: FPGA-Based Trigger and Timer Unit on CompactRIO for the First Sirius Beamlines | ICALEPCS 2021 | Hardware triggering/DAQ; exposes EPICS PVs via Nheengatu; validated on 4 beamlines | [10.18429/JACoW-ICALEPCS2021-THPV021](https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-THPV021.html) |
| RemoteVis: Efficient Library for Remote Visualization of Large Volumes Using NVIDIA IndeX | ICALEPCS 2021 | RDMA volume transfer, Slurm-scheduled multi-GPU render, browser + Jupyter clients | [10.18429/JACoW-ICALEPCS2021-FRBL05](https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-FRBL05.html) |
| Software and Hardware Design for Controls Infrastructure at Sirius Light Source | ICALEPCS 2019 | Foundational EPICS-based accelerator control architecture | [10.18429/JACoW-ICALEPCS2019-MOPHA031](https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-MOPHA031.html) |
| Project Nheengatu: EPICS support for CompactRIO FPGA and LabVIEW-RT | ICALEPCS 2019 | The EPICS-to-FPGA glue (single generic build, per-setup config) underpinning beamline DAQ | [10.18429/JACoW-ICALEPCS2019-WEMPL002](https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-WEMPL002.html) |
| HD-DCM fly-scan motion analyses and upgraded beamline integration architecture | J. Synchrotron Rad. 2023 | Fly-scan integration architecture for the high-dynamic DCM | [10.1107/S1600577522010724](https://doi.org/10.1107/S1600577522010724) |

Additional confirmed control/motion papers (lower relevance to software architecture): HD-DCM FPGA/EPICS control ([ICALEPCS 2021 TUPV004](https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-TUPV004.html)), four-bounce monochromator control on Omron Delta Tau ([ICALEPCS 2021 TUPV003](https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-TUPV003.html)), Sirius Fast Orbit Feedback (FPGA + MicroTCA, [ICALEPCS 2023 MO3AO03](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-MO3AO03.html)), system identification on CompactRIO/LabVIEW ([ICALEPCS 2023 TUPDP006](https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-TUPDP006.html)), embedded dedicated cores feeding Redis + EPICS ([ICALEPCS 2019 WEMPR003](https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-WEMPR003.html)).

**Coverage gaps in the literature search:** IPAC 2023/2024 controls papers not crawled (index naming unresolved); ICALEPCS 2025 not yet on JACoW; no PCaPAC 2022 LNLS entry. The `sophys` stack, `siriuspy`, and Kafka/databroker pipelines have **no findable paper** (cite repos/PyPI directly).

---

## 9. Source list

**Facility (hardware facts):**
- LNLS Sirius page: https://lnls.cnpem.br/sirius-en/
- LNLS beamlines overview: https://lnls.cnpem.br/linhas-de-luz/
- LNLS beamlines (operating list): https://www.lnls.cnpem.br/sirius-en/beamlines/
- CNPEM Sirius: https://www.cnpem.br/en/sirius-2/
- Wikipedia, Sirius (synchrotron light source): https://en.wikipedia.org/wiki/Sirius_(synchrotron_light_source)
- Wikipedia, Brazilian Synchrotron Light Laboratory: https://en.wikipedia.org/wiki/Brazilian_Synchrotron_Light_Laboratory
- Beamline pages: [Carnauba](https://lnls.cnpem.br/facilities/carnauba/), [Caterete](https://lnls.cnpem.br/facilities/caterete/), [Cedro](https://lnls.cnpem.br/facilities/cedro/), [Ema](https://lnls.cnpem.br/facilities/ema/), [Imbuia](https://lnls.cnpem.br/facilities/imbuia/), [Ipe](https://lnls.cnpem.br/facilities/ipe/), [Manaca](https://lnls.cnpem.br/facilities/manaca/), [Mogno](https://lnls.cnpem.br/facilities/mogno/), [Paineira](https://lnls.cnpem.br/facilities/paineira/), [Quati](https://lnls.cnpem.br/facilities/quati/), [Sabia](https://lnls.cnpem.br/facilities/sabia/), [Sapucaia](https://lnls.cnpem.br/facilities/sapucaia/), [Sape](https://lnls.cnpem.br/facilities/sape/), [Tatu](https://lnls.cnpem.br/facilities/tatu/), [Jatoba](https://lnls.cnpem.br/facilities/jatoba/)

**Control software (GitHub orgs):**
- cnpem: https://github.com/cnpem
- lnls-sirius: https://github.com/lnls-sirius
- lnls-dig: https://github.com/lnls-dig
- lnls-fac: https://github.com/lnls-fac
- lnls-sol: https://github.com/lnls-sol

**Beamline orchestration (sophys):**
- sophys-common: https://github.com/cnpem/sophys-common (docs https://cnpem.github.io/sophys-common/)
- sophys-cli-core: https://github.com/cnpem/sophys-cli-core
- sophys-cli-extensions: https://github.com/cnpem/sophys-cli-extensions
- sophys-gui: https://github.com/cnpem/sophys-gui
- sophys-web: https://github.com/cnpem/sophys-web
- sophys-live-view: https://github.com/cnpem/sophys-live-view
- bluesky (fork): https://github.com/cnpem/bluesky
- bluesky-httpserver (fork): https://github.com/cnpem/bluesky-httpserver
- bluesky-queueserver (upstream): https://github.com/bluesky/bluesky-queueserver
- bluesky-httpserver (upstream): https://github.com/bluesky/bluesky-httpserver

**Device IO / EPICS:**
- machine-applications: https://github.com/lnls-sirius/machine-applications
- dev-packages (siriuspy): https://github.com/lnls-sirius/dev-packages
- hla: https://github.com/lnls-sirius/hla
- archiver-viewer: https://github.com/lnls-sirius/archiver-viewer
- etherip-ioc: https://github.com/lnls-sirius/etherip-ioc
- ADPimega: https://github.com/cnpem/ADPimega
- pmac: https://github.com/cnpem/pmac
- epics-in-docker: https://github.com/cnpem/epics-in-docker
- mxcubeweb-lnls: https://github.com/cnpem/mxcubeweb-lnls
- py4syn (legacy): https://github.com/lnls-sol/py4syn (docs https://py4syn.readthedocs.io/)

**Data + processing:**
- ssc-raft: https://github.com/cnpem/ssc-raft
- ssc-cdi: https://github.com/cnpem/ssc-cdi
- harpia: https://github.com/cnpem/harpia
- annotat3d: https://github.com/cnpem/annotat3d
- deepsirius-ui: https://github.com/cnpem/deepsirius-ui
- iguape: https://github.com/cnpem/iguape (docs https://cnpem.github.io/iguape/)
- arara: https://github.com/cnpem/arara
- TEPUI HPC paper: https://doi.org/10.1007/978-3-031-04209-6_1
- ssc-cdi paper (J. Imaging 2024): https://doi.org/10.3390/jimaging10110286
- MOGNO web-system paper (JPCS 3010): https://doi.org/10.1088/1742-6596/3010/1/012137
- CARNAUBA commissioning paper: https://doi.org/10.1117/12.2596496
- Assonant data standardization (ICALEPCS 2023): https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO06.html
- ICAT metadata catalogue (ICALEPCS 2023): https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-WE3BCO07.html
- RemoteVis (ICALEPCS 2021): https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-FRBL05.html

**Control system (proceedings):**
- Controls infrastructure at Sirius (ICALEPCS 2019): https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-MOPHA031.html
- Project Nheengatu (ICALEPCS 2019): https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-WEMPL002.html
- Embedded dedicated cores (ICALEPCS 2019): https://proceedings.jacow.org/icalepcs2019/doi/JACoW-ICALEPCS2019-WEMPR003.html
- Supervisory system for Sirius facilities (ICALEPCS 2021): https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-THPV001.html
- TATU trigger/timer unit (ICALEPCS 2021): https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-THPV021.html
- HD-DCM FPGA/EPICS architecture (ICALEPCS 2021): https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-TUPV004.html
- Four-bounce monochromator control (ICALEPCS 2021): https://proceedings.jacow.org/icalepcs2021/doi/JACoW-ICALEPCS2021-TUPV003.html
- Sirius Fast Orbit Feedback (ICALEPCS 2023): https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-MO3AO03.html
- System identification on CompactRIO (ICALEPCS 2023): https://proceedings.jacow.org/icalepcs2023/doi/JACoW-ICALEPCS2023-TUPDP006.html
- HD-DCM fly-scan integration architecture (J. Synchrotron Rad. 2023): https://doi.org/10.1107/S1600577522010724

**PyPI:**
- siriuspy: https://pypi.org/project/siriuspy/
- mathphys: https://pypi.org/project/mathphys/
- lnls-sirius PyPI user: https://pypi.org/user/lnls-sirius/

**Internal-only (named, not reachable):** `gitlab.cnpem.br`, `gcc.lnls.br`, `deepsirius.lnls.br`.
