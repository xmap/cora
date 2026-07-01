# Techniques

*What the modelled part of P61 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P61's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## High-energy white-beam / energy-dispersive diffraction

P61 uses the high-energy white beam from the damping wiggler for energy-dispersive diffraction (P61B engineering / materials studies) and Large Volume Press high-pressure / high-temperature in-situ studies (P61A), reading the [energy-dispersive detector](equipment/detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy-dispersive diffraction (white beam) | `energy_dispersive_diffraction` | high-energy white-beam energy-dispersive diffraction (P61B) and Large Volume Press in-situ studies (P61A); reuses the `energy_dispersive_diffraction` slug, a further consumer (`TECH-1`, `PRESS-1`) |

## A thin high-energy white-beam beamline

P61 is the fleet's high-energy white-beam wiggler beamline. Its technique reuses the `energy_dispersive_diffraction` slug already carried across the fleet, so it forces no new Method. The instrument anatomy reuses existing Families (`LinearStage`); the sparse registry slice means the model is deliberately thin, with the source, the Large Volume Press, and the detectors carried pending. The Large Volume Press (P61A), when exposed, would reuse the catalog `PressureCell` Family (graduated across 13-id and P02).

## Not modelled yet

The concrete acquisition recipes (the energy-dispersive diffraction scans, the LVP pressure / temperature ramps, the white-beam engineering measurements) are not written yet; they join as the deployment approaches the point where CORA drives P61. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
