---
date: 2026-06-15
slug: how-cora-remembers
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - event-sourcing
  - audit
  - decisions
  - system-of-record
  - pace-layering
links:
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - The Recipe Ladder: blog/posts/the-recipe-ladder.md
  - State (Architecture): architecture/state.md
  - Decision module: architecture/modules/decision/index.md
  - Data (Stack): stack/data.md
---

# How CORA Remembers: an append-only log and no silent decisions

A record you can edit is not really a record. Overwrite a stored value and its past is gone: what it used to say, and why it changed, are simply unrecoverable. Yet those are exactly the things a beamline needs back, long after the fact. Which recipe did this run follow? Who approved the energy? Why was the center of rotation set there? CORA can answer questions like these for the same reason it can be trusted at all: it was built never to overwrite anything in the first place.

<!-- more -->

## The event, not the row

Most software keeps its memory in rows it edits in place: the new value lands on top of the old, and the old is gone. That is efficient, and for a record of work it is the wrong default. CORA inverts it. Every change of state is recorded as an immutable event, appended to a log and never altered. The current state of anything, a Run, a Plan, an Agent, is not stored directly; it is computed by replaying that thing's events in order, an operation called a fold. The approach has a settled name, event sourcing: the log is the system of record, and the state you query is a derived view of it. Nothing is updated in place, so nothing is lost.

You already rely on an event-sourced record. A bank statement is an append-only list of transactions, and your balance is not a number someone edits but a figure derived by adding them up; a refund is a new line, never a quiet change to an old one. A bound laboratory notebook keeps the same rule: strike a line through the mistake, date the correction, never tear out the page. The database underneath CORA does it internally too, writing every change to a log before it touches a table.

The discipline is old, and only the software name is recent. A short lineage of the same idea:

- **c. 1300** Florentine merchants keep full [double-entry ledgers](https://en.wikipedia.org/wiki/Double-entry_bookkeeping), correcting errors with balancing entries rather than erasures.
- **1494** Luca Pacioli prints the method, and accounting has worked that way ever since.
- **2005** Two append-only records arrive in a single year: [Git](https://git-scm.com/) stores history as immutable commits, and Martin Fowler gives the software pattern its name, event sourcing.
- **2009** [Bitcoin](https://en.wikipedia.org/wiki/Bitcoin) launches a public append-only ledger, making the chain-of-records idea widely familiar.
- **2011** LinkedIn open-sources [Apache Kafka](https://kafka.apache.org/), putting the log as the source of truth at industrial scale.
- **2017** Martin Kleppmann's [*Designing Data-Intensive Applications*](https://dataintensive.net/) makes the log-centric view standard reading for system designers.

Event sourcing only promotes that log from a hidden mechanism to the primary record.

## The envelope

Each event has two halves. The payload carries the change itself. The envelope, identical in shape on every event, carries the facts that make a log trustworthy: which tracked entity the event belongs to and what kind of fact it is, its position both within that one stream and across the whole store, the identity of whoever emitted it, and the wall-clock time it happened.

That envelope lets the record be read three ways at once: a subscriber can route an event by its type, a projection can walk the whole store in a stable order, and an auditor can ask who did this and when. The principal that emitted each event lives in the envelope, so attribution is not an afterthought bolted on later. It is structural, present on every fact the system has ever recorded.

## Three invariants

A log is only as trustworthy as the rules it cannot break. CORA leans on three.

The first is that the log is append-only, enforced where the data lives rather than asked for politely in application code. The running application connects to [Postgres](https://www.postgresql.org/) under a database role that may insert events and read them, and nothing else. It cannot update an event and it cannot delete one. A bug in the application, or someone at the application's own console, still cannot rewrite history, because the privilege to do so was never granted. The derived read tables are mutable, since they can always be rebuilt from the log; only the log itself is sealed.

The second is optimistic concurrency by version. Every event carries its position within its stream, and a writer appending a new event states the version it expects to follow. If two writers race, only the one whose expectation still holds commits; the other is rejected and retries against the new reality. There is no last-write-wins, so one update can never silently clobber another.

The third is gap-free ordering. The background workers that build the read models advance only past events that have fully committed, so a reader never sees a newer event appear ahead of an older one still in flight. The order you read is the order that happened.

## Why not just an audit log?

The obvious cheaper version of all this is to keep ordinary mutable tables and bolt an audit log onto the side: a history table, a trigger that records every change. It is a real pattern, and it is weaker than it looks. The audit log is a second copy that has to be kept honest. The live table is still the truth, the log is derivable and optional, and anything with write access to the table can change state without the log agreeing. Event sourcing closes that gap by inverting the two: there is no separate audit log to keep in sync, because the log is the state, and there is no privileged path that edits the truth without being recorded, because editing the truth is not something the system can do.

At the other extreme sits the blockchain, the maximalist append-only ledger, and CORA does not need one. A blockchain buys tamper resistance without a trusted operator, and pays for it with decentralized consensus; a single facility recording its own experiments already has a trusted operator. Its immutability comes instead from the role-level rule from earlier, append and read, never update or delete, with cryptographic event signatures on the way for cases that want a stronger guarantee. Stronger than an audit log, because the log is the record itself; lighter than a blockchain, because it asks no one to reach consensus. That middle is where a system of record for one facility belongs.

## No silent decisions

Recording what changed is half the job. The other half is recording why, and that is a separate, deliberate record called the Decision. Every consequential choice in the system, a human approving a recipe, an operator aborting a run, an AI inferring a result, an agent acting on its own, is written as a Decision: the choice that was made, the rule it was made under, the inputs to that rule, the alternatives that were considered, a confidence and where it came from, and the actor who decided. It is written once, at the moment of the choice, and never edited.

Two things make this more than a log line. First, a Decision is never corrected in place. If a choice turns out to be wrong, or is appealed, superseded, or has to be undone, that lands as a new Decision pointing back at the original and tagged with the kind of transition it is. The original and its correction both survive, so you can always see what was decided and what was decided about it later. It is the ledger's rule applied to judgment rather than arithmetic: correct with a new entry, never alter the old one. Second, a human decider and an AI decider are recorded in exactly the same shape. There is no weaker, separate path for the machine: the record that the RunDebriefer agent classified a scan as a degraded completion has the same structure, and the same standing, as the record that an operator approved the recipe it ran under.

## Reading it back

Because state is a fold over the log, the whole system is replayable: point the fold at a stream and you recover exactly the state that stream was in. Lists, searches, and filters are served not by folding on every request but by projection workers, background processes that tail the log and maintain ordinary query tables off to the side, each advancing a bookmark so it knows where it left off. The read side can be torn down and rebuilt from the log at any time, because it owns no truth of its own.

This is honest about its limits. A single-entity read replays the whole stream every time; there are no snapshots yet, so the cost grows with the length of the stream, and very long-lived records will eventually want them. The Decision's field names already follow [W3C PROV](https://www.w3.org/TR/prov-overview/), the web standard for provenance: a shared vocabulary for stating how something came to be, in terms of which agent performed which activity to produce which entity. That puts a Decision one step from publishable, machine-readable provenance; the full export in PROV's formal ontology form, PROV-O, waits until a consumer asks for it.

## Why this is the slow layer

Return to Brand's phrase. The fast layers of a beamline act in the moment and move on; they are not built to answer questions years later, and should not be asked to. The slow layer exists precisely to remember, and it can only do that if remembering is the one thing it is structurally unable to undo. An append-only log the application cannot rewrite, a decision record that grows by correction rather than erasure, and a state that is always a replay of the two: that is what lets CORA answer, six months on, why this run used that center of rotation and who stood behind the choice. The fast layers learned; the slow layer remembered.
