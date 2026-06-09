"""HTTP setup for the Enclosure BC.

`register_enclosure_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

This sub-slice scaffolds the registrar without any slices wired; the
body is intentionally empty. Slice routers and `add_exception_handler`
registrations land as later sub-slices ship their features.
"""

from fastapi import FastAPI


def register_enclosure_routes(app: FastAPI) -> None:
    """Attach Enclosure slice routers and exception handlers to the FastAPI app."""
    _ = app
