"""G1: the six convergence-loop methods are BYTE-FROZEN; the steered twin is NEW.

`conduct_until_advised` is the DECIDE-axis twin of `conduct_until_converged`.
It must REUSE the existing convergence helpers (`_abort_absolute_ceiling`,
`_abort_after_failed_pass`, ...) verbatim and add its own `_complete_advised`,
NEVER refactor the convergence ones into a shared base. A well-meaning DRY
pull-up that edits `_run_convergence_loop` to share code with the steered loop
would change its source and BREAK this snapshot: that is the point. The pinned
digests were computed against the convergence methods as shipped at the steered
loop's build; a change to any one is either an intentional re-pin (update the
digest deliberately, in its own commit) or an accidental edit to frozen code.

The second test asserts the steered twin exists as NEW symbols, so the
byte-pins are meaningfully guarding ADDITIVITY (the twin was added beside the
frozen six), not merely the absence of the six.
"""

import hashlib
import inspect

import pytest

from cora.operation import conductor as cm

_FROZEN_DIGESTS = {
    "conduct_until_converged": ("e5a97bc1e9ca327feceecfc7d4fc68e9a9204771a91e978d687c5992a8ddc67a"),
    # Re-pinned 2026-08-29 (field-drop fix): these four used to build a fresh
    # ConductorResult on an abort/complete-rejected arm, silently dropping
    # substrate_writes / artifacts / outputs, the same bug class #744 fixed on
    # conduct() / conduct_or_hold() / conduct_from(). See
    # [[project_field_drop_bug_class]]; deliberate re-pin, not drift.
    "_run_convergence_loop": ("7f51fff96ba99d60777ce929b93bbbccdaa2b048ace4ef3fb45e8abdfd92938e"),
    "_complete_converged": ("556697b026aa9dbedeb643145a840b58fbd96bf0dd55c4db7a90bb0d8f242061"),
    "_abort_unconverged_cap": ("f154957c59f6c3078e0bdab0945d23aad2fad6362aebddbf0018c87687ca880f"),
    "_abort_absolute_ceiling": ("6da5833acdf373a3681ce57a6faaecf70567fa8ce37e92b22cd45dd8bcf1b577"),
    "_abort_after_failed_pass": (
        "0ada3a9f98926ad8daa22897ba3cee455d9c58b848bf85c2450283d470d1e514"
    ),
}


@pytest.mark.architecture
@pytest.mark.unit
def test_conduct_until_converged_helpers_byte_for_byte_unchanged() -> None:
    for name, expected in _FROZEN_DIGESTS.items():
        src = inspect.getsource(getattr(cm.Conductor, name))
        actual = hashlib.sha256(src.encode()).hexdigest()
        assert actual == expected, (
            f"{name} source changed (sha256 {actual}, pinned {expected}); the "
            "convergence-loop methods are byte-frozen, reuse them rather than edit them"
        )


@pytest.mark.architecture
@pytest.mark.unit
def test_conduct_until_advised_symbols_are_new_not_refactored() -> None:
    for name in ("conduct_until_advised", "_run_decide_loop", "_complete_advised"):
        assert callable(getattr(cm.Conductor, name, None)), (
            f"{name} must exist as a new symbol beside the frozen convergence methods"
        )
