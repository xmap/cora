---
date: 2026-06-16
slug: the-recipe-ladder
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - recipe-ladder
  - methods
  - runs
  - procedures
links:
  - Recipe ladder (Standards): architecture/standards.md
  - Recipe module: architecture/modules/recipe/index.md
  - Run module: architecture/modules/run/index.md
  - Operation module: architecture/modules/operation/index.md
  - 2-BM experiment: deployments/2-bm/experiment.md
  - 2-BM procedures: deployments/2-bm/procedures.md
---

# The Recipe Ladder: from a portable technique to what actually happens at the beamline

Michael Polanyi observed that "we know more than we can tell." At a beamline this is not a philosophical aside but the daily operating reality. An operator carries years of practice that never fits in the written standard operating procedure, and software that models only the written procedure tends to fail the moment it meets the realities of daily operation. CORA's response is a structure we call the recipe ladder: four steps that give this tacit, unwritten knowledge somewhere to live, so that a technique described once can run at more than one facility, and a single experiment can record precisely where reality departed from the plan.

<!-- more -->

## Four steps, one idea

A scientific technique begins as something general and becomes more specific as it approaches execution. The same description that a research community might publish has to be narrowed, step by step, until it refers to particular instruments performing particular motions on a particular afternoon. The recipe ladder names four stages in that descent.

This pattern is not unique to science. Industry formalized it decades ago in a standard called ISA-88, which describes how a manufacturing recipe moves from a general, equipment-independent description down to the specific instructions a single plant actually runs. ISA-88 distinguishes a general recipe (the technique in the abstract), a site recipe (that technique adapted to one location), a master recipe (bound to specific equipment), and a control recipe (the instance that is actually carried out). CORA borrows this vocabulary directly, because the underlying problem is the same: how to keep one portable description and still arrive at something concrete enough to run.

The four steps map onto those four ISA-88 stages.

| Step | ISA-88 stage | What it fixes | What it leaves open |
| --- | --- | --- | --- |
| Method | general recipe | the technique, expressed as roles | the site, the equipment, the values |
| Practice | site recipe | how one facility runs the Method | the equipment, the values |
| Plan | master recipe | the specific equipment and its wiring | the per-run values |
| Run | control recipe | what actually occurred | nothing; it is the record |

A fifth concept, the Capability, sits above the ladder rather than on it, and we return to it at the end. The four steps are the spine of the story.

To keep the descent concrete, the sections that follow trace a single technique, tomography, as it narrows from a portable description into one run at the APS 2-BM beamline. Each step is read through the same lens: what it is responsible for, the roles it puts in play, and how it connects to the steps above and below it.

## 1. Method: the part that fits on paper

A Method is responsible for one thing: describing what a technique needs, in terms general enough to publish. It names no hardware. Instead it asks for roles, and a role is a job to be done rather than the equipment that does it. CORA defines a small set of them, Detector, Positioner, Controller, and Sensor, and any piece of equipment that can perform one of those jobs advertises which roles it fills. A tomography Method therefore asks for a Detector (something that produces the images) and a Positioner (something that places and turns the sample), lists the parameters an operator will later choose, such as the number of projections and the exposure per frame, and stops there. Which camera, which stage, and which facility are all questions it deliberately leaves open.

A role slot is filled in one of two ways: by naming one of those shared, facility-independent roles, so that a Detector means the same thing everywhere, or, as a deliberate exception, by naming a particular class of equipment when no shared role fits. A Method uses one or the other, never both, and that single constraint is what lets it travel. Published once, the same tomography Method can be carried out at 2-BM and at a facility on another continent whose instruments share none of the same part numbers. What a Method cannot do is run, because its roles are not yet attached to anything real. Supplying that attachment is the work of the steps below it. Other techniques, such as laminography and mosaic scanning, are Methods of the same shape, each a portable description rather than a wiring diagram for one room.

## 2. Practice: the local know-how

A Practice is responsible for binding one Method to one facility, and for holding everything the Method left to local judgment. Its stored record is deliberately small, little more than a link from a Method to a site, but the responsibility it carries is large, because it is the home of the tacit layer Polanyi named. The order in which an operator brings the instrument to readiness, the alignment that must pass before a scan can be trusted, the habit of collecting fresh reference frames before each measurement: this is knowledge that usually lives only in experience, and the Practice is the step at which a facility commits it to the record.

Consider one concrete choice. Tomography depends on flat fields, reference images of the beam taken with no sample in the way, so that the beam's own non-uniformity does not show up in the reconstruction. The Method requires that flat fields be collected, but says nothing about when. That timing is exactly the kind of decision a Practice owns. At 2-BM the flat fields are taken up front, with the sample moved out of the beam before the projections begin. Another facility, running the identical Method, may instead pause at intervals through a long scan to re-measure them as the beam drifts. Same technique, two Practices, and the gap between them is precisely the local judgment the Method declined to make.

At 2-BM, the Practice for tomography is what makes the portable Method operable in that particular hutch. It stands for the rest of the local sequence a 2-BM scan depends on, the homing of the motors and the center-of-rotation alignment that has to pass before the data can be trusted, none of which belongs in a Method meant to travel. A Practice still names no individual instrument, though. It records how this facility runs the technique, not which serial-numbered devices will run it tomorrow morning. Pinning those devices down is the work of the Plan.

## 3. Plan: bound to equipment

A Plan is responsible for turning roles into hardware. It takes a Practice and makes the three commitments the steps above it refused to make. First, it assigns a specific instrument to each role the Method declared: at 2-BM the Detector role is filled by the microscope, a camera behind a scintillator and an objective lens, and the Positioner role by the sample tower that carries the rotation stage. Second, it connects those instruments to one another. Instruments coordinate by passing signals, and the Plan makes that coordination explicit: as the rotation stage turns, its measured position drives a trigger, routed through the timing box, that tells the camera the exact moment to capture each projection, and the Plan records precisely which output connects to which input. Third, it carries the default values an operator begins from, such as the number of projections in a scan and the exposure per frame.

With those commitments made, the Plan is the first step on the ladder that points at the actual instruments standing in the room, and the last that is still only a description. It is complete enough to run, but it has not run. Everything it fixes is, for now, an intention. Turning that intention into an event, and recording how the event departed from it, is the work of the final step.

## 4. Run: where the plan meets reality

A Run is the operator-started execution of a Plan, and it is responsible for the one thing no step above it can capture: what actually happened. It takes the Plan's defaults, applies whatever the operator overrides for this particular measurement, and records the merged values it truly used. It is tied to the sample being measured and grouped with the other runs of the same session, so a result can always be traced back to its sample and its beamtime. And it follows its own course through a lifecycle, which is where the difference between what was planned and what occurred is finally written down. A single tomography Plan at 2-BM appears in the record as a whole family of distinct outcomes:

- a clean scan that completes without incident,
- one that pauses through a beam trip and resumes once the beam returns,
- one that proceeds overnight, straight through a facility power outage,
- one that completes in a degraded state after the operator steps in to intervene,
- and one that is aborted partway through when a hexapod faults.

A single Plan, then, yields many realities, though it is worth being precise about which variation is the Run's own. The outcomes above are one Plan meeting different circumstances as it executes. Other differences are not, and do not belong here. Choosing a continuous sweep over a step-and-shoot acquisition is a different technique, with its own Method and Plan, decided higher up the ladder. And a set of measurements meant to be read together, the four tiles of a mosaic, a rotation series, or the same iron-bearing core measured at two energies to tell its constituents apart, is a coordinated study called a Campaign: several Runs grouped above the Run, not one Plan behaving differently. What the Run alone owns is the distance between a plan and its execution, and that is where the tacit layer becomes visible and auditable. Long after the experiment, one can still ask why a given scan went the way it did, and the record will answer.

Read in order, the four steps tell one continuous story: a tomography Method that names only roles, a 2-BM Practice that supplies the local know-how, a Plan that binds the microscope and the sample tower and wires them to fire together, and a Run that records the morning sample A was actually scanned.

## Beside the ladder: the Procedure

A measurement is not the only thing that happens at a beamline. Before and between scans there is a great deal of preparation and care: returning motors to a known home position, aligning the sample's center of rotation, focusing the optics, recovering a controller that has locked up. These tasks produce no scientific image, yet a well-run facility treats them with the same seriousness as the measurements themselves, because a measurement is only as trustworthy as the setup beneath it. CORA records them as Procedures.

A Run and a Procedure are the same kind of record seen through two different lenses. A Run is the measurement, normally tied to a sample; a Procedure is the operational task that surrounds it. The distinction is the lens and not the data, since either one can produce a dataset. The 2-BM beamline registers real Procedures, among them motor homing, center-of-rotation alignment, optical focusing, a recovery routine that reboots a stuck hexapod, and a coordinated energy change. Several of them have an instructive shape. Center-of-rotation alignment, for instance, repeats and measures, repeats and measures, until the result stops changing, and once it has settled the operator stores that result as a calibration that points back to the very Procedure that produced it. The alignment is the act; the calibration is the value it leaves behind. A Procedure can stand on its own or run as one phase inside a larger Run, which is why it belongs in this account even though it is not itself a step of the ladder.

## Above the ladder: the Capability

One concept sits above all four steps. A Capability is the template for a whole class of operation, a definition of what a kind of task does independent of whatever performs it. Acquisition is a plain example: the ability to capture a stack of frames is a single capability, even though it appears in more than one guise. The dark-field reference, taken with the shutter closed, and the flat-field reference, taken with the shutter open and no sample present, are two realizations of that one capability, separated by little more than the state of the shutter. A Capability is also the hinge between the two halves of this account, because the same template can be realized on the scientific side by a Method and on the operational side by a Procedure.

A facility writes each concrete sequence as a Recipe, a reusable list of setpoints, checks, and actions that expands into a ready-to-run Procedure once an operator fills in the adjustable values. This is also the place to be honest about status. At 2-BM the dark- and flat-field captures run today, because they reuse an action the system already performs. The coordinated energy change and the hexapod reboot are written as Recipes and can be reviewed, but they cannot yet run, because the actions they call are not connected to hardware. The post says which is which on purpose, and that line, between what runs and what is so far only designed, is drawn deliberately across the whole project.

## Why a ladder, not a flat script

A single flat script would force an impossible compromise. Written generally, it could never address real hardware; written specifically, it could never travel to another facility. The ladder refuses that compromise, and it takes four steps rather than one because each draws a reuse boundary at a different rate of change. The technique changes across years and is shared between facilities; a facility's approach changes now and then; the hardware binding changes whenever an instrument is swapped or the wiring is reconfigured; the measurement changes every single time. Giving each concern its own step lets a change land on exactly one of them and leave the rest untouched: swap a detector and only the Plan changes, while the Method and Practice above it are reused as they stand; carry the work to another facility and only the Method travels. The difference between intention and outcome, the knowledge Polanyi said we hold but cannot fully put into words, is preserved at the foot of the ladder, in the Run and its operational counterpart the Procedure. Four steps, one idea: describe the technique once, carry it out anywhere, and keep a faithful record of what actually happened.
