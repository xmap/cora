"""Unit tests for `SshLocateProbe`.

`run_locate_probe`'s own request validation and transport are covered
by `test_ssh_probe.py`; this file pins only the thin composition:
`SshLocateProbe.locate` must forward every keyword argument to
`run_locate_probe` unchanged, plus `config=self._config` from
construction time, and hand back whatever it returns.
"""

from __future__ import annotations

from typing import Any

import pytest

from cora.data.adapters._ssh_probe import SshProbeConfig
from cora.data.adapters.ssh_locate_probe import SshLocateProbe

pytestmark = pytest.mark.unit

_CONFIG = SshProbeConfig(
    host="tomdet",
    remote_python="/venv/bin/python3",
    allowed_roots=("/local1/2BM", "/gdata/dm/2BM"),
    connect_timeout_seconds=5.0,
    command_timeout_seconds=5.0,
    max_walk_seconds=60.0,
)


def test_adapter_advertises_its_kind() -> None:
    assert SshLocateProbe(config=_CONFIG).kind == "SshLocate"


async def test_locate_forwards_every_argument_and_the_configured_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_locate_probe(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"kind": "Located", "matches": [], "match_count": 0}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_locate_probe.run_locate_probe", _fake_run_locate_probe
    )
    probe = SshLocateProbe(config=_CONFIG)

    response = await probe.locate(
        root="/gdata/dm/2BM",
        months=("2026-08", "2026-07"),
        directory_suffix="-1015116",
        filename="scan_005.h5",
        subdirectory="data",
    )

    assert response == {"kind": "Located", "matches": [], "match_count": 0}
    assert captured == {
        "root": "/gdata/dm/2BM",
        "months": ("2026-08", "2026-07"),
        "directory_suffix": "-1015116",
        "filename": "scan_005.h5",
        "subdirectory": "data",
        "config": _CONFIG,
    }


async def test_locate_forwards_a_none_subdirectory(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_locate_probe(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"kind": "Located", "matches": [], "match_count": 0}

    monkeypatch.setattr(
        "cora.data.adapters.ssh_locate_probe.run_locate_probe", _fake_run_locate_probe
    )
    probe = SshLocateProbe(config=_CONFIG)

    await probe.locate(
        root="/gdata/dm/2BM",
        months=("2026-08",),
        directory_suffix="-1015116",
        filename="scan_005.h5",
        subdirectory=None,
    )

    assert captured["subdirectory"] is None
