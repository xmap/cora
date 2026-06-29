# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

A beamline is never standalone: it sits inside a Site, a Federation `Facility` that owns the clearances, principals, practices, and facility-scope supplies the beamline inherits but does not own. The deployments below are grouped by that Site; each beamline page links up to its Site rather than restating it. CORA's operational pilot is 2-BM. Most of the rest are in the design phase, modelled from a design report ahead of construction or recommissioning. The Diamond and NSLS-II beamlines, SLAC's LCLS-MFX, the Australian Synchrotron's MX3, and PSI's Alvra, Bernina, and Cristallina are a third kind: operating beamlines reverse-engineered from public controls configuration, so their pages carry real control facts but every value stays `confirm` until the beamline team verifies it.

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
| [I24](i24/index.md) | Modelling exercise | serial / fixed-target macromolecular crystallography (chip-coordinate single-shot); reuses the Goniometer, first synchrotron serial MX |
| [I06](i06/index.md) | Modelling exercise | APPLE-II variable-polarization soft X-ray (XMCD/XMLD, PEEM, resonant diffraction); polarization as a controllable axis |
| [I10](i10/index.md) | Modelling exercise | BLADE twin APPLE-II soft X-ray: RASOR resonant scattering / reflectivity + i10-1 magnet dichroism |
| [I20-1](i20-1/index.md) | Modelling exercise | energy-dispersive / time-resolved EXAFS (EDE); a deliberately partial first cut, the dispersive polychromator + strip detector deferred (POLY-1 / STRIP-1) |

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
| [IOS](ios/index.md) | Reverse-engineered | in situ / operando soft X-ray spectroscopy (ambient-pressure XPS / AP-PES, NEXAFS / XAS), 23-ID-2; the twin of CSX on the canted 23-ID straight; modelled from public beamline config |
| [XPD](xpd/index.md) | Reverse-engineered | high-energy powder diffraction and total scattering / PDF, 28-ID; the NSLS-II twin of Diamond i11 and i15-1, modelled from public beamline config |
| [ESM](esm/index.md) | Reverse-engineered | electron spectro-microscopy (ARPES), 21-ID; CORA's first photoemission beamline, graduates the Manipulator Family, modelled from public beamline config |
| [SMI](smi/index.md) | Reverse-engineered | small- and wide-angle scattering (SAXS/WAXS) with grazing incidence (GISAXS/GIWAXS), 12-ID; the NSLS-II twin of Diamond i22, modelled from public beamline config |
| [IXS](ixs/index.md) | Reverse-engineered | momentum-resolved hard inelastic X-ray scattering, 10-ID; modelled from public beamline config |
| [SST](sst/index.md) | Reverse-engineered | soft-and-tender dual-branch, multi-endstation (RSoXS scattering, NEXAFS absorption, HAXPES photoemission), 7-ID; modelled from public beamline config |
| [ISS](iss/index.md) | Reverse-engineered | inner-shell spectroscopy (EXAFS by trajectory energy fly-scan, plus XES / HERFD on the Johann + von Hamos crystal emission spectrometers), 8-ID; modelled from public beamline config |
| [FMX](fmx/index.md) | Reverse-engineered | frontier microfocusing macromolecular crystallography (rotation MX on a single-omega goniometer + Eiger, autonomous robot sample exchange), 17-ID-2; CORA's 2nd MX after i03; modelled from public beamline config |
| [CMS](cms/index.md) | Reverse-engineered | complex-materials scattering (SAXS/WAXS/MAXS, GISAXS/GIWAXS) and the fleet's first hard X-ray reflectivity (XR), 11-BM; the NSLS-II twin of SMI; modelled from public beamline config |
| [XFM](xfm/index.md) | Reverse-engineered | scanning X-ray fluorescence microprobe (raster XRF mapping on the Xspress3 + Maia detectors, bending magnet), 4-BM; CORA's 2nd scanning-XRF after 2-ID; modelled from public beamline config |
| [LIX](lix/index.md) | Reverse-engineered | life-science solution scattering (bio-SAXS/WAXS, in-line SEC-SAXS) and scanning-microbeam mapping, 16-ID; the fleet's first solution beamline and fluidic sample-delivery chain; modelled from public beamline config |
| [HEX](hex/index.md) | Reverse-engineered | high-energy engineering X-ray scattering (imaging/tomography + energy-dispersive and powder diffraction on a superconducting wiggler, white 30-250 keV / mono 30-200 keV), 27-ID; the fleet's first true high-energy hard X-ray beamline; modelled from public beamline config |
| [AMX](amx/index.md) | Reverse-engineered | highly automated macromolecular crystallography (rotation MX on a single-omega goniometer + Eiger, EMBL robot sample exchange), 17-ID-1; FMX's sibling, CORA's 3rd MX; modelled from public beamline config |
| [XFP](xfp/index.md) | Reverse-engineered | X-ray footprinting of biological macromolecules in solution (white/pink-beam radiolytic dose delivery, offline mass-spec readout), 17-BM; the fleet's first dose-delivery beamline (no scattering detector); modelled from public beamline config |
| [ISR](isr/index.md) | Reverse-engineered (partial) | in-situ and resonant hard X-ray scattering / surface diffraction, 4-ID; a deliberately partial first cut, the multi-circle diffractometer + in-situ environment + resonant energy axis deferred (DIFF-1 / INSITU-1 / RESONANT-1); modelled from public beamline config |
| [CDI](cdi/index.md) | Reverse-engineered | coherent diffractive imaging (forward CDI, ptychography, Bragg CDI) with a KB nanofocus and Eiger2 / Merlin photon-counting detectors, 9-ID; NSLS-II's coherent-imaging beamline after Diamond i13-1, distinct from APS 9-ID; modelled from public beamline config |
| [PDF](pdf/index.md) | Reverse-engineered | high-energy total scattering / pair distribution function and powder diffraction (side-bounce Laue mono, two-detector two-distance merge on PerkinElmer + Pilatus panels), 28-ID-1; XPD's dedicated PDF twin on the shared 28-ID damping wiggler; modelled from public beamline config |

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

## [PSI](psi/index.md)

CORA's eighth Site (the Paul Scherrer Institut). Like SLAC, the Site is the institute: PSI hosts two photon sources, the Swiss Light Source (SLS / SLS 2.0) storage ring and SwissFEL, with the beamlines as stations under it. The I-TOMCAT beamline (on SLS) is a hybrid modelled from PSI's public beamline pages and the SLS 2.0 design reports (the TomoWise tradition), because no public per-beamline controls config exists for TOMCAT; SLS is an EPICS facility with the BEC scan layer over ophyd, the seam CORA's edge would replace. The three SwissFEL Aramis stations make PSI CORA's second X-ray free-electron laser after SLAC, reverse-engineered from PSI's own controls libraries to re-test the XFEL findings against an independently-built FEL: LCLS-MFX was mined from SLAC's `pcdshub`, the Aramis stations from `eco` / `slic`. Alvra confirms the family-fold and acquisition-gap findings from an independent control stack; Bernina makes the shared-switched-source seam (TOPO-1) concrete, as the second co-equal station on the one Aramis source, and reaches the same gaps through diffraction; Cristallina closes the Aramis triad as the third station, is the first deployment mined from the `slic` library (eco's successor, on gitea.psi.ch) rather than `eco`, and adds a dilution-fridge vector-magnet sample environment. No PSI station coins a new Family.

| Beamline | Status | What it is |
| --- | --- | --- |
| [I-TOMCAT](i-tomcat/index.md) | Reverse-engineered | insertion-device tomographic microscopy (absorption + propagation phase contrast + dynamic 4D CT on the PSI GigaFRoST camera), X02SA; the SLS 2.0 undulator half of the rebuilt TOMCAT, CORA's micro-CT analog of APS 2-BM |
| [Alvra](alvra/index.md) | Reverse-engineered | hard X-ray femtosecond pump-probe (time-resolved XAS / XES / HERFD and serial crystallography) on the SwissFEL Aramis branch; CORA's second XFEL, reinforcing the LCLS-MFX family-fold and acquisition-gap findings from an independent control stack (`eco`) |
| [Bernina](bernina/index.md) | Reverse-engineered (partial) | hard X-ray femtosecond pump-probe diffraction / scattering on two reconfigurable diffractometers (GPS six-circle, XRD You-geometry); the second co-equal station on the shared Aramis source, makes the shared-switched-source seam concrete, reuses the graduated Diffractometer Assembly; a deliberately partial first cut (`eco`), the live device config is externalized |
| [Cristallina](cristallina/index.md) | Reverse-engineered | hard X-ray time-resolved diffraction / scattering on quantum materials (DM1 / DM2 diffractometers in a dilution-fridge vector superconducting magnet) plus serial crystallography; the third Aramis station, closes the shared-source triad, CORA's first deployment mined from `slic`, fourth `Magnet` consumer (held), no new Family |

## [Sirius](sirius/index.md)

CORA's first South American facility (the Brazilian Synchrotron Light Laboratory, LNLS, at CNPEM in Campinas). Its beamlines are reverse-engineered from published papers and public facility pages rather than open controls configs, so they are thin scaffolds: device families are inferred but no control handles or vendor models are public, and every value stays `confirm` until staff verify it.

| Beamline | Status | What it is |
| --- | --- | --- |
| [MOGNO](mogno/index.md) | Reverse-engineered (partial) | cone-beam X-ray micro and nanotomography (phase-contrast, time-resolved 4D) across two stations; reuses the 2-BM / FXI tomography vocabulary, novelty is the Site and the fleet's first custom-Python (non-Bluesky) orchestration layer |
| [MANACA](manaca/index.md) | Reverse-engineered | macromolecular crystallography (rotation MX, serial and room-temperature) on a goniometer + area detector with a 48-pin sample changer; Sirius's first MX beamline, reuses the i03 / FMX / AMX / MX3 Goniometer and MX Methods on the EPICS floor + MXCuBE3, no new Family |

## [ALBA](alba/index.md)

CORA's Site for the ALBA Synchrotron (Barcelona, Spain), and its second Tango / Sardana / Taurus control house-style after MAX IV (ALBA is the originating institution of Sardana). FAXTOR is reverse-engineered from ALBA's public facility pages, chosen to port the Site / Federation kernel again and to reuse the tomography vocabulary on a new facility and control plane.

| Beamline | Status | What it is |
| --- | --- | --- |
| [FAXTOR](faxtor/index.md) | Reverse-engineered | BL31 fast X-ray micro-CT and radiography (continuous-rotation tomography up to 20 Hz) on a multipole wiggler; reuses the tomography Families and Methods, novelty is the Site and its Tango / Sardana control plane |

## [NSRRC](nsrrc/index.md)

CORA's first Taiwan facility (the National Synchrotron Radiation Research Center, Hsinchu, operating two rings, the Taiwan Light Source and the Taiwan Photon Source). TPS 07A is reverse-engineered from public open source (the `light911/NSRRC_TPS07A` + `light911/TPS07A-Meshbest` control trees plus JACoW proceedings), chosen because it is the only NSRRC beamline with a complete public control tree, and because its Blu-Ice/DCSS-over-EPICS seam is the 2-BM TomoScan pattern at an MX beamline. TPS 05A is its MX-cluster sibling, a reuse-and-reinforce deployment on the same Site, Blu-Ice/DCSS stack, and MD3 + ISARA kit (with an EIGER2 X 9M), modelled from the SPXF facility pages and the 2025 cluster paper. NSRRC publishes no official org code, so the corpus is scattered personal GitHub accounts.

| Beamline | Status | What it is |
| --- | --- | --- |
| [TPS 07A](tps-07a/index.md) | Reverse-engineered | micro-focus protein crystallography (rotation MX) on an Arinax MD3 + DECTRIS EIGER2 X 16M with an ISARA robot; reuses the i03 / MX3 Goniometer and MX Methods, novelty is the Site and its Blu-Ice/DCSS-over-EPICS orchestration seam (the 2-BM pattern, confirmed live over MXCuBE) |
| [TPS 05A](tps-05a/index.md) | Reverse-engineered | protein microcrystallography (rotation MX) on the same MD3 + ISARA kit with a DECTRIS EIGER2 X 9M; the MX-cluster sibling of 07A, a reuse-and-reinforce deployment coining no new vocabulary, modelled from the SPXF pages + the 2025 cluster paper (thinner source, PV namespace inferred) |

## [PETRA III](petra-iii/index.md)

CORA's Site for PETRA III (DESY, Hamburg), and its second Tango / Sardana control house-style after MAX IV / ALBA. P01 is reverse-engineered from P01's own public OnlineXML device registry (the `online_*.xml` Tango device list under `petra-iii-debian-packages` on gitlab.desy.de), extracted with the `scripts/reverse_engineer/` `--source onlinexml` path, chosen because the OnlineXML carries real per-device Tango handles across all 18 public PETRA III beamlines and because P01's NRS / RIXS dynamics techniques are new to CORA's technique surface.

| Beamline | Status | What it is |
| --- | --- | --- |
| [P01](p01/index.md) | Reverse-engineered | nuclear resonant scattering and inelastic / resonant-inelastic scattering (2.5-80 keV) across two optics hutches and three experiment hutches (EH1 NRS high-resolution-monochromator stack, EH2 diffraction, EH3 RIXS / KB pair); reuses the optics / motion Families, novelty is the Site, its Tango / Sardana control plane read from the OnlineXML, and the NRS / RIXS technique branch (reusing the pending IXS / RIXS Methods) |
| [P04](p04/index.md) | Reverse-engineered | variable-polarization soft X-ray spectroscopy (250-3000 eV: XAS, photoemission) across a soft X-ray optics section and two experiment endstations; CORA's first `GratingMonochromator` deployment (the plane-grating mono), reuses the optics / motion Families otherwise, reusing the pending `xas_spectroscopy` / `angle_resolved_photoemission` Methods |
| [P06](p06/index.md) | Reverse-engineered | hard X-ray scanning micro / nano fluorescence and diffraction microscopy + nano-tomography across an optics hutch and two scanning-probe endstations (MC01 micro, NC1 nano); the fleet's fullest scanning-probe instrument (the Maia XRF array as `EnergyDispersiveSpectrometer`, hexapods, Aerotech fly-scan stages), coins no new Family, reusing the pending `scanning_fluorescence_microscopy` / `tomography` Methods |
| [P11](p11/index.md) | Reverse-engineered | high-throughput macromolecular crystallography (rotation MX) and bio-imaging on a goniometer + Pilatus detector with cryostream cooling; PETRA III's first MX beamline, a reuse-and-reinforce deployment coining no new vocabulary (reuses the i03 MX vocabulary and the pending `mx_data_collection` / `tomography` Methods); a sparse registry, so the experiment hutch is modelled as grouped stages with the goniometer carried as a question |
| [P03](p03/index.md) | Reverse-engineered | micro- and nanofocus small- and wide-angle X-ray scattering (SAXS / WAXS, 9-23 keV) across shared P02 / P03 optics and two endstations (a microfocus endstation and the nanofocus GINIX waveguide endstation); the fleet's first SAXS / WAXS beamline, coins no new Family, brings Galil DMC and SmarPod controllers, reusing the pending `small_angle_scattering` / `wide_angle_scattering` Methods |
| [P10](p10/index.md) | Reverse-engineered | coherent hard X-ray applications (XPCS, coherent diffraction imaging / ptychography) across an optics hutch and three experiment areas (E1 coherent imaging, E2 XPCS / diffraction, LAB); the fleet's second XPCS beamline and the first PETRA III practice to bind a graduated catalog Method (`xpcs`, earned at 8-ID) rather than a pending slug; coins no new Family, with the widest detector suite in the set |
| [P09](p09/index.md) | Reverse-engineered | resonant scattering, diffraction, and high-field magnetism (XMCD, magnetic scattering) across a resonant-scattering hutch, a diffraction hutch, and a 14 T magnetism endstation; the second consumer of the 4-ID POLAR polarization / magnetism vocabulary (the allowlisted-loose `PhaseRetarder` / `PolarizationAnalyzer` / `Magnet` Families), coins no new Family, reusing the pending `resonant_scattering` / `magnetic_scattering` / `xmcd` Methods |
| [P02](p02/index.md) | Reverse-engineered | high-energy hard X-ray diffraction: P02.1 powder diffraction / total scattering / PDF (~60 keV) + P02.2 extreme conditions (diamond-anvil-cell high-pressure diffraction); the fleet's second diamond-anvil-cell deployment (reuses the 13-id-d allowlisted-loose `PressureCell`), bendable HFM / VFM mirrors, coins no new Family, reusing the pending `powder_diffraction` / `total_scattering` Methods |
| [P64](p64/index.md) | Reverse-engineered | advanced X-ray absorption spectroscopy (dilute / high-rate fluorescence EXAFS / XANES) on a Tsai DCM + a multi-element fluorescence detector (104-channel SIS3302); the advanced half of the PETRA III XAS pair, coins no new Family, reusing the pending `xas_spectroscopy` Method |
| [P65](p65/index.md) | Reverse-engineered | applied / high-throughput X-ray absorption spectroscopy (transmission + fluorescence EXAFS / XANES) on a channel-cut DCM, sharing the P64 optics host; the applied half of the XAS pair, a thin reuse-and-reinforce scaffold (detection carried pending), reusing the pending `xas_spectroscopy` Method |
| [P07](p07/index.md) | Reverse-engineered | high-energy materials-science diffraction (HEMS) on a multi-bounce DCM + four-circle diffractometer, with a 17 T high-field magnet endstation; jointly operated by Helmholtz-Zentrum Hereon + DESY, coins no new Family (a further consumer of the loose `Magnet`), reusing the pending `diffraction` / `magnetic_scattering` Methods |
| [P08](p08/index.md) | Reverse-engineered | high-resolution diffraction (surface / interface, reflectivity, powder / single-crystal) on a six-circle Kohzu diffractometer with a rich detector set (Eiger / Pilatus / Mythen / PerkinElmer / Vortex); coins no new Family, reusing the pending `diffraction` Method |

## [ALS](als/index.md)

CORA's Site for the Advanced Light Source (Lawrence Berkeley National Laboratory, Berkeley), and its first BCS controls house-style: every prior Site is EPICS, Tango / Sardana, or BLISS, while the ALS runs BCS (the Beamline Control System), a LabVIEW stack. 8.3.2 is reverse-engineered from ALS's public facility pages ([als.lbl.gov](https://als.lbl.gov/beamlines/8-3-2/), [microct.lbl.gov](https://microct.lbl.gov/)) and the public [als-computing](https://github.com/als-computing) GitHub org, chosen to reuse the tomography vocabulary on a new facility and a new control plane. Its device topology is read from the DXchange / DXfile HDF5 data-record schema that the ALS tooling reads (a third descriptor mode, between FXI's real EPICS PVs and FAXTOR's no-manifest); the live BCS control handles are not public and stay `confirm`-pending. The ALS-U upgrade (storage-ring dark time no sooner than October 2027, at least two years) is a roadmap constraint, with 8.3.2's upgrade fate carried as a staff question.

| Beamline | Status | What it is |
| --- | --- | --- |
| [8.3.2](8-3-2/index.md) | Reverse-engineered | hard X-ray micro-tomography (micro-CT) on a Superbend source, 6-43 keV, ~1 micron; reuses the 2-BM / FXI / FAXTOR tomography Families and Methods, novelty is the Site and its BCS / LabVIEW control plane |

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
