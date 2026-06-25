# Open questions

*What CORA needs the BMM team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/bmm-profile-collection`](https://github.com/NSLS2/bmm-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build` (changes the model structure), `Blocks-go-live` (needed before CORA controls or observes the hardware), `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 6-BM bending-magnet source parameters (critical energy, fan). The source is confirmed a bending magnet (`SR:C06`), not an insertion device. | A bending-magnet PhotonBeam Supply, identity-only. | The Source Supply settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the front-end and photon shutters (`XF:06BM-PPS{Sh:FE}`, `{Sh:A}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Is the endstation a distinct hutch (6-BM-B) from the optics hutch (6-BM-A)? | Two enclosures, optics + experiment. | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The DCM crystal sets available (Si(111) confirmed; a Si(311) set?) and the energy range. | Si(111), range blank. | The Monochromator settings. |
| OPTIC-1 | Nice-to-have | The mirror coatings / stripes on M1 and M2 (harmonic rejection). | Two mirrors, coatings blank. | The Mirror settings. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| WHEEL-1 | Blocks-go-live | The sample wheel: how many sample positions, and is batch sample-changing a CORA-modelled automation or operator-driven? Should a dedicated sample-changer Family be earned across BMM and the Diamond robots, or does the wheel stay a `RotaryStage`? | A `RotaryStage` indexing samples; sample-changer behaviour is a Method/automation concern, not a new Family. | The sample-wheel model and the sample-changer abstraction. |
| DET-1 | Blocks-go-live | The fluorescence detector configuration: which Xspress3 element count (1, 4, or 7) is the installed/default, and the vendor (Quantum Detectors?). Source carries all three configurations. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; element count blank. | The detector Model and element count. |
| DIAG-1 | Blocks-go-live | The ion chambers (`I0`/`It`/`Ir`) gas fill and the per-channel PV bindings. | The quad electrometer binds the catalog `FluxMonitor` Family (graduated in #353); gas fill and per-channel detail unconfirmed. | The I0/It/Ir bindings and gas fill. |

## Controls and techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, serials, IPs. The endstation controller PV (`MC:09`) is in source; vendor detail is not. | A `MotionController`, specifics blank. | The MotionController Models. |
| ENERGY-1 | Blocks-build | Should CORA coin the `energy_scan` Capability (the catalog anticipates it as pending) now that BMM is its first real consumer, or keep XAS under `characterization` + `energy_change` until a conduct-path forces it? An XAS scan sweeps the energy axis and reads the detectors per point, distinct from the `beamline_energy_change` setpoint move. | XAS mapped to existing Capabilities for now; `energy_scan` deferred per the design-phase discipline. | The spectroscopy Capability decision. |
