"""Unit tests for the SubAssemblyLinkBody wire DTO."""

from uuid import uuid4

import pytest

from cora.equipment._bodies import SubAssemblyLinkBody
from cora.equipment.aggregates.assembly import (
    InvalidSubAssemblyLinkError,
    SubAssemblyLink,
)


@pytest.mark.unit
def test_to_domain_builds_sub_assembly_link() -> None:
    child = uuid4()
    body = SubAssemblyLinkBody(
        slot_name="optics", sub_assembly_id=child, content_hash="sha256:abcd1234"
    )
    link = body.to_domain()
    assert isinstance(link, SubAssemblyLink)
    assert link.slot_name.value == "optics"
    assert link.sub_assembly_id == child
    assert link.content_hash == "sha256:abcd1234"


@pytest.mark.unit
def test_to_domain_rejects_blank_content_hash() -> None:
    """Pydantic min_length=1 admits whitespace; the VO __post_init__
    rejects it at to_domain() time -> HTTP 400."""
    body = SubAssemblyLinkBody(slot_name="optics", sub_assembly_id=uuid4(), content_hash="   ")
    with pytest.raises(InvalidSubAssemblyLinkError):
        body.to_domain()
