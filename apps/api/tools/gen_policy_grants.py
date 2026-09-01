"""Generate the `POST /policies` request body for CORA's back-door Policy.

`cora.api.in_process_grants.IN_PROCESS_GRANTS` is the ground truth for
which in-process principal needs which command. This tool turns that
table into the JSON body `define_policy`'s REST route
(`cora.trust.features.define_policy.route.DefinePolicyRequest`) accepts,
so an operator can pipe it straight into `curl` rather than hand-typing
a `grants` object and risking exactly the drift the table exists to
prevent.

Run it with:

    uv run python tools/gen_policy_grants.py > policy.json
    curl -X POST https://<facility>/policies \\
        -H "Content-Type: application/json" \\
        -d @policy.json

`--conduit-id` defaults to `SYSTEM_LOCAL_CONDUIT_ID` and `--surface-id`
defaults to `SYSTEM_IN_PROCESS_SURFACE_ID`, the two fixed,
seeded-by-migration constants for the deployment's one real Conduit and
its in-process back door. Both are overridable, for a deployment whose
Conduit or Surface differs.

This reads `IN_PROCESS_GRANTS`; it does not write anything back into
`src/`, and nothing in the running app imports this tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from cora.api.in_process_grants import IN_PROCESS_GRANTS
from cora.infrastructure.routing import SYSTEM_IN_PROCESS_SURFACE_ID, SYSTEM_LOCAL_CONDUIT_ID

_DEFAULT_NAME = "System In-Process Policy"


def build_body(*, name: str, conduit_id: UUID, surface_id: UUID) -> dict[str, object]:
    """The `DefinePolicyRequest`-shaped body derived from `IN_PROCESS_GRANTS`."""
    return {
        "name": name,
        "conduit_id": str(conduit_id),
        "surface_id": str(surface_id),
        "grants": {
            str(principal_id): sorted(command_names)
            for principal_id, command_names in sorted(
                IN_PROCESS_GRANTS.items(), key=lambda item: str(item[0])
            )
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=_DEFAULT_NAME, help="Policy.name for the request body")
    parser.add_argument(
        "--conduit-id",
        type=UUID,
        default=SYSTEM_LOCAL_CONDUIT_ID,
        help="Conduit id to bind the Policy to (default: SYSTEM_LOCAL_CONDUIT_ID)",
    )
    parser.add_argument(
        "--surface-id",
        type=UUID,
        default=SYSTEM_IN_PROCESS_SURFACE_ID,
        help="Surface id to bind the Policy to (default: SYSTEM_IN_PROCESS_SURFACE_ID)",
    )
    args = parser.parse_args()
    body = build_body(name=args.name, conduit_id=args.conduit_id, surface_id=args.surface_id)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
