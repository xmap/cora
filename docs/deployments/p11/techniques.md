# Techniques

*What the modelled part of P11 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P11 runs macromolecular crystallography and bio-imaging, reusing Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

## Macromolecular crystallography

P11 mounts a crystal on the goniometer (with cryostream cooling), rotates it through an oscillation, and reads frames on the [Pilatus area detector](equipment/detector.md). It is a high-throughput rotation-MX beamline.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the goniometer reading the Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS), a further consumer (`TECH-1`) |

## Bio-imaging

P11 also runs coherent / full-field bio-imaging on the experiment-hutch stages reading the area detector.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Bio-imaging | `tomography` | full-field / coherent imaging on the experiment-hutch stages + Pilatus; reuses the catalog `tomography` Method (the 2-BM / FXI lineage), a further consumer (`TECH-1`) |

## A familiar beamline on familiar vocabulary

P11 is the fleet's fourth-plus macromolecular-crystallography beamline and PETRA III's first. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, driven here through the PETRA III Tango / Sardana floor. It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet), and the bio-imaging reuses `tomography`; neither forces a new device Family. The automated sample changer, if present, would be a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

## Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the bio-imaging scans, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P11. Whether the MX Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
