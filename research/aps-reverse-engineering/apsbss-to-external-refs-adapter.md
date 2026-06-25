# apsbss field reference for the locked BSS-subscriber design

This is not a new design. CORA already has a gate-reviewed, locked design for ingesting APS
scheduling and ESAF data: see the memory notes `project-aps-scheduling-integration-research`
(the fit map and adapter tiers) and `project-aps-roster-identity-design` (the three one-way
doors). This file adds one thing those notes reference but do not enumerate: the concrete
field-level shapes of the apsbss data model, read from source, so the ESAF leg of that
adapter has an exact contract. Read it as input to the locked design, not as a competing one.

## How this fits the locked design (read first)

- The locked inbound adapter (the "BSS subscriber") is read-only. CORA does not mirror the
  APS scheduling system; the upstream is data to learn from. Proposal, cycle, BTR, and visit
  are a provenance stamp on `external_refs`, not a Run-start gate.
- The locked PRIMARY scheduling source is the beam-api Schedule API
  (`https://beam-api.aps.anl.gov/beamline-scheduling/sched-api/`), whose graph is
  `Run` (cycle) to `Schedule` to `Activity` (awarded window) to `Beamtime` to `Proposal`
  (gupId) to `Experimenters[]`. apsbss is the ESAF and experiment-provisioning leg, read
  through the APS Data Management database. Proposal and experimenter facts exist in both
  surfaces; the field tables below are the apsbss view.
- Of the twelve concept categories the upstream decomposes into, seven are already modeled
  (stamp on `external_refs` / `Visit` / `Clearance` / `Supply` / data `Distribution`), four
  are adapter work (roster identity, beamline and station identity, outbound provisioning,
  notification), and one is rejected (the four schedule-mutation write endpoints; CORA must
  never write the APS schedule). Zero new aggregates are needed for the pilot.

## Sources

Upstream: `BCDA-APS/apsbss` at `main` (archived 2026-03, so the schema is frozen). Field
shapes are in `apsbss/core.py`; the two backends are `apsbss/bss_dm.py` (legacy DM web
service, `DM_APS_DB_WEB_SERVICE_URL`, default `https://xraydtn01.xray.aps.anl.gov:11336`) and
`apsbss/bss_is.py` (APS-U Information Services, REST plus JWT, the forward live source).

CORA targets, verified against shipped code (the architecture docs have drifted; trust the
code):

- `Visit.external_refs: frozenset[Identifier]`, `Identifier(scheme, value)` from
  `cora.shared.identifier`. `Visit` carries `planned_start_at`, `planned_end_at`,
  `type: VisitType`, `policy_id`, `surface_id` (`docs/architecture/modules/trust/index.md`).
- The Clearance external arm is `ExternalRefBinding(ref=Identifier(scheme, value))`, defined
  at `apps/api/src/cora/safety/aggregates/clearance/state.py:518`. The architecture doc calls
  it `ExternalBinding(scheme, id)`; that is doc drift. The shipped serialized form is
  `{"kind": "External", "scheme": "proposal", "value": "GUP-12345"}`. The canonical 2-BM
  pattern is already a shipped scenario: `tests/integration/scenarios/test_2bm_proposal_clearance.py`.
- `Clearance.template_id` references a `ClearanceTemplate` addressed by `(facility_code, code)`;
  ESAF is one of the ten auto-seeded form-types. `Clearance.external_id` carries the
  facility-minted id (`ESAF-12345`). `Clearance` has `valid_from`, `valid_until`,
  `review_steps`, and an 8-state `status`.

## apsbss field shapes (the contribution)

Property name, then the raw server key in parentheses.

### ProposalBase (the beamtime request, GUP)

| apsbss property (raw key) | feeds | scheme or field |
| --- | --- | --- |
| `proposal_id` (`id`) | `Visit.external_refs` and a Clearance `ExternalRefBinding` | `Identifier("proposal", "GUP-<id>")` |
| `run` (the cycle name passed in, for example `2024-1`) | `Visit.external_refs` | `Identifier("cycle", "<name>")` |
| `startDate` (`startTime`) | `Visit.planned_start_at` | datetime |
| `endDate` (`endTime`) | `Visit.planned_end_at` | datetime |
| `submittedDate` (`submittedDate`) | provenance only | not modeled |
| `title` (`title`) | `Clearance.title` context | |
| `proprietary` (`proprietaryFlag`, Y/N) | embargo hint, no consumer | descriptive only |
| `mail_in` (`mailInFlag`, Y/N) | presence-expectation hint | descriptive only |
| `users` / `emails` / `badges` (from `experimenters`) | roster, see roster note | not Visit fields |
| `_pi` (`piFlag` per user) | the LEAD participant | see roster note |
| `current` (computed) | adapter-side scheduling logic | not ingested |

### Esaf (the safety form)

| apsbss property (raw key) | feeds | field |
| --- | --- | --- |
| `esaf_id` (`esafId`) | `Clearance.external_id` | `"ESAF-<esaf_id>"` |
| (ESAF form-type) | `Clearance.template_id` | `ClearanceTemplate(facility_code="aps", code="ESAF")` |
| `status` (`esafStatus`, single string) | `Clearance.status` by explicit map | not verbatim, see pitfalls |
| `startDate` (`experimentStartDate`) | `Clearance.valid_from` | datetime |
| `endDate` (`experimentEndDate`) | `Clearance.valid_until` | datetime |
| `title` (`esafTitle`) | `Clearance.title` | |
| `description` (`description`) | payload or notes | no structured hazards upstream |
| `sector` (`sector`) | facility context | owning Facility is `aps` |
| `users` / `badges` (from `experimentUsers`) | roster | not `review_steps` |

The proposal id binds the ESAF clearance: `bindings += ExternalRefBinding(ref=Identifier("proposal", "GUP-<id>"))`.

### User (an experimenter, keyed by ANL badge)

| apsbss property (raw key) | feeds |
| --- | --- |
| `badge` (`badge`) | the Actor correlation key, see roster note |
| `is_pi` (`piFlag`, y/n) | the at-most-one LEAD participant |
| `email` (`email`), `institution` (`institution`), `institution_id` (`instId`) | Actor profile, PII vault |
| `fullName`, `firstName`, `lastName` | Actor display |

### Run (an APS cycle, not a CORA Run)

`name` (`name` or `runName`, for example `2024-1`), `run_id` (`runId`), `startDate`
(`startTime`), `endDate` (`endTime`). Maps to scheme `cycle`. See the first pitfall.

### Query model

`ScheduleInterfaceBase.proposals(beamline, run)` returns proposals keyed by id;
`getProposal(proposal_id, beamline, run)` fetches one; `runs` lists cycle names;
`current_run` resolves the active one. The beamline id is the APS scheduling id, for example
`2-BM-A,B`, `7-BM-B`, `32-ID-B,C` (station letters included). `gupId == 0` is the
commissioning sentinel and maps to a `VisitType` value, retiring the sentinel.

## Pitfalls (aligned to the locked design)

1. apsbss "Run" is an APS cycle (`2024-1`), not a CORA Run (a measurement that leaves a
   Dataset of record). Map it to scheme `cycle`, never to the Run aggregate.
2. `esafStatus` is a single string; the Clearance is an 8-state FSM with a `ReviewStep` chain.
   Translate through an explicit status map and leave `review_steps` empty on ingest. The
   review chain is owned by CORA's review-board flow. ESAF to Clearance stays manual for the
   pilot (safety watch #12); the auto-sync mapping above is the eventual shape.
3. Roster is locked elsewhere, do not re-derive it here. A badge is a forgettable correlation
   key (`Identifier(scheme="aps-badge", value=<badge>)`) kept in a mutable bindings table
   physically separate from auth, never folded into events, never a `SubjectMapper` key.
   Per-beamtime participation is a `Participant` VO with `Participation` in
   `{LEAD, CO_EXPERIMENTER, OTHER}`; PI is the at-most-one LEAD and never an authz input.
   Presence (`Visit.presence_entries`) is observed at check-in, not populated from a proposal.
   See `project-aps-roster-identity-design`.
4. A rescheduled window is an amend on the same `visit_id` (`RescheduleVisit` to
   `VisitRescheduled`, status unchanged), not void plus re-register; the ingest derives
   `visit_id = uuid5(scheme:external_id)`, so void plus re-register self-collides, and `void`
   means entered-in-error. The poller is a diff-and-amend engine.
5. The shipped `ClearanceLookupResult` does not expose `external_id`, so a failed gate reports
   a count only and cannot name "ESAF-12345"; a gating ESAF must be emitted with a typed
   `RunBinding`, not a proposal-only `ExternalRefBinding`, if ESAF gating is in pilot scope.
6. Pin one `external_refs` scheme vocabulary (`proposal`, `btr`, `cycle`, `visit`) as a
   shared constant in `cora/shared` before any adapter writes refs. Real drift exists today:
   Run carries `lab_visit` and `session`, Campaign and Visit carry `visit` and `cycle`, and
   no constant module exists (`cora/shared/` has `identifier.py` but no `scheme.py`).
7. apsbss is archived. Pin the production adapter to the APS-U Information Services backend
   (`bss_is.py`); the DM backend (`bss_dm.py`) is for older runs. The locked design also flags
   a route-form question (path versus query params) to verify against the live server.

## Open questions (already tracked, do not re-file)

The locked design already tracks these in `docs/deployments/2-bm/questions.md` and the
roster memo: SCHED-1 (reschedule-after-arrival source widening), SCHED-2 (staff-contact as
roster member versus allocation-side local contact), SCHED-3 (badge erasability and reuse
semantics), plus the `esafStatus` closed value set and the exact `gupId == 0` representation
2-BM uses. The genuinely new, field-level item this extraction surfaces:

- Does the APS-U IS backend expose a beamtime-request id distinct from the GUP, so scheme
  `btr` carries its own value rather than aliasing `proposal`? The apsbss `core.py` view does
  not separate them; only the beam-api `Beamtime`/`BeamtimeRequests` graph might.
