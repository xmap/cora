---
date: 2026-06-24
slug: no-clearance-no-beam
authors:
  - dgursoy
categories:
  - Safety
tags:
  - safety
  - authorization
  - clearance
  - enclosure
  - isa-99
  - system-of-record
links:
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - Derive, Don't Stamp: blog/posts/derive-dont-stamp.md
  - What a Beamline Is Made Of: blog/posts/what-a-beamline-is-made-of.md
  - Safety module: architecture/modules/safety/index.md
  - Enclosure module: architecture/modules/enclosure/index.md
  - 2-BM enclosures: deployments/2-bm/enclosures.md
---

# No Clearance, No Beam: what it means for a record to be able to say no

The operator has done everything right. The sample is mounted, the recipe ladder is defined, the beam is up, and the scan is one keystroke away. They press start, and the system says no. Not a yellow banner they can click past, not a checkbox to acknowledge and move on: a flat refusal, because the safety form covering this particular sample has not yet been activated. A few minutes later a reviewer walks the form through its last approval, the operator presses the very same start again, and this time it runs cleanly, with no edits and no workaround. Nothing about the experiment changed. What changed is that the paperwork became real, and the system was watching for exactly that.

<!-- more -->

Most of these posts have been about remembering: an [event log that never forgets](how-cora-remembers.md), a [calibration that grows by revision](what-calibrated-means.md), a [run recorded as what actually happened](the-recipe-ladder.md). This one is about the opposite reflex. A system of record earns the word "record" only if it can also decline to write one, because some work should never have happened, and a faithful history of unsafe work is worth very little. The interesting question is where that refusal should live. The answer CORA settled on is that the paper bureaucracy every synchrotron already runs, the experiment safety form and the hutch interlock, becomes a set of preconditions enforced in code at the exact moment a run starts.

## A clearance is a safety form with teeth

Every facility has its own name for the form. At the APS it is the Experiment Safety Assessment Form; at NSLS-II the Safety Approval Form; at the ESRF an A Form; at MAX IV a DUO submission and an experimental safety review; at Diamond a risk assessment and a local hazard declaration; at DESY a DOOR form; at SLAC a beam time request; at SPring-8 Form 9. CORA models all of them with one aggregate, the Clearance, and seeds the ten baseline form types into every deployment automatically so the same machinery hosts a clearance at whichever facility CORA federates with. A Clearance is the digital twin of one filled-in form: the hazards it declares, the things it covers, and where it is in its review.

The "where it is in its review" part is the teeth. A Clearance walks an eight-state review chain, from `Defined` when it is first registered, through `Submitted` and `UnderReview` as reviewers pick it up, to `Approved` once the chain signs off, and finally to `Active` when it is put in force. From there it can only move to a terminal state: `Expired` when its validity window passes, `Rejected` if review turns it down, or `Superseded` when an amended version replaces it. The whole point of the FSM is the gap between `Approved` and `Active`. A form that has been approved is not yet a form that is in force, and only the in-force state opens the gate.

That gate sits inside `start_run`. Before a run is allowed to begin, the decider asks a narrow question: is there an Active Clearance whose scope covers this run? Scope is the run, the sample under the beam, and the equipment the run binds, and a Clearance bound to the sample covers any run on that sample. If the answer is yes, the run starts and its start is recorded. If the answer is no, nothing is written at all, because the run never began.

## Two refusals, two questions

A refusal is only useful if it tells you what to do next, and "no clearance" and "the clearance is not active yet" are two different problems with two different fixes. CORA keeps them apart on purpose.

The first case is the empty one. Nothing in the system covers the run's scope, and the gate raises `RunRequiresActiveClearanceError`. The fix is simple: file the form.

The second case is subtler. A Clearance does cover the scope, but no covering one is in force. Perhaps the only match is still `UnderReview`. Perhaps it has `Expired`. Perhaps an amendment superseded it and the replacement was never activated. Here the gate raises `RunClearanceCoverageMismatchError` instead, and the error carries the count of clearances that referenced the scope but failed the in-force check. The fix is not to file a new form; it is to finish, renew, or activate the one that already exists.

Keeping these apart matters, because the operator at the console is asking two genuinely different questions: is there a form at all, and is the form I have live yet? A single flat "denied" would answer neither. The error names which of the two they are standing in.

## The safety scope is derived, never hand-maintained

The second gate is physical rather than procedural: the hutch interlock. A beam-on volume at a synchrotron is searched, secured, and permitted before anyone lets beam into it, and a run inside an unsecured hutch is exactly the kind of work the record should refuse to start.

The tempting way to enforce this is to make each recipe declare which hutch it needs, and then check that hutch's permit. CORA does the opposite, for the same reason the [last post](derive-dont-stamp.md) argued against stamping values you could derive: a hand-maintained list is a list that drifts. Methods declare no hutch at all. Instead, the gate starts from the equipment the run actually binds, walks up the containment chain from each device to the larger assembly and beamline unit it sits inside, collects the hutch that each of those declares as the place it physically lives, and checks the permit on every hutch in that derived set. The safety scope is computed from where the equipment is, not from what a recipe remembered to write down.

How load-bearing that choice is becomes obvious when you turn it off. The scenario suite includes a deliberate control: run the same gate without the chain walk, so only a device's own directly-declared hutch is considered. A device whose hutch is declared one level up, on its parent unit, then has no hutch in scope at all, and the run starts silently into a volume nobody checked. The walk is the whole reason a misconfiguration cannot quietly bypass the permit, because nobody has to remember to list the hutch. The equipment's own position is the declaration.

## Naming the hutch that blocked you

2-BM is two hutches, the optics hutch `2-BM-A` and the experiment hutch `2-BM-B`, each its own access-gated volume with its own Personnel Safety System permit, observed independently. Because each device names exactly one hutch, the gate produces three operationally distinct outcomes, and the error shape matches the shape of the problem.

If every hutch in the derived scope is permitted and active, the run starts. If a run binds only A-side equipment, it starts when `2-BM-A` is permitted even while `2-BM-B` is not, because B is simply not in its scope. If every hutch in scope fails the check, the run is refused with `RunRequiresPermittedEnclosureError`. And if some hutches pass and some fail, which is what a cross-hutch run hits while one of its two hutches is still unsecured, the gate raises `RunEnclosureCoverageMismatchError` and names the failing hutch, so the operator knows which permit to go chase rather than which beamline to give up on. There is one more case worth stating plainly: a device that sits in no modeled hutch contributes nothing to the scope, and an empty scope permits by default. The gate refuses on the hutches it knows about; it does not invent one.

## Reading the interlock without joining the safety chain

This is the line that matters most, and it is the concrete payoff of a boundary [the positioning post](where-cora-fits.md) drew in the abstract. CORA reads the Personnel Safety System; it never touches it. It polls the read-only Channel Access signals the PSS publishes, the per-hutch secured flags and the front-end and station shutter states, and it uses them to decide whether to let a run start. It does not drive, hold, or release the interlock, and reading those signals does not put CORA into the safety chain. The PSS keeps sole interlock authority. This is the ISA-99 zones-and-conduits trust model at the bench, and the spine-reads-never-drives posture made literal: the record observes the floor and refuses on what it sees, but the floor's safety systems remain exactly where they were.

Reading rather than driving has a sharp edge that the gate respects. The shutter signals report blocking state with inverted polarity, where zero means open and one means closed, so "the shutter is open" is a predicate you have to get right rather than a value you can trust at face value. And because CORA only reads, it fails closed: when the deployment is wired to read the beam state and that read comes back disconnected or low-quality, the run is refused rather than waved through on the assumption that beam is available. A read it cannot trust is treated as a reason to stop, not a reason to proceed. The reading itself is never stored on the run, because a run that started necessarily passed the gate, so a saved snapshot would always say "all open" and carry no information at all.

## Honest edges

The two gates are real and carry 2-BM today, with limits worth stating.

Both gates read replicated projections rather than the upstream aggregates, so the gate drains its read model to the current point before it checks. The moment a Clearance reaches Active, there is a brief, bounded interval before that fact is visible to the gate, which is the ordinary cost of reading a projection and the reason the start path waits for it rather than racing it. The two-error split on the clearance side is fully modeled, but the coverage-mismatch path, the one for a clearance that exists and is expired or superseded, is exercised less end-to-end than the plain "no clearance" path and is on the watch list until a scenario walks an Active clearance to Expired and then retries a run against it. The gate is a safety net, not the front door: a real operator meets the form in the facility's intake UI long before they reach a console, and the aggregate-level refusal exists so that an unsafe start is impossible even if something upstream lets it through. And the usual caveat holds, that this is a pre-1.0 system grounded in a single deployment, so these are claims about a working model rather than a fleet.

## The first place the record shows teeth

The arc so far has been a system learning to remember: where it fits above the floor, what a beamline is made of, how a recipe travels, how a value stays citable. This is the first place it pushes back. The same instinct that records a decision with its reason, and a calibration with its source, also refuses to open a run that no one cleared and no interlock permitted, and it refuses in a way that names the missing thing. A record you can trust later is, in part, a record that would not let itself be written about work that should not have happened. Saying no, precisely and for a stated reason, is not the opposite of remembering well. It is part of it.
