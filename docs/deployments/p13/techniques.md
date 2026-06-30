# Techniques

*What the modelled part of P13 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P13 runs macromolecular crystallography, reusing a Method the fleet already carries pending, so the Method below renders unlinked until a technique enters scope (`TECH-1`).

## Macromolecular crystallography

P13 mounts a crystal on the EMBLMiniDiff microdiffractometer (with cryostream cooling), rotates it through an oscillation, and reads frames on the [Eiger or Pilatus area detector](equipment/detector.md). It is a high-throughput rotation-MX beamline, with an XRF detector for anomalous-edge identification.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the EMBLMiniDiff reading the Eiger / Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS / P11), a further consumer (`TECH-1`) |

## A familiar beamline on an unfamiliar floor

P13 is the fleet's seventh macromolecular-crystallography beamline and CORA's first at EMBL Hamburg. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy. What is new is not the technique but the floor it runs on: where P11 drives MX through the DESY Tango / Sardana stack, P13 drives it through EMBL's MXCuBE over Exporter + TINE (`SEAM-1`). It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet); it forces no new device Family. The automated sample changer is a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

## Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the anomalous-edge scans, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P13. Whether the MX Method enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
