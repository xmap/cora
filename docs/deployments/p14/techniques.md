# Techniques

*What the modelled part of P14 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P14 runs macromolecular crystallography across two endstations, reusing a Method the fleet already carries pending, so the Method below renders unlinked until a technique enters scope (`TECH-1`).

## Macromolecular crystallography

P14 mounts a crystal on a diffractometer (with cryostream cooling), rotates it through an oscillation, and reads frames on an area detector, across two experiment hutches: EH1 on the [EMBLMiniDiff + Eiger detectors](equipment/detector.md), EH2 on the [EMBLBSD + Pilatus 2M](equipment/detector.md). The EH1 CdTe Eiger variants extend the technique to high-energy data collection, and the X-ray imaging camera supports in-situ centring.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the EMBLMiniDiff (EH1) / EMBLBSD (EH2) reading the Eiger / Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS / P11 / P13), a further consumer (`TECH-1`) |

## A familiar technique across two hutches

P14 is the fleet's eighth macromolecular-crystallography beamline and CORA's second at EMBL Hamburg. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, here run through EMBL's MXCuBE over Exporter + TINE (`SEAM-1`). What is distinctive is the two-endstation layout, one source feeding two hutches each running rotation MX, and the high-energy CdTe detector variants in EH1. It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet); it forces no new device Family. The automated sample changer is a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

## Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the high-energy CdTe collection, the anomalous-edge scans, the X-ray imaging centring, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P14. Whether the MX Method enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
