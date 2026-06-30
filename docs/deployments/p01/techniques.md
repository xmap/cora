# Techniques

*What the modelled part of P01 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P01 runs hard X-ray dynamics techniques (nuclear resonant scattering and resonant inelastic scattering) that earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## Nuclear resonant scattering (EH1)

P01 sets the X-ray energy onto a Moessbauer isotope's nuclear resonance with the [double-crystal monochromator](beamline.md), then carves a meV / Moessbauer-energy bandwidth with the [high-resolution monochromator stack](equipment/sample.md) (the four nested / channel-cut HRMs). Scanning the high-resolution-monochromator energy axis while reading the time- and energy-resolved detector signal produces the nuclear inelastic / resonant spectrum.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Nuclear resonant scattering / nuclear inelastic scattering | `inelastic_x_ray_scattering` | the high-resolution-monochromator energy scan reading the avalanche-photodiode signal; no catalog Method fits, reuses the IXS slug ESRF ID28 / NSLS-II IXS share, a further consumer (`TECH-1`) |

## Resonant inelastic X-ray scattering (EH3)

P01's EH3 endstation focuses the beam with the [KB mirror pair](equipment/sample.md) onto the sample and analyzes the inelastically scattered photons on the spectrometer arm, scanning the incident energy against the analyzed energy to map the excitation spectrum.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | KB-focused incident beam analyzed on the EH3 spectrometer; reuses the RIXS slug SIX / ESRF ID32 share, a further consumer (`TECH-1`) |

## Diffraction (EH2)

P01's EH2 endstation carries a theta / two-theta [goniometer](equipment/sample.md) reading a detector on a positioning stage, for hard X-ray diffraction. The catalog carries no general diffraction Method today; the technique is noted, not bound, pending confirmation of the endstation's routine use (`TECH-1`, `DIFF-1`).

## A new technique branch on familiar vocabulary

P01 is the fleet's NRS / RIXS dynamics beamline. Its techniques are new to CORA's catalog (which is tomography- and MX-centric today), but they reuse the inelastic- and resonant-inelastic-scattering slugs already carried pending across the fleet (ESRF ID28 IXS, ESRF ID32 / SIX RIXS, NSLS-II IXS), so none forces a new Method to be coined now. The instrument anatomy reuses existing Families end to end: the monochromators bind `Monochromator`, the KB mirrors `Mirror`, the lens `Transfocator`, the stages `LinearStage` / `RotaryStage` / `Table`, the sample circle `Goniometer`.

## Not modelled yet

The concrete acquisition recipes (the high-resolution-monochromator energy-scan sequences and their exposures, the RIXS incident-energy scans, the diffraction scans) are not written yet; they join as the deployment approaches the point where CORA drives P01. Whether the NRS / RIXS Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
