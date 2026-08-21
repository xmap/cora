"""Regression tests for infra/atlas/scripts/scan_*.sh.

Before this file, nothing in the repository referenced these scripts
except ci.yml: no pytest, no Makefile target, no pre-commit hook. That is
exactly how the original safety-scan step's path bug went unnoticed for
three months (it always exited 0, and nothing else ever ran it to find
out). These tests run the scripts directly, the same way ci.yml does,
against small fixture files, so a future change to either script gets
caught here instead of on the next real migration.

pytest lives only in the apps/api virtualenv; there is no separate Python
environment for infra/atlas. Run with:

    apps/api/.venv/bin/pytest infra/atlas/scripts/tests/test_scan_scripts.py -v

from the repository root.
"""

import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent.parent
DESTRUCTIVE_SCRIPT = SCRIPTS_DIR / "scan_destructive_ddl.sh"
CONSTRAINT_SCRIPT = SCRIPTS_DIR / "scan_constraint_drops.sh"


def run_scan(script: Path, root: Path, *files: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(script), str(root), *files],
        capture_output=True,
        text=True,
        timeout=10,
    )


def write_sql(root: Path, name: str, content: str) -> str:
    (root / name).write_text(content)
    return name


class TestScanDestructiveDdl:
    def test_scan_destructive_ddl_clean_file_passes(self, tmp_path):
        f = write_sql(tmp_path, "clean.sql", "CREATE TABLE t (id int);\n")
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_destructive_ddl_unmarked_drop_column_fails(self, tmp_path):
        f = write_sql(tmp_path, "drop.sql", "ALTER TABLE t DROP COLUMN a;\n")
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 1
        assert "line=1" in result.stderr

    def test_scan_destructive_ddl_same_line_marker_passes(self, tmp_path):
        f = write_sql(
            tmp_path,
            "marked.sql",
            "ALTER TABLE t DROP COLUMN a; -- atlas:safety:allow=intentional\n",
        )
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_destructive_ddl_alter_column_type_with_using_passes(self, tmp_path):
        f = write_sql(
            tmp_path,
            "retype.sql",
            "ALTER TABLE t ALTER COLUMN a TYPE TEXT USING a::text;\n",
        )
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_destructive_ddl_alter_column_type_without_using_fails(self, tmp_path):
        f = write_sql(tmp_path, "retype.sql", "ALTER TABLE t ALTER COLUMN a TYPE TEXT;\n")
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 1

    def test_scan_destructive_ddl_revoke_truncate_privilege_list_passes(self, tmp_path):
        f = write_sql(
            tmp_path,
            "revoke.sql",
            "REVOKE UPDATE, DELETE, TRUNCATE ON t FROM cora_app;\n",
        )
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_destructive_ddl_leading_truncate_statement_fails(self, tmp_path):
        f = write_sql(tmp_path, "truncate.sql", "TRUNCATE t;\n")
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 1

    def test_scan_destructive_ddl_marker_on_prior_statement_does_not_exempt_next_line(self, tmp_path):
        # F1 case 1 from the review that reopened this check: a marker on
        # one DROP must not carry over to an unmarked DROP right below it.
        f = write_sql(
            tmp_path,
            "leak.sql",
            "ALTER TABLE t DROP COLUMN a; -- atlas:safety:allow=intentional\n"
            "ALTER TABLE t DROP COLUMN b;\n",
        )
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 1
        assert "line=2" in result.stderr

    def test_scan_destructive_ddl_unrelated_marker_above_does_not_exempt_drop(self, tmp_path):
        # F1 case 2: a marker on an unrelated earlier statement must not
        # exempt a later, unmarked DROP.
        f = write_sql(
            tmp_path,
            "unrelated.sql",
            "CREATE INDEX i ON t (a); -- atlas:safety:allow=unrelated-thing\n"
            "ALTER TABLE t DROP COLUMN a;\n",
        )
        result = run_scan(DESTRUCTIVE_SCRIPT, tmp_path, f)
        assert result.returncode == 1
        assert "line=2" in result.stderr

    def test_scan_destructive_ddl_corpus_revoke_line_passes(self):
        # The real regression this script exists to fix: a migration
        # already in the repo (20260701020000:88) revokes TRUNCATE as a
        # privilege, which is safety-increasing, not destructive.
        migration = "infra/atlas/migrations/20260701020000_init_entries_operation_procedure_outcomes.sql"
        result = run_scan(DESTRUCTIVE_SCRIPT, REPO_ROOT, migration)
        assert result.returncode == 0, result.stderr

    def test_scan_destructive_ddl_corpus_known_violation_still_flagged(self):
        # A real, currently-unmarked violation from the migration corpus.
        # Guards against a future change silently narrowing the pattern
        # past what this fix intended.
        migration = "infra/atlas/migrations/20260609130000_drop_proj_supply_summary_scope.sql"
        result = run_scan(DESTRUCTIVE_SCRIPT, REPO_ROOT, migration)
        assert result.returncode == 1
        assert "line=37" in result.stderr


class TestScanConstraintDrops:
    def test_scan_constraint_drops_clean_file_passes(self, tmp_path):
        f = write_sql(tmp_path, "clean.sql", "CREATE TABLE t (id int);\n")
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_unmarked_drop_constraint_fails(self, tmp_path):
        f = write_sql(tmp_path, "drop.sql", "ALTER TABLE t DROP CONSTRAINT a;\n")
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 1
        assert "line=1" in result.stderr

    def test_scan_constraint_drops_same_line_marker_passes(self, tmp_path):
        f = write_sql(
            tmp_path,
            "marked.sql",
            "ALTER TABLE t DROP CONSTRAINT a; -- atlas:safety:allow=ok\n",
        )
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_standalone_marker_above_blank_line_passes(self, tmp_path):
        # The repo's own precedent: a standalone marker comment, then a
        # blank line, then the statement it excuses.
        f = write_sql(
            tmp_path,
            "gap.sql",
            "-- atlas:safety:allow=drop-index-allowed-data-preserving\n"
            "\n"
            "DROP INDEX IF EXISTS i;\n",
        )
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_addback_in_same_file_passes(self, tmp_path):
        f = write_sql(
            tmp_path,
            "addback.sql",
            "ALTER TABLE t DROP CONSTRAINT a;\n"
            "ALTER TABLE t ADD CONSTRAINT a CHECK (x > 0);\n",
        )
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_drop_index_recreated_plain_passes(self, tmp_path):
        # F5: dropping an index and recreating it, even without UNIQUE, is
        # an add-back, not a bare removal.
        f = write_sql(
            tmp_path,
            "reindex.sql",
            "DROP INDEX IF EXISTS i;\nCREATE INDEX i ON t (a, b);\n",
        )
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_marker_on_prior_drop_does_not_exempt_next_drop(self, tmp_path):
        # F1 case 3: a same-line marker on one DROP CONSTRAINT must not
        # silence a second, unmarked DROP CONSTRAINT right below it.
        f = write_sql(
            tmp_path,
            "leak.sql",
            "ALTER TABLE t DROP CONSTRAINT a; -- atlas:safety:allow=ok\n"
            "ALTER TABLE t DROP CONSTRAINT b;\n",
        )
        result = run_scan(CONSTRAINT_SCRIPT, tmp_path, f)
        assert result.returncode == 1
        assert "line=2" in result.stderr

    def test_scan_constraint_drops_corpus_marker_gap_file_passes(self):
        # Real corpus file whose marker sits two lines above the DROP
        # INDEX it excuses, with a blank line between them. This is the
        # exact shape the backward marker lookup must honour.
        migration = "infra/atlas/migrations/20260518210000_drop_proj_recipe_capability_summary_code_unique.sql"
        result = run_scan(CONSTRAINT_SCRIPT, REPO_ROOT, migration)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_corpus_addback_file_passes(self):
        # Real corpus file with a genuine same-file add-back (DROP
        # CONSTRAINT followed by ADD CONSTRAINT of the same name), no
        # marker needed.
        migration = "infra/atlas/migrations/20260519233000_widen_proj_access_actor_summary_kind.sql"
        result = run_scan(CONSTRAINT_SCRIPT, REPO_ROOT, migration)
        assert result.returncode == 0, result.stderr

    def test_scan_constraint_drops_corpus_known_violation_still_flagged(self):
        # A real, currently-unmarked violation from the migration corpus.
        # Guards against a future change silently narrowing the check
        # past what this fix intended.
        migration = "infra/atlas/migrations/20260609130000_drop_proj_supply_summary_scope.sql"
        result = run_scan(CONSTRAINT_SCRIPT, REPO_ROOT, migration)
        assert result.returncode == 1
        assert "line=34" in result.stderr
