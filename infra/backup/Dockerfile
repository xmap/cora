# Postgres with pgBackRest, for backup and point-in-time recovery.
#
# ## Why this derives from the pgvector image
#
# It is the SAME base the rest of CORA runs against: infra/docker-compose.yml
# for local dev and tests/conftest.py for the test containers both name
# pgvector/pgvector:pg18. A backup tool validated against a different
# Postgres build is a backup tool validated against a different database.
#
# ## Why pgBackRest lives IN this image and not in a sidecar
#
# Backup reads PGDATA directly and restore writes into it. Neither goes
# through a socket, so pgBackRest has to share a filesystem with the
# cluster. In a container deployment that means the same image; on a VM
# or a workstation it means the same host, installed from the distro
# package.
#
# pgbackrest.conf carries the same OPTIONS on either path, but a VM needs
# two things this image provides for free: pg1-path differs, and local
# socket authentication differs (this image writes `local all all trust`
# into pg_hba.conf, where a package-managed Postgres ships `peer`). Both
# are called out in pgbackrest.conf against the settings they affect.

ARG POSTGRES_IMAGE=pgvector/pgvector:pg18
FROM ${POSTGRES_IMAGE}

# pgBackRest comes from the PGDG apt repo, which this base image already
# configures (/etc/apt/sources.list.d/pgdg.list). The version is carried
# as an ARG rather than left floating so an image rebuild does not
# silently change the tool that owns the restore path. PGDG eventually
# drops old point releases; when that breaks the build, bump this
# deliberately rather than unpinning it:
#
#   docker build --build-arg PGBACKREST_VERSION=<new> ...
ARG PGBACKREST_VERSION=2.58.0-1.pgdg12+1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        "pgbackrest=${PGBACKREST_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# The repository and log paths must exist and belong to postgres BEFORE
# the first archive_command fires. Postgres runs archive-push as the
# postgres user during normal operation, and a directory it cannot write
# turns every WAL segment into an archiving failure, which in turn makes
# Postgres retain WAL until the volume fills. Creating the repository
# path here also decides the OWNERSHIP of the named volume Docker
# initialises from it; without this the volume is root-owned and every
# archive-push fails.
#
# The spool path is unused by the current configuration, which does not
# enable archive-async. It is created so that turning archive-async on is
# a one-line change in pgbackrest.conf rather than a puzzle.
RUN install -d -m 0750 -o postgres -g postgres \
        /var/lib/pgbackrest \
        /var/log/pgbackrest \
        /var/spool/pgbackrest
