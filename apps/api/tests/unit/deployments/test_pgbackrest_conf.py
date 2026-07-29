"""Drift guards for infra/backup/pgbackrest.conf.

The backup configuration carries decisions whose failure mode is
silence: retention that quietly stops applying, an archive check that
someone disables to make an error go away, and above all repository
encryption, which pgBackRest fixes at stanza creation and cannot add
later. The conf file documents each of these in prose; these tests are
the prose made enforceable, so the day someone re-points `repo1-type`
at a facility share or an object store without deciding encryption, CI
refuses instead of the beamline finding out.
"""

import configparser
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CONF_PATH = _REPO_ROOT / "infra" / "backup" / "pgbackrest.conf"


def _load_conf() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=True)
    parser.read_string(_CONF_PATH.read_text(encoding="utf-8"))
    return parser


def test_conf_file_exists_where_the_drill_mounts_it() -> None:
    assert _CONF_PATH.is_file(), (
        "infra/backup/pgbackrest.conf moved; the drill compose file and "
        "the deployment docs both mount it by this path."
    )


def test_non_posix_repository_declares_a_cipher() -> None:
    """The now-or-never guard. Encryption is fixed at stanza creation;
    a posix repository on the database's own host is inside the same
    trust boundary as PGDATA, but the moment the repository points
    anywhere else, facility data leaves the host and the cipher must be
    decided BEFORE the first backup at the new target. This test makes
    forgetting impossible: flip `repo1-type` without `repo1-cipher-type`
    and CI refuses with the same sentence the conf file says in prose.
    """
    conf = _load_conf()
    repo_type = conf.get("global", "repo1-type", fallback="posix")
    if repo_type == "posix":
        return
    assert conf.has_option("global", "repo1-cipher-type"), (
        f"repo1-type={repo_type} points the repository off-host, and "
        f"repository encryption cannot be added after stanza creation. "
        f"Set repo1-cipher-type (and source repo1-cipher-pass from the "
        f"secret store) in the SAME change, or every backup taken before "
        f"someone notices is unencrypted forever."
    )


def test_retention_is_declared_as_a_count() -> None:
    """Retention is applied when a backup finishes; without these two
    settings the repository grows without bound. The type matters as
    much as the number: with `count`, WAL archive retention defaults to
    covering every retained full, and switching to `time` silently
    changes that default too (the conf documents the trap; this pins
    it)."""
    conf = _load_conf()
    assert conf.has_option("global", "repo1-retention-full")
    assert conf.get("global", "repo1-retention-full-type", fallback=None) == "count"


def test_archive_check_stays_enabled() -> None:
    """Turning archive-check off is how a backup set becomes
    unrestorable while every command still reports success. It is on by
    default; this test refuses the explicit `n` that someone might add
    to silence a failing archive instead of fixing it."""
    conf = _load_conf()
    assert conf.get("global", "archive-check", fallback="y") != "n"


def test_stanza_names_the_cluster_credentials() -> None:
    """The cora cluster has no `postgres` role or database, so the
    stanza must carry both settings or stanza-create fails with an
    error that reads like a broken installation."""
    conf = _load_conf()
    assert conf.get("cora", "pg1-user", fallback=None) == "cora"
    assert conf.get("cora", "pg1-database", fallback=None) == "cora"
    assert conf.has_option("cora", "pg1-path")
