---
date: 2026-06-14
slug: agents-as-principals
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - agents
  - ai-governance
  - identity
  - audit
links:
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - Agent module: architecture/modules/agent/index.md
  - Access module: architecture/modules/access/index.md
  - 2-BM experiment: deployments/2-bm/experiment.md
---

# Agents as Principals: one identity for humans and AI

Two of the operators at the 2-BM beamline are not people. One of them reads a finished scan and records whether it completed cleanly, ran degraded, or aborted on a fault. The other watches for terminal run events and proposes a caution for a human to review. Both are software, and both raise the question every team adopting AI is now asking: how do you let an automated actor do real work without giving it a special, weaker, or unaccountable identity of its own? CORA's answer is that there is no special path. An agent is a principal, recorded, authorized, and audited exactly as a person is.

<!-- more -->

## Two records, one identity

The starting point is identity. In CORA an AI agent and the actor that represents it are not two linked records; they are one id shared across two parts of the system. One part holds the agent's typed configuration. The other holds the canonical actor that every module attributes work to. They carry the same UUID, and that UUID is written once, atomically: defining an agent records two facts in a single transaction, the agent's configuration and an actor marked as being of kind agent, so both commit or neither does. There is no window in which an agent exists without an actor, or an actor without the configuration that explains it. And the discipline is enforced, not merely intended: the ordinary path for registering a person refuses to create an agent-kind actor at all, because an agent's actor may come only from that atomic write.

The payoff is uniformity. Because a human and an agent are the same kind of thing, an actor with an id, every downstream reference works without special cases. The same id authors a decision, passes an authorization check, and signs a logbook entry, whether the actor behind it is a person or a model.

## The same gate

Identity is who you are; it is not permission. CORA keeps the two apart: one module answers "who," and another answers "may they." What matters for agents is that there is one gate, not two. An agent's action is authorized by the same policy machinery that gates a human's, against the same actor id. An agent cannot do something a person in its position could not, and it cannot quietly acquire authority a person would have to be granted. There is no agent-shaped hole in the permission model, because agents are not a separate kind of caller. They are actors, and actors are what the gate checks.

## What the agent carries

If an agent is to be trusted with a choice, you have to be able to answer, later, exactly what made it. So an agent is a typed configuration record, not a loose script. It pins the model it runs on: the provider, the model, and an optional snapshot pin, the provider's string for the exact weights in use. That last field is reproducibility by construction, because two runs of "the same model" are only truly the same if the snapshot is, and CORA treats a change of model identity as a new agent with a new id rather than a quiet edit of an old one. Alongside the model sit the prompt template the agent uses, a tool allow-list naming exactly which operations it is permitted to call, and a budget of monthly cost and daily tokens. With those on the record, "what configuration decided this" is a lookup, not an investigation.

One honesty note: the budget today is declared, not enforced. The caps are recorded and the enforcement is deferred to a dedicated part of the system. The record is ahead of the meter.

## Accountable by the same record

An agent earns the word principal by being accountable, and accountability here is the append-only record from the previous post. When the run-debriefing agent classifies a scan, it does not flip a status field; it writes a Decision, the same structured record a human approval writes, carrying the choice, the rule, the inputs, and the actor that made it, which is the agent's shared id. When the caution-drafting agent has something to say, it does not raise a caution directly; it records a proposal, and a person reviews it before the caution becomes real. A wrong call is corrected the way any decision is corrected, by a new entry that points back at the old one, never by erasing it. Months later, the question "why was this run marked degraded, and what marked it" resolves to a named actor and a dated, immutable record, and the answer has the same shape whether that actor was a person or a model.

## What these agents do, and do not

It is worth being plain about scope. The two agents at 2-BM observe and advise; they do not drive the beamline. One writes findings; the other proposes cautions for a person to accept or reject. The agent record itself is configuration only: the runtime that actually invokes a model lives elsewhere, and the configuration never even knows it was called. None of this is autonomous control of hardware, and the design does not pretend otherwise. What it provides is the part that has to exist before autonomy could be safe: an automated actor with a real identity, a bounded authority, a reproducible configuration, and a decision trail that reads exactly like a person's.

## What the field is building

CORA is not alone in pointing at this, but the pieces tend to sit apart. The synchrotron world has built the decision half: [bluesky-adaptive](https://blueskyproject.io/bluesky-adaptive/) puts an algorithm in the experiment loop, and engines like [gpCAM](https://gpcam.lbl.gov/) choose the next measurement under uncertainty. There is an execution half too: [Academy](https://academy-agents.org/), from Globus Labs, is middleware for deploying and coordinating autonomous agents across federated research infrastructure, spanning HPC, instruments, and data repositories at once. There are interoperability protocols: the [Model Context Protocol](https://modelcontextprotocol.io/) for connecting an agent to the tools it may call, and the Agent2Agent protocol for how agents advertise their identity and capabilities to one another. And the governance world has its own canon: [ISO/IEC 42001](https://www.iso.org/standard/81230.html) and the [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) describe how an organization should manage AI.

What falls between all of them is the running record where an autonomous agent's identity, authority, and decisions actually live. Academy is a telling case: built precisely to run agents across facilities, its focus is execution and coordination, and identity, authorization, and an audit trail sit outside it. That is the layer CORA provides, and it is complementary rather than competing, because an agent that a framework deploys still needs a name, a bounded authority, and a decision record. CORA keeps its own record interoperable with the rest: the tool allow-list names Model Context Protocol tools, and an agent's identity card is kept forward-compatible with Agent2Agent, so CORA sits beneath the execution layer rather than against it. Not an optimizer in the loop, not a deployment fabric, and not a framework on paper, but the system that holds the agent to account while it works.

## Why this matters now

A companion post ended on a question: as software increasingly decides what to measure next, the issue stops being whether a machine can choose and becomes who answers for what it chose. This is the answer. An agent in CORA is not a privileged black box bolted onto the side; it is a colleague with a name, held to the same permissions and the same audit trail as the people it works alongside. The fast layer that acts can be a person or a model. The slow layer remembers them both the same way.
