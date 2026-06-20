---
date: 2026-06-28
slug: no-proof-no-resume
authors:
  - dgursoy
categories:
  - Safety
tags:
  - safety
  - agents
  - automation
  - ai-governance
  - runs
links:
  - No Clearance, No Beam: blog/posts/no-clearance-no-beam.md
  - What Actually Happened: blog/posts/what-actually-happened.md
  - Agents as Principals: blog/posts/agents-as-principals.md
  - Safety module: architecture/modules/safety/index.md
  - Run module: architecture/modules/run/index.md
---

# No Proof, No Resume: a machine may pause the beam, but it has to earn its way back

It is two in the morning and a fifteen-hundred-projection scan is half done when the storage ring drops its beam. Nobody is in the control room. On most setups one of two bad things happens: the acquisition grinds on, writing hundreds of dark, useless frames, or it sits there, technically running, until someone arrives at eight and finds the night wasted. What you want is the obvious human thing: pause when the beam goes, pick back up when it returns. What you do not want is a machine that picks back up at the wrong moment. CORA now does the first, automatically, precisely because it refuses to do the second.

<!-- more -->

This is the active counterpart to two earlier posts. [No Clearance, No Beam](no-clearance-no-beam.md) described the gates a run must pass to start; [What Actually Happened](what-actually-happened.md) described the run's lifecycle, including the pause. This post is about an agent that drives that lifecycle on its own, and about the one asymmetry that makes autonomous control safe to switch on: a machine may wind work *down* freely, but winding it back *up* has to re-earn everything it took to start.

## Winding down is the easy direction

CORA ships an optional supervisor: a small agent that, each tick, reads whether the beam is actually available and decides what to do about each in-flight run. Its first rule is the simple one. When the beam is definitely down while a run is running, it holds the run, and records a decision saying why. That is it. Holding is fail-safe by construction: the worst a buggy hold can do is pause a run that did not need pausing, which wastes a little time and breaks nothing. A machine is allowed to make that call unattended because the call can only ever calm the floor.

The supervisor is off by default, and it is not a safety system. The real interlocks, the search-and-secure, the shutters, the personnel safety system, sit on the floor and are authoritative on their own. The supervisor is a steward of beamtime, not a guardian of life; it reads the same signals a person would and acts a few seconds faster.

## Resuming has to be earned

Bringing a run back is the dangerous direction, and the design treats it that way. When the beam returns, the supervisor does not simply flip the run back to running. It re-checks the entire set of conditions a brand-new run has to satisfy before it may start: a safety clearance still actively covers the work, every hutch the equipment sits in is still permitted, every consumable the method needs is still available, and the beam is genuinely open. Only if all of that holds does it resume.

The important part is *how* it re-checks. It runs the very same check the start path runs, the one [No Clearance, No Beam](no-clearance-no-beam.md) described, from a single shared piece of code. The resume gate cannot drift away from the start gate, cannot grow a loophole the start gate lacks, because there is only one gate. A resume can never put a run back into a state a fresh start would have refused. And it is fail-closed: if any signal is missing or unreadable, not just failing but merely unknown, the run stays held. A clearance that quietly expired while the run was paused is enough to keep it down until a person sorts it out. The supervisor would rather leave a run safely held than resume it on a guess.

## Only its own holds, and never over a person

Two more limits keep the machine in its lane. It will only resume a run it held itself. If an operator paused a run, the supervisor leaves it alone; bringing that one back is the operator's decision, not the machine's. And if a person resumes a run the supervisor had been holding, the supervisor stands down rather than fight them. The human always wins the tug-of-war, in both directions.

There is an honest edge here worth stating: the supervisor tracks which runs it holds in its own memory, so if the process restarts while a run is paused, it forgets that the hold was its own and will not auto-resume it. That is the safe way to fail. A person resumes it instead, exactly as they would have before any of this existed.

## A wobble is not a return

Beam does not always come back cleanly; it can flicker at the edge of a fill or an injection. A supervisor that resumed the instant it saw one good reading, then re-held on the next dip, would flap a run between running and held and make a mess of the record. So resume waits for the conditions to hold steady across a short settle window before it acts. A single good blink is not a return; a stretch of good readings is. This is a small thing that matters a great deal at three in the morning, when the alternative is a run that toggles forty times before dawn.

## It continues; it does not restart

When the supervisor resumes a run, it continues that run; it does not start a new one and it does not rewind. The run keeps its identity, its parameters including any mid-flight adjustments, and the calibrations it was pinned to. The record simply moves from held back to running, with a decision attached explaining that the supervisor judged it safe and why.

What CORA does not claim is to put the detector back at projection seven hundred. CORA is the system of record, not the machine that drives the scan. Whether the acquisition tool picks up where it paused or re-acquires is the tool's behavior on the floor, which CORA observes but does not control. The supervisor's resume is the authoritative "it is safe to proceed again" signal plus the audit of why; making the physical scan continue frame-for-frame is a separate, larger piece of work, and an honest post does not pretend the spine reaches down to the metal.

## An agent, accountable like any other

Everything the supervisor does flows through the same front door a person uses. It is a registered agent with its own identity, as [an earlier post](agents-as-principals.md) described; it issues the ordinary resume command through the ordinary authorization check, with no special path; and every disposition it takes, hold or resume, lands as a decision carrying its evidence and its reasoning. Switching on the wind-up is a deliberate, separate opt-in from switching on the wind-down, so a facility can let the supervisor pause runs for months before it ever lets the supervisor bring one back. When it does resume a run, the question "why did this come back at 02:14, and who decided it was safe" has a stored answer, and the answer names the agent.

## The asymmetry is the point

Autonomous control at a beamline is usually discussed as a single capability: can the machine run the experiment. The more useful question is directional. Letting a machine *stop* beam-on work is easy to trust, because stopping is fail-safe. Letting a machine *resume* it is where the care has to live, because resuming asserts that the world is safe, and an assertion can be wrong. CORA draws that line exactly: the supervisor pauses freely and resumes only after re-proving, from one shared check, the full envelope that a fresh start demands, holding steady, on its own holds, never over a person, and never on a guess. No clearance, no beam. And now: no proof, no resume.
