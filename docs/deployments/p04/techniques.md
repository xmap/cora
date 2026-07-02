# Techniques

*What the modelled part of P04 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P04 runs soft X-ray spectroscopy, which earns no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## Soft X-ray absorption spectroscopy

P04 sets the photon energy (250-3000 eV) by coupling the [variable-polarization undulator](source.md) and the [plane-grating monochromator](source.md), then scans it across an absorption edge while reading the sample drain current on the [electrometer](detector.md) (total electron yield).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Soft X-ray absorption (XAS / NEXAFS) | `xas_spectroscopy` | the undulator + PGM photon-energy scan reading the Keithley electrometer; reuses the `xas_spectroscopy` slug four sites share, a further consumer (`TECH-1`) |

## Photoemission

P04's variable polarization and soft X-ray energy range suit photoemission on the EXP endstations (the analyzer is an endstation instrument not exposed as a motor in the registry).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Soft X-ray photoemission | `angle_resolved_photoemission` | photoemission on the EXP endstations; reuses the `angle_resolved_photoemission` slug, a further consumer (`TECH-1`) |

## A new technique regime on mostly familiar vocabulary

P04 is the fleet's soft X-ray spectroscopy beamline. Its energy regime is new (250-3000 eV, below the hard X-ray beamlines), and it forces the one genuinely new device binding, the `GratingMonochromator` (the soft X-ray analog of the crystal `Monochromator`). The techniques themselves reuse the `xas_spectroscopy` and `angle_resolved_photoemission` slugs already carried pending across the fleet, so neither forces a new Method to be coined now. The rest of the instrument anatomy reuses existing Families: the undulator binds `InsertionDevice`, the mirrors `Mirror`, the slits `Slit`, the manipulators `Manipulator`, the diagnostics `Camera` / `FluxMonitor` / `Screen`.

## Not modelled yet

The concrete acquisition recipes (the photon-energy-scan sequences and their dwell times, the polarization switching, the photoemission analyzer sweeps) are not written yet; they join as the deployment approaches the point where CORA drives P04. Whether the soft X-ray Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
