# Controls

*The control stack that drives SYRMEP, and the seam where CORA's edge would sit. First cut, reverse-engineered.*

SYRMEP runs on the Elettra **Tango** control stack (the device floor, shared with the ESRF's ID32) with the in-house, trigger-driven **DonkiOrchestra** framework as the scan / acquisition engine. This is the fleet's first Tango + DonkiOrchestra controls house-style (the rest are EPICS, Tango / Sardana at MAX IV, or Tango / BLISS / IcePAP at the ESRF).

## The device floor: Tango

Tango is the distributed device / control substrate across both the Elettra synchrotron and the FERMI FEL; no EPICS is used at the facility level. Beneath it, the Elettra 2.0 GeCo stack provides PLC-based interlock and beamline control (Siemens S7-1500 over PROFINET, bound to Tango via a Python device server), with Tango motion / detector device servers and HDB++ historical archiving. CORA actuates **through** this Tango floor over the `ControlPort`; it never owns Tango device servers, the GeCo PLC interlock logic, or the device layer.

## The orchestration seam: DonkiOrchestra

The beamline scan / acquisition engine is DonkiOrchestra: DonkiDirector schedules DonkiPlayers over a ZeroMQ trigger train (each trigger carries a progressive index and a priority tag), collecting data into HDF5 archives. The Elettra 2.0 successor names this orchestration an abstract **"Executer"** Tango device server, feeding the STP3 / MAPI reconstruction and the Elettra Scientific Data Lake.

This orchestration is the seam CORA's edge replaces: experiment-as-sequence-of-phases maps onto CORA's run / acquisition modelling, and the ZeroMQ trigger train plus HDF5 collection is functionally the orchestration and capture legs. CORA's EdgeConductor would conduct over Tango rather than over BLISS or EPICS. Whether CORA replaces the DonkiOrchestra orchestration outright or drives through the "Executer" device server is the central seam design question.

## Handles are not in public source

Unlike the ID32 BLISS scaffold (read from a public Beacon config), **SYRMEP's device handles are not in public source**: the DonkiOrchestra source location is unconfirmed and the acquisition code lives in the private `gitlab.elettra.eu` `syrmep_acquisition` group. So every device handle in the [Inventory](../inventory.md) is a confirm-pending placeholder, deliberately not an invented Tango device URL (`CTRL-1`). The whole control plane is `Blocks-build` on the [Open questions](../questions.md) until staff provide the namespaces.

## The reconstruction pipeline

The SYRMEP Tomo Project (phase retrieval via TIE-HOM / Paganin, ring removal, FBP / iterative reconstruction on ASTRA + TomoPy, with Pore3D for analysis) is post-acquisition compute. CORA would record its invocation as Method / Compute provenance (the compute-as-adapter-axis model), not reimplement it and not own its output (`COMPUTE-1`).

## Pending

| Value to confirm | Applies to | Tracking |
| --- | --- | --- |
| The Tango device namespaces and DonkiOrchestra / "Executer" scan-engine handles | every device | `CTRL-1` |
| The PSS permit signals and front-end / safety shutters | the enclosures, `FrontEndShutter` | `PSS-1` |
| Whether CORA records the reconstruction pipeline as Compute provenance | the SYRMEP Tomo Project | `COMPUTE-1` |
