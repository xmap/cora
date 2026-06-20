---
date: 2026-06-26
slug: undo-is-a-lie
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - event-sourcing
  - immutability
  - compensation
  - retraction
  - audit
  - system-of-record
links:
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - The Right to Be Forgotten: blog/posts/the-right-to-be-forgotten.md
  - Derive, Don't Stamp: blog/posts/derive-dont-stamp.md
  - State (Architecture): architecture/state.md
  - Data module: architecture/modules/data/index.md
---

# Undo Is a Lie: how you take something back on a log that cannot forget

You published a reconstruction at the end of a beamtime, marked it production-grade, and handed the dataset on to whoever needed it. A week later you realize it should never have carried that grade: the run behind it was off, or a calibration it leaned on was wrong. On almost any system, the reflex is obvious. Delete it. Roll it back. Press undo. But CORA is built on a log that physically cannot delete anything, where the database role the application runs as is granted exactly two rights on the event table, read and append, and is refused update, delete, and truncate at the boundary. So the undo button is not disabled. It does not exist. The question becomes interesting: what do you press instead?

<!-- more -->

An [earlier post](how-cora-remembers.md) described why the log works this way: a system whose job is to remember, faithfully and for a long time, cannot also be a system that quietly rewrites its own past. Immutability is the whole point. But immutability raises a question it does not answer, and it is the question every real operation eventually asks. Mistakes happen, grades get revised, equipment is retired, access is pulled. If you cannot erase, how do you take something back? CORA's answer is a small family of operations it calls compensation, and the shape they share is the subject of this post. Taking something back, on an append-only log, is not an act of deletion. It is an act of declaration.

## Retraction is a new line, not an erased one

Start with the dataset. To take back that production grade, an operator demotes it, and what happens is exactly one thing: a new event, "this dataset is retracted, and here is why," is appended after the event that once said "this dataset is production-grade." The original is not touched. It still says what it said, still sits where it sat, still reads as true of the moment it was written, because it was true then. The new line is true now. The history does not lie in either direction; it simply records that the trust level changed, and when, and at whose hand.

Notice what does not happen. The bytes are not deleted, because CORA never held them; the dataset's files live wherever their storage URI points, untouched. The dataset's own lifecycle is not disturbed either. Demotion moves a separate axis, the trust level, from production down to retracted, and leaves everything else exactly as it was. This is the model a scientific publisher uses for a retracted paper: the paper does not vanish from the record, it carries a retraction notice, and the two together are more honest than a blank space where the paper used to be. A reader who finds a result built on that dataset can follow it to the retraction and understand what happened, which is precisely what a silent delete would have stolen from them.

## Four things it is not

It is tempting to file this under a word we already know, but compensation is none of the four it most resembles, and the differences are the design.

It is not **cancel**. Cancel stops something that is still happening; compensation acts on something already finished and committed. You do not cancel a published dataset, you retract it.

It is not **retry**. Retry re-issues a command hoping for a better outcome and leaves no particular trace of the attempt. Compensation is a distinct, recorded fact, and most of these operations are strict about it: ask to retract a dataset that is already retracted and the system refuses with a conflict rather than pretending the second attempt did something.

It is not **soft-delete**. Soft-delete hides a row behind a flag and teaches every query to look away. Compensation hides nothing. The retracted dataset is still fully present and fully readable; what changed is a fact added on top, not a fact concealed underneath.

It is not **rollback**. Rollback removes history to reach an earlier state. Compensation can only move forward, because the database will not let it move any other way. There is no version to roll back to and no row to remove; there is only the next line you are allowed to write.

## The same shape in four corners of the system

The dataset is the clearest case, but the pattern repeats wherever something needs taking back. A consumable supply that is spent or contaminated, a liquid-nitrogen dewar pulled from service, is deregistered: a tombstone event marks it decommissioned, carrying the status it held just before, while its whole history stays on the log. A federation permit or a signing credential that should no longer be honored is revoked, flipped to a terminal revoked state by an appended event. A tool granted to an automated agent is revoked by removing it from the agent's allowed set. Five operations, in four different parts of the system, none of which deletes anything; each adds the one terminal fact that says "this no longer stands," on its own aggregate's stream.

The family resembles itself but is not uniform, and the differences are worth stating plainly rather than smoothing over. Where a reason belongs, it is taken seriously: demoting a dataset and deregistering a supply both require a non-empty operator reason, validated twice, once at the edge and once again in the core, so "why was this taken back" is a field on the permanent record, not a guess. The other operations are lighter: revoking a permit or a credential accepts an optional note, and revoking a tool from an agent records who did it, through the event's own attribution, but not why. The agent case is the real outlier in two more ways. It is the one operation that is idempotent rather than strict, revoking a tool the agent never held simply does nothing and records nothing, and it is a change to a configuration set rather than a lifecycle, so it governs which tools a future invocation may reach rather than reaching into one already in flight.

## Why nothing cascades

The most consequential choice in the whole family is a thing it deliberately does not do. Demoting a dataset does not automatically demote the datasets derived from it. Revoking a credential does not reach out and invalidate the signing seals that point at it. Each compensation touches exactly one aggregate and stops.

This looks like a gap until you see the two reasons behind it. The first is structural: in this system each aggregate is the sole writer of its own history, and a decider that reached into a peer's stream to cascade a change would break that boundary, coupling one part of the system to the internal state of another and making the log much harder to reason about. The second is a matter of judgment. An automatic cascade is a blunt instrument for a decision that is usually anything but blunt; whether a derived result is also invalid is a question a person should answer, dataset by dataset, not a side effect that fans out the moment one demotion lands. So cascades, when they are wanted, are explicit operator actions, each one its own recorded line. What protects a consumer in the meantime is not a push from the retraction but a check at the point of use: a run will not start on a decommissioned supply, because the start gate reads its status and refuses, exactly as the [safety gates](no-clearance-no-beam.md) refuse on a missing clearance.

## Honest edges

The model is real and carrying the 2-BM beamline, with limits worth naming.

Reason capture is not yet uniform across the family, as described above, and where a reason is recorded it is free-form prose, not a structured taxonomy you could tally. Because nothing cascades, a stale dependent can outlive the thing it depended on until an operator addresses it; the safety net is the use-time check, not an automatic sweep. The immutability guarantee binds the application's own database role, which is the role that matters at runtime, but it is a role-level guarantee, not a claim of tamper-proofing against a database administrator with owner rights. And there is exactly one place CORA does delete, by deliberate exception: erasing a person's [personal data](the-right-to-be-forgotten.md) scrubs a separate, mutable vault while still appending an event to the immutable log to record that the erasure happened, so even the one sanctioned deletion leaves a forward-only trace. As always, this is a pre-1.0 system grounded in a single deployment, so these are claims about a working model rather than a fleet.

## A correction you can read

The undo button is a small lie even on ordinary software; most of the time it just hides the last thing you did and hopes you do not look. On a system whose entire purpose is to remember what was done and why, the honest move is the opposite one: make the correction itself a thing worth remembering. You do not reach back and erase the mistake. You write the next line, the one that says it was a mistake, who decided so, and when, and you leave the original exactly where it stands. Taking something back becomes a part of the record instead of a hole in it, which is the only kind of undo a system of record is allowed to offer.
