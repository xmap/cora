# Open questions

*What CORA needs the NSRRC / TPS 07A team to confirm. This model is reverse-engineered from public open source (the [`light911/NSRRC_TPS07A`](https://github.com/light911/NSRRC_TPS07A) control tree and [`light911/TPS07A-Meshbest`](https://github.com/light911/TPS07A-Meshbest) app): the EPICS PV namespace (`07a:` / `07a-ES:`) is read from it, but per-device PV records, vendor identities, physical positions, the source, and the PSS signals are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: TPS 07A is fed by the IU22 in-vacuum undulator (per the SPXF spec page), but no source PV is in the public tree. | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. No PSS permit signals are in the public source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? The trees expose no enclosure structure. | An optics hutch (DCM, mirrors) plus an experiment hutch (the MD3 / EIGER2 / robot). | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator crystal cut and exact range, and the attenuator foil set. | A Si DCM over 6-20 keV and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The micro-focus optic delivering the ~2.9 x 1.8 micron spot: is it a KB mirror pair, and what are its PVs? The SPXF page states the focal spot, not the optic. | A KB micro-focus mirror system (`KBMirrors`, Mirror family), configuration blank. | The mirror Assets and PVs. |
| ENERGY-1 | Nice-to-have | Does TPS 07A scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

## Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer axis PV records (`07a-ES:` namespace, reached through the EPICS DHS), the full axis set, and the settling confirmation that the live scan orchestration is Blu-Ice/DCSS and not a live MXCuBE `mxcubecore` HardwareObjects deployment. (Public evidence is high-confidence DCSS; a live MXCuBE config for 07A would flip the seam to mixed.) | A `Goniometer` Asset (omega / kappa / phi + centring / alignment) on the EPICS floor; the DCSS-over-EPICS seam (the 2-BM pattern), not MXCuBE; PV records deployment config. | The Goniometer interface, axes, and the seam confirmation. |
| DET-1 | Blocks-go-live | The EIGER2 X 16M detector PV records and its SIMPLON REST endpoint, and whether the ZMQ frame egress has migrated to DESY ASAP::O in production. | An EIGER2 `Camera` commanded through the DCSS workflow; frames over ZMQ migrating to ASAP::O; endpoint deployment config. | The detector Model, interface, and frame-egress path. |
| ENV-1 | Nice-to-have | The cryostream sample-cooling vendor and PV. | A `TemperatureController` Asset, settings blank. | The cryostream Model and PV. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (mount / unmount trajectories gated on the MD3 state). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the i03 / i24 / MX3 loops. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The beam-position / XBPM and OAV-camera channel maps and PVs. | Read-only beam-position (graduated catalog `PositionMonitor`) and OAV (`Camera`) probes; channel maps blank. | The diagnostic bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs behind the endstation, goniometer-base, and detector stages (EPICS motor records reached through the DHS). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities (rotation data collection, mesh / grid scan) enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i03 opened; TPS 07A reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
| GOV-1 | Nice-to-have | The operator / beamline-scientist roster and review structure (the trees show LDAP auth at `ldap://10.7.1.1` and a mandatory training portal at `safetytraining.nsrrc.org.tw`, but no roster). | CORA's role kernel scoped at the Site; the training portal maps to the worldwide-invariant training axis on the principal. | The Actor roster and training-axis binding. |
