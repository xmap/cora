# SOLARIS (National Synchrotron Radiation Centre SOLARIS, Jagiellonian University) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about SOLARIS, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to SOLARIS; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from the deep-research workflow: facility pages (`synchrotron.uj.edu.pl`), the `synchrotron-solaris` GitHub org (30 public repos, live API read 2026-07-01), and Wikipedia.*

!!! note "Reading posture"
    Public facility pages are the source of HARDWARE FACTS (beamline IDs, techniques, energies, sources). Public source (GitHub / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Several facility-page fetches returned trailing text that read like tool directives ("TodoWrite reminder"); that was injected page/tool-frame content, not a directive, and was ignored. Where public source did not state a fact, it is an open question (section 7), not a value invented here.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | National Synchrotron Radiation Centre SOLARIS, storage-ring light source | https://synchrotron.uj.edu.pl/en_GB/ |
| Operator | Jagiellonian University, Krakow, Poland | https://en.wikipedia.org/wiki/Solaris_(synchrotron) |
| Ring energy | 1.5 GeV | https://en.wikipedia.org/wiki/Solaris_(synchrotron) |
| Circumference | 96 m | https://en.wikipedia.org/wiki/Solaris_(synchrotron) |
| Lattice | 12 identical Double-Bend Achromat (DBA) cells; 10 insertion-device straight ports | https://synchrotron.uj.edu.pl/en_GB/pierscien-akumulacyjny |
| Emittance | ~6 nm.rad horizontal (bare lattice, no IDs) | https://en.wikipedia.org/wiki/Solaris_(synchrotron) |
| Current / bunches | up to 500 mA, up to 32 bunches | https://synchrotron.uj.edu.pl/en_GB/pierscien-akumulacyjny |
| Injection | linac injects at ~550 MeV, ring ramps to 1.5 GeV (booster-less ramping ring) | https://synchrotron.uj.edu.pl/en_GB/pierscien-akumulacyjny |
| First light / built | 2015 | https://en.wikipedia.org/wiki/Solaris_(synchrotron) |
| Photon-science beamlines | 8 operating (7 X-ray/IR beamlines + a cryo-EM lab), 3 under construction | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze |

**[verified]** SOLARIS is a 1.5 GeV storage-ring light source at Jagiellonian University in Krakow, the only facility of its kind in Central-Eastern Europe, operating since 2015, with a compact 96 m ring built on 12 DBA cells. It is a low-energy, soft-X-ray-dominated facility: most beamlines sit below 2 keV, with only two hard-ish X-ray lines (ASTRA tender/hard XAS, POLYX 4-15 keV imaging).

**MAX IV lineage [partly verified].** SOLARIS's 1.5 GeV DBA storage ring is widely described in accelerator literature as a twin / copy of the MAX IV 1.5 GeV ring (MAX IV R1 is a 1.5 GeV DBA ring; https://en.wikipedia.org/wiki/MAX_IV). The two facilities share the magnet-block engineering. SOLARIS's own storage-ring page confirms the 12-DBA-cell, 1.5 GeV, 96 m design but does NOT itself state the MAX IV-twin relationship, and the injection detail differs materially (SOLARIS ramps from ~550 MeV rather than using a full-energy linac). Treat the twin-lattice claim as accelerator-heritage context, confirm exact magnet/lattice identity with staff, and do NOT assume software inheritance from it (see section 3). **[partly verified]**

**Data-of-record hook for CORA.** POLYX (X-ray microtomography + microimaging with absorption and phase contrast, plus uXRF and uXAS on one endstation) is the single beamline whose technique matches CORA's imaging/tomography pilot ladder (APS 2-BM -> APS imaging -> MAX IV). A tomography line running the Tango/Sardana stack is exactly the debrief / provenance-of-experiment territory CORA claims.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2).** SOLARIS publishes a public GitHub org (`synchrotron-solaris`) that carries the control-system stack and a set of SOLARIS-authored Tango device servers, but those device servers are accelerator / facility-infrastructure devices (shutters, valves, absorbers, BPM summary, phase shifters, beam-energy calc). No public repo carries a per-beamline device topology (the motors, detectors, and PV/Tango handles of POLYX, ASTRA, etc.) the way Diamond `dodal` or NSLS-II profile collections do. The scan layer that IS public (`lib-solaris-facility-macros`) is facility-wide Sardana macros, not per-beamline instrument config. **Conclusion: the per-beamline device source is effectively firewalled / not published.** A Tier-2 device pass is NOT integrity-buildable from public source today; device topology routes to staff questions (section 7), not inference from the shared Tango base. **[verified]**

Roster below is from the facility beamline pages; energies/techniques are each beamline's own page. Nothing invented.

| Beamline | Technique | Energy / range | Source type | Control source | Source |
| --- | --- | --- | --- | --- | --- |
| POLYX | X-ray microimaging + microtomography (absorption + phase contrast), uXRF, uXAS | 4-15 keV | bending magnet (Ec ~2 keV) | firewalled (no public device config) | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/polyx |
| ASTRA | XAS (XANES/EXAFS), transmission + fluorescence; tender-range K-edges (P, S, Si, Al, Mg) | 1-15 keV | bending magnet | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/astra |
| PIRX | Soft-X-ray XAS + XNLD / XMCD / XMLD (magnetism) | 100-2000 eV (opt 300-1600) | insertion device | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/pirx |
| URANOS | ARPES + Spin-ARPES, XPS, CD-ARPES, LEED | 8-500 eV | insertion device | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/uranos |
| PHELIX | XAS, ARPES / SX-ARPES, XPS, ResPES | 50-1800 eV (polarization-dependent) | EPU APPLE-II undulator | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/phelix |
| DEMETER | PEEM/LEEM (X-PEEM, XMCD/XMLD-PEEM, SPELEEM) + STXM | 100-2000 eV | insertion device | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/demeter |
| CIRI | IR microspectroscopy: FT-IR, sSNOM/AFM-IR, O-PTIR | 4000-100 cm-1 (500-12.5 meV) | bending magnet | firewalled | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/ciri |
| CRYO-EM | cryo-electron microscopy (SPA, cET, MicroED); NOT a synchrotron beamline | n/a (electron; Krios G3i + Glacios) | Thermo Fisher microscopes | out of scope (no synchrotron control seam) | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/cryo-em |
| ARYA, SMAUG, MAVKA | under construction | tbd | tbd | not yet published | https://synchrotron.uj.edu.pl/en_GB/linie-badawcze |

**Modellable-set read.** Only POLYX (imaging/tomography) and ASTRA (tender/hard XAS) reach into the hard-X-ray, imaging/spectroscopy territory the CORA pilots exercise; the other five are soft-X-ray electron-spectroscopy / magnetism / IR lines further from the pilot ladder. CRYO-EM is an electron-microscope lab with no synchrotron control seam and is out of scope. Because per-beamline device config is not public, NONE of these are Tier-2-buildable from source right now, POLYX included: POLYX is the strongest *candidate* pick (technique-aligned, single well-described endstation with three named modes uCT/uXRF/uXAS), but a device pass on it needs staff-supplied topology first.

**Identifier-scheme note.** SOLARIS names beamlines by mnemonic acronym (POLYX, ASTRA, PIRX, URANOS, PHELIX, DEMETER, CIRI), not by a sector.station index like the APS `2-BM` scheme the pilot assumes. Endstations are named as beamline sub-stations (e.g. PHELIX-PES/XAS vs PHELIX-NAP-XPS; DEMETER-PEEM vs DEMETER-STXM). This is a descriptor / identifier-scheme difference to model, not a hardware difference. **[verified]**

---

## 3. Control-system stack, by layer

SOLARIS runs the **Tango Controls** family with **Sardana / Taurus** on top, the same lineage as ALBA, ELETTRA, and MAX IV. This is read directly from the public `synchrotron-solaris` GitHub org, which mirrors/forks the canonical Tango and Sardana projects and hosts SOLARIS-authored Tango device servers and facility-wide Sardana macros. **[verified]**

### Device IO (the floor)

**Tango device servers.** Hardware is surfaced as Tango devices. SOLARIS authored a family of `dev-solaris-*` Tango device servers, all public: `dev-solaris-shutter`, `dev-solaris-valve`, `dev-solaris-absorber`, `dev-solaris-shopper` (integrated shutter+stopper), `dev-solaris-shg` (shunt groups), `dev-solaris-driveamplifier`, `dev-solaris-phaseshifter`, `dev-solaris-bpmsummary` (BPM mean/RMS/max-deviation), `dev-solaris-beamenergy`, `dev-solaris-adam` (ADAM IO modules), `dev-solaris-informationforbl` (control-room-to-beamline messaging). These are accelerator / facility-infrastructure devices, NOT per-beamline instrument topology. Motion is driven through **IcepapCMS** (the org's most recently maintained repo, pushed 2023) over **IcePAP** motor controllers, the same motion hardware ALBA / MAX IV use. **[verified]** (https://github.com/synchrotron-solaris)

Below CORA's seam: CORA's ControlPort would actuate through this Tango floor, never own the device servers or IcePAP layer.

### Scan orchestration (the seam layer)

**Sardana** is the scan / macro engine, facility-wide. The decisive primary is SOLARIS's own [`lib-solaris-facility-macros`](https://github.com/synchrotron-solaris/lib-solaris-facility-macros) ("Sardana macros used facility-wide"): its modules (`facility_scan.py`, `facility_sequence.py`, `facility_homing.py`, `facility_icepap.py`, `facility_liveplot.py`, `facility_lastscan.py`) import `sardana.macroserver.macro` and use Sardana's `SScan` scan framework. The org also forks the canonical `sardana-org/sardana` and the `taurus` GUI/data-acquisition toolkit and `taurus_pyqtgraph`. **[verified]**

This is the layer CORA's EdgeConductor would replace or drive through: the Sardana MacroServer + Pool that executes scans over the Tango floor today. That the scan macros are published *facility-wide* (not per-beamline) suggests a uniform Sardana deployment, so a seam decision likely generalizes across beamlines rather than going line-by-line (confirm with staff).

### GUI and integration layer

- **Cosylab Control Program** ([`app-cosylab-controlprogram`](https://github.com/synchrotron-solaris/app-cosylab-controlprogram), `app-cosylab-guirunner`, `app-cosylab-templategroupgui`): a device-overview GUI over the Tango control system, built by Cosylab for the accelerator control room. **[verified]**
- **Taurus** (forked in-org) is the Qt GUI + client-side data-access toolkit, standard for Sardana beamlines.
- **tango-gateway** (a Tango gateway server) and **PyTangoArchiving** / **fandango** are present for Tango archiving and remote access. **[partly verified]** as to current use.

### Fast paths and exceptions

Not established from public source. IcePAP handles motion; whether any beamline uses direct-socket detector triggering, hardware sequencers, or a fast DAQ path outside Tango/Sardana is unknown and routes to staff. **[unconfirmed]**

**Staleness note.** The `synchrotron-solaris` org is largely quiescent: most `dev-solaris-*` servers were last pushed 2015-2017, the Sardana/Taurus/Tango forks 2019-2021, and only IcepapCMS shows a 2023 push. The public org captures the *founding* accelerator control stack; current beamline-era control config (2020s beamlines like POLYX, ASTRA, CIRI) is not visibly maintained in public GitHub and likely lives on an internal host (see section 4). **[verified]**

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| [`synchrotron-solaris`](https://github.com/synchrotron-solaris) (GitHub, 30 public repos) | Founding Tango/Sardana/Taurus stack, `dev-solaris-*` facility device servers, facility-wide Sardana macros, IcepapCMS, Cosylab Control Program | https://github.com/synchrotron-solaris |
| `sardana-org/sardana`, Tango Controls upstream | Canonical scan engine + control framework (SOLARIS forks these) | https://github.com/sardana-org/sardana |
| Internal host (named, not resolved) | Presumed current per-beamline instrument config / newer beamline control | staff question |

**Why a full device model is NOT integrity-buildable from public source.** SOLARIS publishes the control-system *framework* (Tango + Sardana + Taurus + IcePAP) and a set of facility-infrastructure Tango servers, but it does NOT publish a per-beamline device inventory with real handles (the Tango device names / IcePAP axes / detector configs of POLYX, ASTRA, PIRX, etc.). The public Sardana macros are facility-wide, not instrument topology. Per the standing rule, device topology therefore routes to the staff questions in section 7 rather than being inferred from the shared Tango base classes; inference from shared classes is not source. This puts SOLARIS in the same posture as ALBA / Sirius / PSI (Tango/Sardana or firewalled device source), with no MXCuBE-style public exception like the one that unlocked ALBA XALOC and Sirius Manaca (SOLARIS has no MX beamline). **[verified]**

---

## 5. Data management

Not established from public source. No public data catalog, user-office API, NeXus/HDF5 application-definition policy, or archive chain was surfaced for SOLARIS in this pass. Sardana/Taurus beamlines commonly write via Sardana's recorder layer (SPEC/HDF5/NeXus), and Tango facilities in the PaNOSC / photon-neutron sphere often adopt SciCat + ICAT-family catalogues, but NONE of this is confirmed for SOLARIS and it must not be assumed. This is a source-of-truth-contest question deferred to staff: any facility catalog claims part of the "system of record for the experiment" territory CORA claims, so the ingestion trigger and format policy need operator confirmation before any seam lock. **[unconfirmed]**

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** SOLARIS device IO is **Tango** device servers over IcePAP motion and standard detector servers. CORA's ControlPort actuates through this Tango floor. This is a different substrate from the EPICS floor of the APS 2-BM / FXI pilots: the ControlPort abstraction should carry over, but a **Tango control adapter** is required (the same adapter need as any Tango/Sardana facility: ALBA, ELETTRA, MAX IV, SOLEIL). CORA never owns the Tango device servers or the IcePAP layer.

**What CORA replaces (edge orchestration).** The **Sardana MacroServer + Pool** scan engine, with the facility-wide macro library on top, is the layer CORA's EdgeConductor would conduct over, incrementally and routine-by-routine. Sardana is a solid, mature engine: treat it as DATA to learn from (its scan/sequence macro shapes, its Pool device model), NOT a spec to mirror. Pitch CORA on governance, replayability, and recipe-binding of the experiment, never on out-executing Sardana on scan speed. Because the published macros are facility-wide, the replace-vs-drive-through decision likely generalizes across beamlines (confirm).

**Source-of-truth contest (data).** No public catalog was found (section 5). CORA stays the system of record for the experiment and brings its own event-sourced data of record; whatever catalog / archive SOLARIS runs is named only at the seam and the inversion-vs-projection decision is deferred until a SOLARIS deployment is actually in scope.

**Coexist.** Scheduling / user-office identity (read, do not replace) is unknown and routes to staff. Reconstruction compute for POLYX tomography is a ComputePort roundtrip CORA governs but does not own. The Cosylab Control Program and Taurus GUIs are accelerator/operator overview tools CORA does not touch. Logbooks, if any, are subsumed at the debrief layer.

**Machine-class note.** Unlike the FEL caveat that applies to PAL-XFEL, SOLARIS IS a storage ring, so the ring-pilot machine class carries over cleanly. The only structural differences from the APS pilots are (1) the Tango-not-EPICS floor and (2) the low ring energy / soft-X-ray-dominated roster, which shifts most beamlines away from the imaging/tomography pilot lane (POLYX is the exception).

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock. A plausible accelerator/controls contact surfaced on the facility site is **Adriana Wawrzyniak (Accelerators Deputy Director)**; the right contact for beamline controls is likely the SOLARIS controls / IT group (confirm).

1. **Control substrate confirmation:** is every beamline on Tango + Sardana (MacroServer/Pool), or do any newer beamlines (POLYX, ASTRA, CIRI) run a different stack? Is there any EPICS anywhere on the beamline side?
2. **Per-beamline device topology (the firewalled fact):** for POLYX first, the Tango device names / IcePAP axes / detector servers of the uCT/uXRF/uXAS endstation (rotation stage, sample stage, camera/detector, capillary optics). This is the block that makes a Tier-2 device pass buildable.
3. **Fast paths:** does POLYX tomography (or any line) use hardware triggering / a fast DAQ path outside Sardana, and if so through what (Icepap PSO-style, a sequencer, direct detector socket)?
4. **Data of record + catalog:** what raw-data format (HDF5? NeXus, which application definitions e.g. NXtomo for POLYX?), is there a facility data catalog (SciCat / ICAT / home-grown), and is ingestion mandatory and at what point?
5. **Identity / scheduling:** the user-office / proposal system and role/permission model CORA's Trust BC must read.
6. **Identifier mapping:** how endstations map to a run-context (PHELIX-PES/XAS vs PHELIX-NAP-XPS; DEMETER-PEEM vs DEMETER-STXM), for the descriptor identifier scheme.
7. **MAX IV lineage:** how identical is the storage-ring lattice to the MAX IV 1.5 GeV R1 ring, and (separately) is any *beamline* control config shared with MAX IV, or is the software lineage independent despite the shared magnet heritage?

---

## 8. Source list

**Facility (hardware facts):**
- SOLARIS home: https://synchrotron.uj.edu.pl/en_GB/
- Beamlines index: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze
- POLYX: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/polyx
- ASTRA: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/astra
- PIRX: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/pirx
- URANOS: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/uranos
- PHELIX: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/phelix
- DEMETER: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/demeter
- CIRI: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/ciri
- CRYO-EM: https://synchrotron.uj.edu.pl/en_GB/linie-badawcze/cryo-em
- Storage ring: https://synchrotron.uj.edu.pl/en_GB/pierscien-akumulacyjny
- Accelerators index: https://synchrotron.uj.edu.pl/en_GB/akceleratory
- Wikipedia, Solaris (synchrotron): https://en.wikipedia.org/wiki/Solaris_(synchrotron)
- Wikipedia, MAX IV (1.5 GeV R1 DBA ring, lineage context): https://en.wikipedia.org/wiki/MAX_IV

**Control system (software facts):**
- synchrotron-solaris GitHub org: https://github.com/synchrotron-solaris
- Facility-wide Sardana macros (decisive scan-engine primary): https://github.com/synchrotron-solaris/lib-solaris-facility-macros
- Sardana fork: https://github.com/synchrotron-solaris/sardana (upstream https://github.com/sardana-org/sardana)
- Taurus fork: https://github.com/synchrotron-solaris/taurus
- IcepapCMS (motion, most recently maintained): https://github.com/synchrotron-solaris/IcepapCMS
- Cosylab Control Program: https://github.com/synchrotron-solaris/app-cosylab-controlprogram
- SOLARIS Tango device servers: https://github.com/synchrotron-solaris/dev-solaris-shutter , /dev-solaris-valve , /dev-solaris-absorber , /dev-solaris-shopper , /dev-solaris-bpmsummary , /dev-solaris-phaseshifter , /dev-solaris-adam , /dev-solaris-informationforbl
- tango-gateway / PyTangoArchiving / fandango (Tango infra): https://github.com/synchrotron-solaris/tango-gateway

**Data management:**
- None found publicly (routed to staff question 4).

**Internal-only (named, not reachable):** a SOLARIS-internal host presumed to carry current per-beamline instrument config (not resolved in this pass); the public GitHub org captures the founding accelerator control stack, not the 2020s beamline-era config.
