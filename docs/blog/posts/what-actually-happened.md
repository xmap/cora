---
date: 2026-06-27
slug: what-actually-happened
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - runs
  - lifecycle
  - event-sourcing
  - operations
  - system-of-record
links:
  - The Recipe Ladder: blog/posts/the-recipe-ladder.md
  - Derive, Don't Stamp: blog/posts/derive-dont-stamp.md
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - Run module: architecture/modules/run/index.md
---

# What Actually Happened: a run is the record of reality, deviations and all

A tomography scan is fifteen hundred projections long, and it is seven hundred frames in when the storage ring dumps its beam. Another night, an overnight scan still reads "Running" the next morning, hours after a power cut, a dropped network link, and a dead laptop quietly killed it; the operator finds the corpse at the start of shift. A plan describes what was supposed to happen. A Run is the harder, more honest thing next to it: the record of what actually did, including the pause for the beam dump, the exposure that got nudged mid-scan, and the gap between the experiment as imagined and the experiment as it ran.

<!-- more -->

The [recipe ladder](the-recipe-ladder.md) descends from a portable technique down to a single execution, and the Run is the bottom rung, the place where intention finally meets a real beam and real hardware. It would be easy to model that rung as a flag: started, then either succeeded or failed. CORA does not, because that flag throws away everything interesting about the descent from plan to reality. A Run is modeled as a small lifecycle whose whole job is to record the shape of what happened, and three of its moves are where that shape lives: a pause that needs no excuse, a steer that is not a restart, and several honest ways to end.

## A pause needs no excuse

When the beam goes down mid-scan, the operator holds the run; when it comes back, they resume. Both are first-class transitions, and the notable thing is what they leave out: neither one takes a reason.

That is deliberate, and it mirrors how mature control and acquisition systems already treat a pause. A hold is a routine operation, not an incident, and the act of holding is itself the signal. Requiring a typed justification for every beam-down hold would turn an ordinary part of a shift into paperwork, and teach operators to type "beam down" five hundred times until the field meant nothing. So hold and resume stay slim, and a run can cycle between running and held as many times as the night demands, each hold closed by a resume before the run goes on.

A pause need not even wait for a person. CORA ships an optional supervisor, an agent that watches the beam and holds a run on its own when the beam drops, then brings it back once the beam has safely returned. That second half is more careful than it sounds, careful enough to deserve [its own post](no-proof-no-resume.md): a machine may pause beam-on work freely, because pausing can only make the floor calmer, but resuming has to re-earn the full set of checks a fresh start passes before it lets the beam back onto the sample.

## Steer, do not restart

Sometimes the fix is not to wait but to change something. The live slice looks noisy because the exposure is too short; the old reflex is to abort the scan, edit the number, and start over, discarding the frames already collected. CORA lets you steer instead. An adjustment carries a patch, applied to the run's current parameters as an [RFC 7396 JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396), the same merge the system uses at the start of a run to combine a plan's defaults with an operator's overrides. The merged result is then checked against the owning Method's parameter schema before anything is recorded, so you can move the exposure but you cannot move it outside what the technique declared legal. When a Method publishes a schema, an out-of-bounds steer is refused; when it declares none, the adjustment is trusted.

What matters is what does not happen: no new run is created, and nothing restarts. The same run keeps going under revised parameters, the adjustment is stamped with who made it and counted so the history shows how many times the run was nudged, and the seven hundred frames already on disk are not thrown away. Unlike a pause, an adjustment does require a reason, because changing the recipe mid-flight is exactly the kind of deviation a later reader will want explained.

## Three ways to end, and one that needs no words

A run can reach four terminal states, and the difference between them is the difference a flag would erase.

A run that finishes its planned work is completed, and completion is the one ending that carries no reason at all. Success claims itself; there is nothing to explain about a scan that did what it set out to do. The other three endings are exits, and every one of them demands a reason, validated as real text and not an empty string, both at the edge and again in the core so that a script or an automated actor cannot slip a blank past the gate.

A run is stopped when an operator ends it early on purpose and the data collected up to that point is still good. It is aborted in an emergency, the ending that says something went wrong and the result needs review before anyone trusts it. And it is truncated when nobody ended it at all, which is the case worth its own section. Three exits, three different stories, three required explanations; one silent success. Completion claims achievement, and the exits demand an account of themselves.

## The run that died in the night

The overnight scan that still says "Running" is the interesting failure, because the truthful answer is that CORA does not know it died. There is no liveness watchdog, no heartbeat that auto-closes a stale run, and this is a stated design decision rather than a missing feature. A run stays Running in the record until a person says otherwise.

When the operator arrives and finds it, they truncate it, and the truncation carries two distinct timestamps. One is when the truncation was recorded, the moment the operator filed it. The other is the operator's best guess at when the run actually died, which for a weekend outage might be two days earlier. Keeping those two times apart is the whole point: the record does not pretend the run ended when the paperwork was done, and it does not pretend the system caught the failure in the moment. It says, honestly, that the run was interrupted around such-and-such a time and that a human reconciled the books later. A watchdog that auto-closed stale runs would be writing a fact nobody witnessed, dressing a guess as a detection; CORA would rather record that an operator made the call, and when, and roughly when the thing really stopped.

## Why the shape is the point

Put the moves together and the reason for modeling a run this richly comes into focus. An [earlier post](where-cora-fits.md) drew the line between the manufacturing world, which keeps an excellent record in order to prove that reality matched the plan, and exploratory beamline science, where the plan is a hypothesis and the deviation is often the finding. A run built only to certify conformance can be a flag. A run meant to capture exploratory work cannot, because the pauses, the mid-flight steer, and the messy ending are not noise to be discarded; they are frequently the most informative thing about the session. Modeling the lifecycle faithfully is how the record keeps them.

This is also the most carefully tested corner of the system. Every lifecycle verb, start, hold, resume, adjust, stop, abort, truncate, and complete, carries both worked-example tests and property-based tests that assert invariants across a wide space of generated inputs, and the Run aggregate sits in the nightly rotation where its logic is mutated to check that the tests would actually catch a regression. The lifecycle is small on purpose, and held to a high standard precisely because so much of the record hangs off it.

## Honest edges

The model is real and carrying the 2-BM beamline, with limits worth naming. The reasons attached to stops, aborts, and truncations are free-form text today, not a structured taxonomy you could tally across runs. The absence of a liveness watchdog means a dead run really does sit as Running until someone truncates it; honest reconciliation is the design, not automatic detection. A completed run can carry a few provenance fields when a compute runtime conducted it, but on an ordinary acquisition those are empty, and a substantive run summary, frame counts and durations and the like, is still ahead rather than shipped. And the usual caveat holds: this is a pre-1.0 system grounded in a single deployment, so these are claims about a working model rather than a fleet.

## The bottom rung, written down

The ladder is about portability, a technique that travels from one beamline to another. The Run is where that portable intention touches a specific beam on a specific night and becomes a fact. Modeling it as a lifecycle rather than a flag is what lets the system answer, long afterward, not just whether a scan ran but what actually happened to it: where it paused, where it was steered, how it ended, and, when it ended without anyone watching, roughly when it really stopped and who reconciled the record. A plan is what you meant to do. The run is what you did, and a system of record owes the second one at least as much honesty as the first.
