"""Access BC adapters: concrete implementations of infrastructure ports.

`EventStorePrincipalLivenessLookup` answers the liveness question for
any principal by folding its Actor stream, so callers that cannot import
Access (the Trust BC gate, notably) can still read `Actor.active`.
"""

from cora.access.adapters.event_store_principal_liveness_lookup import (
    EventStorePrincipalLivenessLookup,
)

__all__ = ["EventStorePrincipalLivenessLookup"]
