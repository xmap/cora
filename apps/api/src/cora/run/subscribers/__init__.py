"""Run BC event-reaction subscribers.

Reactions the Run BC hosts on the projection worker. First one:
AuthorityRevocationHolderSubscriber (the authority-revocation kill-switch,
reacting to Trust's PolicyGrantRevoked). Add a new subscriber by creating
a module here with a `make_<stem>_subscriber(deps)` factory and
registering it in `cora.run._subscribers.register_run_subscribers`.
"""

from cora.run.subscribers.authority_revocation_holder import (
    AuthorityRevocationHolderSubscriber,
    make_authority_revocation_holder_subscriber,
)

__all__ = [
    "AuthorityRevocationHolderSubscriber",
    "make_authority_revocation_holder_subscriber",
]
