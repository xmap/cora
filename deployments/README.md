# Deployments

The descriptors for CORA's real deployments: `<slug>/beamline.yaml` per beamline, `<slug>/site.yaml` per facility. The docs build renders these directly (`scripts/beamline_descriptor.py`, `scripts/site_descriptor.py`, `scripts/mkdocs_hooks.py`), and a handful of `apps/api` fitness tests validate against them.

Two directories today: `2-bm` (CORA's one real, operational deployment) and `aps` (the Facility record 2-BM belongs to). That is deliberate, not partial: CORA models further beamlines, at APS and elsewhere, from public source, to test that the domain model generalizes, but a beamline CORA has no operational relationship with is not a deployment. That corpus lives in the private [`xmap/descriptors`](https://github.com/xmap/descriptors) repo instead, kept out of both this directory and the public docs site.
