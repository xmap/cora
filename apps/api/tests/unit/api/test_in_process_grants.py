"""Unit tests for the in-process back-door grant table.

`IN_PROCESS_GRANTS` is inert data: nothing in the running app reads it
(only the architecture fitness test and `tools/gen_policy_grants.py`
do), so these tests are a light sanity check on the table's own shape
rather than a behavioral test of anything it drives.
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
def test_table_is_read_only() -> None:
    """`MappingProxyType` refuses mutation; a plain dict here would let a
    future import quietly rewrite the table it is meant to be inert."""
    (principal_id,) = list(IN_PROCESS_GRANTS.keys())[:1]
    with pytest.raises(TypeError):
        IN_PROCESS_GRANTS[principal_id] = frozenset()  # type: ignore[index]
