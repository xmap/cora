---
date: 2026-06-29
slug: what-it-leaves-behind
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - runs
  - procedures
  - calibration
  - datasets
  - modeling
links:
  - Run vs Procedure boundary: reference/modeling.md
  - The Recipe Ladder: blog/posts/the-recipe-ladder.md
  - What Actually Happened: blog/posts/what-actually-happened.md
  - What Calibrated Means: blog/posts/what-calibrated-means.md
  - Run module: architecture/modules/run/index.md
  - Operation module: architecture/modules/operation/index.md
---

# What It Leaves Behind: telling a Run from a Procedure

Two acts at the beamline can look identical from across the hutch. In the first, the sample rotates through a full turn while the camera fires hundreds of times. In the second, the sample rotates through a full turn while the camera fires hundreds of times. Same stage, same motion, same detector, same operator. Yet one of them is a tomography scan, and the other is a center-of-rotation alignment, and CORA records them as two different kinds of thing: the first as a Run, the second as a Procedure. If the motion does not tell them apart, what does?

<!-- more -->

This is not a pedantic question. CORA has two top-level records for planned work, the Run and the Procedure, and every act at a beamline has to land in exactly one of them. Put an act in the wrong bin and the five-year record starts to lie: a search for "every measurement of this sample" turns up calibration sweeps, or a search for "how did this instrument behave" turns up science data. The line between the two has to be sharp, and it has to be decidable by looking at the act itself, not by asking the operator which bin felt right that morning.

## The discriminators that do not work

The tempting answers all fail, and it is worth watching them fail, because each one is somebody's honest first guess.

*Does it touch the sample?* The tomography scan measures a sample; the alignment also turns a sample on the stage. And the dark-field reference, taken with the shutter closed and nothing in the beam at all, touches no sample yet is unmistakably a measurement. Sample-presence sorts nothing.

*Does it move hardware?* Both acts drive the same rotation stage. A reconstruction, meanwhile, moves no hardware whatsoever, runs entirely on a compute node, and is still a measurement in every sense that matters. Actuation sorts nothing either.

*Does it read the detector?* Both read the camera. The alignment reads hundreds of frames to find the center of rotation. Reading frames is not the same as keeping them.

That last failure is the clue. Each of these acts reads the detector, but they do not all *leave the frames behind* as the thing they were for. The scan exists in order to produce those frames. The alignment reads frames only to compute a single number and then discards them. The difference is not in the doing; it is in what survives the act.

## The one question

Here is the rule CORA actually uses, and it fits in a sentence. An act is a **Run** if its reason for existing is to leave a finite, identity-bearing dataset of record. Otherwise it is a **Procedure**: it changes or verifies the state of the instrument, and its output of record, if it has one at all, is a calibration value, never a dataset of record.

One question decides the track. *Does the act leave a dataset of record?* If yes, however it was produced, by a camera or by a reconstruction node, with a sample or without one, it is a Run. If no, if what it leaves is a calibrated value or simply a changed and verified machine, it is a Procedure.

Run the two look-alikes through it. The tomography scan leaves a projection dataset; that is the whole point of running it, so it is a Run. The center-of-rotation alignment leaves a number, the rotation center, stored as a calibration; the frames it read along the way are gone. So it is a Procedure. The acts looked the same from across the hutch, but they answer the one question differently, and the answer is unambiguous.

## Why the sample is not the axis

The most stubborn wrong intuition is that a Run is "the one with the sample" and a Procedure is "the prep around it." It is stubborn because it is usually true, and usually true is exactly the kind of rule that fails quietly at the edges.

Consider the dark-field and flat-field references that every tomography pipeline needs, the no-beam and no-sample images used to correct the raw projections. They involve no sample. The intuition says prep, and therefore Procedure. But each one captures a stack of frames and stores it as a baseline dataset that later runs consume. They leave a dataset of record, so by the one question they are Runs, subject or no subject. They are simply Runs that happen to carry no sample.

Now run the intuition the other way. The center-of-rotation alignment is performed on the sample stage, turning the actual sample. The intuition says sample, and therefore Run. But it leaves a calibration, not a dataset, so it is a Procedure. The sample was present and it did not matter.

So the sample is metadata on a Run, a field that is sometimes filled and sometimes empty, and never the thing that decides the track. The moment you let "has a sample" stand in for "is a measurement," the dark fields land in the wrong bin and the alignment lands in the other wrong bin, and the record is wrong in both directions at once.

## Data that merely passes through

The heart of the rule is a distinction the eye misses: the difference between data an act *produces* and data that merely *passes through* it.

The center-of-rotation alignment is the clean example. It rotates the stage to a handful of angles, reads an image at each, and fits those images to find where the axis of rotation sits on the detector. Hundreds of frames flow through the act. Not one of them is the output of record. The output of record is a single value, the rotation center, and that value is what gets written down, attached to a calibration that points back to the very alignment that produced it. The frames were scaffolding. They held the answer up while it was being computed and then they were let go.

This is why "does it read the detector" sorts nothing, and it is the subtlety that makes the one question precise rather than glib. A dataset of record is not any data the act happened to touch. It is the finite, identity-bearing lot the act existed to create. An alignment that reads a thousand frames and keeps a number is a Procedure. A scan that reads a thousand frames and keeps the frames is a Run. The frame count is identical; the thing that survives is not.

## A backstop built into the model

A good rule is one the system cannot easily violate even if someone wants to, and here the structure does most of the enforcing. A measured calibration in CORA can be sourced in only a few ways, and a Run is not one of them: the calibration's record can point back to a Procedure that measured it, or to a dataset that a computation derived it from, or to a person who simply asserted it. There is no arm that says "a Run produced this calibration." The model literally cannot express it.

That single missing arm carries a lot of weight. It means any act whose output of record is a measured calibration, every alignment, every characterization, is a Procedure by construction, not by anyone's decree. You could not file the rotation center as the product of a Run if you tried; there is nowhere to put the link. So the rule is mostly *derivation*, not decree: given that calibrations come from Procedures and datasets-of-record come from Runs, almost every act sorts itself, and the one question is just the short way of saying what the structure already guarantees.

## Two axes people conflate

One more confusion is worth clearing, because it masquerades as the Run-versus-Procedure question and is not.

Who *drives* an act is a separate axis from what the act *leaves behind*. A scan can be driven by a facility tool that CORA only records, or conducted step by step by CORA itself; either way it leaves a dataset, so either way it is a Run. A calibration can be measured by an operator working by hand or by an automated routine; either way it leaves a calibration, so either way it is a Procedure. Conducted-versus-recorded and Run-versus-Procedure are perpendicular. Neither answers the other.

Compute is the case that makes this vivid. A reconstruction moves no hardware and touches no sample; it reads existing data on a node and writes a reconstructed volume. By the doing, it resembles nothing on the beamline floor. By the one question, it is obvious: it leaves a dataset of record, so it is a Run, and its provenance is simply the data it was derived from. What an act is made of does not decide its kind. What it leaves behind does.

## Why the sharpness pays off

All of this exists so that the record stays answerable years later. Two questions get asked of an experiment long after it ends, and they must not collide. *Reproduce this result* walks a Run and the dataset it produced, forward into the lineage of what was derived from it. *How did this instrument behave* walks a Procedure and the calibration history it wrote, the drift of a center of rotation across a run cycle, the energy recalibrations and what each one changed. Because every act lands in exactly one bin, decided by the one observable fact of what it left behind, neither walk ever trips over the other. The measurements are all on one side and the instrument's biography is all on the other.

The dark and flat fields show the payoff and the subtlety together. They look like preparation, they run before the science, an operator would call them setup. But they leave a baseline dataset, so they are Runs, and they sit on the measurement side of the ledger where the reconstruction can find them by lineage. When CORA conducts one itself, the step-by-step driving is recorded as a Procedure phase *inside* that Run, so the operational detail is captured without ever becoming the thing of record: the Run owns the dataset, the phase owns the steps, and the one question is answered the same way it always is.

## The honest edges

The boundary is documented as a modeling rule rather than enforced by a single gate, and it leans on the structure described above to do most of the work. The corpus agrees with the choice, and it agrees on both sides of the line. Manufacturing drew the same split decades ago and gave each side its own standard: ISA-88 governs the batch, the finite lot a process produces, while ISA-106 governs the operational procedures around it, the bring-up and changeover and recovery that leave no lot behind. A Run is the ISA-88 batch; a Procedure is the ISA-106 procedure, the same two records under different names. The wider corpus sorts the produced side the same way: Bluesky brackets a measurement with an explicit open and close, schema.org separates a CreateAction that yields an entity from a ControlAction that only operates a device, and provenance and data-catalog standards alike key on the entity that was generated, not on the thing it was measured against. There is exactly one shape the rule does not yet decide, an act whose dataset and calibration are genuinely co-equal deliverables, and no act at the beamline crosses that line today; the plan is to resolve it by declaring a primary output when one finally does, not to guess now.

Two acts can look identical from across the hutch. Ask what each one leaves behind, and they were never the same act at all.
