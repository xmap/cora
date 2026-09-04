---
theme: default
title: 'CORA: A Connecting Layer for Beamline Experiments'
info: |
  Introduction to CORA, tuned for the MAX IV Fields of View workshop (May 2026).
  Generalisable to any tomography- or AI-adjacent venue with light edits.
  Doğa Gürsoy.
author: Doğa Gürsoy
keywords: cora, synchrotron, tomography, provenance, ai, autonomy
presenter: false
download: true
exportFilename: 2026-maxiv-fov
mdc: true
transition: fade
layout: cover
background: /hero-bloom.webp
class: text-white
---

# CORA

## Toward a Connecting Layer for Beamline Experiments

<div class="text-sm opacity-90 mt-8">
Doğa Gürsoy · Argonne National Laboratory<br/>
<span class="text-xs opacity-75">Fields of View Workshop · MAX IV · May 2026</span>
</div>

<div class="text-xs opacity-65 italic mt-6">
Humans, instruments, and AI agents reading one record.<br/>
A project status, looking for the people who care about the same problem.
</div>

---

# Who I am

<div class="text-base mt-4">

*Mission: close the loop between what we measure and what we know.*

</div>

<div class="border-l-2 border-[#0A7E8C]/50 pl-5 mt-6">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3">Four layers, same mission</div>
  <div class="space-y-1.5 text-sm">
    <div><span class="font-semibold text-[#0A7E8C]">Software</span> <span class="opacity-80">· TomoPy: open-source CT reconstruction in production at multiple synchrotrons.</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Algorithms</span> <span class="opacity-80">· iterative methods for imaging with coherent sources.</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Scale</span> <span class="opacity-80">· distributed reconstruction methods for large-scale CT problems.</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Systems</span> <span class="opacity-80">· coded-aperture CT prototypes.</span></div>
  </div>
</div>

<div class="text-base mt-6 opacity-80">
Plus 10+ facilities visited as a user, never as a settled local.
</div>

---

# What I saw

<div class="text-base mt-4 opacity-80">

Every layer, every visit, the same gap.

</div>

<div class="text-2xl font-semibold text-[#0A7E8C] my-16 text-center leading-normal">
This field's knowledge lives in people's heads,<br/>not in anything shared.
<div class="text-sm font-normal opacity-60 italic mt-3">
after Polanyi, <span class="not-italic">The Tacit Dimension</span> (1966)
</div>
</div>

<div class="text-base">

Every visit costs hours just to remember and realign. That is the fragmentation problem, lived. After enough years, you stop accepting that the field cannot have a memory.

</div>

---

# Where the context lives

<div class="text-base mt-2 opacity-80">

The same kind of information takes a different shape at every phase. The shapes rarely meet.

</div>

<div class="mt-5 text-sm">

| Kind | Before the beam | At the beamline | After the beam |
|---|---|---|---|
| **The sample** | recipe, inventory | mounting notes, photos | returned, archived, or destroyed |
| **Live state** | scheduled config | EPICS, Tango, Bluesky | rarely retained beyond the run |
| **Records** | proposal, safety forms | HDF5 headers, logbook entries | notebooks, paper supplements |
| **Memory** | what we agreed | the PI, the student's notes | *"ask Dave"* |

</div>

<div class="mt-6 text-sm opacity-80">

Read across a row. Same kind of thing, three different artifacts, no continuous identity between them.

</div>

---

# And what you cannot ask of it

<div class="text-base mt-2 opacity-80">

Information is everywhere. Connection is nowhere.

</div>

<div class="mt-5 text-sm">

| What you cannot ask | Pieces that exist | What's missing |
|---|---|---|
| *What did we actually run, vs the proposal?* | proposal text, live state | nothing <span class="text-teal-600 font-semibold">joins</span> them |
| *Which sample was on the stage during this anomaly?* | mounting notes, logbook | nothing <span class="text-teal-600 font-semibold">links</span> sample to event |
| *Everything I ever did with sample A across visits?* | sample inventory, per-visit logs | nothing <span class="text-teal-600 font-semibold">carries</span> it across visits |
| *Which raw frames produced figure 3?* | TIFF files, paper supplement | nothing <span class="text-teal-600 font-semibold">chains</span> frame to figure |
| *Can an agent steer the next scan?* | live state, prior runs | nothing <span class="text-teal-600 font-semibold">closes</span> the loop |

</div>

<div class="mt-6 text-sm opacity-80">

Every piece is real. **No one owns the connections between them.** The picture assembles in someone's head, and only while they are around.

</div>

---

# What's been tried

<div class="text-base mt-2 opacity-80">

Each layer below solved a piece. None of them owned the connections.

</div>

<div class="mt-5 text-sm">

| Layer | Examples | Blind to |
|---|---|---|
| **Schema** | NeXus, CIF/mmCIF, DataCite (FAIR principles overall) | <span class="text-teal-600 font-semibold">who</span> fills the slots |
| **Catalog** | SciCat, ICAT, Tiled | <span class="text-teal-600 font-semibold">why</span> each output exists |
| **Logbook** | Olog, ELOG, eLabFTW | <span class="text-teal-600 font-semibold">what</span> the instrument was doing |
| **Orchestrator** | Bluesky, Sardana, NICOS | anything <span class="text-teal-600 font-semibold">across visits</span> |
| **Instrument archive** | EPICS Archiver, Channel Archiver | the sample, the <span class="text-teal-600 font-semibold">intent</span>, the decision |
| **Sample tracking** | facility LIMS (ISPyB, openBIS), paper notebooks | <span class="text-teal-600 font-semibold">what</span> the beamline did with it |

</div>

<div class="mt-6 text-sm opacity-80">

Read the right column down. That column is the layer **no one owns**.

</div>

---

# Why no one has built the connecting layer

<div class="text-base mt-2 opacity-80">

Three reasons, in different registers.

</div>

<div class="mt-6 space-y-5 text-sm">

<div>

<span class="text-teal-600 font-semibold">Tolerable demand.</span> Humans were the connecting layer. The PI was always around; the student took the notes; the operator remembered the calibration drift. *"Ask Dave"* worked. The absence of machine-queryable connections was not felt as a bug, because the workaround was free at the scale of a single career.

</div>

<div>

<span class="text-teal-600 font-semibold">Wrong incentives.</span> Glue between other people's tools does not get funded, papered, or credited (Howison & Herbsleb 2011). Per-facility integrations get built, but on borrowed sysadmin time, and they do not transfer when the sysadmin moves on. The "connecting tissue" role does not exist in any org chart.

</div>

<div>

<span class="text-teal-600 font-semibold">Recent transfer.</span> The patterns are not new: event sourcing began in banking in the 1980s, domain-driven design dates from Evans (2003), Postgres LISTEN/NOTIFY has been production-stable since 2010. What is recent is the cost (cheap enough for a solo project) and the cross-domain transfer into scientific instrumentation (rare until now).

</div>

</div>

<div class="mt-6 text-sm opacity-80">

The cultural reason was the load-bearing one. It is about to break: the reasoner is now a model that does not share the room.

</div>

---

# What CORA is

<div class="text-xl font-semibold text-[#0A7E8C] mt-4 mb-4 text-center leading-relaxed">
So I stopped waiting, and started building the connecting layer.
</div>

<div class="text-base opacity-80 mb-3 text-center leading-relaxed">

A queryable causal record of **what was set, read, produced, and decided**. Shared by humans and AI agents, plugged into existing systems through adapters.

</div>

<div class="grid grid-cols-[1fr_auto_1fr_auto_1fr] gap-4 items-stretch mt-4 text-xs">

<div class="border border-gray-400/50 rounded-xl p-3.5 flex flex-col">
  <div class="text-[11px] font-medium mb-3 text-center opacity-60 uppercase tracking-[0.22em]">Beamline systems</div>
  <div class="grid grid-cols-2 grid-rows-2 gap-2 text-center flex-1">
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">EPICS / Tango</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">Bluesky / Sardana</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">SciCat / ISPyB</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">Globus / files</div>
  </div>
</div>

<svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0 self-center" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 12h18"/>
  <path d="M8 7l-5 5 5 5"/>
  <path d="M16 7l5 5-5 5"/>
</svg>

<div class="border-2 border-[#0A7E8C] rounded-xl p-3 bg-[#0A7E8C]/8 flex flex-col">
  <div class="text-[11px] font-medium mb-3 text-center text-[#0A7E8C] uppercase tracking-[0.22em]">CORA</div>
  <div class="flex flex-col items-center gap-1 text-center flex-1">
    <div class="w-full border border-[#0A7E8C]/40 rounded-lg flex-1 flex items-center justify-center px-2 py-4 bg-[#0A7E8C]/10 text-xs font-medium text-[#0A7E8C]">Adapters</div>
    <svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 6v12"/>
      <circle cx="12" cy="4" r="3" fill="currentColor" stroke="none"/>
      <circle cx="12" cy="20" r="3" fill="currentColor" stroke="none"/>
    </svg>
    <div class="w-full border-2 border-[#0A7E8C]/60 rounded-lg flex-1 flex items-center justify-center px-2 py-4 bg-[#0A7E8C]/10 text-xs font-medium text-[#0A7E8C]">Domain BCs</div>
    <svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 6v12"/>
      <circle cx="12" cy="4" r="3" fill="currentColor" stroke="none"/>
      <circle cx="12" cy="20" r="3" fill="currentColor" stroke="none"/>
    </svg>
    <div class="w-full border border-[#0A7E8C]/40 rounded-lg flex-1 flex items-center justify-center px-2 py-4 bg-[#0A7E8C]/10 text-xs font-medium text-[#0A7E8C]">Event log</div>
  </div>
</div>

<svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0 self-center" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 12h18"/>
  <path d="M8 7l-5 5 5 5"/>
  <path d="M16 7l5 5-5 5"/>
</svg>

<div class="border border-gray-400/50 rounded-xl p-3.5 flex flex-col">
  <div class="text-[11px] font-medium mb-3 text-center opacity-60 uppercase tracking-[0.22em]">Consumers</div>
  <div class="grid grid-cols-2 grid-rows-2 gap-2 text-center flex-1">
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">REST clients</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">MCP agents</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">Dashboards</div>
    <div class="border border-gray-400/40 rounded-lg flex items-center justify-center px-2 bg-gray-500/10">Notebooks</div>
  </div>
</div>

</div>

<div class="mt-6 text-sm opacity-80">

The point is not to record more. **It is to make the record one that humans and machines can both reason about.**

</div>

---

# What CORA is not

<div class="text-base mt-2 opacity-80">

CORA is intentionally narrow. Each layer below keeps doing its job.

</div>

<div class="mt-5 text-sm">

| Layer | Examples | Keeps doing |
|---|---|---|
| **Control system** | EPICS, Tango | <span class="text-teal-600 font-semibold">driving</span> the hardware |
| **Orchestrator** | Bluesky, Sardana, NICOS | <span class="text-teal-600 font-semibold">sequencing</span> the scan *(CORA fills in where absent)* |
| **Data movement** | Globus, Tiled, file system | <span class="text-teal-600 font-semibold">moving</span> the bytes |
| **Analysis** | TomoPy, NumPy, PyTorch | <span class="text-teal-600 font-semibold">doing</span> the math |
| **LIMS / catalog** | SciCat, ISPyB | <span class="text-teal-600 font-semibold">holding</span> samples and finished products |
| **Scheduler** | DUO, SMIS | <span class="text-teal-600 font-semibold">booking</span> the beam |
| **Agent runtime** | LangChain, AutoGen, MCP clients | <span class="text-teal-600 font-semibold">running</span> the agent loop (CORA is the MCP server they call) |

</div>

<div class="mt-6 text-sm opacity-80">

CORA reads from and writes to these through adapters. **CORA's job is the record above them:** what happened, who decided, and why. LIMS owns sample logistics; CORA records what the beamline did *with* the sample. Where no orchestrator is in place, CORA can sequence runs itself; where one already drives the beamline, it keeps driving and CORA stays the record.

</div>

---

# Why now

<div class="text-base mt-2 opacity-80">

The gap was tolerable for decades. What changed: **AI as a working participant**.

</div>

<div class="mt-5 text-sm">

| Then it was tolerable | Now it isn't |
|---|---|
| The reasoner was in the room | The reasoner is <span class="text-teal-600 font-semibold">a model that isn't</span> |
| Joins lived in someone's head | A model only reasons from <span class="text-teal-600 font-semibold">what it can read</span> |
| AI agents were research demos | Agents <span class="text-teal-600 font-semibold">plan, tune mid-run, flag anomalies</span> |
| Building this scale needed a team | Humans design, <span class="text-teal-600 font-semibold">LLMs implement the scaffolding</span> |

</div>

<div class="mt-6 text-base font-semibold">

An agent is only as coherent as the record it can read.

</div>

<div class="mt-3 text-sm opacity-80">

AI also lies, drifts, and hallucinates. A unified record is what lets you tell when it is doing those things. CORA does not assume the agent is right; it makes the agent answerable.

</div>

---

# A concrete example

<div class="text-base mt-2 opacity-80">
In-situ freezing of brine in a porous sample; 30 minutes into a 4-hour scan, an interesting growth front emerges in the streaming reconstruction.
</div>

<div class="mt-5 text-sm">

| Beat | Without a unified record | With CORA |
|---|---|---|
| **Notice** | a glance at the live recon | Run telemetry <span class="text-teal-600 font-semibold">surfaces</span> the brightening rate and dose-to-date |
| **Recall** | *"this looked like last winter's NaBr run"* | <span class="text-teal-600 font-semibold">queries</span> prior runs at matched composition |
| **Propose** | *"let's zoom to 5× there"* | Decision <span class="text-teal-600 font-semibold">proposes</span> lens 1.1× → 5× on the brightest front |
| **Bound** | gut check on remaining dose budget | Trust <span class="text-teal-600 font-semibold">authorizes</span> against the envelope j.park pre-set; Budget gates remaining dose |
| **Act** | operator switches the lens by hand | scan-runner agent <span class="text-teal-600 font-semibold">executes</span>; Optique Peter ack and new dataset land as events |
| **Audit** | *"the postdoc remembers when"* | <span class="text-teal-600 font-semibold">one query</span> traces every zoom across the cooling |

</div>

<div class="mt-6 text-sm opacity-80 text-center">

The cooling happens once. Every zoom either gets recorded against intent, or it gets remembered. Next slide: what that record actually looks like.

</div>

---

# What the record looks like

<div class="grid grid-cols-2 gap-5 text-[10px] mt-3 [&>div]:rounded-xl [&>div]:border [&>div]:border-[#0A7E8C]/25 [&>div]:bg-[#0A7E8C]/[0.04] [&>div]:p-3 [&_pre]:!text-[10px] [&_pre]:!leading-snug">

<div>

<div class="flex items-center gap-2 mb-2">
  <div class="w-1 h-4 bg-[#0A7E8C] rounded-full"></div>
  <div class="text-[10px] font-bold uppercase tracking-[0.15em] text-[#0A7E8C]">What CORA writes</div>
  <div class="ml-auto text-[9px] opacity-50 font-mono uppercase tracking-wider">event</div>
</div>

```json
{
  "event": "ZoomProposed",
  "run_id": "run_2026-05-15_2bm_ice_007",
  "subject_id": "brine_sand_NaBr_5pct_S12",
  "principal": {"kind": "agent", "id": "front_tracker_v3"},
  "from_lens": "1.1x",
  "to_lens":   "5x",
  "from_pixel_size": 3.14,
  "to_pixel_size":   0.69,
  "roi_center_px": {"x": 1280, "y": 1024},
  "brightening_pct_min": 8.2,
  "reasoning_ref": "decision_front_pattern_t1820s",
  "ts": "2026-05-15T11:08:42.187Z"
}
```

<div class="mt-2 pt-2 border-t border-[#0A7E8C]/20 text-[10px] opacity-70 italic">
Immutable. Every actor (human or agent) writes the same shape, signed by the same identity model.
</div>

</div>

<div>

<div class="flex items-center gap-2 mb-2">
  <div class="w-1 h-4 bg-[#0A7E8C] rounded-full"></div>
  <div class="text-[10px] font-bold uppercase tracking-[0.15em] text-[#0A7E8C]">What you can ask back</div>
  <div class="ml-auto text-[9px] opacity-50 font-mono uppercase tracking-wider">query</div>
</div>

```text
$ cora why "S12 lens change at t=1820s"

11:08:42.0  RunReading
            brightening 8.2%/min, dose 3.1/8.0 kGy

11:08:42.2  ZoomProposed
            by agent front_tracker_v3
            lens: 1.1x → 5x, ROI (1280, 1024)

11:08:42.3  EnvelopeChecked
            pre-authorized policy (operator: j.park)

11:08:42.4  LensChanged
            by agent scan_runner
            Optique Peter ack: pixel 3.14 → 0.69 µm
```

<div class="mt-2 pt-2 border-t border-[#0A7E8C]/20 text-[10px] opacity-70 italic">
Four hundred milliseconds, four events. The reason the lens changed is in the record, not in someone's head.
</div>

</div>

</div>

<div class="mt-4 grid grid-cols-3 gap-4 text-[10px] opacity-85">

<div class="border-l-2 border-[#0A7E8C]/50 pl-3">
<span class="font-bold text-[#0A7E8C] uppercase tracking-wider text-[9px] block mb-0.5">One shape</span>
Every event names the principal, the change, and the reasoning ref. Same envelope across all bounded contexts.
</div>

<div class="border-l-2 border-[#0A7E8C]/50 pl-3">
<span class="font-bold text-[#0A7E8C] uppercase tracking-wider text-[9px] block mb-0.5">One log</span>
Append-only and immutable at the database level. Replay rebuilds any projection from scratch.
</div>

<div class="border-l-2 border-[#0A7E8C]/50 pl-3">
<span class="font-bold text-[#0A7E8C] uppercase tracking-wider text-[9px] block mb-0.5">One query</span>
<i>"Why did X"</i> returns the causal chain in order. Not a search across files; a walk along the log.
</div>

</div>

<div class="mt-4 text-sm opacity-80 text-center">

Audit, explainability, and reproducibility become <b>query operations</b>, not human reconstruction.

</div>

---

# How it's designed

<div class="text-base mt-2 opacity-80">

Six choices. Each is well-known in industry. The new part is the combination, applied to a beamline.

</div>

<div class="mt-5 text-sm">

| Choice | What it gives you |
|---|---|
| **Domain-driven design** (bounded contexts) | each domain <span class="text-teal-600 font-semibold">owns</span> its rules; one place to change them |
| **Event-sourced storage** | every state change is one <span class="text-teal-600 font-semibold">immutable</span> event; replay is free |
| **Functional core, side effects at edges** | pure decisions; <span class="text-teal-600 font-semibold">testable</span> without the beam |
| **REST + MCP twin surfaces** | every command on both, <span class="text-teal-600 font-semibold">same handler</span> |
| **Agents as principals** | humans and LLMs <span class="text-teal-600 font-semibold">share</span> identity, authz, audit |
| **Recipe ladder** (Method → Practice → Plan → Run) | abstract intent flows to concrete execution; <span class="text-teal-600 font-semibold">facility-neutral</span> |

</div>

<div class="mt-6 text-sm opacity-80">

None of the rows are individually novel. **The combination, applied to scientific instrumentation, is.**

</div>

---

# How it's built

<div class="text-base mt-2 opacity-80">

The CORA card, opened up. Three layers, each with a single job.

</div>

<div class="grid grid-cols-[1fr_auto_1fr_auto_1fr] gap-3 items-stretch mt-6">

<div class="border-2 border-[#0A7E8C] rounded-xl p-4 bg-[#0A7E8C]/8 flex flex-col">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3 text-center">Adapters</div>
  <div class="flex-1 text-xs opacity-85 text-center leading-relaxed mb-3">
    Translate between CORA's model and external tools.
  </div>
  <div class="flex flex-wrap gap-1 justify-center text-[10px]">
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">FastAPI <span class="opacity-60">REST</span></span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">MCP SDK <span class="opacity-60">agents</span></span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30 opacity-70">EPICS / SciCat <span class="opacity-80">next</span></span>
  </div>
</div>

<svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0 self-center" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 12h18"/>
  <path d="M8 7l-5 5 5 5"/>
  <path d="M16 7l5 5-5 5"/>
</svg>

<div class="border-2 border-[#0A7E8C] rounded-xl p-4 bg-[#0A7E8C]/8 flex flex-col">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3 text-center">Domain BCs</div>
  <div class="flex-1 text-xs opacity-85 text-center leading-relaxed mb-3">
    Model what an experiment <i>is</i> in beamline language.
  </div>
  <div class="flex flex-wrap gap-1 justify-center text-[10px]">
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">Python 3.13</span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">pyright strict</span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">no I/O deps</span>
  </div>
</div>

<svg class="w-5 h-5 text-[#0A7E8C] flex-shrink-0 self-center" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 12h18"/>
  <path d="M8 7l-5 5 5 5"/>
  <path d="M16 7l5 5-5 5"/>
</svg>

<div class="border-2 border-[#0A7E8C] rounded-xl p-4 bg-[#0A7E8C]/8 flex flex-col">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3 text-center">Event log</div>
  <div class="flex-1 text-xs opacity-85 text-center leading-relaxed mb-3">
    Append-only history. Replay rebuilds any projection.
  </div>
  <div class="flex flex-wrap gap-1 justify-center text-[10px]">
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">Postgres + pgvector</span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">Atlas migrations</span>
    <span class="px-2 py-0.5 rounded-md bg-[#0A7E8C]/15 border border-[#0A7E8C]/30">INSERT-only role</span>
  </div>
</div>

</div>

<div class="mt-6 text-center text-sm font-semibold bg-[#0A7E8C]/10 p-3 rounded-lg border border-[#0A7E8C]/20">
Today: <span class="text-[#0A7E8C]">14 bounded contexts · 20 aggregates · 9,963 passing tests · pyright 0/0/0 strict · forward-only migrations</span>
</div>

<div class="mt-4 text-sm opacity-80">

The repo has more under each layer: per-BC aggregates, deciders, projections. **But this is the picture to leave with.**

</div>

---

# Where the project is

<div class="text-base mt-2 opacity-80">

Architecture stable. Pilot in flight. Honest about both.

</div>

<div class="grid grid-cols-2 gap-8 mt-5">

<div class="flex flex-col gap-5">

<div class="border-l-2 border-[#0A7E8C]/50 pl-5">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3">Built and stable · 14 bounded contexts</div>
  <div class="space-y-1 text-xs">
    <div><span class="font-semibold text-[#0A7E8C]">Access</span> <span class="opacity-75">· actor identity (register, deactivate)</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Trust</span> <span class="opacity-75">· zones, conduits, policies</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Equipment</span> <span class="opacity-75">· family, affordances, settings, ports, condition</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Recipe</span> <span class="opacity-75">· Capability template · Method → Practice → Plan → Run → Dataset</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Subject</span> <span class="opacity-75">· sample identity across stations</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Run</span> <span class="opacity-75">· execution, readings, procedure</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Campaign</span> <span class="opacity-75">· multi-run studies (in-situ, operando, sweeps)</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Data</span> <span class="opacity-75">· datasets with lineage and intent</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Decision</span> <span class="opacity-75">· proposals, approvals, reasoning refs</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Supply</span> <span class="opacity-75">· reagents and consumables state</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Operation</span> <span class="opacity-75">· procedure execution (ISA-106 lens)</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Safety</span> <span class="opacity-75">· clearances, hazard classifications, approval chains</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Caution</span> <span class="opacity-75">· operator tribal-knowledge cautions and workarounds</span></div>
    <div><span class="font-semibold text-[#0A7E8C]">Agent</span> <span class="opacity-75">· AI agents as principals (RunDebrief, CautionDrafter live)</span></div>
  </div>
</div>

<div class="border-l-2 border-[#0A7E8C]/25 pl-5 opacity-75">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C]/80 mb-3">Designed, next · 2 more in scope</div>
  <div class="space-y-1 text-xs italic">
    <div><span class="font-semibold not-italic">Strategy</span> <span class="opacity-75">· decision modes (human / AI / hybrid) for workflows</span></div>
    <div><span class="font-semibold not-italic">Budget</span> <span class="opacity-75">· allocation tracking (hours, storage, USD, tokens) with limits</span></div>
  </div>
</div>

</div>

<div class="flex flex-col gap-6">

<div>
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-3">Pilot ladder</div>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center gap-3 p-2.5 border-2 border-[#0A7E8C] rounded-lg bg-[#0A7E8C]/8">
      <div class="text-lg font-medium text-[#0A7E8C] flex-shrink-0 w-6 text-center">1</div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-xs">APS 35-BM</div>
        <div class="text-[11px] text-[#0A7E8C]">integration in progress</div>
      </div>
    </div>
    <div class="flex items-center gap-3 p-2.5 border border-[#0A7E8C]/25 rounded-lg">
      <div class="text-lg font-medium text-[#0A7E8C]/70 flex-shrink-0 w-6 text-center">2</div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-xs opacity-90">Other APS imaging beamlines</div>
        <div class="text-[11px] opacity-60">next</div>
      </div>
    </div>
    <div class="flex items-center gap-3 p-2.5 border border-[#0A7E8C]/25 rounded-lg">
      <div class="text-lg font-medium text-[#0A7E8C]/70 flex-shrink-0 w-6 text-center">3</div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-xs opacity-90">Cross-facility (MAX IV the natural step)</div>
        <div class="text-[11px] opacity-60">the conversation I'm here to start</div>
      </div>
    </div>
  </div>
</div>

<div class="border-l-2 border-gray-400/40 pl-5 italic opacity-75 text-xs leading-relaxed">
Solo, multi-year horizon. Architecture stable; pilot integration ongoing; not yet handling production beamline traffic.
</div>

<div class="border-l-2 border-[#0A7E8C]/50 pl-5">
  <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-[#0A7E8C] mb-2">Where I'd most welcome challenge</div>
  <div class="text-xs opacity-85 leading-relaxed">
    High-frequency telemetry · cross-experiment sagas · agent trust boundaries · schema governance across facilities.
  </div>
</div>

</div>

</div>

---

# What I'd want from you

<div class="text-base mt-2 opacity-90">
Depending on who you are, different things help:
</div>

<div class="mt-5 text-sm">

|  | If you run a beamline | If you build scientific software | If you work on AI for science |
|---|---|---|---|
| **Show me <span class="text-teal-600 font-semibold">what breaks</span>** | what about the model would not fit your facility | which integration points your stack would expose | what context your agents actually need from instruments |
| **Tell me <span class="text-teal-600 font-semibold">what's missing</span>** | how a real shift actually unfolds (I'd love a half-day walkthrough) | the adapter shape you'd want; open an issue | what would close the gap from demo to working tool |

</div>

<div class="text-center mt-10">
<div class="text-base font-semibold">
<code>dgursoy@anl.gov</code> · <code>github.com/xmap/cora</code>
</div>
<div class="text-sm opacity-75 mt-2">
Issues, design memos, BC maps: all public. The repo is the work.
</div>
</div>

---

# Three things to remember

<div class="mt-8 space-y-8 text-base">

<div class="flex gap-4">
<div class="text-3xl font-bold text-[#0A7E8C] flex-shrink-0 w-10">1</div>
<div>
The connecting layer between instruments, samples, data, and decisions has been missing for decades. <span class="font-semibold">AI is what makes it urgent.</span>
</div>
</div>

<div class="flex gap-4">
<div class="text-3xl font-bold text-[#0A7E8C] flex-shrink-0 w-10">2</div>
<div>
CORA is one honest attempt at that layer: <span class="font-semibold">event-sourced, REST + MCP, beamline-vocabulary, open-source.</span> Complementary to NeXus, EPICS, SciCat, not a replacement.
</div>
</div>

<div class="flex gap-4">
<div class="text-3xl font-bold text-[#0A7E8C] flex-shrink-0 w-10">3</div>
<div>
It exists today: <span class="font-semibold">14 bounded contexts, 9,963 tests, APS 35-BM pilot in progress.</span> Looking for collaborators who care about the same problem, including this room.
</div>
</div>

</div>

---
layout: cover
background: /hero-bloom.webp
class: text-white text-center
---

# Thank you

<div class="text-lg opacity-90 mt-8">
The most useful thing for me today is what felt off, or what felt missing.<br/>
Do not sugarcoat it.
</div>

<div class="mt-12 text-sm opacity-70">
Q&A
</div>
