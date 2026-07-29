# Deferred

For tracking what we haven't picked yet and why. Each row names a category, the candidate set, and the trigger that would force a decision.

## Infrastructure

| Pick | Candidates | Trigger |
| --- | --- | --- |
| Streaming bus | NATS JetStream vs in-process | First cross-BC saga |
| Cache | Redis vs in-process | First read pattern that needs it |
| Search index | Meilisearch vs Postgres FTS | First user-facing search query |
| File / blob storage | filesystem vs S3-compatible (MinIO, R2, S3) | First non-local Dataset volume |
| Container orchestration | Helm, Argo CD | First non-local deployment. The image itself has landed (`apps/api/Dockerfile`); what runs it has not. |
| Snapshot store | In-events vs sidecar table | Fold-on-read becomes a measurable bottleneck |
| Outbox | Table-based vs NOTIFY-only | First cross-process consumer needing at-least-once |
| Background scheduler | in-process (current) vs APScheduler vs Temporal | First job that needs to outlive a process. That trigger has FIRED once, for backups, and was answered at the host layer rather than in the application: `infra/backup/systemd/` ships the timers (inert until HOST-5 answers). This row remains open for the first APP-internal job needing to outlive a process |
| Backup repository target | local disk vs facility share vs S3-compatible | Where the 2-BM host can durably write. The tool is picked and does not change with the answer (`repo1-type` in `infra/backup/pgbackrest.conf`), but two decisions ride along: a credential, for the S3 and SFTP targets though not for a mounted share, which ties this to secrets management; and repository encryption, which is fixed at stanza creation and cannot be added to an existing repository |
| Secrets management | Vault, cloud, sealed-secrets | First non-local deployment |
| TLS / load balancer | nginx vs Caddy vs cloud LB | Deployment chooses its proxy |

## Application

| Pick | Candidates | Trigger |
| --- | --- | --- |
| Authz engine | SpiceDB vs OpenFGA | First non-Cedar authz rule |
| Embedding / vector workload | pgvector (in store) vs dedicated index | First embedding workload (no vector column today) |
| Versioning / release | hatch + setuptools_scm vs custom | First external consumer of the API or library |

## Standards and publishing

| Pick | Candidates | Trigger |
| --- | --- | --- |
| Asset persistent ID profile | PIDINST profile vs raw DataCite Schema 4.6 `Instrument` resourceType vs ePIC Handle | First Asset that needs publication-quality cross-facility identity (paper citation, cross-facility share). PIDINST adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026); CORA + APS would be peer #2. |
| Release-hygiene bundle | CycloneDX SBOM (Syft) + Sigstore (PyPI Trusted Publishing or cosign on containers) + SLSA L1-L2 (GitHub Actions native attestations) + in-toto attestation envelope (cross-trust egress) | CORA's release / distribution surface decided (PyPI wheel? container image? source-only?) |
| Experiment-bundle format | RO-Crate 1.2 (Process Run Crate / Workflow Run Crate profile) vs raw HDF5 + sidecar metadata | First external publishing of an experiment bundle (Zenodo, institutional repository, MAX IV data portal) |
