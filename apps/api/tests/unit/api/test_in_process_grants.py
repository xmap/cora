"""Unit tests for the in-process back-door grant table.

`IN_PROCESS_GRANTS` is inert data: nothing in the running app reads it
(only the architecture fitness test and `tools/gen_policy_grants.py`
do), so most of these are a light sanity check on the table's own shape
rather than a behavioral test of anything it drives. The exception is
`test_no_agent_is_granted_resume_procedure`, which guards a safety
property the table can silently break.
"""

from uuid import UUID

import pytest

from cora.api.in_process_grants import IN_PROCESS_GRANTS


@pytest.mark.unit
def test_every_principal_id_is_a_uuid() -> None:
    assert all(isinstance(principal_id, UUID) for principal_id in IN_PROCESS_GRANTS)


@pytest.mark.unit
def test_every_grant_is_a_non_empty_frozenset_of_str() -> None:
    for principal_id, command_names in IN_PROCESS_GRANTS.items():
        assert isinstance(command_names, frozenset), principal_id
        assert command_names, f"{principal_id} has no granted commands"
        assert all(isinstance(name, str) and name for name in command_names), principal_id


@pytest.mark.unit
def test_no_two_principal_ids_collide() -> None:
    """`MappingProxyType` already forbids a literal duplicate key; this
    guards the semantic case, two *different* constants that happen to
    resolve to the same UUID."""
    principal_ids = list(IN_PROCESS_GRANTS.keys())
    assert len(principal_ids) == len(set(principal_ids))


@pytest.mark.unit
def test_no_agent_is_granted_resume_procedure() -> None:
    """A machine resumer would inherit an operator's reach without asking.

    `ResumeProcedure.cause` defaults to `operator`, and an operator's resume
    clears every ATTENTION claim on a Procedure: the whole point, since nothing
    else discharges a fault-parked conduct. Nothing checks the caller's
    species, so `operator` means only "the caller named no other concern". An
    agent added here would default into it and gain the authority to restart a
    conduct a Conductor parked, or to clear a person's deliberate pause, with
    no one having decided that.

    That the widening is safe today rests on this table and not on the claim
    algebra, which is why the table is where the guard belongs.

    If an agent genuinely needs to resume, the fix is not to delete this test.
    Give the concern its own cause in `HOLD_CAUSES`, decide whether it belongs
    in `ATTENTION_HOLD_CAUSES`, and set it explicitly at the call site the way
    `_run_supervisor` sets `HOLD_CAUSE_SUPERVISOR` on a Run. Then update this
    test to require that agent sets a cause rather than to forbid the grant.
    """
    holders = [
        principal_id
        for principal_id, command_names in IN_PROCESS_GRANTS.items()
        if "ResumeProcedure" in command_names
    ]
    assert holders == []


@pytest.mark.unit
def test_table_is_read_only() -> None:
    """`MappingProxyType` refuses mutation; a plain dict here would let a
    future import quietly rewrite the table it is meant to be inert."""
    (principal_id,) = list(IN_PROCESS_GRANTS.keys())[:1]
    with pytest.raises(TypeError):
        IN_PROCESS_GRANTS[principal_id] = frozenset()  # type: ignore[index]
