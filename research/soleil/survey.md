# SOLEIL (Synchrotron SOLEIL) research brief

*Research seed for future CORA deployment pages. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about SOLEIL, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. CORA is not connected to SOLEIL; the seam section is an initial read, not a commitment. Compiled 2026-06-30 from the SOLEIL facility pages plus a direct read of the public MXCuBE device configuration and SOLEIL's Tango/Lima source on GitHub.*

!!! note "Reading posture"
    Public facility pages (`synchrotron-soleil.fr`) are the source of HARDWARE FACTS (ring, beamline roster, techniques). Public source is the source of CONTROL-SOFTWARE FACTS: the MXCuBE `mxcubecore/configuration/soleil_px*` HardwareObject XML tree (per-device Tango handles for the MX beamlines) and the `soleil-ica` GitHub org (Lima detector Tango servers). Confidence is flagged inline as **[verified]**, **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6). Provenance caveat: the device topology read here is the MXCuBE hardware-object layer (a deployment config, public via the upstream mxcubecore repo), so it is a strong-evidence snapshot of the MX beamlines, not the full facility controls; every value is carried `confirm` until SOLEIL staff verify it.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Synchrotron SOLEIL, the French national storage-ring light source | [SOLEIL](https://www.synchrotron-soleil.fr/) |
| Location / operator | Saint-Aubin (Plateau de Saclay), France; a civil company of CNRS + CEA | [SOLEIL](https://www.synchrotron-soleil.fr/) |
| Storage ring | 2.75 GeV storage ring (SOLEIL upgrade / SOLEIL II in planning) | facility docs, **[partly verified]** |
| Beamline count | ~29 beamlines across the full soft-to-hard X-ray range | facility docs, **[partly verified]** |

SOLEIL is a major European national source, a Tango / SOLEIL-house-style facility (SOLEIL co-developed Tango and the Sardana/Taurus-adjacent ecosystem). Its distinguishing value for CORA in this pass is the MX side: the Proxima beamlines run MXCuBE, whose per-device Tango topology is public via the upstream `mxcubecore` configuration tree, the same cross-facility MX-config corpus that also exposes ALBA, ESRF, DESY, and EMBL MX beamlines. The governance / provenance / recipe spine CORA adds is absent from the MXCuBE config (it is hardware-objects + a queue model), the usual gap that justifies the spine.

---

## 2. Candidate beamlines

SOLEIL's own GitHub org (`synchrotron-soleil`) is thin (electronics / KiCad), and the facility's canonical per-beamline Tango device config is not published as one public tree. The device topology that IS public is the **MXCuBE hardware-object configuration** for the Proxima (MX) beamlines, in the upstream `mxcube/mxcubecore` repo under `mxcubecore/configuration/soleil_px*`. Plus SOLEIL publishes its **Lima detector Tango servers** (`soleil-ica` org).

The modellable set (public MXCuBE config, read 2026-06):

| Beamline | Name | Technique | MXCuBE config | EPICS/Tango | Source |
| --- | --- | --- | --- | --- | --- |
| PX1 | Proxima-1 | macromolecular crystallography (rotation MX) | `soleil_px1` (59 device files, rich) | Tango (`i10-c-*` prefix) | [mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/soleil_px1) |
| PX2 | Proxima-2A | microfocus MX | `soleil_px2` (3 files, stub) | Tango | [mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/soleil_px2) |

Only **PX1** is device-modellable from the public config (59 hardware-object files with real Tango handles). PX2 is a 3-file stub (beamline-setup + a diffractometer placeholder), so it is survey-only. The ~27 other SOLEIL beamlines (the soft X-ray, spectroscopy, IR, and scattering lines) do not publish a public per-beamline device config; their Tango topology is staff-only. **[verified for PX1; partly verified for the roster]**

**Identifier scheme:** SOLEIL Tango device names use a structured path, e.g. `i10-c-cx1/ex/sgonaxis` (the Proxima-1 Smargon goniometer), `i10-c-c00/ex/beamlineenergy`, `i10-c-cx1/dt/pilatus`. The `i10-c` prefix is the SOLEIL location/cell code; `/ex/` and `/dt/` are the experiment / detector device families. This is a Tango device-server path, not an EPICS PV, distinct from the EPICS facilities. **[verified]**

---

## 3. Control-system stack, by layer

SOLEIL is a **Tango** facility (SOLEIL is one of Tango's originating institutions, with ALBA / ESRF / DESY / Elettra).

### Device IO (the floor)

Tango device servers. The MX beamlines surface motors as `TangoDCMotor` / `SardanaMotor` / Smargon-axis device classes, detectors via **Lima** Tango servers (SOLEIL publishes Lima + many Lima camera plugins in `soleil-ica`: imXPAD, SlsDetector, Dhyana, etc.), and beamline devices (shutters, attenuators, energy, flux) as named Tango devices (`i10-c-*`). This is below CORA's seam; CORA's ControlPort actuates through the Tango floor (the same shape as ESRF BLISS/Tango and the Elettra/ALBA Tango houses), not over EPICS. **[verified for the MX devices]**

### Scan orchestration (the seam layer)

For MX, **MXCuBE** (the macromolecular-crystallography experiment-control suite: mxcubecore back-end hardware-objects + a queue model + ISPyB LIMS). For the non-MX beamlines, SOLEIL's house-style is a Tango + (historically) Passerelle / Sardana-adjacent scan layer, not established in this pass. The MXCuBE queue + hardware-object layer is what CORA's EdgeConductor would conduct over / replace for the Proxima beamlines. **[verified for MX]**

### Fast paths and exceptions

MX data collection drives the Smargon goniometer omega via the diffractometer with hardware-triggered shutter + Pilatus, the standard MX rotation acquisition; the `PX1MiniDiff` / `Smargon` classes wrap the SOLEIL Proxima-1 diffractometer. Confirm the trigger path with staff (FLY-1). **[partly verified]**

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| `mxcube/mxcubecore` (upstream MXCuBE) | the public MX hardware-object config for SOLEIL Proxima (soleil_px1 / soleil_px2), alongside ALBA / ESRF / DESY / EMBL | [mxcubecore](https://github.com/mxcube/mxcubecore) |
| `github.com/soleil-ica` (SOLEIL org, ~36 repos) | Lima Tango detector servers + camera plugins (imXPAD, SlsDetector, Dhyana...) | [soleil-ica](https://github.com/soleil-ica) |
| `github.com/synchrotron-soleil` (SOLEIL org) | thin (electronics / KiCad libraries) | [synchrotron-soleil](https://github.com/synchrotron-soleil) |
| internal `gitlab.synchrotron-soleil.fr` | the canonical per-beamline Tango device config (not publicly resolvable) | named, not reachable |

**Why a per-beamline device model IS buildable for PX1.** The `soleil_px1` MXCuBE config carries 59 hardware-object XML files, each a device with a real Tango handle (verified: `i10-c-cx1/ex/sgonaxis` Smargon, `i10-c-c00/ex/beamlineenergy`, `i10-c-cx1/dt/detdist.1-control`, `i10-c-cx1/dt/ketek.2`, `i10-c-cx1/dt/pilatus`). This is the MXCuBE hardware-object layer (a deployment config), the same source the project's `reverse_engineer --source mxcube` path reads. PX2 and the non-MX beamlines lack a public config.

---

## 5. Data management

MX uses **ISPyB** (the standard MX LIMS, referenced in the PX1 config `dbconnection.xml` / `lims-rest.xml`) plus EDNA / auto-processing for data analysis. The facility-wide data-policy / catalog / archive chain was not established in this pass (DATA-1). **[partly verified]**

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility LIMS/catalog is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** SOLEIL device IO is Tango (Smargon/TangoDCMotor motors, Lima detectors, named beamline devices). CORA's ControlPort actuates through the Tango floor, the same shape as ESRF / Elettra / ALBA; the Tango-vs-EPICS difference is an adapter detail, not a model difference.

**What CORA replaces (edge orchestration).** For the Proxima beamlines, the MXCuBE queue + hardware-object orchestration is the layer the 2-BM seam designates as CORA's. CORA's EdgeConductor would conduct the MX data-collection routine (centre, characterise, collect, the autonomous loop) over the Tango floor. Treat MXCuBE as DATA to learn from (the device topology, the queue model), NOT a spec to mirror; this is the "replacing a solid existing implementation" case (like 2-BM TomoScan), so pitch CORA on governance, replayability, recipe-binding, never on out-executing MXCuBE.

**Source-of-truth contest (data).** ISPyB is the MX LIMS and the sharpest seam: it claims the sample / proposal / data-collection metadata territory CORA claims for the experiment. CORA stays the system of record for the experiment; ISPyB is named only at the seam (fed downstream or projected into). Decision deferred until a SOLEIL MX deployment is in scope; the same ISPyB tension will recur at every MXCuBE facility (ALBA, ESRF, DESY MX).

**Coexist.** SOLEIL facility scheduling / identity (read, do not replace), the EDNA / auto-processing compute (a port roundtrip CORA governs but does not own), any data archive (an egress destination).

---

## 7. Open questions (for SOLEIL staff)

1. **Beamline roster / techniques:** confirm the full SOLEIL beamline list and which (beyond Proxima-1/2A) could expose a device config CORA could read.
2. **PX2 / non-MX config:** the public MXCuBE config for PX2 is a 3-file stub; is the full PX2 (Proxima-2A microfocus) config available, and do the non-MX beamlines publish any device topology?
3. **Tango namespace:** confirm the `i10-c-*` Proxima-1 device paths and whether the canonical config lives on the internal `gitlab.synchrotron-soleil.fr`.
4. **MX trigger path (FLY-1):** how is the Smargon rotation + Pilatus acquisition triggered (Tango, hardware, a SOLEIL timing system)?
5. **ISPyB seam (DATA-1):** is ISPyB the authoritative MX metadata store, and at what point would CORA invert vs project into it?
6. **Ring parameters:** confirm 2.75 GeV ring facts from the SOLEIL machine design / SOLEIL II upgrade docs.

---

## 8. Source list

**Facility (hardware facts):**
- SOLEIL: https://www.synchrotron-soleil.fr/

**Control system / device topology:**
- MXCuBE core (SOLEIL Proxima config): https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/soleil_px1
- soleil-ica (Lima Tango detector servers): https://github.com/soleil-ica
- synchrotron-soleil (electronics): https://github.com/synchrotron-soleil

**Internal-only (named, not reachable):** the canonical SOLEIL per-beamline Tango config on `gitlab.synchrotron-soleil.fr`.
