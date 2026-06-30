# Controls

*The control plane P13 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P13 runs on **EMBL Hamburg's own control domain**, distinct from the DESY Tango / Sardana floor the other PETRA III beamlines ([P01](../../p01/equipment/controls.md), [P06](../../p06/equipment/controls.md), [P11](../../p11/equipment/controls.md)) bind to. This is the sub-operator seam: P13 shares the PETRA III ring and Facility, but not its house style (`SEAM-1`, `CTRL-1`).

## The orchestration layer: MXCuBE

The experiment-orchestration layer is **MXCuBE** (the macromolecular-crystallography beamline-control application, shared with i03 / FMX / MANACA / TPS). The device topology in this descriptor is read from EMBL Hamburg's public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p13), `configuration/embl_hh_p13`): each `.xml` object is one device, carrying its class, its control channels, and its role wiring to sub-objects.

## The floor: two protocols

Underneath MXCuBE, the device floor is two protocols:

- The **Exporter protocol** on the microdiff host (`p13md201.embl-hamburg.de:9001`): the EMBLMiniDiff omega / kappa / centring axes and the aperture / beamstop / objective / light motions are Exporter motors and commands on this host (the microdiff / MD2-style server).
- **TINE channels** (`/P13/...`): the detectors (`/P13/detector/eiger16m`, `/P13/detector/pilatus6m`), the energy / wavelength service (`/P13/Energy/P13Energy`), the detector distance / resolution (`/P13/collection/*`), and the flux / XRF services are TINE-addressed.

The handles are read from the public MXCuBE config and carried confirm; the config is the `develop` branch of the upstream MXCuBE repository, so some entries may lag the live beamline deployment (`CTRL-1`). The optics / experiment hutch split is inferred from the device prefixes and the MX layout, not from distinct hosts (`ENC-1`).

## The seam: where CORA's edge conducts

The MXCuBE data-collection routine (the goniometer oscillation coupled to the Eiger frame capture) is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the MXCuBE routine per routine, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A, here landing on the Exporter / TINE floor rather than Sardana (`CTRL-2`, `SEAM-1`). CORA never owns the Exporter host, the TINE servers, or MXCuBE's ISPyB / queue bookkeeping; it conducts the scan over them. The MXCuBE data-analysis and file-writing chain is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the two control services read from the config: `ExporterMotionController` (`Exporter_microdiff`, the microdiff-hosted diffractometer and beam-defining motions) and `TINEMotionController` (`TINE_embl`, the KB mirror motions, the energy / wavelength service, the detector distance / resolution, and the flux / XRF services). These are carried confirm; their physical controller inventory is not in the config (`CTRL-1`).
