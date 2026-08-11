"""Redaction disposition table drift test.

Asserts that the committed
`src/cora/infrastructure/record_export/_dispositions.py` matches what
`tools/gen_record_dispositions.py` produces right now. Adding an event
type, adding a field, or changing a field's declared type fails this
test until the table is regenerated and the diff reviewed.

That review is the point. The table decides what a published record
discloses, so a field's arrival has to be a line in a pull request
rather than a silent behaviour change. Regenerate with:

    make record-dispositions

The generator runs in a SUBPROCESS rather than being imported. It lives
outside `src/` precisely so nothing shippable can import it, and this
test declining to import it keeps that true. It also means the test
exercises the same entry point a developer runs.

Fail-closed is NOT provided by this test. An unlisted field drops at
export time by the rule itself; this test only catches staleness early.
Deleting it would make the table rot silently, not make the exporter
leak.

Running the generator in a subprocess hides this test's real dependency
(every `events.py` in the tree) from pytest-tach's impact analysis, so
`pytest --tach` would skip it after an event-only change. CI runs the
suite without that flag, so it is covered today; anyone turning impact
analysis on in CI has to exempt this test.
"""

import subprocess
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[2]
_GENERATOR = _API_ROOT / "tools" / "gen_record_dispositions.py"
_TABLE = _API_ROOT / "src" / "cora" / "infrastructure" / "record_export" / "_dispositions.py"


def test_committed_disposition_table_matches_generator() -> None:
    """Committed `_dispositions.py` equals a fresh generator run."""
    before = _TABLE.read_text(encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(_GENERATOR)],
        cwd=_API_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    after = _TABLE.read_text(encoding="utf-8")
    if before != after:
        _TABLE.write_text(before, encoding="utf-8")

    assert result.returncode == 0, (
        "The disposition generator refused to produce a table. An "
        "annotation it cannot classify ABORTS the run by design, because "
        "an unrecognised type is a question about the design rather than "
        f"a row to skip. Run `make record-dispositions`.\n{result.stderr}"
    )
    assert before == after, (
        f"Disposition table drift detected at {_TABLE.name}. Run "
        "`make record-dispositions`, then review the diff: it is the "
        "list of what a published record would disclose."
    )
