---
date: 2026-06-22
slug: metadata-from-the-other-end
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - metadata
  - provenance
  - system-of-record
  - event-sourcing
  - fair
links:
  - Derive, Don't Stamp: blog/posts/derive-dont-stamp.md
  - Where CORA Fits: blog/posts/where-cora-fits.md
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - 2-BM assets: deployments/2-bm/inventory.md
---

# The Metadata Problem, From the Other End: record the work, and let the labels be a read

Every facility runs on metadata, the labels and fields attached to data so that it can be found, understood, and reused after the people who took it have moved on. And almost everywhere, metadata disappoints. It is incomplete, because the field you need now is the one nobody thought to capture then. It is inconsistent, because two people labeled the same thing two ways. It is retrofitted, filled in long after the moment it was meant to describe, from memory. None of this is a failure of diligence. It is built into how metadata is usually produced, and the cause is worth naming plainly. At the moment of acquisition you are asked to anticipate every question a future reader might ask and stamp a label for each. You cannot, so there is always a missing field, and a missing field is usually gone for good. That is the metadata problem.

<!-- more -->

CORA comes at it from the other end. An [earlier post](derive-dont-stamp.md) named the habit, derive rather than stamp, and this is its largest application. Instead of labeling artifacts up front, you record the work as connected facts while it happens, and let the labels be something you read back out afterward. This post is about why that is a genuinely different answer to the metadata problem, what it dissolves, and, just as honestly, what it does not.

## Why you cannot win it from the front

The usual response to bad metadata is to demand more of it: richer schemas, stricter controlled vocabularies, more mandatory fields at submission. These help with the questions you foresaw. They cannot help with the question you did not, because no schema can require a field for a question nobody had yet thought to ask. Pressing harder on the front end makes the labels you captured better; it does not make the unforeseen question answerable, and it grows the burden of anticipation, which is the part that does not scale.

There is a second, quieter weakness, and one small example carries it. A tomography file marks certain frames as flat fields, the reference images, taken with no sample in the beam, that later correct for non-uniformity. The label looks like solved metadata. But a frame is a valid flat only if the sample was actually out of the beam, the shutter was actually open, and the energy matched the projections it will correct. If any of those failed, the label still says flat, and whatever reads the file believes it. The word was stamped; the conditions that would justify the word live in other systems, unconnected to it. That is the metadata problem in miniature: a label that asserts without being able to prove itself.

## The other end: record the work, read the labels

The alternative is to stop trying to label the artifact and start recording the process. As work happens, CORA writes down what happened as immutable, connected events: the run that executed, the equipment it used and the state that equipment was in, the calibration in effect, the sample involved, the decisions taken and why. The data files stay where they are; what CORA keeps is the connected account of how they came to be.

Once that account exists, labels stop being something you must foresee and stamp, and become something you derive. Return to the flat field. CORA does not relabel the frame, but it has recorded the conditions, where the sample was, whether the beam was open, what energy was set, as facts on one record. So "is this a valid flat field" turns into a read against those recorded conditions, rather than trust in a word someone wrote into a header. The same shift applies to a question nobody thought to ask at acquisition time: if the facts were recorded, the label is a query, not a guess you needed to have made in advance.

## Why the floor labels anyway

It is worth being fair to the systems that stamp, because they are not careless. A detector program cannot know the calibration lineage, the beam history, or the sample's prior runs; it sees its own slice of the afternoon, and writing that slice into its own file is the responsible thing to do with the view it has. Stamping is the rational behavior of a tool that can only see a fragment. The metadata problem is a consequence of fragmentation, not of negligence, which is why pressing individual tools to label harder never resolves it. CORA does not ask any tool to label better; it changes the precondition by holding a connected record the fragments never had.

## What this does not solve

It would be dishonest to call this the end of metadata, so here is the boundary, drawn carefully.

CORA stores none of the heavy data: not the frames, not the PV streams, not the bytes. The dataset still needs metadata for its own content, a [NeXus](https://www.nexusformat.org/) layout, a checksum, the descriptive fields a catalog indexes, and the FAIR aims, that data be findable, accessible, interoperable, and reusable, remain the right target for the artifacts themselves. This approach does not replace that metadata or the catalogs and standards that carry it. It also does not conjure metadata from nothing: a derived answer is only as good as the facts that were recorded, so if a fact was never captured, no amount of folding will produce it.

What changes is where the burden sits, and that is the whole point. The front-loaded model asks you to anticipate questions and label for them, which is impossible to do completely. The recorded-process model asks you to write down what happens, which is achievable because it is occurring as you watch. The flat field stays in the file; what CORA adds is the connected context that tells you whether to trust the label. And because the account it records follows the shape of standard provenance, it is a natural input to a catalog rather than a competitor, the same point an [earlier post](where-cora-fits.md) made about sitting above the floor rather than against it. The honest summary is that this dissolves the core of the metadata problem, the anticipation and the drift and the unverifiable label, without abolishing the metadata an artifact will always need, and it does so today against a single grounding deployment at 2-BM, as a pre-1.0 system.

## The label stops being a guess

Underneath it is one shift. The metadata problem is, at bottom, an anticipation problem: you are asked to know in advance which facts you will wish you had written down. You cannot solve an anticipation problem by labeling harder, because the harder you label the more you are betting on having guessed right. You solve it by recording the work as it happens and reading the labels back when you actually need them. A label stops being a guess you froze at acquisition and becomes a fact you can derive, and check, long after.
