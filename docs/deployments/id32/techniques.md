# Techniques

*What the modelled part of ID32 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../esrf/index.md#the-techniques-adapted-here) is how a facility adapts it. ID32 runs three soft X-ray techniques, all new to CORA's catalog, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## Resonant inelastic X-ray scattering, magnetic dichroism, emission

ID32 sets the X-ray energy and polarization with the twin APPLE-II undulators and the plane-grating monochromator, then either disperses the inelastically scattered beam on a long spectrometer arm (RIXS), or measures the absorption asymmetry between polarizations in a high magnetic field (XMCD), or disperses the emitted beam (XES).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | the roughly 5 m dispersive [spectrometer arm](detector.md) on the RIXS endstation, scanned in energy against the [incident-energy axis](source.md); reuses the SIX RIXS Method, the second consumer; Method not yet in the catalog |
| X-ray magnetic dichroism | `xmcd` | absorption asymmetry in the 9 T [XMCD magnet](sample.md) between circular / linear polarizations set on the [APPLE-II](source.md); reuses the 4-ID / i06 / i10 dichroism Method; pending |
| X-ray emission spectroscopy | `xas_spectroscopy` | the [XES Rowland arm](detector.md) at the XMCD endstation; reuses the `xas_spectroscopy` Method that ISS / LCLS-MFX left pending for XES; pending |

RIXS needs the [incident-energy and polarization axes](source.md), the [RIXS diffractometer](sample.md) to set the scattering geometry, and the [dispersive spectrometer arm and its CCD](detector.md). XMCD needs the polarization axis, the [9 T magnet and its VTI](sample.md), and a detection channel. XES needs the [emission spectrometer arm](detector.md).

## A new operating axis for the fleet, on familiar vocabulary

RIXS at ID32 is the fleet's second soft X-ray RIXS after SIX, and the dispersive spectrometer arm is the device that ties them together: the same `SpectrometerArmsController` anatomy that SIX coined loose, sighted three times across two sites (the ID32 RIXS arm, the ID32 XES arm, and SIX). That rule-of-three earned the graduation of the `SpectrometerArm` Family, which has since landed as a catalog Family (SIX + ID32 RIXS/XES + ID28; see [Model](model.md#loose-families-held-at-the-rule-of-three)). XMCD and XES likewise reuse the dichroism and emission Methods the fleet already carries pending; none forces a new device family.

## Not modelled yet

The concrete acquisition recipes (the RIXS energy maps and arm alignment, the XMCD field-and-polarization sequences, the XES scans, and the counting times) are not written yet; they join as the deployment approaches the point where CORA drives ID32. Whether RIXS, XMCD, and XES enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
