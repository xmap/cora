# Enclosures

*Enclosure BC permits that gate Runs and Procedures at 2-BM.*

An Enclosure models the observed permit status of an access-gated volume: a physical space whose interlock and search-and-secure sequence must be satisfied before beam-on work proceeds inside it. See the [Enclosure module](../../architecture/modules/enclosure/index.md) for the aggregate shape, the permit and lifecycle axes, and the pre-flight gate that reads them.

2-BM has two hutch Enclosures, the optics hutch `2-BM-A` and the experiment hutch `2-BM-B`. Each is its own access-gated volume with its own Personnel Safety System permit, observed independently, and each is anchored to the APS Site via `facility_code = "aps"` (a space contained in a larger space, not a pointer to an equipment Asset).

| Enclosure | Role | Anchored to | Gates |
| --- | --- | --- | --- |
| `2-BM-A` | optics hutch | `aps` Site (`facility_code`) | the `front-end` and `conditioning-optics` Devices and their descendants |
| `2-BM-B` | experiment hutch | `aps` Site (`facility_code`) | the `beam-defining-and-safety`, `sample-environment`, and `detector` Devices and their descendants |

Each Device declares which hutch it sits in via `located_in_enclosure_id`. The optics band (`FrontEndDrive` and the mirror, monochromator, conditioning-slit, filter, and diagnostic-flag chain) is in `2-BM-A`; the beam-defining-and-safety stack (including the P6-50 safety stack and its SBS shutter), the sample environment, and the detector are in `2-BM-B`. The Located-in column on [Assets](inventory.md) is the per-Device source of truth.

## Permit signal and gate

Each hutch's permit maps off one Personnel Safety System search-and-secure PV, the `permit_signal` in the descriptor: `2-BM-A` is Permitted when `S02BM-PSS:StaA:SecureM == 1`, `2-BM-B` when `S02BM-PSS:StaB:SecureM == 1`. CORA reads these read-only: it never drives, holds, or releases the permit or the beam, reading the PVs does not put CORA in the safety chain, and the PSS retains sole interlock authority.

`start_run` and `start_procedure` run an Enclosure pre-flight gate that derives the hutches in scope from the bound Assets and requires each to be Permitted. The chain walk, the error classes, and the HTTP codes are on the [module page](../../architecture/modules/enclosure/index.md#cross-module-boundaries). Because each 2-BM Device names exactly one hutch, an A-only Run gates on `2-BM-A` alone while a cross-hutch Run spanning both needs both Permitted. The `test_2bm_two_hutch_enclosure_gate` and `test_2bm_enclosure_chain_walk` scenarios exercise both shapes; the gate fires the moment the two hutch Enclosures register.

## Beam-availability PVs

Separate from the per-hutch permit, CORA reads upstream beam-availability signals. These are a beam-availability concern (modeled by the `BeamAvailabilityLookup` port, used by [Recipes](recipes.md) and [Procedures](procedures.md)), not the Enclosure permit. The names below were CORA-proposed against the post-migration 2-BM staff screens and await a formal sign-off by the APS PSS gateway owner; treat the strings as unconfirmed.

| Signal | PV | Read |
| --- | --- | --- |
| FES permit ("beam ready") | `S02BM-PSS:FES:FEEPSPermitM` | `1` = permitted |
| FES (front-end shutter) state | `S02BM-PSS:FES:BeamBlockingM` | `1` = blocked / CLOSED, `0` = open (inverted) |
| SBS (P6-50 station shutter) state | `S02BM-PSS:SBS:BeamBlockingM` | `1` = blocked / CLOSED, `0` = open (inverted) |
| Upstream permit (composite) | `SR-ACIS:2BM:FesPermitM` | `1` = FES-open permitted |

Of these, only `SR-ACIS:2BM:FesPermitM` is wired today (through the `BeamAvailabilityLookup` port); it folds storage-ring health, injection state, the APS-wide permits, and the BLEPS fault chain into one boolean and is the recommended single read for an "upstream OK" pre-flight check. The gateway host (`s2pvgate.xray.aps.anl.gov:5064`) and the exact FES / SBS shutter PV leaf names are unconfirmed and need staff confirmation before the observer adapter binds them.
