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
    "conduct_until_converged": ("f6aa1070a5dca174bab7b4cc90afcaf309b10025aa1241b5d76b3da485bf40f1"),
    "_run_convergence_loop": ("f2b6f22c3ea1de8fae2581f99ccf2d047e876816ea9863b47d64e530c14b87ec"),
    "_complete_converged": ("eb13d348525223ff7f4aa481c51afecc0d45660acdd5feee49f6df2f005e6f5a"),
    "_abort_unconverged_cap": ("606e0122ed687df310c89d6b6d0c65b06c42150a9ed2a05c1eb4d9a2e526bd18"),
    "_abort_absolute_ceiling": ("310ac222040c2813e44b8bafee78ba97ff1f9a4a8aaefe2af27e2a9881075e3d"),
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
