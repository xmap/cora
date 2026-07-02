# Techniques

*What the modelled part of MANACA is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../sirius/index.md#the-techniques-adapted-here) is how a facility adapts it. MANACA runs macromolecular crystallography, reusing the same cross-facility MX Methods Diamond i03 introduced, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`, `ROBOT-1`).

## Macromolecular crystallography

MANACA sets the X-ray energy (5-20 keV) with the undulator and the monochromator, mounts a crystal on the goniometer (from the automated 48-pin sample changer), and rotates it through an oscillation while the area detector reads frames. It supports serial and room-temperature MX in addition to standard cryocooled rotation collection.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the [goniometer](sample.md) reading the [area detector](detector.md); reuses the i03 Method (also at FMX / AMX / MX3), not yet in the catalog (`TECH-1`) |
| Grid scan | `grid_scan` | fast grid scan for sample location and centring on the [goniometer](sample.md); reuses the i03 Method; pending (`TECH-1`) |
| Sample exchange | `sample_exchange` | the automated 48-pin changer load / centre / collect / unmount loop, modelled as a Procedure over the spine; reuses the i03 / MX3 Method; pending (`ROBOT-1`) |

Rotation MX needs the [incident energy](source.md) set by the [monochromator](source.md), the [goniometer and cryostream](sample.md), and the [area detector](detector.md). Serial and room-temperature MX reuse the same chain with the sample-delivery and environment varied.

## A new beamline on familiar vocabulary

MANACA is a further macromolecular-crystallography beamline after Diamond i03, NSLS-II FMX / AMX, and the Australian Synchrotron MX3, and Sirius's first MX beamline (its [MOGNO](../mogno/index.md) sibling is tomography). It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, driven here through the Sirius EPICS floor and MXCuBE3. It reuses the `mx_data_collection`, `grid_scan`, and `sample_exchange` Methods directly (all carried pending across the MX fleet); none forces a new device family, and the 48-pin sample changer is a Procedure, not a new device.

## Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the grid-scan centring, the sample-changer custody loop, the serial / room-temperature delivery) are not written yet; they join as the deployment approaches the point where CORA drives MANACA. Whether the MX Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
