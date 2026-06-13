"""Trust bounded context.

Owns the authorization concerns of CORA: which principals are allowed
to do what, where. Authentication (who a principal *is*) lives in the
Access BC. Trust answers "may this principal issue this command via
this conduit" against `Zone` / `Conduit` / `Policy` aggregates.

Four aggregates: `Zone` (security boundary), `Conduit` (a network
path between principals and zones), `Surface` (an API surface like
HTTP or MCP), and `Policy` (the permission grant). The real
`TrustAuthorize` adapter replaces the `AllowAllAuthorize` stub once
a `Policy` exists; `verify_bootstrap_seed_present` enforces seed
presence at startup.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>_<noun>/   -- vertical slice: command + decider + handler + route + tool
    wire.py                   -- TrustHandlers bundle + wire_trust(deps)
    routes.py                 -- register_trust_routes(app)
"""

from cora.trust._bootstrap import (
    SYSTEM_BOOTSTRAP_POLICY_ID,
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    verify_bootstrap_seed_present,
)
from cora.trust._projections import register_trust_projections
from cora.trust.authorize import TrustAuthorize
from cora.trust.build_authorize import build_authorize
from cora.trust.errors import UnauthorizedError
from cora.trust.routes import register_trust_routes
from cora.trust.tools import register_trust_tools
from cora.trust.wire import TrustHandlers, wire_trust

__all__ = [
    "SYSTEM_BOOTSTRAP_POLICY_ID",
    "SYSTEM_HTTP_SURFACE_ID",
    "SYSTEM_MCP_STDIO_SURFACE_ID",
    "SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID",
    "TrustAuthorize",
    "TrustHandlers",
    "UnauthorizedError",
    "build_authorize",
    "register_trust_projections",
    "register_trust_routes",
    "register_trust_tools",
    "verify_bootstrap_seed_present",
    "wire_trust",
]
