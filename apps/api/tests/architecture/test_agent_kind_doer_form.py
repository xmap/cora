"""R5 fitness: every seeded Agent.kind value follows `<DomainNoun><DoerNoun>`.

The R5 lock in `project_naming_conventions.md` requires agent
aggregate identities to use the doer form (`CautionDrafter`,
`RunDebriefer`, `ClaimsVerifier`), not work-product nouns
(`RunDebrief`, `Caution`). Cross-corpus audit of OpenAI Agents SDK,
CrewAI, Anthropic multi-agent, AutoGen, Microsoft Agent Framework
locked the convention at 6/6 frameworks.

Rule: every `*_AGENT_KIND` constant in any `cora.agent.seed*` module
MUST be a PascalCase compound whose final segment is a natural
English doer noun.

This pin discovers seed modules dynamically from the git-tracked
file set (per `feedback_architecture_test_git_aware`); when a third
Agent BC seed ships, the new `*_AGENT_KIND` constant is pulled in
automatically. A contributor adding a work-product-named agent
(say `kind="CautionDraft"` instead of `"CautionDrafter"`) gets a
fitness-function failure at architecture-test time.
"""

import importlib
import re

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

# Doer-form shape: PascalCase compound, at least two segments
# (DomainNoun + DoerNoun). Single-word names like `Drafter` would
# collide across BCs; R5 requires the BC-qualifier prefix.
_PASCAL_COMPOUND = re.compile(r"^[A-Z][a-z]+([A-Z][a-z]+)+$")

# Natural English doer suffixes per R5. The list is not exhaustive
# (zero-change doers like `Monitor` or `Coordinator` also count, though
# both happen to already end in `-or`); extend when a new agent
# legitimately needs a doer form outside this set.
_DOER_SUFFIXES = ("er", "or", "ist", "ant", "tor")

# Whole-word zero-change doers that are natural English doer nouns on
# their own but do not end in any of `_DOER_SUFFIXES` (a witness is one
# who witnesses, exactly as a monitor is one who monitors, but "witness"
# has no suffix to match against). Checked against the compound's final
# PascalCase segment, not the whole value.
#
# "Registrar" (DurableCopyRegistrar) is the same shape: a registrar is
# one who registers, via the "-ar" agentive suffix rather than "-er",
# which `_DOER_SUFFIXES` does not carry because no other agent kind in
# the fleet uses it.
_ZERO_CHANGE_DOER_WORDS = frozenset({"Registrar", "Witness"})

_AGENT_DIR = CORA_ROOT / "agent"


def _seed_modules() -> list[str]:
    """Importable module names of Agent BC seed modules.

    Filters by git's tracked-file set so a half-staged new seed
    (untracked file + stashed import edit) does not false-fail.
    """
    out: list[str] = []
    for path in sorted(tracked_python_files()):
        if path.parent != _AGENT_DIR:
            continue
        if not (path.name == "seed.py" or path.name.startswith("seed_")):
            continue
        rel = path.relative_to(CORA_ROOT.parent)
        out.append(".".join(rel.with_suffix("").parts))
    return out


def _seeded_kinds() -> dict[str, str]:
    """`{qualified_constant_name: kind_value}` for every `*_AGENT_KIND` constant."""
    found: dict[str, str] = {}
    for mod_name in _seed_modules():
        mod = importlib.import_module(mod_name)
        for attr in dir(mod):
            if attr.startswith("_") or not attr.endswith("_AGENT_KIND"):
                continue
            value = getattr(mod, attr)
            if isinstance(value, str):
                found[f"{mod_name}.{attr}"] = value
    return found


@pytest.mark.architecture
def test_seeded_agent_kinds_follow_r5_doer_form() -> None:
    """Every seeded Agent.kind value is `<DomainNoun><DoerNoun>` PascalCase."""
    kinds = _seeded_kinds()
    assert kinds, (
        "No `*_AGENT_KIND` constants discovered; check the seed-module scan "
        "(expected at least one module under `cora.agent.seed*`)."
    )

    failures: list[str] = []
    for ref, value in sorted(kinds.items()):
        if not _PASCAL_COMPOUND.match(value):
            failures.append(
                f"{ref}={value!r}: not a PascalCase compound. R5 requires "
                "`<DomainNoun><DoerNoun>` (for example `RunDebriefer`, "
                "`CautionDrafter`)."
            )
            continue
        final_segment = re.findall(r"[A-Z][a-z]+", value)[-1]
        if not any(value.endswith(suffix) for suffix in _DOER_SUFFIXES) and (
            final_segment not in _ZERO_CHANGE_DOER_WORDS
        ):
            failures.append(
                f"{ref}={value!r}: doesn't end in a doer suffix {_DOER_SUFFIXES} "
                f"or a known zero-change doer word {sorted(_ZERO_CHANGE_DOER_WORDS)}. "
                "If this name is intentionally a whole-word doer noun (a "
                "witness is one who witnesses, exactly as a monitor is one "
                "who monitors), extend `_ZERO_CHANGE_DOER_WORDS`."
            )

    assert not failures, "Found R5 violations:\n  - " + "\n  - ".join(failures)
