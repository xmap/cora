# Open questions

*What CORA needs the Australian Synchrotron / MX3 team to confirm. This model is reverse-engineered from public open source (the [`AustralianSynchrotron/mx3-beamline-library`](https://github.com/AustralianSynchrotron/mx3-beamline-library) device library): the EPICS PVs are read from it, but vendor identities, physical positions, the source, and the non-EPICS subsystem endpoints are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: MX3 is an undulator beamline, but no source PV is in the library, only the storage-ring current monitor (`SR11BCM01:CURRENT_MONITOR`). | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the photon-shutter enable / status PVs (`MX3FE01SHT01`, `MX3BLSH01SHT01`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? The library exposes no enclosure structure. | An optics hutch plus an experiment hutch (the MD3 / Eiger / robot). | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-multilayer monochromator coating stripes and range, and the attenuator foil set. Both (`MX3MONO01`, `MX3FLT05`) are in source. | One Monochromator and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The beam-conditioning optics not in the library: mirrors and any standalone slits (the `devices/optics.py` stub is empty). | None modelled; the `MX3FLT05` unit carries the beam-size readback. | The mirror / slit Assets. |
| ENERGY-1 | Nice-to-have | Does MX3 scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

## Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer host / port (it is driven over the MXCuBE Exporter protocol at `MD3_ADDRESS:MD3_PORT`, an env-config default in the library, not a baked PV), and the full axis set behind the Exporter property names. | A `Goniometer` Asset (omega / kappa / phi + centring / alignment) over the Exporter seam; the host is deployment config. | The Goniometer interface and axes. |
| DET-1 | Blocks-go-live | The DECTRIS Eiger model (16M / 4M) and its SIMPLON REST endpoint (`SIMPLON_API`, an env-config default in the library). | An Eiger `Camera` over the SIMPLON REST seam; the endpoint is deployment config. | The detector Model and interface. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (a TCP client at `ROBOT_HOST`, mount / unmount trajectories gated on the MD3 state). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the i03 / i24 loops. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The flux and beam-position channel maps, and the `BeamPositionMonitor` sensor fold-vs-promote hold. | Read-only flux (`FluxMonitor`) and beam-position (loose `BeamPositionMonitor`) probes; channel maps blank. | The FluxMonitor / BeamPositionMonitor bindings. |
| STEER-1 | Nice-to-have | The closed-loop beam-steering controller (`MX3DAQIOC04:` PID + DAC paired with the BPM): is it a device Family of its own, or a settings-only feedback variant? It fits no existing family cleanly. | The BPM half binds the loose `BeamPositionMonitor`; the PID steering controller is named but not modelled. | The beam-steering device boundary. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs (the Australian Synchrotron Power Brick PMAC behind the `MX3STG..MOT..` axes). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities (rotation data collection, grid scan) enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i03 opened; MX3 reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
