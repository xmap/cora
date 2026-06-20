---
date: 2026-06-25
slug: the-banner-that-warns
authors:
  - dgursoy
categories:
  - Safety
tags:
  - caution
  - tribal-knowledge
  - operations
  - event-sourcing
  - system-of-record
links:
  - No Clearance, No Beam: blog/posts/no-clearance-no-beam.md
  - What a Beamline Is Made Of: blog/posts/what-a-beamline-is-made-of.md
  - Agents as Principals: blog/posts/agents-as-principals.md
  - Caution module: architecture/modules/caution/index.md
  - 2-BM cautions: deployments/2-bm/cautions.md
---

# The Banner That Warns But Never Blocks: tribal knowledge that reaches the console without standing in the way

Every beamline runs on a second body of knowledge that never made it into a manual. The Aerotech rotary stage at 2-BM misses its index pulse on the first home after a power cycle, so you home it, wait five seconds, and home it again. After the hexapod controller reboots, every axis comes back correctly except Y, whose dial resets to zero while the encoder still reads 350, and if you command a Y move before fixing it by hand you earn a drive error and another reboot. None of this is a fault. None of it is in the vendor documentation. It is the stuff the last shift learned the hard way, and it usually lives in a sticky note on a monitor, a thread in a chat channel, or the head of whoever happens to be on shift. Which means that on the night the right person is not on shift, it does not exist at all.

<!-- more -->

The [last post](no-clearance-no-beam.md) was about the system saying no. A run will not start unless an active safety clearance covers it and every hutch it touches is permitted, and those are hard refusals with no override button. This post is about the other half of the same instinct, and it is deliberately the opposite. Some things the system should be able to stop. Most things it should only tell you about. A beamline's folklore is the second kind: you want it in front of the operator at the moment it matters, and you almost never want it to block the work. CORA models that second kind as a Caution, and the most important fact about a Caution is the thing it cannot do.

## A caution is the sticky note, given a lifecycle

A Caution is an operator-authored note attached to a piece of equipment or a procedure: the quirk, plus what to do about it. The aggregate is deliberately small. It points at one target, either an Asset or a Procedure. It carries a category drawn from a closed list of six, the kinds of thing that actually recur at a beamline: wear, calibration, wiring, an operational window, an interlock quirk, a procedure gotcha. It carries a body of free text, a set of free tags for whatever the six categories do not capture, and an optional expiry for a quirk you expect to age out.

Two design choices give it more spine than a sticky note. The first is that the workaround is a required field, not an optional one. A Caution that records only "the hexapod locks up under sustained load" is logbook spam; a Caution has to also say "recover by running the hexapod reboot routine," because the whole point is to hand the next operator the fix, not just the symptom. The second is a small lifecycle. A Caution is Active when it is written. It can be Superseded, when a newer note revises its text or its workaround, in which case the old one is marked Superseded and a fresh child takes its place with the lineage preserved, so the history of how the advice evolved stays readable. Or it can be Retired, for one of three stated reasons: the problem was resolved, it no longer applies, or it was filed against the wrong thing. There is no review board and no approval ceremony. The author is the operator who saw the issue, and that is the entire authority the note needs.

## The missing rung is the whole design

A Caution carries a severity, and the severity ladder is where the architecture shows its hand. It has three rungs: Notice, an informational note; Caution, something that will not block but may bite; and Warning, something the safety office would care about but has not formalized. The ladder is borrowed from the ANSI Z535 signal-word standard, the Notice / Caution / Warning / Danger sequence on the labels you have seen on industrial equipment, with one change. CORA drops the top rung. There is no Danger.

That omission is not a gap; it is the boundary drawn in the open. The authority to actually stop work lives in exactly one place, the safety clearance from the last post, and a Caution is by construction not that place. If the severity ladder had a Danger rung, a Caution would either have to start blocking, which would defeat the reason this part of the system exists, or it would dishonestly imply a power it does not have. So the ladder stops one notch short, and the shape of the ladder tells you what the module is for. Tribal knowledge informs. Clearances and interlocks block. The two never blur into each other, and the absence of a single enum value is what keeps them apart.

## It never blocks, but it never just vanishes

Here is where a Caution is more than the banner you are used to. On most systems a warning is a modal you click past, and the moment you dismiss it, it is gone, with no trace that it was ever shown. CORA's caution never blocks you either, but it also never simply disappears, because the act of starting work captures it.

When a run starts, the decider looks up every Active Caution covering the run's scope and writes a snapshot of them onto the run's start event itself: the quirk, an excerpt of its text, and its workaround, frozen into the permanent record of that run. It does not pause. It does not require a checkbox. If nothing applies, the snapshot is simply empty, and that empty snapshot is itself a pinned fact, the non-blocking contract made explicit rather than assumed. A retired caution is left out, because only what was Active at that moment belongs on the record. The run starts regardless, every time.

This is why the acknowledgement does not live on the Caution. There is no per-operator "seen it" flag accumulating on the note, because the meaningful record is not "someone dismissed this warning" but "this run was started while this advice was in force." The ack rides on the run that consumed it. Six months later, the question is not whether a banner flashed; it is which quirks were known and standing when this exact scan was taken, and that question has an answer in the run's own history. The warning let the work through and stayed on the record anyway.

## Surfaced where the decision is made

A note is only useful if it reaches the person at the moment they can act on it, so a Caution surfaces at the points where work begins and on the detail page of the thing it targets, rather than in a separate feed nobody reads. The scope is a little wider than an exact target match: a quirk filed against a controller still reaches a run that drives the stage that controller runs, because the lookup follows the equipment's own relationships. The Y-dial quirk at 2-BM, filed against the hexapod, surfaces on any run that touches the hexapod, including the reboot procedure itself, so the operator who just rebooted is reminded to fix the dial before the first Y move, at exactly the moment that reminder is worth something.

## A caution does not have to start with a human

The author of a Caution is usually the operator who got bitten, but it does not have to be. CORA seeds a drafting agent whose job is to read what happened and propose tribal knowledge: a recurring stall, a recovery that keeps working, a gotcha worth writing down. As [an earlier post](agents-as-principals.md) described, that agent is a principal with its own identity, and what it produces is a Decision, recorded with its reason and the evidence behind it. What it cannot do is make the note binding on its own. The proposal becomes an Active Caution only when a person promotes it, the same identity model applied to a machine: an agent may suggest the folklore, a human decides it counts.

## Honest edges

The non-blocking stance is the design, not a missing feature, and it is worth being precise about its limits.

A Warning-severity Caution that keeps accumulating evidence is a natural candidate to become a formal safety clearance, the kind that does block. Today that is a hint and nothing more: there is no mechanism that promotes a Caution into a Clearance, and the judgment to formalize a recurring hazard stays a human one, made through the safety workflow from scratch. Cautions also do not yet attach to runs or to samples; the targets are equipment and procedures, because a note about a single short-lived run is rarely actionable and sample-level hazards belong to a different part of the system. And the usual caveat holds: this is a pre-1.0 system grounded in a single deployment, so these are claims about a working model rather than a fleet.

## Two ways to be told something

Put this beside the previous post and the pair completes a thought. A system of record that is worth trusting has to be able to tell an operator something at the moment of action, and there are exactly two honest ways to do it. One can refuse, and own the weight of refusing, which is the clearance and the interlock. The other can only inform, and must never quietly grow teeth, which is the caution. CORA keeps them in separate modules with a line drawn between them so clearly that you can read it off a missing rung on a severity ladder. The folklore that used to evaporate when the right person was off shift now reaches the console every time, carries its own fix, and stays on the record of the work it accompanied, without ever once standing in the way.
