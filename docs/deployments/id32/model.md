# Model

*The developer's index into where ID32 content lives, the new ESRF Site and BLISS control house-style it introduces, the three loose families it brings to a rule-of-three (and holds), and the record of what is deliberately deferred. First cut.*

ID32 is a descriptor-and-docs scaffold today, reverse-engineered from the ESRF's BLISS Beacon device database: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/id32/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id32/beamline.yaml) | the device walk with bound handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/esrf/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/esrf/site.yaml) | the NEW ESRF facility surface; `ID32` its first beamline, with RIXS / XMCD / XES Practices |
| Extraction provenance | [gitlab.esrf.fr/id32/beamline_configuration](https://gitlab.esrf.fr/id32/beamline_configuration) | the public BLISS Beacon device database (a git mirror of the live config) the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; three loose families reach a rule-of-three and are held (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the RIXS / XMCD / XES Methods are pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers ID32 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes ID32 new

ID32 is two things the fleet has not had: a new Site and a new controls house-style. It is CORA's **seventh Site** (the ESRF, Grenoble), the biggest re-test of the Site and Federation kernel a single deployment can be, and the **first BLISS / Beacon / Tango / IcePAP** control plane CORA models (the rest are EPICS, or Tango / Sardana at MAX IV). Its science is soft X-ray resonant inelastic scattering (RIXS) with a ~5 m dispersive spectrometer arm, and X-ray magnetic dichroism (XMCD) plus X-ray emission spectroscopy (XES) at a 9 Tesla high-field-magnet endstation, all fed by twin APPLE-II undulators through a soft X-ray plane-grating monochromator.

## No new families (the polarization spine reuses the i06 / i10 precedent)

ID32 coins no new Family. The twin APPLE-II undulators bind the catalog `InsertionDevice`, and the polarization is a `PseudoAxis` over the undulator phase, exactly as i06 and i10 modelled their APPLE-II sources; the PGM binds `GratingMonochromator`; the 4-circle diffractometer binds `Goniometer` with a reciprocal-space `PseudoAxis` (the Assembly named, not built, DIFF-1 / DIFF-2); the Andor CCDs bind `Camera`; the LakeShore VTI and coil-diagnostic controllers bind `TemperatureController`; the XMCD sample stage binds `LinearStage`; the machine state binds the loose `StorageRing`.

## Loose families held at the rule-of-three

ID32 pushes three loose families to a genuine rule-of-three. Per the owner decision (2026-06-27) all three are **held loose here**, with their graduations deferred to dedicated, gated catalog PRs rather than bundled into this scaffold:

| Loose family | Sightings with ID32 | ID32 binding | Decision |
| --- | --- | --- | --- |
| `SpectrometerArm` | SIX + ID32 RIXS arm + ID32 XES arm | the two dispersive spectrometer arms (the same `SpectrometerArmsController` class instantiated twice) | **hold** (`RIXS-1`): the rule-of-three is met in-source (one controller class, two geometries, a third site), so it is graduation-ready; the graduation is a separate gated PR |
| `Magnet` | 4-ID + i10-1 + ID32 | the 9 T / 4 T XMCD split-coil magnet | **hold** (`MAG-1`): a third consumer; graduation deferred to a dedicated PR |
| `PolarizationAnalyzer` | 4-ID + i10 + ID32 | the RIXS scattered-beam polarimeter | **hold** (`POL-2`): a third consumer; graduation deferred |

Holding rather than graduating keeps this PR a clean scaffold (no catalog.yaml or Role change), and lets each graduation get its own naming-r3 and gate-review. The `_PROMOTION_REVIEWED` notes record all three as graduation-due. The clearest is `SpectrometerArm`: it presents the `Positioner` Role (an arm that positions a grating and carries a `Camera` at its focus), which is exactly why it never fit the point-Sensor families (`FluxMonitor` / `EnergyDispersiveSpectrometer`) and was coined loose at SIX.

## The BLISS / Tango control plane

ID32 is the first non-EPICS, non-Sardana controls house-style in the fleet: BLISS / Beacon (a YAML device database) over Tango and IcePAP. CORA models the control handles as opaque edge strings regardless of transport, the way the MX3 heterogeneous-control precedent does: a Tango device URL (`id32/limaccds/andor_1`), an IcePAP host+address (`iceid324`), or a BLISS axis name is the handle, carried confirm (`CTRL-1`). The RIXS / XMCD / XES acquisition runs through BLISS sequences; that orchestration is the seam CORA's edge replaces, conducting over Tango / IcePAP rather than replacing BLISS.

## Deliberately not here yet

- **The three graduations (`RIXS-1`, `MAG-1`, `POL-2`).** Held loose; each graduation (catalog.yaml family + Role + naming-r3 + gate-review) is a dedicated follow-on PR. `SpectrometerArm` is the readiest.
- **The exact optics handles (`MONO-1`, `OPT-1`, `OPT-2`, `DIFF-1`, `SAMPLE-1`).** The PGM, mirrors, slits, diffractometer axes, and XMCD sample stage are carried confirm-pending; the decision-critical devices (the arms, the magnet, the LakeShores, the CCDs, the undulator) carry their real BLISS addresses.
- **The Assembly(Diffractometer) and the reciprocal-space rule (`DIFF-1`, `DIFF-2`).** Named, not built, as the other diffractometer beamlines deferred theirs.
- **The RIXS / XMCD / XES Methods.** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the SIX RIXS, the 4-ID / i06 / i10 XMCD, and the xas_spectroscopy XES slugs (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_id32_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
