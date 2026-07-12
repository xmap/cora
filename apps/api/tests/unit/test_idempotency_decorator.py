# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportPrivateUsage=false

"""Unit tests for `cora.infrastructure.idempotency`.

Covers:
  - hash_command: stable, frozenset normalization, dataclass-only.
  - Decorator happy path: no-key skip, cache hit (success), cache hit (error),
    claim, finalize, key-length cap, principal namespacing, causation forward.
  - 4xx error caching, 5xx pass-through (uncached), stale-lock recovery,
    claim race -> IdempotencyClaimLostError.
  - classify_error_status: convention-based mapping per name pattern.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from cora.infrastructure.idempotency import (
    classify_error_status,
    hash_command,
    with_idempotency,
)
from cora.infrastructure.ports import (
    CachedHandlerError,
    CachedSuccess,
    Claimed,
    IdempotencyClaimLostError,
    IdempotencyConflictError,
    LockedRecent,
)

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NIL_SURFACE_ID = UUID(int=0)
_LOCK_STALE = 60


@dataclass(frozen=True)
class _DummyCommand:
    name: str


_FIXED_RESULT = UUID("01900000-0000-7000-8000-000000001111")


def _make_handler(
    track_calls: list[int],
    *,
    capture_causation: list[UUID | None] | None = None,
    raise_exc: BaseException | None = None,
) -> object:
    async def handler(
        command: _DummyCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SURFACE_ID,
    ) -> UUID:
        _ = (command, principal_id, correlation_id, surface_id)
        track_calls.append(1)
        if capture_causation is not None:
            capture_causation.append(causation_id)
        if raise_exc is not None:
            raise raise_exc
        return _FIXED_RESULT

    return handler


def _wrap(store: InMemoryIdempotencyStore, handler: object) -> object:
    return with_idempotency(
        handler,  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
        lock_stale_seconds=_LOCK_STALE,
    )


# ---------- hash_command ----------


@pytest.mark.unit
def test_hash_command_is_stable_across_calls() -> None:
    cmd = _DummyCommand(name="Doga")
    assert hash_command(cmd) == hash_command(cmd)


@pytest.mark.unit
def test_hash_command_differs_for_different_field_values() -> None:
    assert hash_command(_DummyCommand(name="A")) != hash_command(_DummyCommand(name="B"))


@pytest.mark.unit
def test_hash_command_rejects_non_dataclass() -> None:
    with pytest.raises(TypeError, match="dataclass instance"):
        hash_command({"name": "Doga"})  # type: ignore[arg-type]


@pytest.mark.unit
def test_hash_command_normalizes_frozenset_fields_deterministically() -> None:
    """Pin cross-process determinism for set-typed command fields."""
    import hashlib
    import json

    @dataclass(frozen=True)
    class _CmdWithSets:
        cmds: frozenset[str]
        principals: frozenset[UUID]

    p1 = UUID("01900000-0000-7000-8000-000000000a01")
    p2 = UUID("01900000-0000-7000-8000-000000000a02")
    cmd = _CmdWithSets(cmds=frozenset({"Z", "A", "M"}), principals=frozenset({p2, p1}))

    expected_canonical = json.dumps(
        {
            "cmds": ["A", "M", "Z"],
            "principals": [str(p1), str(p2)],
        },
        sort_keys=True,
        default=str,
    )
    expected_hash = hashlib.sha256(expected_canonical.encode()).hexdigest()
    assert hash_command(cmd) == expected_hash


@pytest.mark.unit
def test_hash_command_set_normalization_is_order_independent() -> None:
    @dataclass(frozen=True)
    class _CmdWithSets:
        cmds: frozenset[str]

    a = _CmdWithSets(cmds=frozenset(["A", "B", "C"]))
    b = _CmdWithSets(cmds=frozenset(["C", "A", "B"]))
    assert hash_command(a) == hash_command(b)


# ---------- decorator: no-key fast path ----------


@pytest.mark.unit
async def test_no_key_skips_cache_entirely() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))

    r1 = await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    r2 = await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert r1 == r2 == _FIXED_RESULT
    assert len(calls) == 2


# ---------- decorator: success caching ----------


@pytest.mark.unit
async def test_first_call_with_key_executes_and_finalizes_success() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))

    result = await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    assert result == _FIXED_RESULT
    assert len(calls) == 1
    outcome = await store.claim(
        _PRINCIPAL_ID,
        "key-1",
        _NIL_SURFACE_ID,
        hash_command(_DummyCommand(name="A")),
        "DummyCommand",
        lock_stale_seconds=_LOCK_STALE,
    )
    assert isinstance(outcome, CachedSuccess)
    assert outcome.result == str(_FIXED_RESULT)


@pytest.mark.unit
async def test_retry_with_same_key_and_body_returns_cached_without_reexec() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))
    cmd = _DummyCommand(name="A")

    r1 = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )
    r2 = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    assert r1 == r2 == _FIXED_RESULT
    assert len(calls) == 1


# ---------- decorator: hash conflict ----------


@pytest.mark.unit
async def test_retry_with_same_key_but_different_body_raises_conflict() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))

    await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    with pytest.raises(IdempotencyConflictError) as exc_info:
        await wrapped(  # type: ignore[operator]
            _DummyCommand(name="B"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key="key-1",
        )
    assert exc_info.value.key == "key-1"
    assert len(calls) == 1


# ---------- decorator: 4xx error caching ----------


class InvalidActorNameError(Exception):
    """Mimics a real BC's validation error class shape."""


@pytest.mark.unit
async def test_handler_4xx_error_is_cached_and_replayed() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    err = InvalidActorNameError("name must be 1-200 chars (got: '   ')")
    wrapped = _wrap(store, _make_handler(calls, raise_exc=err))

    with pytest.raises(InvalidActorNameError):
        await wrapped(  # type: ignore[operator]
            _DummyCommand(name="A"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key="bad-key",
        )
    assert len(calls) == 1

    with pytest.raises(CachedHandlerError) as exc_info:
        await wrapped(  # type: ignore[operator]
            _DummyCommand(name="A"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key="bad-key",
        )
    assert len(calls) == 1  # NOT re-executed
    assert exc_info.value.error_type.endswith("InvalidActorNameError")
    assert exc_info.value.error_msg == "name must be 1-200 chars (got: '   ')"


@pytest.mark.unit
async def test_handler_5xx_error_is_not_cached_lock_remains() -> None:
    """RuntimeError (5xx-shape) doesn't cache; row stays locked, recoverable on next retry."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    err = RuntimeError("transient db hiccup")
    wrapped = _wrap(store, _make_handler(calls, raise_exc=err))

    with pytest.raises(RuntimeError, match="transient db hiccup"):
        await wrapped(  # type: ignore[operator]
            _DummyCommand(name="A"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key="hiccup-key",
        )
    assert len(calls) == 1

    outcome = await store.claim(
        _PRINCIPAL_ID,
        "hiccup-key",
        _NIL_SURFACE_ID,
        hash_command(_DummyCommand(name="A")),
        "DummyCommand",
        lock_stale_seconds=_LOCK_STALE,
    )
    assert isinstance(outcome, LockedRecent)


# ---------- decorator: claim race ----------


@pytest.mark.unit
async def test_concurrent_claim_race_one_wins_one_loses() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def slow_handler(
        command: _DummyCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SURFACE_ID,
    ) -> UUID:
        _ = (command, principal_id, correlation_id, causation_id, surface_id)
        calls.append(1)
        started.set()
        await proceed.wait()
        return _FIXED_RESULT

    wrapped = _wrap(store, slow_handler)
    cmd = _DummyCommand(name="A")

    async def call() -> object:
        try:
            return await wrapped(  # type: ignore[operator]
                cmd,
                principal_id=_PRINCIPAL_ID,
                correlation_id=_CORRELATION_ID,
                idempotency_key="race-key",
            )
        except IdempotencyClaimLostError as exc:
            return exc

    first_task = asyncio.create_task(call())
    await started.wait()
    second_result = await call()
    proceed.set()
    first_result = await first_task

    assert first_result == _FIXED_RESULT
    assert isinstance(second_result, IdempotencyClaimLostError)
    assert len(calls) == 1


# ---------- decorator: stale-lock recovery ----------


@pytest.mark.unit
async def test_stale_lock_is_taken_over_by_subsequent_claim() -> None:
    """A row locked longer than `lock_stale_seconds` can be re-claimed
    (covers the 'worker crashed mid-handler' case)."""
    from datetime import UTC, datetime, timedelta

    from cora.infrastructure.adapters.in_memory_idempotency_store import _Row

    store = InMemoryIdempotencyStore()
    ancient = datetime.now(tz=UTC) - timedelta(hours=1)
    cmd_hash = hash_command(_DummyCommand(name="A"))
    store._records[(_PRINCIPAL_ID, "stuck", _NIL_SURFACE_ID)] = _Row(
        command_hash=cmd_hash,
        command_name="DummyCommand",
        created_at=ancient,
        locked_at=ancient,
    )

    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))

    result = await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="stuck",
    )

    assert result == _FIXED_RESULT
    assert len(calls) == 1


# ---------- decorator: surface_id namespace ----------


@pytest.mark.unit
async def test_same_key_same_body_different_surface_yields_independent_cache_slots() -> None:
    """Per IETF Idempotency-Key §5 + CORA anti-hook: surface_id is a
    server-side composite component of the cache namespace. Two
    invocations with the same (principal, key, body) but DIFFERENT
    surface_id must each run the handler and cache their own slot —
    a Surface's V2 policy must not be bypassed by a cache hit from
    a different arrival Surface."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))
    cmd = _DummyCommand(name="A")
    surf_http = UUID("00000000-0000-0000-0000-000000000020")
    surf_mcp = UUID("00000000-0000-0000-0000-000000000022")

    r_http = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        surface_id=surf_http,
        idempotency_key="shared",
    )
    r_mcp = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        surface_id=surf_mcp,
        idempotency_key="shared",
    )
    assert r_http == _FIXED_RESULT
    assert r_mcp == _FIXED_RESULT
    assert len(calls) == 2, "handler should run once per surface, not be cache-shared"


@pytest.mark.unit
async def test_same_key_same_body_same_surface_replays_cached_result() -> None:
    """Sanity: the per-surface partitioning still allows normal
    cache replay when the same surface retries with the same body."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))
    cmd = _DummyCommand(name="A")
    surf = UUID("00000000-0000-0000-0000-000000000020")

    r1 = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        surface_id=surf,
        idempotency_key="shared",
    )
    r2 = await wrapped(  # type: ignore[operator]
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        surface_id=surf,
        idempotency_key="shared",
    )
    assert r1 == _FIXED_RESULT
    assert r2 == _FIXED_RESULT
    assert len(calls) == 1, "second call on same surface should hit cache, not re-run"


# ---------- decorator: validation + plumbing ----------


@pytest.mark.unit
async def test_decorator_rejects_idempotency_key_over_255_chars() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))
    too_long = "x" * 256

    with pytest.raises(ValueError, match="exceeds maximum 255"):
        await wrapped(  # type: ignore[operator]
            _DummyCommand(name="A"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key=too_long,
        )

    assert len(calls) == 0
    outcome = await store.claim(
        _PRINCIPAL_ID,
        too_long,
        _NIL_SURFACE_ID,
        "any",
        "X",
        lock_stale_seconds=_LOCK_STALE,
    )
    assert isinstance(outcome, Claimed)


@pytest.mark.unit
async def test_decorator_forwards_causation_id_through_to_inner_handler() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    seen_causations: list[UUID | None] = []
    wrapped = _wrap(store, _make_handler(calls, capture_causation=seen_causations))
    causation = UUID("01900000-0000-7000-8000-0000000000bb")

    await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    await wrapped(  # type: ignore[operator]
        _DummyCommand(name="B"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
        idempotency_key="key-causation",
    )

    assert seen_causations == [causation, causation]


@pytest.mark.unit
async def test_keys_namespaced_by_principal() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = _wrap(store, _make_handler(calls))
    other_principal = uuid4()

    await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="shared-key",
    )
    await wrapped(  # type: ignore[operator]
        _DummyCommand(name="A"),
        principal_id=other_principal,
        correlation_id=_CORRELATION_ID,
        idempotency_key="shared-key",
    )

    assert len(calls) == 2


# ---------- classifier ----------


class InvalidFooError(Exception):
    pass


class FooNotFoundError(Exception):
    pass


class FooAlreadyExistsError(Exception):
    pass


class FooCannotBarError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class ConcurrencyError(Exception):
    pass


class _ExplicitOverrideError(Exception):
    idempotency_http_status = 418


class UnknownShapeError(Exception):
    pass


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc_cls", "expected"),
    [
        (InvalidFooError, 400),
        (FooNotFoundError, 404),
        (FooAlreadyExistsError, 409),
        (FooCannotBarError, 409),
        (UnauthorizedError, 403),
        (ConcurrencyError, 409),
        (UnknownShapeError, None),
    ],
)
def test_classifier_maps_known_patterns(exc_cls: type[Exception], expected: int | None) -> None:
    assert classify_error_status(exc_cls("msg")) == expected


@pytest.mark.unit
def test_classifier_idempotency_conflict_error_returns_422() -> None:
    from cora.infrastructure.ports import IdempotencyConflictError

    assert classify_error_status(IdempotencyConflictError("k", "h1", "h2")) == 422


@pytest.mark.unit
def test_classifier_explicit_override_attribute_wins() -> None:
    assert classify_error_status(_ExplicitOverrideError("teapot")) == 418


@pytest.mark.unit
def test_classifier_language_model_not_approved_error_returns_400() -> None:
    """The define_agent gate refusal carries the explicit 400 override:
    without it the class name matches no pattern, the error classifies
    as 5xx, and the idempotency claim strands Claimed instead of
    finalizing like every sibling validation error."""
    from cora.agent.aggregates.language_model import LanguageModelNotApprovedError

    assert classify_error_status(LanguageModelNotApprovedError("anthropic", "m", None)) == 400
