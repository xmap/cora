# Controls

*The control stack and the BLISS-orchestration seam. First cut; handles read from the BLISS Beacon config, carried confirm.*

ID28 runs on the ESRF BLISS / Beacon control stack over Tango and IcePAP, the same house-style CORA modelled first at ID32. CORA observes that floor and, where it replaces BLISS-style orchestration, conducts over it; it does not replace BLISS.

## Device handles

The control handles are filled from the ESRF's own BLISS Beacon device database ([gitlab.esrf.fr/id28/beamline_configuration](https://gitlab.esrf.fr/id28/beamline_configuration), a git mirror of the live config), so the descriptor carries the real addresses, mostly as BLISS controller / axis names with Tango device URLs underneath:

| Handle | Device |
| --- | --- |
| BLISS `PI_E518` (`pimth` / `pimchi`) | the high-resolution backscattering monochromator |
| BLISS `hfm_ctrl` / `vfm_ctrl` (benders) | the HFM / VFM focusing mirrors |
| BLISS `tth_multilayer` (`tth`) + `a2_inca` / `a3_inca` / `a4_inca` | the two-theta spectrometer arm and its inclined analyzer crystals |
| BLISS `lakeshore340_10k_displex` | the 10 K displex sample-temperature controller |
| BLISS lima `basler` / `pco` | the counting / imaging detectors |

CORA models each as an opaque control handle set at the edge, the way the ID32 / MX3 heterogeneous-control precedent does: the transport (BLISS, Tango, IcePAP) is a `ControlPort` adapter concern, not a difference in the Asset. The handles remain confirm-pending: a value read from the public Beacon config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`). The exact sample-stage axes and the per-analyzer detector handles are carried confirm-pending (`SAMPLE-1`, `DET-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam.

## The orchestration seam

The IXS acquisition (the meV incident-energy scan against the fixed-angle multi-analyzer arm, the two-theta moves that set the momentum transfer, the per-analyzer counting, the cryostat temperature control) runs through BLISS sequences. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through Tango / IcePAP rather than replacing BLISS. The live BLISS calc controllers that compute the arm geometry and the energy stay the floor; CORA names the energy and arm axes and records the moves. The detector file-writing to the ESRF data store is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The ESRF personnel-safety permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the BLISS Beacon config and are not invented here (`PSS-1`). The Beacon config is a device database, not a safety-system description: it carries the motion, optics, and detector handles, not the permit leaves behind an interlocked enclosure. ID28 also carries a hazard class governed at the Site, not modelled here: a cryogenic sample environment (the 10 K displex cryostat and its cryogens). The Enclosure permit shape and the hazard tier are carried pending at the ESRF Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../esrf/index.md#the-safety-envelope)).
