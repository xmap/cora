---
date: 2026-06-20
slug: write-once-run-anywhere
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - federation
  - portability
  - content-addressing
  - identity
  - recipe-ladder
links:
  - The Recipe Ladder: blog/posts/the-recipe-ladder.md
  - What a Beamline Is Made Of: blog/posts/what-a-beamline-is-made-of.md
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - Federation module: architecture/modules/federation/index.md
  - Equipment module: architecture/modules/equipment/index.md
---

# Write Once, Run at Another Beamline: content-addressing for portable experiments

Here is a promise the recipe ladder made, and a question it left open. A Method, the portable rung of the ladder, is meant to describe a technique without naming any one facility's hardware, so that in principle a tomography technique perfected at one beamline could run at another. The question is what "in principle" is hiding. Hand a recipe from one facility to another and it will only run if both places agree on what its words mean: that "Hexapod" refers to the same kind of device, that "the microscope" refers to the same cluster of parts, that a "Positioner" is the same contract. And they have to agree without calling anyone, because in a federation of independent facilities there is no central authority to call. This is the same problem Git solved for source code, and CORA borrows the same answer.

<!-- more -->

One honest note before the promise. What follows describes a foundation that is built and a destination that is not yet reached, and it keeps the two apart on purpose. The machinery that lets two facilities agree on identity is real and shipped. The pipe that actually carries a recipe from one facility to another is not. The interesting claim is that the hard part is the first one.

## Why not just keep a registry

The obvious way to make two facilities agree is a shared registry: one authoritative service that hands out an identifier for every device class, every role, every assembly, and everyone looks things up there. It is the obvious answer and it is the wrong one for this setting, for the same reasons a single central server is the wrong shape for source control.

A central registry is a single point of failure: when it is down, no one can mint or resolve an identity. It is a governance bottleneck: every facility that wants to name a new kind of device has to wait on a shared authority to bless it. And it assumes a level of connectivity and trust between facilities that a federation of independent labs, each with its own security posture and its own offline periods, simply does not have. Science federations are loosely coupled by nature. The coordination cost of a central namespace is exactly the cost they cannot pay.

Git faced the same fork and took the other road. There is no central server that assigns an identity to a file or a commit. The identity of a thing is computed from the thing itself, and two people who hold the same content arrive at the same identity on their own, having never spoken. CORA applies that idea to the parts of an experiment.

## The hash is the name

Content-addressing means the identifier of a thing is derived from its content, so identical things get identical identifiers everywhere, with no coordination. CORA uses two flavors of it, for two kinds of thing.

The first is identity derived from a name. A device class, a Family, takes its identifier from its own name: the system normalizes the name and hashes it into a stable identifier, so the Family called "Hexapod" resolves to the same identifier at every facility that uses that name. The same holds for a Role like "Positioner" and for a vendor Model keyed on its manufacturer and part number. Agreement here is agreement on vocabulary: if two facilities call the thing by the same name, they are already pointing at the same identifier, automatically. There is no registration step, because there is nothing to register; defining "Hexapod" a second time does not create a second identity, it lands on the one that already exists.

The second is identity derived from structure. An Assembly, the blueprint for a cluster of devices, takes its identifier from a hash over its structure: the slots it declares, the wiring between them, the sub-assemblies it includes, the roles it presents. Two engineers at two facilities who independently describe the same microscope, the same slots wired the same way, arrive at the same hash. Engineering trivia that does not change what the thing is, like a local drawing number, is deliberately left out of the hash, so two descriptions that mean the same thing are not split apart by incidental metadata. This is exactly how Git fingerprints a file, a directory, and a commit: the [object model](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects) is content all the way down, and the hash is the name.

One detail made this work, and it is worth pausing on. An assembly's hash is built partly from the identifiers of the Families and Roles inside it. So two facilities only arrive at the same hash for the same assembly if those inner parts already share identifiers at both. If the Families had carried random identifiers, two identical assemblies would have hashed differently, and the agreement would have quietly broken. The names had to point to the same identifier everywhere first; only then could the structures built on top of them line up. You cannot content-address the outside of a thing while its insides are still arbitrary.

## Agreeing is not the same as trusting

Content-addressing solves agreement: it lets a consumer confirm that the assembly they received is bit-for-bit the one that was described. It does not solve trust. Knowing two things are identical tells you nothing about whether the source is who it claims to be, or whether you are being handed an old version that has quietly been rolled back. Git draws the same line and answers it with signed tags. CORA answers it with the Federation layer, and this part is shipped.

Each facility has a Seal: a single signing authority that signs the head pointer over that facility's published registry of definitions, so a consumer can verify that a registry really came from that facility and has not been tampered with or rewound. The Seal deliberately separates two keys, a warm online key that signs each new head and a cold offline root that is only used to rotate the online key or to authorize a full republish, which is the standard discipline for keeping a signing system recoverable if the everyday key is compromised. Every signed head carries a strictly increasing sequence number, so a consumer can detect an attempt to serve them a stale state. The facility's trust anchors, the credentials a consumer would check the signatures against, are recorded against the facility's own identity. The cryptographic shape of "trust a registry from another facility" is built, even though the act of consuming one is not.

## What is built, and what is not

Put the pieces together and the foundation is genuinely there. The same device class resolves to the same identifier at every facility that names it. The same assembly converges on the same hash. A facility can sign the head of its registry so others could verify it. A Method written against those convergent identifiers references things that mean the same thing elsewhere, which is the precondition for it to travel at all.

What is not built is the travel itself. There is no command today that serializes a facility's registry into a shareable artifact, ships it, and there is no importer on the far side that fetches it, checks the signature, verifies the hashes, and ingests the definitions into a local deployment. In Git's terms, CORA has the object model and the signing, but not yet the fetch and the clone. It waits not because it is hard but because it is the reversible part: with a single facility there is nothing to carry data to, and the requirements that would shape a sync protocol only become real when a second deployment arrives with its own constraints. And the larger claim, that a Method genuinely runs unchanged at a second facility, remains unproven for the honest reason that there is only one facility today: the 2-BM beamline is the single corpus that grounds all of this. Cross-facility portability is forward design resting on a foundation that is real, not a capability you can exercise this afternoon. The positioning post said as much, and it is worth repeating rather than letting the foundation read as the finished building.

## Why the foundation is the hard part

It is tempting to think the sharing is the substance and the identity scheme is plumbing. The opposite is closer to the truth. Git did not become the backbone of distributed collaboration because it added pull requests; it became that because the hash made two clones agree about history without asking anyone, and everything social was built on top of that quiet guarantee. The fetch is the part you can build later: once two repositories are certain that the same hash means the same commit, moving data between them is a transport problem you can revise freely, not a one-way decision you have to get right before any history exists.

CORA is making the same bet for experiments. Get identity right, so that a device class, a role, and an assembly mean the same thing in two places that never coordinated, and sign it, so that agreement can be trusted and not just assumed, and the act of moving a technique from one beamline to another becomes a transport problem layered on a solved foundation rather than a coordination problem with no good answer. The transport is the next chapter. The reason it can be a next chapter at all, rather than a redesign, is that the names were content-addressed from the start.
