# Open questions

*What CORA needs the TomoWISE team to confirm before the model can be trusted.*

TomoWISE is in the design phase, so this page is long by design: almost every value in the [Inventory](inventory.md) is a TDR design specification, not a commissioned measurement. Each row below is a fact the beamline team or the TDR owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the Tango/Sardana device and attribute names for each device? | Control handles are unassigned; CORA leaves the device handle empty (no EPICS PV). | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for the optics and experiment hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Nice-to-have | Which MLM coating is selected, W/Si or W/B4C? | The MLM is one Monochromator Asset; coating is a setting. | The MLM coating setting. |
| LAYOUT-1 | Nice-to-have | What is the single z-coordinate reference for the layout? The TDR mixes "from the CPMU14 source" (front end) and "from the straight-section centre" (optics and downstream), about 505 mm apart. | z values are carried as approximate from-source and flagged confirm. | Exact device z positions. |

## Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| NANO-1 | Blocks-build | What is the nanotomography sample stage (model, travel, resolution)? The TDR defers it to procurement. | A nano sample stage exists but is unspecified. | The nanotomography endstation sample positioning. |
| STAGE-1 | Blocks-go-live | Is the rotary stage the Lab Motion Systems RT100AX, and are its specs final? | The "(target)" RT100AX, used as the trigger master clock. | The rotary stage Model binding. |
| STAGE-2 | Nice-to-have | Is the sample positioning stage the Lab Motion Systems XY150B-12? | The "(target)" XY150B-12. | The sample positioning Model binding. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which camera models will be procured for cameras I to IV? (Chosen in project year 2.) | Four cameras at the stated design-target sensors/speeds; models unbound. | The camera Model bindings. |
| DET-2 | Blocks-go-live | Which microscope optics vendor and model (Optique Peter MICRX080 reference, or a smaller vendor)? | Two microscopes (MicLFOV, MicHR) at the stated magnifications; vendor unbound. | The microscope Model bindings. |
| TRIG-1 | Blocks-go-live | Will the rotary TTL (3600 pulses/rev) feed the camera triggers directly, or is an FPGA conditioner needed? | Direct TTL, no conditioner; may evolve once camera trigger requirements are firm. | The trigger/sync chain. |
