"""Stage repo-root docs into the mkdocs build directory.

Copies CONTRIBUTING.md -> docs/reference/contributing.md and
SECURITY.md -> docs/reference/security.md, and slices the README's
bring-up sections into docs/stack/run.md.

The README as a whole serves a different audience (cloners), so it is not
staged wholesale. But its Quick start and API surfaces sections are the
only place the commands to install and run CORA are written down, and a
reader of the site needs them too. Slicing keeps one source: edit the
README and the page follows.

Link rewriting still happens in-memory at build time via the mkdocs hook
in scripts/mkdocs_hooks.py.

Run from the repo root:  python scripts/stage_docs.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
STAGED_CONTRIBUTING = DOCS_DIR / "reference" / "contributing.md"
STAGED_SECURITY = DOCS_DIR / "reference" / "security.md"
STAGED_RUN = DOCS_DIR / "stack" / "run.md"

_RUN_PAGE_LEAD = """# Run it locally

*How to install CORA, bring up its database, and start the dev server.*

Sliced from the repo README at build time, so these commands stay the ones
a cloner actually runs. For bringing CORA up at a facility rather than on a
laptop, see [Deployment](deployment.md).

"""


class StagingError(RuntimeError):
    """A source section the site depends on could not be found."""


def _section(markdown: str, heading: str) -> str:
    """Return one `## heading` section, up to the next `## ` or EOF."""
    pattern = rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, re.S | re.M)
    if match is None:
        raise StagingError(
            f"README.md has no '## {heading}' section. The staged page "
            f"docs/stack/run.md is sliced from it; rename the section here too, "
            f"or the site loses the only copy of the bring-up commands."
        )
    return match.group(1).strip()


def main() -> None:
    STAGED_CONTRIBUTING.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "CONTRIBUTING.md", STAGED_CONTRIBUTING)
    shutil.copyfile(REPO_ROOT / "SECURITY.md", STAGED_SECURITY)

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    body = "\n\n".join(
        [
            _RUN_PAGE_LEAD.rstrip(),
            "## Quick start",
            _section(readme, "Quick start"),
            "## API surfaces",
            _section(readme, "API surfaces"),
        ]
    )
    STAGED_RUN.parent.mkdir(parents=True, exist_ok=True)
    STAGED_RUN.write_text(body + "\n", encoding="utf-8")

    print(f"Staged contributing.md and security.md into {STAGED_CONTRIBUTING.parent}")
    print(f"Staged run.md into {STAGED_RUN.parent}")


if __name__ == "__main__":
    main()
