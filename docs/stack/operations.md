# Operations

For implementers picking deployment and developer tooling. Each row names a role, the current pick, and the trigger that would force a swap.

## Deployment

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Build backend | hatchling | Standard PEP 517, uv-friendly | Workspace tool requiring different backend |
| Container image | SHIPPED | `apps/api/Dockerfile`; the build command and the three non-negotiable image facts are on the [Deployment page](deployment.md#container-image) | Registry and orchestrator remain deferred |
| Runtime target | Deferred (Kubernetes, Cloud Run, ECS, bare VMs) | Not deployed beyond local dev | First non-local deployment |
| Image registry | Deferred (ghcr, Docker Hub) | Tied to runtime-target pick | Locked alongside runtime target |

## Tooling

| Role | Pick | Why |
| --- | --- | --- |
| Package manager | uv | One fast tool replaces pip + virtualenv + pip-tools |
| Lint + format (Python) | Ruff | One tool, fast, growing rule coverage |
| Type checker | Pyright (strict) | Strictest available; structural typing aligns with `Protocol` ports |
| Test runner | pytest + pytest-asyncio | Python standard; `--import-mode=importlib` for `src/` layout |
| HTTP test client | httpx | FastAPI's `TestClient` rides on it |
| Integration test isolation | testcontainers (Postgres) | Fresh Postgres per run; mirrors prod schema via Atlas |
| Import-boundary linter | tach | Enforces BC isolation at import time |
| Pre-commit | pre-commit | Hooks for lint, format, and type-check on commit |
| Local container runtime | Docker + docker-compose | Postgres + pgvector for local dev |
| CI | GitHub Actions | Repo on GitHub; standard |
| Docs site generator | MkDocs Material | Renders these docs, published to GitHub Pages. The version is pinned in exactly two places that must agree, `.github/workflows/docs.yml` and the `MKDOCS` variable in the `Makefile`; this row deliberately names no number, because a third copy is a third thing to drift | Authoring needs MkDocs cannot meet (versioned docs, heavy JS components) |
