"""Shared-kernel layer: cross-BC value objects and pure helpers.

Every module here has zero `cora.*` imports outside `cora.shared.*` itself:
the purity test that distinguishes shared-kernel from infrastructure. These
are domain primitives (Identifier VOs, NewType identity aliases, bounded-text
validators, JSON Schema helpers, canonical-JSON / content-hash machinery)
usable from any BC without booting a kernel, opening a connection pool, or
touching a port.

Layer dependency direction: `BCs -> infrastructure -> shared`, plus
`BCs -> shared` directly. `cora.shared` itself depends on nothing under
`cora.*`. Pinned by `apps/api/tach.toml` and architecture fitness tests.

Modules that depend on ports, the kernel, or adapters belong in
`cora.infrastructure`, not here.
"""
