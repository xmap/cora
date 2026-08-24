"""Unit tests for `cora.infrastructure.logging`'s live-`sys.stdout` fix.

Pins the fix documented in the module's own "live `sys.stdout`" section:
`logging.StreamHandler` binds whatever `sys.stdout` IS at construction
time, which breaks under pytest's `capsys` (a per-test monkeypatch of
`sys.stdout`) whenever `configure_logging()` is not called freshly for
every test. That is exactly the situation `make_inmemory_kernel` puts
most unit tests in: it never calls `configure_logging()`, so a test
built on it inherits whichever handler an EARLIER, unrelated test's
`build_kernel()` call last installed, built under THAT test's `capsys`.
"""

import io

import pytest

from cora.infrastructure.logging import configure_logging, get_logger

pytestmark = pytest.mark.unit


def test_configured_handler_follows_sys_stdout_across_a_later_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler must route to whichever `sys.stdout` is CURRENT at
    write time, not whichever one was live when it was built.

    Mirrors the real failure shape: `configure_logging()` runs once (as
    it would from an earlier, unrelated test's `build_kernel()` call),
    then `sys.stdout` is swapped TWICE more with no further
    reconfiguration (as `capsys` does, once per test, for every test
    built on `make_inmemory_kernel`). Each write must land in whichever
    buffer is live at that moment, not the one that was live when the
    handler was constructed -- which, under the pre-fix
    `logging.StreamHandler(sys.stdout)`, was neither buffer at all: at
    the point `configure_logging()` runs below, `sys.stdout` has not
    been monkeypatched yet, so both writes would have escaped to the
    real terminal and this test would fail on both assertions below,
    not pass on the wrong one.
    """
    configure_logging()
    logger = get_logger(__name__)

    buffer_a = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer_a)
    logger.warning("first-marker-alpha")

    buffer_b = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer_b)
    logger.warning("second-marker-bravo")

    assert "first-marker-alpha" in buffer_a.getvalue()
    assert "second-marker-bravo" not in buffer_a.getvalue()
    assert "second-marker-bravo" in buffer_b.getvalue()
    assert "first-marker-alpha" not in buffer_b.getvalue()


def test_handler_construction_does_not_capture_a_stale_stdout_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuring while `sys.stdout` is swapped must not bind to THAT
    swap either: a later swap must still win.

    The companion case to the one above, and the one that would have
    passed for the wrong reason if the fix only worked when
    `configure_logging()` runs against the real stdout: this proves the
    handler follows `sys.stdout` no matter what it pointed at when
    `configure_logging()` was called.
    """
    first_buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", first_buffer)
    configure_logging()
    logger = get_logger(__name__)

    second_buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", second_buffer)
    logger.warning("routed-after-reconfigure")

    assert "routed-after-reconfigure" not in first_buffer.getvalue()
    assert "routed-after-reconfigure" in second_buffer.getvalue()
