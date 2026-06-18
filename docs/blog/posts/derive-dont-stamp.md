---
date: 2026-06-21
slug: derive-dont-stamp
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - event-sourcing
  - projections
  - cqrs
  - state
  - read-models
links:
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - What a Beamline Is Made Of: blog/posts/what-a-beamline-is-made-of.md
  - State (Architecture): architecture/state.md
  - Domain model: architecture/model.md
---

# Derive, Don't Stamp: what a ledger lets you stop storing

Ask an ordinary system a simple question, is this detector active, and it usually answers by reading a column. Somewhere a row has a `status` field, and at some earlier moment a piece of code ran an update to set it. The answer is trustworthy exactly to the degree that every code path which should have set that column actually did. CORA answers the same question a different way: it has no status column to read. It looks at what happened to the detector and lets the most recent fact speak for itself. This is a small inversion with large consequences, and it is the quiet habit that an append-only log makes possible: derive the answer from the record of facts, rather than stamping the answer into a field of its own.

<!-- more -->

An [earlier post](how-cora-remembers.md) described the foundation: CORA stores immutable events, and the current state of anything is a fold over those events rather than a row it edits in place. This post is about what that buys you on the read side. Once the log is the source of truth, a surprising amount of what other systems store and maintain by hand turns out to be derivable, and CORA leans into that on purpose. The discipline has a slogan: derive, don't stamp.

## The cost of stamping

Stamping is the ordinary way: when something changes, write the consequence into its own field. Set `status = 'active'`. Bump `updated_at`. Increment a count. Write the current location into a column on the thing that moved. Each of these is convenient to read later, and each is a second copy of a truth that already exists somewhere else.

The trouble with a second copy is that it has to be kept in sync, and keeping things in sync is where bugs live. The status column drifts out of step with reality because one code path forgot to set it. The cached count double-counts after a retry. The `updated_at` is stale because an update slipped through a side door. None of these is exotic; they are among the most common bugs in ordinary software, and they all have the same shape: a stored value and the reality it was supposed to mirror have quietly diverged, and nothing forced them back together. Every stamped field is a standing promise to update it everywhere, forever, and promises like that are broken by ordinary human oversight.

## What CORA derives instead

When the log is the source of truth, whole categories of these fields simply stop existing, because the answer they held can be computed from the events that are already there.

**Status is the event type, not a field.** When CORA needs to know an Asset's lifecycle state, it does not read a stored status. It folds the Asset's events, and the *type* of the most recent lifecycle event is the answer: the fact that an `AssetActivated` event happened is what "Active" means. The word "Active" is never written into any event payload. There is no status column to forget to update, because there is no status column. The event that occurred is the status, and the event cannot be un-occurred.

**"When" comes from the event's own timestamp.** Ask when a device was commissioned and CORA reads the timestamp of the event that commissioned it, the moment recorded on the `AssetRegistered` event itself. There is no separate `commissioned_at` that someone had to remember to set at registration time; the registration event already carries the moment it happened, so the date is read off the fact rather than stamped beside it. The same holds for "when was this last signed" elsewhere in the system: the answer is the timestamp of the signing event, computed when the read model is built, not a field maintained on the side.

**"Where" is a projection, not a field on the thing.** You might expect an Asset to carry a field saying which mount it sits in. It does not. The fact that an asset was installed lives on the mount's own install and uninstall events, and the question "where is this asset right now" is answered by a small read model that tails those events and keeps a location table up to date. The asset itself stays ignorant of its location, because that fact belongs to the history of installations, not to the asset. Asking where something is becomes a query against a derived table, not a read of a field that an install operation had to remember to write.

**Lists, counts, and searches are projections.** "All the active assets," "every run this month," "datasets awaiting attestation" are not maintained by incrementing counters and appending to lists as things happen, the way a stamping system would. They are projections: background workers that read the log in order and keep ordinary query tables current off to the side. Each bounded context has its own, and each can be torn down and rebuilt from the log at any time, because it owns no truth of its own. The read tables are a convenience for fast queries, not a second record that could disagree with the first.

## Why derived state cannot drift

The reason this is more than a style preference is that a derived answer has no independent existence to drift from. A status column can fall out of step with reality because it is a separate thing that must be deliberately maintained. A status computed from the latest event cannot fall out of step, because there is nothing separate: it is just a way of reading the events, recomputed each time from the one source of truth. The bug class disappears, not because the code is more careful, but because the thing that used to be careless is no longer there to get wrong. And because every read model is rebuildable from the log, a projection that does drift, through a bug in the projection itself, is repaired by replaying the log, not by hunting down and hand-patching corrupted rows.

## When CORA does write it down, and why that is different

The slogan is "derive, don't stamp," not "never write anything down," and the difference between the two is the most important idea here.

Some things genuinely cannot be derived, because they did not come from prior facts. The exact moment a command was handled, an identifier that was generated, the free-text reason an operator typed, a reading taken from an instrument: these enter the system from outside, and CORA captures them into the event at the moment they happen. That is not stamping in the bad sense; it is recording a fact. The line is between a *fact that occurred*, which the event must carry because nothing else can, and a *consequence of facts*, which should be derived because the facts already imply it.

There is also a deliberate middle case worth being honest about. Sometimes CORA does write a computed value into an event, on purpose. When a run starts, the parameters it will actually use are resolved by merging several layers of defaults and overrides, and that resolved set is frozen into the run's start event as a snapshot. That looks like stamping a derived value, but it is the opposite of the drift problem, because the event is immutable. The snapshot is not a current value that must be kept in sync; it is a permanent record of exactly what the parameters were at the instant the run began, preserved even if every upstream default changes afterward. Freezing a point in time into an immutable event is faithful by construction. The danger was never writing a derived value down; it was writing it into something mutable that then has to be maintained.

So the discriminator is clean. Current state that is a consequence of history gets derived from the log. Facts that arrive from outside, and point-in-time snapshots that must be frozen as they were, get recorded into immutable events. Neither of those can drift: the first has no independent copy, and the second cannot be changed.

## The trade-off

This is not free, and it would be dishonest to pretend otherwise. Deriving state means paying compute to recompute it: every command folds an aggregate's events to reconstruct its current state, and every list query is served by a projection that had to be built and kept current. CORA pays the first cost per command and the second with background workers. The honest edge, the same one the memory post admitted, is that folding a single long-lived stream gets more expensive as the stream grows, and CORA does not yet take snapshots to bound that cost; very long histories will eventually want them. Some derived views are also simply deferred until a use case asks for them, like asking for every device transitively beneath a beamline rather than just its direct children. Deriving trades storage and the risk of drift for compute and the need for projections. For a system whose whole purpose is a record you can trust years later, that is the right trade, but it is a trade.

## The habit

Underneath the examples is a single habit. When a new fact about the world arrives, ask what actually happened and record that, the bare event, the thing that cannot be reconstructed any other way. Then resist the urge to also write down everything that follows from it. The status, the timestamp, the location, the count, the list: those are consequences, and consequences can be derived. A system built this way stores less, and the less it stores, the less it can be wrong about. The log carries the facts; everything else is just a way of reading them.
