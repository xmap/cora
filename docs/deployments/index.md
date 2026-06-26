# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

A beamline is never standalone: it sits inside a Site, a Federation `Facility` that owns the clearances, principals, practices, and facility-scope supplies the beamline inherits but does not own. The deployments below are grouped by that Site; each beamline page links up to its Site rather than restating it. CORA's operational pilot is 2-BM. Most of the rest are in the design phase, modelled from a design report ahead of construction or recommissioning. The Diamond and NSLS-II beamlines, SLAC's LCLS-MFX, and the Australian Synchrotron's MX3 are a third kind: operating beamlines reverse-engineered from public controls configuration, so their pages carry real control facts but every value stays `confirm` until the beamline team verifies it.

## [APS](aps/index.md)

CORA's first multi-beamline Site: five beamlines share one APS envelope, which is reused rather than re-created per beamline.

| Beamline | Status | What it is |
| --- | --- | --- |
| [2-BM](2-bm/index.md) | Pilot | bending-magnet micro-CT, the operational pilot |
| [2-ID](2-id/index.md) | In design | scanning fluorescence microprobe (2-ID-D hutch), mined from the EAA toolkit |
| [7-BM](7-bm/index.md) | In design | multi-technique flow and combustion imaging, recommissioned for APS-U |
| [19-BM](19-bm/index.md) | In design | bending-magnet autonomous high-throughput tomography |
| [32-ID](32-id/index.md) | In design (partial) | canted multi-instrument: optics spine and transmission X-ray microscope |

## [MAX IV](maxiv/index.md)

The second Site CORA models; thin while its beamline is in design.

| Beamline | Status | What it is |
| --- | --- | --- |
| [TomoWise](tomowise/index.md) | In design | micro- and nano-tomography, Technical Design Report phase |

## [Diamond Light Source](diamond/index.md)

The third Site CORA models, and a deliberate off-roadmap exercise: real, operating beamlines modelled from Diamond's open `dodal` controls library to test that the dry-fact seed feeds CORA's intentional model, and that the model generalizes beyond tomography (SCOPE-1).

| Beamline | Status | What it is |
| --- | --- | --- |
| [I22](i22/index.md) | Modelling exercise | small- and wide-angle X-ray scattering (SAXS/WAXS), reverse-engineered from dodal |
| [I03](i03/index.md) | Modelling exercise | macromolecular crystallography (MX); graduates the Goniometer Family and exercises autonomous sample handling |
| [I15-1](i15-1/index.md) | Modelling exercise | X-ray total scattering / pair distribution function (XPDF); a reuse + reinforce deployment (no new vocabulary) |
| [I11](i11/index.md) | Modelling exercise | high-resolution powder diffraction; the rule-of-three that earned the TemperatureController graduation + the Regulator Role (landed via gate-review) |

## [NSLS-II](nsls2/index.md)

The fourth Site CORA models. Like the Diamond exercise, its beamlines are reverse-engineered from public open source (the NSLS-II bluesky profile collections), not a design report or a live connection.

| Beamline | Status | What it is |
| --- | --- | --- |
| [FXI](fxi/index.md) | Reverse-engineered | full-field transmission X-ray microscopy and tomography, 18-ID; modelled from public beamline config |
| [HXN](hxn/index.md) | Reverse-engineered | scanning hard X-ray nanoprobe (nano-XRF, ptychography, nano-tomography), 3-ID; modelled from public beamline config |
| [BMM](bmm/index.md) | Reverse-engineered | X-ray absorption spectroscopy (transmission + fluorescence XAS/EXAFS), 6-BM; modelled from public beamline config |
| [SRX](srx/index.md) | Reverse-engineered | submicron X-ray fluorescence microprobe (XRF mapping, XANES, XRF-tomography, diffraction), 5-ID; modelled from public beamline config |
| [SIX](six/index.md) | Reverse-engineered | soft X-ray resonant inelastic scattering (RIXS), 2-ID; CORA's first soft X-ray beamline, modelled from public beamline config |
| [CHX](chx/index.md) | Reverse-engineered | coherent hard X-ray scattering (XPCS, SAXS/WAXS, GISAXS), 11-ID; the second coherent beamline after APS 8-ID, modelled from public beamline config |
| [CSX](csx/index.md) | Reverse-engineered | coherent soft X-ray scattering and RSXS (TARDIS diffractometer), 23-ID; graduates the GratingMonochromator Family, modelled from public beamline config |
| [XPD](xpd/index.md) | Reverse-engineered | high-energy powder diffraction and total scattering / PDF, 28-ID; the NSLS-II twin of Diamond i11 and i15-1, modelled from public beamline config |
| [ESM](esm/index.md) | Reverse-engineered | electron spectro-microscopy (ARPES), 21-ID; CORA's first photoemission beamline, graduates the Manipulator Family, modelled from public beamline config |
| [SMI](smi/index.md) | Reverse-engineered | small- and wide-angle scattering (SAXS/WAXS) with grazing incidence (GISAXS/GIWAXS), 12-ID; the NSLS-II twin of Diamond i22, modelled from public beamline config |
| [IXS](ixs/index.md) | Reverse-engineered | momentum-resolved hard inelastic X-ray scattering, 10-ID; modelled from public beamline config |
| [SST](sst/index.md) | Reverse-engineered | soft-and-tender dual-branch, multi-endstation (RSoXS scattering, NEXAFS absorption, HAXPES photoemission), 7-ID; modelled from public beamline config |
| [ISS](iss/index.md) | Reverse-engineered | inner-shell spectroscopy (EXAFS by trajectory energy fly-scan, plus XES / HERFD on the Johann + von Hamos crystal emission spectrometers), 8-ID; modelled from public beamline config |
| [FMX](fmx/index.md) | Reverse-engineered | frontier microfocusing macromolecular crystallography (rotation MX on a single-omega goniometer + Eiger, autonomous robot sample exchange), 17-ID-2; CORA's 2nd MX after i03; modelled from public beamline config |

## [SLAC](slac/index.md)

The fifth Site CORA models, and its first X-ray free-electron laser. Like the Diamond and FXI exercises, LCLS-MFX is reverse-engineered from public open source (here SLAC's `pcdshub` stack), chosen as the one deployment that tests whether CORA generalizes beyond the storage-ring acquisition paradigm to an XFEL.

| Beamline | Status | What it is |
| --- | --- | --- |
| [LCLS-MFX](lcls-mfx/index.md) | Modelling exercise | macromolecular femtosecond crystallography at the LCLS free-electron laser; the first XFEL, where the device families fold but the per-shot acquisition paradigm does not |

## [Australian Synchrotron](as/index.md)

The sixth Site CORA models, and its first Australian facility (operated by ANSTO). Its MX3 beamline is reverse-engineered from the public `AustralianSynchrotron/mx3-beamline-library`, chosen to test that the Site / Federation kernel ports again and to stress the seam against a heterogeneous control plane (EPICS plus the MXCuBE Exporter protocol, the DECTRIS SIMPLON REST API, and a TCP sample robot).

| Beamline | Status | What it is |
| --- | --- | --- |
| [MX3](mx3/index.md) | Reverse-engineered | macromolecular crystallography (rotation MX) on an MD3 microdiffractometer + DECTRIS Eiger with an ISARA robot; reuses the i03 Goniometer and MX Methods, novelty is the Site and its heterogeneous control plane |

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
