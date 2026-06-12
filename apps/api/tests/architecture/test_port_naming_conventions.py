"""Pin: hexagonal port Protocols follow the bare-role-noun naming policy.

A port is a `typing.Protocol` seam the domain depends on and adapters
implement. They live under `cora/**/ports/` (cross-BC ports at
`infrastructure/ports/`, BC-owned ports at `<bc>/ports/`, shared-kernel
ports at `shared/ports/`). Three rules hold across the corpus, and until
this test landed none was enforced, so several files had drifted.

## Rule 1: bare role noun, `Port` suffix only as an allowlisted carve-out

The port class is named for its ROLE, and the role noun already signals
the abstract seam: `EventStore`, `TokenVerifier`, `AssetLookup`,
`IdGenerator`, `DoiMinter`, `EditionSerializer`. The generic word `Port`
is redundant on top of a role noun (the sibling pair `TokenVerifier` /
`ChecksumVerifier` is the tell), so it is forbidden EXCEPT where stripping
it would leave a bare verb / abstract non-agent noun, or would collide
with a value object. Those exceptions are enumerated in
`_PORT_SUFFIX_ALLOWLIST`, each with its reason.

This mirrors the locked `<Tech><Role>` adapter rule (`PostgresEventStore`,
`AnthropicLLM`): the adapter prepends a tech token to the bare port role,
so the port carries the role and nothing more.

## Rule 2: filename equals snake_case(port class)

An import-path reader should predict the class from the path:
`event_store.py` -> `EventStore`, `signature_port.py` -> `SignaturePort`.
When the class legitimately carries the `Port` suffix the file carries it
too (`control_port.py` -> `ControlPort`), so the snake_case identity still
holds. The rejected shape is a domain-named module whose stem omits a
suffix the class keeps.

## Rule 3: lookup-result DTOs use the `LookupResult` suffix

A `<X>Lookup` port returns a denormalized read-side row. That DTO is named
`<X>LookupResult` (`AssetLookupResult`, `SupplyLookupResult`), never
`<X>Reference`. The two suffixes once split the corpus 9-to-5 for the
identical concept; `Reference` is reserved for genuine reference value
objects, which live in `value_types.py` (excluded here) or carry a domain
name. A port file declaring a `*Reference` class is the rejected shape.

## Deferred: the signing/canonicalization cluster

`SigningPort` (`signing.py`) and `CanonicalizationPort`
(`canonicalization.py`) still carry the suffix AND mismatch their files.
Their rename rides with the signing-stack dedup (the audit's
MERGED-SIGNING-STACK finding: `Signer` vs `SigningPort` is an open
which-survives decision, and the canonicalization rename touches the same
crypto cluster). They sit in `_DEFERRED_SIGNING_CLUSTER` so this test
stays green without prejudging that decision; remove them from the set
when the dedup lands and the renames happen.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

# Port classes that keep the generic `Port` suffix on purpose. Each entry
# names why no bare role noun fits.
_PORT_SUFFIX_ALLOWLIST: dict[str, str] = {
    "ControlPort": "value-IO seam; 'Control' alone is a bare verb, no role noun fits",
    "SignaturePort": "stripping to 'Signature' collides with the Signature value object",
    "PublishPort": "federation publish seam; 'Publish' is a bare verb, no graceful agent noun",
    "PullPort": "federation pull seam; 'Pull' is a bare verb, no graceful agent noun",
}

# Suffix-carrying ports whose rename is deferred to the signing-stack dedup
# (audit MERGED-SIGNING-STACK). Exempt from BOTH rules until that lands.
_DEFERRED_SIGNING_CLUSTER: frozenset[str] = frozenset({"SigningPort", "CanonicalizationPort"})

# Files under a ports/ tree that do not define a port Protocol.
_NON_PORT_FILES: frozenset[str] = frozenset({"__init__.py", "errors.py", "value_types.py"})

# Genuine reference value objects allowed to keep the `Reference` suffix inside a
# scanned port file. Empty today: lookup-result DTOs are `<X>LookupResult`, and
# real reference VOs live in value_types.py (excluded above). Add a class here
# only with a reason if a non-lookup reference legitimately belongs in a port file.
_REFERENCE_SUFFIX_ALLOWLIST: frozenset[str] = frozenset()


def _camel_to_snake(name: str) -> str:
    """`EventStore` -> `event_store`, `LLM` -> `llm`, `IdGenerator` -> `id_generator`."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _is_protocol_base(base: ast.expr) -> bool:
    return (isinstance(base, ast.Name) and base.id == "Protocol") or (
        isinstance(base, ast.Attribute) and base.attr == "Protocol"
    )


def _protocol_classes(tree: ast.AST) -> list[str]:
    """Names of top-level classes that directly subclass `Protocol`."""
    return [
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.ClassDef) and any(_is_protocol_base(b) for b in node.bases)
    ]


def _class_names(tree: ast.AST) -> list[str]:
    """Names of all top-level classes in a module."""
    return [node.name for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)]


def _port_files() -> list[Path]:
    """Tracked `.py` files under any `ports/` tree that may define a port Protocol."""
    return sorted(
        path
        for path in tracked_python_files()
        if "/ports/" in str(path).replace("\\", "/") and path.name not in _NON_PORT_FILES
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
@pytest.mark.parametrize("path", _port_files(), ids=_qualified)
def test_port_class_drops_redundant_port_suffix(path: Path) -> None:
    """No port Protocol class ends in `Port` unless it is an allowlisted carve-out."""
    protocols = _protocol_classes(ast.parse(path.read_text()))
    if not protocols:
        pytest.skip(f"{_qualified(path)} declares no port Protocol")
    allowed = _PORT_SUFFIX_ALLOWLIST.keys() | _DEFERRED_SIGNING_CLUSTER
    offenders = sorted(p for p in protocols if p.endswith("Port") and p not in allowed)
    assert not offenders, (
        f"{_qualified(path)} declares port Protocol(s) with a redundant `Port` suffix:\n  "
        + "\n  ".join(offenders)
        + "\n\nName the port for its role; the role noun already signals the seam, so the "
        "generic `Port` suffix is redundant (compare TokenVerifier / ChecksumVerifier). "
        "Strip it to a bare role noun. If no graceful role noun exists (bare verb, abstract "
        "noun, or value-object collision), add the class to `_PORT_SUFFIX_ALLOWLIST` with a "
        "one-line reason."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", _port_files(), ids=_qualified)
def test_port_filename_matches_class(path: Path) -> None:
    """A port file is named `snake_case(<PortClass>).py` for its port Protocol."""
    protocols = _protocol_classes(ast.parse(path.read_text()))
    if not protocols:
        pytest.skip(f"{_qualified(path)} declares no port Protocol")
    if any(p in _DEFERRED_SIGNING_CLUSTER for p in protocols):
        pytest.skip(f"{_qualified(path)} rename deferred to the signing-stack dedup")
    stem = path.stem
    snake_names = {_camel_to_snake(p) for p in protocols}
    assert stem in snake_names, (
        f"{_qualified(path)} filename '{stem}.py' does not match snake_case of any port "
        f"Protocol it defines ({sorted(protocols)}).\n\n"
        "Rename the file to snake_case(<PortClass>).py so an import-path reader can predict "
        "the class from the path. A domain-named module whose stem omits a suffix the class "
        "keeps (signing.py for SigningPort) is the rejected shape."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", _port_files(), ids=_qualified)
def test_port_lookup_result_uses_lookupresult_suffix(path: Path) -> None:
    """A lookup-result DTO in a port file is `<X>LookupResult`, never `<X>Reference`."""
    offenders = sorted(
        name
        for name in _class_names(ast.parse(path.read_text()))
        if name.endswith("Reference") and name not in _REFERENCE_SUFFIX_ALLOWLIST
    )
    assert not offenders, (
        f"{_qualified(path)} declares a `Reference`-suffixed class in a port file:\n  "
        + "\n  ".join(offenders)
        + "\n\nA row returned by a `<X>Lookup` port is a lookup result; name it "
        "`<X>LookupResult` to match the canonical suffix. The `Reference` suffix is reserved "
        "for genuine reference value objects, which belong in value_types.py or carry a domain "
        "name. If this really is such a VO, add it to `_REFERENCE_SUFFIX_ALLOWLIST` with a reason."
    )
