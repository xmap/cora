# Controls

*The control plane P14 runs on, and the seam where CORA's edge would conduct over it. First cut.*

P14 runs on **EMBL Hamburg's own control domain**, distinct from the DESY Tango / Sardana floor the other PETRA III beamlines ([P01](../../p01/equipment/controls.md), [P06](../../p06/equipment/controls.md), [P11](../../p11/equipment/controls.md)) bind to, and shared in style with its sibling [P13](../../p13/equipment/controls.md). This is the sub-operator seam: P14 shares the PETRA III ring and Facility, but not its house style (`SEAM-1`, `CTRL-1`).

## The orchestration layer: MXCuBE

The experiment-orchestration layer is **MXCuBE** (the macromolecular-crystallography beamline-control application, shared with i03 / FMX / MANACA / TPS). The device topology in this descriptor is read from EMBL Hamburg's public MXCuBE HardwareObjects configuration, published as two configs for P14's two endstations: [`embl_hh_p14`](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p14) for EH1 and [`embl_hh_pe2`](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_pe2) for EH2. Each `.xml` object is one device, carrying its class, its control channels, and its role wiring to sub-objects.

## The floor: two protocols, three hosts

Underneath MXCuBE, the device floor is two protocols across three diffractometer hosts:

- The **Exporter protocol** on the microdiff hosts: `p14md301` / `p14md302` for the EH1 EMBLMiniDiff, and `pe2bsd01` for the EH2 EMBLBSD. The diffractometer omega / kappa / centring axes and the aperture / beamstop / objective / light motions are Exporter motors and commands on these hosts.
- **TINE channels** (`/P14/...`, `/PE2/...`): the detectors (`/P14/detector/eiger16m`, `/PE2/detector/pilatus2m`), the shared energy / wavelength service (`/P14/Energy/P14Energy`), the CRL transfocator (`/P14/p14CRLs.CDI`), the detector distance / resolution (`/P14/collection/*`, `/PE2/collection/*`), and the flux / XRF services are TINE-addressed.

The handles are read from the public MXCuBE configs and carried confirm; the configs are the `develop` branch of the upstream MXCuBE repository, so some entries may lag the live beamline deployment, and some EH2 axes are published as `MotorMockup` simulation placeholders (`CTRL-1`, `MOCK-1`).

## Two hutches, one source

P14's two experiment hutches share one source / optics chain: the photon energy and the primary CRL are common to both endstations (the EH2 config's energy and CRL handles point back to `/P14/...`), while each hutch carries its own diffractometer host. The optics / experiment hutch split is inferred from the device prefixes and the MX layout, not from distinct interlock domains (`ENC-1`, `EH-1`).

## The seam: where CORA's edge conducts

The MXCuBE data-collection routine (the goniometer oscillation coupled to the Eiger / Pilatus frame capture) is the layer CORA's edge would conduct over its `ControlPort`, driving through or replacing the MXCuBE routine per routine, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A, here landing on the Exporter / TINE floor rather than Sardana (`CTRL-2`, `SEAM-1`). CORA never owns the Exporter hosts, the TINE servers, or MXCuBE's ISPyB / queue bookkeeping; it conducts the scan over them. The MXCuBE data-analysis and file-writing chain is plumbing CORA observes, not data it owns.

## Modelled controllers

The descriptor records the two control services read from the configs: `ExporterMotionController` (`Exporter_microdiff`, the microdiff-hosted diffractometers and beam-defining motions across all three hosts) and `TINEMotionController` (`TINE_embl`, the KB mirror motions, the CRL transfocator, the energy / wavelength service, the detector distance / resolution, and the flux / XRF services). These are carried confirm; their physical controller inventory is not in the configs (`CTRL-1`).
