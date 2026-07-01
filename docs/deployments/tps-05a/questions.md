# Open questions

*What CORA needs the NSRRC / TPS 05A team to confirm. This model is reverse-engineered from public open source, but TPS 05A's source is thinner than [TPS 07A](../tps-07a/questions.md)'s: there is no dedicated 05A control tree (the public `NSRRC_TPS05A_BeamMonitor` repo is an empty stub), so the device kit is read from the [SPXF facility pages](https://nsrrcspxf.github.io/nsrrcspxf/index.html) and the 2025 J. Synchrotron Rad. cluster paper, and the seam / PV model is inherited from the 07A reading. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Provenance (05A-specific)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PV-1 | Blocks-go-live | The EPICS PV namespace. 07A's `07a:` / `07a-ES:` was read from its control tree; 05A has no public tree, so its namespace is **inferred** as `05a:` / `05a-ES:` by cluster convention. Is that correct? | The 05A beamline namespace is `05a:` and the endstation `05a-ES:`, inferred, not verified. | The PV namespace for every Asset. |

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: TPS 05A is fed by a TPS undulator (per the SPXF page), but no source PV is in public source. | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. No PSS permit signals are in public source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? Public source exposes no enclosure structure. | An optics hutch (DCM, mirrors) plus an experiment hutch (the MD3 / EIGER2 / robot). | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator crystal cut and exact range, and the attenuator foil set. | A Si DCM over ~5.7-20 keV and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The focusing optic and the microcrystallography spot size (not stated in public source for 05A). | A KB focusing mirror system (`KBMirrors`, Mirror family), configuration and spot blank. | The mirror Assets, spot size, and PVs. |
| ENERGY-1 | Nice-to-have | Does TPS 05A scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

## Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer axis PV records, the full axis set, and the settling confirmation that 05A's live scan orchestration is Blu-Ice/DCSS and not a live MXCuBE deployment (the 2025 cluster paper says Blu-Ice/DCS for all three MX endstations; high confidence, but per-beamline confirmation is owed). | A `Goniometer` Asset on the EPICS floor; the DCSS-over-EPICS seam (the 07A / 2-BM pattern), not MXCuBE; PV records deployment config. | The Goniometer interface, axes, and the seam confirmation. |
| DET-1 | Blocks-go-live | The EIGER2 X 9M detector PV records, its SIMPLON REST endpoint, and any detector minimum-distance interlock (07A has one at 139 mm; 05A's is unknown). | An EIGER2 X 9M `Camera` commanded through the DCSS workflow; endpoint and interlock deployment config. | The detector interface and safety limit. |
| ENV-1 | Nice-to-have | The cryostream sample-cooling vendor and PV. | A `TemperatureController` Asset, settings blank. | The cryostream Model and PV. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (the same model as 07A). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the i03 / i24 / 07A / MX3 shape. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The beam-position / XBPM and OAV-camera channel maps and PVs. | Read-only beam-position (graduated catalog `BeamPositionMonitor`) and OAV (`Camera`) probes; channel maps blank. | The diagnostic bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs behind the endstation, goniometer-base, and detector stages. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities enter CORA's catalog, or stay deferred? The same owner-scope decision i03 opened; 05A reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
