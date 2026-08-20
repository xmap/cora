"""Vertical slices owned by the Data BC.

Slices ship per command + read side:
  - 7a: register_dataset, get_dataset
  - 7b: discard_dataset (Registered -> Discarded terminal)
  - Distribution: register_distribution, discard_distribution
    (guarded confirm-before-purge: requires a Verified sibling on a
    different tier and a non-Discarded parent Dataset),
    mark_distribution_stale (records a fact about the world, not a
    deliberate act CORA can refuse: the only guard is structural, a
    target already Discarded)
  - Attestation: record_attestation (ChecksumVerified, fact-chain genesis)
"""
