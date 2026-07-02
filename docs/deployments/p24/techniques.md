# Techniques

*What the modelled part of P24 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P24's chemical crystallography earns no dedicated catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Chemical crystallography

P24 mounts a single crystal on the [diffractometer](sample.md) and collects single-crystal diffraction on the area detector to solve small-molecule / chemical structures (including at non-ambient conditions).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Single-crystal / chemical crystallography | `diffraction` | single-crystal diffraction on the EH2 diffractometer + area detector; reuses the `diffraction` slug (no dedicated chemical-crystallography Method exists), a further consumer (`TECH-1`) |

## A chemical crystallography beamline on familiar vocabulary

P24 is PETRA III's chemical (small-molecule) crystallography beamline, the fleet's second after Diamond [I19](../i19/index.md). It is distinct from the macromolecular-crystallography beamlines (P11, i03, FMX / AMX, MANACA, TPS): those bind the `Goniometer` Family and the `mx_data_collection` Method, while P24 does small-molecule chemical crystallography, which CORA models as `diffraction` for now (no dedicated chemical-crystallography Method exists, and the registry does not expose a labelled goniometer). The instrument anatomy reuses existing Families (`LinearStage`, `Slit`, `EnergyDispersiveSpectrometer`); the area detector is carried pending.

## Not modelled yet

The concrete acquisition recipes (the single-crystal data-collection strategies, the multi-temperature / variable-condition collection) are not written yet; they join as the deployment approaches the point where CORA drives P24. Whether a dedicated chemical-crystallography Method (vs reusing `diffraction`) enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
