# Techniques

*What CORA would run at SMI: scattering techniques, each a [Catalog](../../catalog/methods.md) Method. SMI is the NSLS-II twin of the Diamond [I22](../i22/techniques.md) (SAXS / WAXS) beamline, and it follows i22's deferral exactly, adding the grazing-incidence variants.*

SMI's techniques are small- and wide-angle scattering, the science domain Diamond i22 brought to CORA. As there, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| Small-angle scattering (SAXS) | monochromatic, long camera | low-Q on the SAXS Pilatus 2M; the i22 Capability, new Capability pending (TECH-1) |
| Wide-angle scattering (WAXS) | monochromatic, swing arc | wide-Q on the WAXS Pilatus 900KW; the i22 Capability, new Capability pending (TECH-1) |
| Simultaneous SAXS+WAXS | both detectors at once | coordinated Runs under one Campaign, the routine mode, not a third technique (TECH-1) |
| Grazing-incidence (GISAXS / GIWAXS) | shallow incidence, reflected geometry | the same scattering Methods with the sample at a grazing angle and the WAXS arc swung; a sample-orientation variant (TECH-1) |

All the scattering techniques need the [grazing-incidence sample stack](equipment/sample.md) and the [SAXS / WAXS detectors](equipment/detector.md); the fast shutter gates the exposure.

## Why the Capabilities stay deferred

Diamond i22 opened the question of whether the SAXS and WAXS Capabilities enter CORA's catalog (TECH-1), and `main` deliberately left them pending: SAXS and WAXS do not reduce to the imaging-heritage `tomography` / `acquisition` Capabilities, and a modelling exercise does not mint cross-facility vocabulary until a technique enters a real scope. The device Roles already exist (the Pilatus detectors present the Detector Role, the flux monitor presents Sensor), so what is new is the science Capability, not a device shape. SMI reinforces the case for both at a second facility without coining either, the same earn-the-abstraction discipline the deferred `scanning` (HXN), `energy_scan` (BMM), and powder / total-scattering (XPD) Capabilities follow.

Grazing incidence (GISAXS / GIWAXS) is the genuinely new wrinkle SMI adds over i22, but it is a sample-orientation variant of the same scattering Capability (the sample sits at a shallow angle, the WAXS arc swings), not a new Capability of its own. Simultaneous SAXS+WAXS is coordinated Runs under one Campaign over a shared trigger, the same way 7-BM and i22 model parallel detector reads, not a combined technique. Because the defining Capabilities are not in the catalog, SMI records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); the binding lands when the Capability does.

The azimuthal integration and reduction (turning the 2D scattering frames into I(Q) curves and GISAXS maps) are `ComputePort` work, not beamline Methods.
