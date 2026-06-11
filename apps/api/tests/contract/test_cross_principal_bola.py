"""Cross-principal BOLA contract test.

OWASP API Top 10 #1 is Broken Object-Level Authorization (BOLA):
the API authenticates the caller but doesn't gate the operation
on the *resource* the caller is trying to touch. The classic
failure mode is "principal P1 creates resource R; principal P2
issues GET /resource/<R> and reads it".

CORA's day-1 defense is the Trust BC's `permitted_principal_ids` x
`permitted_commands` policy: when `TrustAuthorize` is wired with
a real policy, every command is gated by `(principal_id,
command_name)`. This test pins the load-bearing chain end-to-end
across multiple BCs to prove the gating actually fires for cross-
principal reads, not just create-style writes (BOLA's most common
exposure surface is reads).

This test does NOT exercise per-resource ownership (ReBAC); see
`memory/project_authz_future.md` for that planned phase. What it
DOES prove today: a deployment that turns on TrustAuthorize and
configures `permitted_principal_ids` correctly cannot leak a P1
aggregate to a P2 read just because both are authenticated, even
when both have valid X-Principal-Id headers.

Parametrized across the BOLA-exposed BCs — each runs the same shape:
P1 creates, P2 reads, expect 403. Adding a new BC to the parametrization
is a one-line change.

## Coverage policy

The parametrization covers `(principal_id x command_name)` gating for
aggregates with per-instance ownership semantics: Access (Actor),
Subject, Equipment (Asset), Safety (Clearance), Campaign, Data
(Dataset), Calibration, Caution, Decision, Operation (Procedure),
Agent, Recipe (Method, Practice, Plan), Run.

Recipe-ladder (Method/Practice/Plan) and Run scenarios share a
`_seed_recipe_chain` helper that walks the Capability → Method →
Practice → Asset → Plan dependency chain via the HTTP API as P1.
Capability is seeded by the helper (not BOLA-scenario'd itself) so
that Plan's FK validation (PracticeNotFoundError / MethodNotFoundError
/ AssetNotFoundError) passes. Agent uses POST /agents which atomically
writes ActorRegistered + AgentDefined via `EventStore.append_streams`
(the cross-BC pattern described in [project_agent_bc_design] memo).

Explicitly NOT covered: Family + Capability (Equipment + Recipe shared
catalogs, governance-tier not user-owned), Supply (continuous facility
resource, inherently shared), Surface (Trust BC platform config). These
inherit the same command-level gating but the per-resource BOLA framing
doesn't fit. Capability IS permitted in the fixture's command set
because the recipe-chain helper needs it as a prereq for Method.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.asset import AssetTier
from cora.infrastructure.event_envelope import to_new_event
from cora.safety.aggregates.clearance_template import clearance_template_stream_id
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)


def _seed_policy(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal: UUID,
    permitted_commands: frozenset[str],
) -> None:
    """Seed a single PolicyDefined event into the running app's
    in-memory store. Same shape as `test_principal_header.py`'s
    helper; duplicated here to keep the BOLA test self-contained
    rather than coupling two files via a shared fixture file."""
    event = PolicyDefined(
        policy_id=policy_id,
        name="Bola-test-policy",
        conduit_id=UUID(int=0),
        permitted_principal_ids=(permitted_principal,),
        permitted_commands=tuple(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    asyncio.run(
        app.state.deps.event_store.append("Policy", policy_id, 0, [new_event]),
    )


@pytest.fixture
def bola_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with `TrustAuthorize` wired against a policy
    that permits ONE principal (P1) to issue every command this test
    exercises. P2 is any other UUID; the policy denies it implicitly.

    Yields (client, p1, p2).
    """
    policy_id = UUID("01900000-0000-7000-8000-00000000bb01")
    p1 = UUID("01900000-0000-7000-8000-00000000bb11")
    p2 = UUID("01900000-0000-7000-8000-00000000bb12")

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()  # start lifespan; app.state.deps populated

    _seed_policy(
        cast("FastAPI", client.app),
        policy_id=policy_id,
        permitted_principal=p1,
        permitted_commands=frozenset(
            {
                # Create-side
                "RegisterActor",
                "RegisterSubject",
                "RegisterAsset",
                "RegisterClearance",
                "RegisterCampaign",
                "RegisterDataset",
                "DefineCalibration",
                "RegisterCaution",
                "RegisterDecision",
                "RegisterProcedure",
                "DefineAgent",
                "DefineCapability",  # prereq for the recipe-chain helper
                "DefineMethod",
                "DefinePractice",
                "DefinePlan",
                "StartRun",
                # Read-side (the gates this test exercises)
                "GetActor",
                "GetSubject",
                "GetAsset",
                "GetClearance",
                "GetCampaign",
                "GetDataset",
                "GetCalibration",
                "GetCaution",
                "GetDecision",
                "GetProcedure",
                "GetAgent",
                "GetMethod",
                "GetPractice",
                "GetPlan",
                "GetRun",
                # List-side (8e-1c, 8e-2a, 8e-3a, 8e-3b, 8e-4, 8e-5, 8e-6, 8e-7, 8e-8)
                "ListActors",
                "ListSubjects",
                "ListAssets",
                "ListFamilies",
                "ListMethods",
                "ListPractices",
                "ListPlans",
                "ListRuns",
                "ListDatasets",
                "ListDecisions",
                "ListZones",
                "ListConduits",
                "ListPolicies",
            }
        ),
    )
    try:
        yield client, p1, p2
    finally:
        client.__exit__(None, None, None)


def _create_actor_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/actors",
        json={"name": "P1's actor"},
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["actor_id"])


def _create_subject_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/subjects",
        json={"name": "P1's subject"},
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["subject_id"])


def _create_asset_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/assets",
        json={
            "name": "P1's asset",
            "tier": AssetTier.UNIT.value,
            "parent_id": None,
            "facility_code": "cora",
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


def _create_clearance_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Safety BC Clearance via POST /clearances; used by the BOLA
    parametrization to verify GET /clearances/{id} respects per-command gating.

    Clearances carry regulatory IDs and hazard descriptions, so cross-principal
    leaks here are higher-stakes than Actor/Subject/Asset reads.
    """
    from uuid import uuid4

    template_id = clearance_template_stream_id("cora", "ESAF")
    response = client.post(
        "/clearances",
        json={
            "template_id": str(template_id),
            "facility_code": "cora",
            "title": "P1's clearance",
            "bindings": [{"kind": "Run", "id": str(uuid4())}],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["clearance_id"])


def _create_campaign_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Campaign via POST /campaigns. `lead_actor_id` is a bare
    UUID (no FK existence check at register time per the eventual-
    consistency stance), so a uuid4() works without seeding an Actor."""
    response = client.post(
        "/campaigns",
        json={
            "name": "P1's campaign",
            "intent": "Series",
            "lead_actor_id": str(uuid4()),
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["campaign_id"])


def _create_dataset_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Dataset via POST /datasets. All cross-aggregate FKs
    (producing_run_id, subject_id, derived_from, used_calibration_ids) are
    optional and omitted here; checksum is a 64-char zero string
    (well-formed sha256 hex)."""
    response = client.post(
        "/datasets",
        json={
            "name": "P1's dataset",
            "uri": "file:///tmp/p1-dataset",
            "checksum": {"algorithm": "sha256", "value": "0" * 64},
            "byte_size": 1,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["dataset_id"])


def _create_calibration_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Calibration via POST /calibrations. `target_id`
    is a bare UUID (no FK existence check), and `operating_point` validates
    STRICT against the `rotation_center` quantity's JSON Schema (energy +
    optics_config required, no additional properties)."""
    response = client.post(
        "/calibrations",
        json={
            "target_id": str(uuid4()),
            "quantity": "rotation_center",
            "operating_point": {"energy": 25.0, "optics_config": "5x"},
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["calibration_id"])


def _create_caution_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Caution via POST /cautions. `target` is the polymorphic
    discriminated DTO (kind + id); we attach to a synthetic Asset id
    since the target's existence is NOT verified at register time."""
    response = client.post(
        "/cautions",
        json={
            "target": {"kind": "Asset", "id": str(uuid4())},
            "category": "Wear",
            "severity": "Notice",
            "text": "P1's caution",
            "workaround": "Operator-asserted workaround",
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["caution_id"])


def _create_decision_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Decision via POST /decisions. Decision REQUIRES the
    decided_by to exist (DeciderActorNotFoundError otherwise), so the
    helper first creates an Actor as P1 and then references it. P1
    therefore needs both `RegisterActor` and `RegisterDecision` in
    the permitted-commands set; both are seeded in the fixture."""
    actor_id = _create_actor_as(client, principal)
    response = client.post(
        "/decisions",
        json={
            "decided_by": str(actor_id),
            "context": "RunAbort",
            "choice": "abort: beam down",
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["decision_id"])


def _create_procedure_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Procedure via POST /procedures. `target_asset_ids` is
    optional (empty list valid for facility-envelope procedures);
    `parent_run_id` and `capability_id` are also optional and omitted."""
    response = client.post(
        "/procedures",
        json={
            "name": "P1's procedure",
            "kind": "bakeout",
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["procedure_id"])


def _create_agent_as(client: TestClient, principal: UUID) -> UUID:
    """Create an Agent via POST /agents. Agent.id is shared with Actor.id
    for the same agent — the route handler atomically writes both
    `ActorRegistered` and `AgentDefined` via `EventStore.append_streams`
    (see [project_agent_bc_design] memo). The fixture permits DefineAgent
    only; RegisterActor is not needed here because the atomic write
    bypasses the standalone Access slice."""
    response = client.post(
        "/agents",
        json={
            "kind": "RunDebriefer",
            "name": "P1's agent",
            "version": "v1",
            "model_ref": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "snapshot_pin": None,
            },
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["agent_id"])


def _seed_recipe_chain(client: TestClient, principal: UUID) -> UUID:
    """Walk the Capability → Method → Practice → Asset → Plan dependency
    chain via the HTTP API as P1 and return the resulting plan_id.

    All FK existence checks pass because each link is created as a real
    aggregate. The Capability uses empty `required_affordances` so
    Plan's affordance-cover validation is trivially satisfied even when
    the seeded Asset has no families.

    Used by `_create_plan_as` (returns plan_id directly) and
    `_create_run_as` (starts a Run from the seeded plan_id)."""
    capability_response = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.test_bola",
            "name": "BOLA test capability",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert capability_response.status_code == 201, capability_response.text
    capability_id = UUID(capability_response.json()["capability_id"])

    method_response = client.post(
        "/methods",
        json={
            "name": "BOLA test method",
            "capability_id": str(capability_id),
            "needed_family_ids": [],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert method_response.status_code == 201, method_response.text
    method_id = UUID(method_response.json()["method_id"])

    practice_response = client.post(
        "/practices",
        json={
            "name": "BOLA test practice",
            "method_id": str(method_id),
            "site_id": str(uuid4()),
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert practice_response.status_code == 201, practice_response.text
    practice_id = UUID(practice_response.json()["practice_id"])

    asset_id = _create_asset_as(client, principal)

    plan_response = client.post(
        "/plans",
        json={
            "name": "BOLA test plan",
            "practice_id": str(practice_id),
            "asset_ids": [str(asset_id)],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert plan_response.status_code == 201, plan_response.text
    return UUID(plan_response.json()["plan_id"])


def _create_method_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Method via POST /methods. Method validates Capability
    existence (CapabilityNotFoundError otherwise), so the helper seeds
    a Capability first as P1."""
    capability_response = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.test_bola_method",
            "name": "BOLA test capability",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert capability_response.status_code == 201, capability_response.text
    capability_id = UUID(capability_response.json()["capability_id"])

    response = client.post(
        "/methods",
        json={
            "name": "P1's method",
            "capability_id": str(capability_id),
            "needed_family_ids": [],
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


def _create_practice_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Practice via POST /practices. Practice does NOT FK-check
    method_id at register time (validation lives at Plan/Run binding),
    so a bare uuid4() for method_id is sufficient for the BOLA test."""
    response = client.post(
        "/practices",
        json={
            "name": "P1's practice",
            "method_id": str(uuid4()),
            "site_id": str(uuid4()),
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["practice_id"])


def _create_plan_as(client: TestClient, principal: UUID) -> UUID:
    """Create a Plan via POST /plans. Plan FK-checks practice + method +
    each asset; the recipe-chain helper seeds them all as P1."""
    return _seed_recipe_chain(client, principal)


def _create_run_as(client: TestClient, principal: UUID) -> UUID:
    """Start a Run via POST /runs. Run FK-checks plan + practice + method
    + assets; the recipe-chain helper seeds them all as P1. `subject_id`
    is None (allowed; Run without bound Subject is valid for ceremony
    Procedure-style executions)."""
    plan_id = _seed_recipe_chain(client, principal)
    response = client.post(
        "/runs",
        json={"name": "P1's run", "plan_id": str(plan_id), "subject_id": None},
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["run_id"])


CreateFn = Callable[[TestClient, UUID], UUID]
"""Shape of a BOLA-scenario factory: takes the test client and the
principal to create-as, returns the new aggregate's id."""


_BOLA_SCENARIOS = [
    pytest.param(_create_actor_as, "/actors", id="access:actor"),
    pytest.param(_create_subject_as, "/subjects", id="subject:subject"),
    pytest.param(_create_asset_as, "/assets", id="equipment:asset"),
    pytest.param(_create_clearance_as, "/clearances", id="safety:clearance"),
    pytest.param(_create_campaign_as, "/campaigns", id="campaign:campaign"),
    pytest.param(_create_dataset_as, "/datasets", id="data:dataset"),
    pytest.param(_create_calibration_as, "/calibrations", id="calibration:calibration"),
    pytest.param(_create_caution_as, "/cautions", id="caution:caution"),
    pytest.param(_create_decision_as, "/decisions", id="decision:decision"),
    pytest.param(_create_procedure_as, "/procedures", id="operation:procedure"),
    pytest.param(_create_agent_as, "/agents", id="agent:agent"),
    pytest.param(_create_method_as, "/methods", id="recipe:method"),
    pytest.param(_create_practice_as, "/practices", id="recipe:practice"),
    pytest.param(_create_plan_as, "/plans", id="recipe:plan"),
    pytest.param(_create_run_as, "/runs", id="run:run"),
]


@pytest.mark.contract
@pytest.mark.parametrize(("create_fn", "read_path_prefix"), _BOLA_SCENARIOS)
def test_p2_cannot_read_p1s_aggregate_when_policy_gates_principal(
    bola_app: tuple[TestClient, UUID, UUID],
    create_fn: CreateFn,
    read_path_prefix: str,
) -> None:
    """P1 (permitted) creates an aggregate; P2 (not permitted) tries
    to read it. The policy denies P2 -> 403 from the read endpoint.
    Pin: cross-principal reads are gated even when both principals
    are authenticated."""
    client, p1, p2 = bola_app

    aggregate_id = create_fn(client, p1)

    # P2 attempts to read the resource P1 just created.
    response = client.get(
        f"{read_path_prefix}/{aggregate_id}",
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, (
        f"BOLA gap: P2 was able to read P1's aggregate at "
        f"{read_path_prefix}/{aggregate_id} (status={response.status_code}, "
        f"body={response.text}). The policy permits only P1; this "
        f"read should have been denied."
    )


@pytest.mark.contract
@pytest.mark.parametrize(("create_fn", "read_path_prefix"), _BOLA_SCENARIOS)
def test_p1_can_still_read_their_own_aggregate(
    bola_app: tuple[TestClient, UUID, UUID],
    create_fn: CreateFn,
    read_path_prefix: str,
) -> None:
    """Inverse sanity: the gate is per-principal, not blanket-deny.
    P1 (permitted) reads their own resource and gets 200."""
    client, p1, _ = bola_app

    aggregate_id = create_fn(client, p1)

    response = client.get(
        f"{read_path_prefix}/{aggregate_id}",
        headers={"X-Principal-Id": str(p1)},
    )
    assert response.status_code == 200, (
        f"P1 was unexpectedly denied observation their own aggregate "
        f"({response.status_code}, {response.text}). Policy/permitted-"
        f"commands setup is wrong."
    )


# ---------- List endpoint BOLA (weaker, command-level only today) ----------


@pytest.mark.contract
def test_p2_cannot_call_list_actors_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    """List-endpoint BOLA defense at TODAY's granularity: the
    `ListActors` command is gated by Trust policy. P2 isn't in
    `permitted_principal_ids` so the command itself is denied with 403
    before the projection table is queried.

    This is the WEAKER assertion than per-row BOLA (P2 sees zero of
    P1's items in the response body) — see `project_deferred.md`
    entry "BOLA per-row scoping for list endpoints (ReBAC dependency)".
    Today the projection has no per-principal scoping, so once
    ListActors IS permitted to a principal, that principal sees
    every actor regardless of who created them. The honest test
    pins the defense that DOES exist.
    """
    client, _, p2 = bola_app

    response = client.get("/actors", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403, (
        f"P2 should be denied ListActors at the command level "
        f"(status={response.status_code}, body={response.text})."
    )


@pytest.mark.contract
def test_p1_can_call_list_actors_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Inverse: the gate is per-principal, not blanket-deny."""
    client, p1, _ = bola_app

    response = client.get("/actors", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200, (
        f"P1 should be permitted ListActors (status={response.status_code}, body={response.text})."
    )


@pytest.mark.contract
def test_p2_cannot_call_list_subjects_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Same shape as ListActors test: P2 not permitted -> 403 at the
    command-name gate. Per-row scoping deferred until ReBAC."""
    client, _, p2 = bola_app
    response = client.get("/subjects", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_subjects_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/subjects", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_assets_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/assets", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_assets_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/assets", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_families_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/families", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_families_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/families", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize("path", ["/methods", "/practices", "/plans"])
def test_p2_cannot_call_recipe_list_endpoints_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
    path: str,
) -> None:
    """Recipe BC's three list endpoints (8e-4) all sit behind the
    same command-name gate. P2 isn't permitted, so each is denied
    at the route boundary before the projection table is queried."""
    client, _, p2 = bola_app
    response = client.get(path, headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.parametrize("path", ["/methods", "/practices", "/plans"])
def test_p1_can_call_recipe_list_endpoints_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
    path: str,
) -> None:
    client, p1, _ = bola_app
    response = client.get(path, headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_runs_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/runs", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_runs_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/runs", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_datasets_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/datasets", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_datasets_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/datasets", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_decisions_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/decisions", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_decisions_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/decisions", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_zones_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/zones", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_zones_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/zones", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_conduits_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/conduits", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_conduits_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/conduits", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200


@pytest.mark.contract
def test_p2_cannot_call_list_policies_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, _, p2 = bola_app
    response = client.get("/policies", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403


@pytest.mark.contract
def test_p1_can_call_list_policies_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, _ = bola_app
    response = client.get("/policies", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200
