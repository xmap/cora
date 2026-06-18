---
date: 2026-06-18
slug: the-right-to-be-forgotten
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - privacy
  - gdpr
  - pii
  - erasure
  - event-sourcing
  - identity
links:
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - Agents as Principals: blog/posts/agents-as-principals.md
  - Access module: architecture/modules/access/index.md
  - State (Architecture): architecture/state.md
  - Data (Stack): stack/data.md
---

# The Right to Be Forgotten: erasing a person from a log that cannot be edited

An [earlier post](how-cora-remembers.md) argued that CORA can be trusted for one reason above all: it was built never to overwrite anything. Every change of state is an immutable event, appended to a log the application is not even permitted to edit. That is the whole point. So here is the uncomfortable question it raises. A person has a legal right to ask that their personal data be erased, named in European law as the right to erasure, or the right to be forgotten, in [Article 17 of the GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj). How does a system whose defining property is that it cannot forget honor a request to forget someone?

<!-- more -->

The contradiction is real, and it is not solved by cleverness with the log. It is solved by being careful, from the start, about what goes into the log in the first place. That care turns out to have a precise legal vocabulary and a settled engineering pattern, and the rest of this post is about how the two meet in CORA's code.

## Two things that look like one

The confusion hides in a single word: identity. When an operator approves an energy, or an agent classifies a scan, the record needs to say who did it. It is tempting to read "who" as a name. But a record of work needs two different things, and they have opposite lifetimes.

The first is a stable reference: a way to say that the same actor who approved this run is the one who later aborted that one, so the history hangs together and can be audited. This reference must never change and must never disappear, or the past stops making sense.

The second is the human-facing detail behind that reference: a display name today, and an email, a phone number, or an ORCID later. This is personal data in the legal sense, and a data subject can ask for it back.

Collapse the two and you are stuck: the name is welded into events you have promised never to edit. Keep them apart and the problem dissolves. CORA records the stable reference inside the log and keeps the personal detail somewhere else, in a small mutable table built to be changed and emptied. The events carry an opaque actor identifier and nothing more. They never carry a name. In the regulation's own terms this is pseudonymisation, defined in Article 4(5) of the GDPR: the data in the log can no longer be attributed to a particular person without separately held information, the line the regulation draws in Recital 26 between data that is merely pseudonymous and data that is truly anonymous. The technical methods behind it are catalogued in [ENISA's guidance on pseudonymisation](https://www.enisa.europa.eu/publications/data-pseudonymisation-advanced-techniques-and-use-cases).

A library makes the same separation without thinking about it. The borrowing ledger records that card number 4471 took out a book on a Tuesday; a separate cardholder file maps 4471 to a person. The ledger is the permanent record of what happened. Shred the cardholder card and the ledger is untouched, still complete, still auditable, but 4471 now points to no one. CORA's actor identifier is the card number. The small table is the cardholder file. The pattern has a settled name in event-sourced systems, [the forgettable payload](https://verraes.net/2019/05/eventsourcing-patterns-forgettable-payloads/), or the vault: keep the data you may have to delete out of the records you have promised to keep. It is well documented for production event stores, including in [Oskar Dudycz's writing on GDPR in event-driven systems](https://event-driven.io/en/gdpr_in_event_driven_architecture/).

## The answers that do not work

Before the vault, it is worth being clear about why the obvious alternatives fail, because each is a tempting shortcut.

The first is to simply delete from the log. CORA cannot, and that is by design rather than by accident. The running application connects to the database under a role that may insert events and read them, and nothing else; the privilege to update or delete an event was never granted. The seal that makes the record trustworthy is exactly the seal that forbids this shortcut. It is not available, and it should not be.

The second is to claim an exemption: the log is immutable, therefore erasure is technically impossible, therefore the obligation does not apply. Regulators have closed this door explicitly. The [European Data Protection Board's 2025 guidance on append-only and blockchain-style stores](https://edpb.europa.eu/system/files/2025-04/edpb_guidelines_202502_blockchain_en.pdf), issued for public consultation, states that technical impossibility cannot be invoked to justify non-compliance, and that controllers must therefore design for erasure before personal data is ever committed to such a store. "We built it so we cannot delete" is not a defense; it is a design problem to be solved up front, which is precisely what the vault does.

The third is more sophisticated: encrypt each person's data with a key unique to them, and "delete" by destroying the key, leaving unreadable ciphertext behind in the log. This is a genuine pattern, called [crypto-shredding](https://verraes.net/2019/05/eventsourcing-patterns-throw-away-the-key/), and it is the right tool for some systems, particularly multi-tenant platforms that share event streams with parties they do not control. CORA does not use it, for two reasons. The [same European guidance](https://edpb.europa.eu/system/files/2025-04/edpb_guidelines_202502_blockchain_en.pdf) notes that encrypted personal data is still personal data, and that destroying a key while the ciphertext survives is a mitigation rather than an erasure; what is infeasible to break today may not be tomorrow. And operationally it would add a key-management system that becomes a new single point of failure mirroring the event store itself. For a single facility recording its own experiments, that is a large machine to solve a problem a small table solves more honestly. If CORA ever publishes its events to downstream consumers it cannot reach to revoke, that calculation changes, and crypto-shredding comes back onto the table. Until then, the vault wins on both simplicity and standing.

## The vault

The vault is one small table, `actor_profile`, with one row per actor. Today it holds a display name; future personal fields land as additional nullable columns on the same row, with no new machinery. It is mutable on purpose, which makes it the one place in the system where personal data can be changed and removed.

Because it is the one mutable surface that holds identifying data, it carries a second layer of protection the sealed event log does not need. The events table is protected by a blunt instrument: a database role that simply cannot update or delete. The vault must allow update and delete, so it leans on row-level security instead, enabled and forced, so that even an accidental query from a privileged role is subject to policy rather than silently bypassing it. The events table is sealed shut; the vault is locked, not sealed, because its whole job is to be emptied on request.

Keeping personal data out of the log is not left to good intentions. A small architectural test walks the source of every event the actor can emit and fails the build if any of them ever grows a field named like personal data: a name, an email, a phone number, an ORCID. The separation is not a convention a future change might quietly erode; it is a wall, and the test is what keeps the wall standing.

## What "forget" actually does

Erasure is a single deliberate action, and what is striking is that it makes the log longer rather than shorter.

When an operator forgets an actor, two things happen inside one database transaction. The vault row is scrubbed and then deleted: the name is first overwritten with an empty value and then the row is removed, so that the leftover bytes a database keeps on a page until it later reclaims the space no longer contain anything identifying. And a new event, `ActorProfileForgotten`, is appended to that actor's stream. The two commit together or not at all. If the event fails to append, the deletion rolls back and the row reappears intact, so the system is never left claiming an erasure that did not happen.

The new event carries no personal data. It records only that this actor identifier had its profile erased, on this date, at the hand of this principal. This is the same rule the ledger has always followed, now applied to forgetting itself: you do not quietly remove the past, you record a new fact about it. The log does not lose the knowledge that a person was once here and asked to leave; it gains the knowledge that the request was honored, with a timestamp and an accountable actor, which is exactly the record a later auditor, or the person themselves, has every right to expect. Retaining that bookkeeping note is not a loophole. The right to erasure is expressly qualified by Article 17(3) of the GDPR: it does not require deleting what is needed to comply with a legal obligation, or to establish, exercise, or defend a legal claim, and a content-free record that an erasure was performed falls squarely within those exceptions.

## After erasure

Once the row is gone, the actor identifier in all those past events still resolves. Ask the system for that actor's display name and it answers with a neutral placeholder, "&lt;deleted user&gt;", through a single read helper every surface uses. The list views show the same, because the read model swaps the cached name for the placeholder the moment it sees the forgotten event, with no lookup required.

So the experiment record stays whole. You can still see that some actor approved this run and aborted that one, that the history is consistent, that nothing was tampered with. What you can no longer see is who that person was. The reference survived; the identity behind it did not. That is the precise shape the law is reaching for: the data that identifies a human being is gone, while the account of what was done at the beamline remains trustworthy and complete. The residual identifier left in the events is pseudonymised rather than anonymous, and the [European board's 2025 guidance on pseudonymisation](https://edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf) is clear that pseudonymised data is still personal data so long as someone could re-link it; its own worked example of an identity provider that deletes its lookup table is, in effect, a description of this design.

## The same shape beyond Europe

The discussion so far has been framed in European terms because the European guidance is the most developed, but the design is not parochial. A right to deletion now appears, with local variations, in [California's privacy law](https://oag.ca.gov/privacy/ccpa), in [Brazil's LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm), in [China's PIPL](https://digichina.stanford.edu/work/translation-personal-information-protection-law-of-the-peoples-republic-of-china-effective-nov-1-2021/), in [Turkey's KVKK](https://www.kvkk.gov.tr/Icerik/6649/Personal-Data-Protection-Law), and in [India's 2023 data-protection act](https://www.meity.gov.in/content/digital-personal-data-protection-act-2023). Within the European Union the same right binds every member state directly through Article 17, enforced by national authorities such as Italy's [Garante per la protezione dei dati personali](https://www.garanteprivacy.it/). The substance differs mostly in deadlines and in the list of permitted exceptions, not in the underlying move, which is the same everywhere: a person can demand that data identifying them be removed, while a controller may keep what it must for accounting and legal defense. A system that separates the durable reference from the erasable detail satisfies all of them by construction, because the hard part, deleting the personal data without dismantling the record of what happened, is handled once, at the level of where each fact is allowed to live, rather than re-litigated per jurisdiction.

## Honest edges

It would be dishonest to present this as a finished privacy programme. It is a sound foundation with deliberate edges.

Erasure today removes the personal data from the live system and proves it did so. It does not, by itself, reach into database backups, into the write-ahead log a database keeps before it recycles those segments, or into a replica. Those are real places a determined recovery could still find pre-erasure bytes, and closing them is an operational discipline, a retention and restore policy, that belongs to a production deployment. CORA does not have one yet; it is a pre-1.0, single-facility research system, and these are documented obligations for the day it grows up, not claims about today.

The erasure itself is synchronous and local: one facility, one database, one transaction. The moment CORA begins publishing events to a downstream party that can independently re-link the identifier, that party becomes part of what the European guidance calls the [pseudonymisation domain](https://edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf), and local erasure stops being globally sufficient on its own; forgetting then has to become a message those consumers act on too, which is a larger design left for when the need is real. The gate that authorizes a forget request runs on the same path as every other command, but a dedicated data-protection role, distinct from an ordinary operator, waits for the broader authorization work rather than being invented speculatively here. And the vault holds exactly one personal field today, a display name; the structure is ready for more, but more has not yet been collected.

## Why both halves are the point

It is easy to read remembering and forgetting as opposites, and to assume a system can be good at one only by being bad at the other. The argument here is that they are not in tension once you separate what each applies to. The log remembers the work: the runs, the decisions, the reasons, the accountable references, faithfully and for a long time, because that is the one thing it is structurally unable to undo. The vault lets a person be forgotten: cleanly, provably, and without disturbing any of that, because the personal data was never allowed into the part that cannot change. A record you can edit is not a record. A record that cannot let a person go is not one you should be allowed to keep. CORA aims to be neither, by deciding carefully, before anything is written down, which of the two each fact belongs to.
