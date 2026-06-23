# Open questions

*What CORA needs the 19-BM team to confirm before the model can be trusted.*

19-BM is in the design phase, so almost every value in the [Inventory](inventory.md) is a Final Design Report specification, not a commissioned measurement. Each row below is a fact the beamline team or the FDR owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV names for each device, and does 19-BM follow the 2-BM TomoScan / MCTOptics IOC layout? | Control handles are unassigned; CORA leaves each device handle empty (no PV) until the control system is up. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for 19-BM-A, 19-BM-C, and 19-BM-D? | Each enclosure exists with a permit signal to be named (ICMS APS_1181415). | The Enclosure permit signals. |
| ENC-1 | Blocks-build | 19-BM-C and 19-BM-D share a downstream-wall guillotine held open during operation, so they act as one shielded volume. Do they share a single PSS search-and-secure, and should CORA model them as one Enclosure or two coupled ones? | Modelled as two Enclosures today (19-BM-C carries no Assets); the coupling is noted, not yet a structural link. | The Enclosure shape for the C and D volumes. |
| BLEPS-1 | Blocks-go-live | How should the BLEPS equipment-protection chain (beamline vacuum, and the cooling water plumbed in series across the Be window and the photon stop) map onto CORA Supplies and the beam-availability signal? | Vacuum and cooling water are facility Supplies whose faults the BLEPS folds into beam availability, following 2-BM; no separate equipment-protection aggregate. | The BLEPS-to-Supply mapping. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FILTER-1 | Nice-to-have | How should the F3-30 two-bank Si/Ge/Cu filter unit be modelled: one selector over the combinatorial effective thicknesses, or one selector per bank? And what fills bank 2 slot 5? | One `Filter` Asset whose selectable foils are a per-Asset setting plus a position-to-thickness calibration, as at 2-BM; the combinatorial map is a setting, not a family split. | The filter selector modelling and the bank 2 slot 5 value. |

## Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | What are the sample rotary and linear positioning stages (the manipulator design was out of FDR scope)? | A rotary stage plus a linear positioning stage, reusing the `RotaryStage` and `LinearStage` Families, models unbound. | The sample stage Model bindings. |
| ROBOT-1 | Blocks-go-live | What is the robotic sample changer, and what is the separate safety review it requires before implementation? How should CORA gate autonomous loading on it? | The changer is one Positioner Asset that loads and unloads Subjects; its operation is gated by a Clearance that must be Active, issued after the separate safety review. Modelled when the design and review land. | The sample-changer Asset, its Clearance gate, and the autonomous loading flow. |
| TRIG-1 | Blocks-go-live | What is the high-throughput trigger and sync scheme: is the sample rotary TTL encoder the master clock, and is PSO-style fly-scan triggering used? | A single `TimingController` carries the scheme; the rotary encoder is the candidate master clock; conditioner and PSO use to be confirmed. | The trigger / sync chain. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which scintillator, microscope optics, and camera will be procured for the indirect-detection system? | A scintillator, a visible-light microscope (composed as the cross-facility `Microscope` Assembly presenting the Detector Role), and a camera; models unbound until procurement. | The detector hardware Model bindings. |
