---
date: 2026-06-23
slug: what-calibrated-means
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - calibration
  - reproducibility
  - provenance
  - event-sourcing
  - metadata
links:
  - The Metadata Problem: blog/posts/metadata-from-the-other-end.md
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - Calibration module: architecture/modules/calibration/index.md
  - Equipment module: architecture/modules/equipment/index.md
---

# What "Calibrated" Means: a dated fact, not a number you overwrite

"Calibrated" sounds like a settled property of an instrument, the way "two meters long" is settled. In daily practice it is something much softer: a number in a spreadsheet, or a field in a config, that someone measured once and that gets overwritten the next time the instrument is calibrated. The current value is easy to find. Everything around it is not. What was the center of rotation last March, when this dataset was taken? Who measured it, and was it a careful measurement or a quick estimate typed in to get a shift moving? Once the number has been overwritten, those questions have no answer, and the data that depended on the old value is quietly orphaned from the value it actually used.

<!-- more -->

This is the same shape as [the metadata problem](metadata-from-the-other-end.md): a value stamped in one place, with no lineage, that cannot prove itself later. Calibration is worth its own post because it is the case where the cost is most concrete. A reconstruction does not just annotate itself with the center of rotation and the energy offset; it is computed from them. Get the lineage of those numbers wrong and you cannot say what a result actually means. So CORA does not store a calibration as a current number. It stores it as a dated, sourced fact that grows by revision and never gets overwritten.

## A value is only true at an operating point

The first thing CORA insists on is that a calibration is not a bare number; it is a number attached to the conditions under which it holds. Each Calibration is keyed by a triple: the target it belongs to, the quantity being calibrated, and the operating point it was measured at.

The target is a specific piece of equipment, the same Asset every other part of the system refers to. The quantity comes from a small closed catalog of the things that actually get calibrated at an imaging beamline: the rotation center, the detector pixel size, the magnification, the effective thickness of a filter, the monochromator's energy offset, and a couple of curve-valued quantities such as a positioner's position as a function of beam energy. The operating point is the set of conditions that make the number meaningful, the beam energy, the optics in place, and so on. The center of rotation at 25 keV with one objective is simply a different fact from the center of rotation at 30 keV with another, and CORA treats them as different calibrations rather than pretending one number covers both. A value with no operating point is a value you cannot safely reuse, because you do not know when it applies.

## Recalibration appends, it does not overwrite

When the instrument is calibrated again, the new value does not replace the old one. It is appended as a new revision on the same calibration, and the previous revision stays exactly where it was, readable forever. A calibration is therefore not a number but an ordered history of measurements of the same thing at the same operating point, the careful re-measurement last week sitting alongside the rough estimate from the month before.

This is the ledger discipline an [earlier post](how-cora-remembers.md) described, applied to instrument values: you correct by adding, never by erasing. The benefit is the one overwriting throws away. Because the old revision still exists, a dataset taken under it is not orphaned; it still points at a value that is still there. And re-baselining is kept honest: a revision may supersede an earlier revision on the same calibration, but you cannot reach across to rewrite a different one, and starting fresh at a new operating point is a new calibration, not a quiet edit of an old one.

## Provisional or verified, and where it came from

Two facts ride on every revision, and both are usually the first things lost when a calibration is just a number.

The first is how much to trust it. Each revision carries its own status: Provisional, an initial estimate or an early-data figure that downstream work may use but should know is unblessed, or Verified, blessed for production reconstructions. Status lives on the revision, not on the calibration as a whole, precisely so a Provisional first guess and a later Verified refinement can sit side by side, and a consumer that pinned the Provisional one stays valid when the Verified one lands. Promotion from Provisional to Verified is a human act, recorded as such; the system does not silently bless a number.

The second is where the value came from. Every revision tags its source as one of three things: measured by a procedure, computed from a dataset, or asserted by a person who typed it in. A calibration can mix these across its history, an asserted estimate to start, a measured value once an alignment ran, a computed refinement from a later reconstruction, and the record says, for each revision, which it was. "Where did this number come from" stops being a question you ask the person who happened to be on shift and becomes a field on the revision.

## Pinning: what a measurement actually used

None of this would matter if a dataset could not say which calibration it used. So the citation is explicit, and it survives later change. A run pins the exact set of calibrations it consumed when it starts, so the record of what it was taken under is fixed at that moment. A dataset, in turn, records the specific calibration revisions its reconstruction consumed. And a virtual axis whose motion is driven by a calibration curve references a specific revision of that curve rather than copying its numbers, so the calibration history stays the single source of truth and the axis survives recalibration by pinning a newer revision.

The payoff is the question the last two posts kept gesturing at. "What calibration was this scan taken under" is answerable forever, by following the pin to the exact revision, even after the instrument has been recalibrated five times since. And the reverse question, "which datasets used the revision we have now superseded, and should be looked at again", is answerable too, because the superseded revision still exists and the pins that point at it still resolve. Reproducibility here is not a slogan; it is the pin plus the immutable revision it points to.

## Honest edges

The model is real and carrying the 2-BM beamline, with deliberate limits.

The catalog of quantities is closed and grows by a code change, not by free-form entry, on purpose: a quantity arrives with the schemas that validate its operating point and its value, so a calibration cannot drift into a free text bag. The trust ladder ships with two rungs, Provisional and Verified; a middle "refined" tier waits until real use shows a distinct gap between them. Today a consumer fetches the calibration it needs by the id a run or dataset pinned; a time-keyed lookup, "give me whatever was current for this asset and quantity as of this date", is deferred, because the explicit pin already answers the reproducibility question without it. The bridge that would let a finished alignment procedure draft its own Provisional revision automatically is also deferred; for now a person appends it and a person verifies it, which keeps a human in the loop on every value a reconstruction will trust. And the usual caveat: this is a pre-1.0 system grounded in a single deployment, so these are claims about a working model, not a fleet.

## Calibrated, as a fact you can cite

The shift is small to state and large in consequence. A calibration stops being a number you look up and overwrite, and becomes a dated fact with an operating point, a status, a source, and a history, that a measurement can cite and that later work can check. "Calibrated" was always supposed to mean "we know this value and we can stand behind it." Recording it this way is what lets the system actually say, long afterward, which value, how well we knew it, who measured it, and exactly which results were built on it.
