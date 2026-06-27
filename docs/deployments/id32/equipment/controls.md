# Controls

*The control stack and the BLISS-orchestration seam. First cut; handles read from the BLISS Beacon config, carried confirm.*

ID32 runs on the ESRF BLISS / Beacon control stack over Tango and IcePAP, the fleet's first non-EPICS, non-Sardana controls house-style (the rest are EPICS, or Tango / Sardana at MAX IV). CORA observes that floor and, where it replaces BLISS-style orchestration, conducts over it; it does not replace BLISS.

## Device handles

The control handles are filled from the ESRF's own BLISS Beacon device database ([gitlab.esrf.fr/id32/beamline_configuration](https://gitlab.esrf.fr/id32/beamline_configuration), a git mirror of the live Beacon config), so the descriptor carries the real addresses, in three forms that BLISS uses interchangeably:

| Handle form | Example | Where it appears |
| --- | --- | --- |
| Tango device URL | `id32/cryogenic_magnet_ps/xmcd1`, `id32/limaccds/andor_1`, `id32/regulation/ls336_hfm` | the magnet, the Andor CCDs, the LakeShore controllers |
| IcePAP host + address | `iceid324` (RIXS arm), `iceid329` (XES arm) | the spectrometer-arm motor crates |
| BLISS axis / controller name | `rixs_spectro`, `xes_spectro`, `hu70ag`, `hu70ap` | the spectrometer-arm calc controllers and the undulator gap / phase |

CORA models each as an opaque control handle set at the edge, the way the MX3 heterogeneous-control precedent does: the transport (Tango, IcePAP, BLISS) is a `ControlPort` adapter concern, not a difference in the Asset. The handles remain confirm-pending: a value read from the public Beacon config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`). The exact PGM, mirror, slit, diffractometer, and XMCD-sample-stage handles are carried confirm-pending where the config read did not pin them (`MONO-1`, `OPT-1`, `OPT-2`, `DIFF-1`, `SAMPLE-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam.

## The orchestration seam

The ID32 acquisition (the coordinated energy and polarization moves over the APPLE-II and the PGM, the spectrometer-arm Rowland trajectories, the field sweeps at the XMCD magnet, the diffractometer scans, the CCD readouts) runs through BLISS sequences. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through Tango / IcePAP rather than replacing BLISS. The live BLISS calc controllers that compute the spectrometer-arm radii and the undulator energy-to-gap stay the floor; CORA names the energy, polarization, and arm axes and records the moves, the controller owns the kinematics (`POL-1`). The Lima detector file-writing to the ESRF data store is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The ESRF personnel-safety permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the BLISS Beacon config and are not invented here (`PSS-1`). The Beacon config is a device database, not a safety-system description: it carries the motion, optics, and detector handles, not the permit leaves behind an interlocked enclosure. ID32 also carries hazard classes governed at the Site, not modelled here: a 9 Tesla superconducting magnet and its liquid-helium cryogens at the XMCD endstation, and an intense polarized soft X-ray beam. The Enclosure permit shape and the hazard tier are carried pending at the ESRF Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../esrf/index.md#the-safety-envelope)).
