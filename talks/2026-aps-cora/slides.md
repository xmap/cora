---
theme: default
title: 'CORA: the questions an experiment can be asked afterwards'
info: |
  CORA as a stream of entries, each one there because somebody will have a
  question; a climb from the questions a log can answer to the ones a record
  has to answer about itself. Doğa Gürsoy.
author: Doğa Gürsoy
keywords: aps, record, provenance, beamline, accountability, cora
presenter: false
download: true
exportFilename: 2026-aps-cora
mdc: true
transition: fade
layout: cover
background: /hero-typewriter.webp
class: text-white
---

# CORA

## What an experiment can be asked and who is asking

<div class="text-sm opacity-90 mt-8">
Doğa Gürsoy · Argonne National Laboratory<br/>
<span class="text-xs opacity-75">Advanced Photon Source · 2026</span>
</div>

---

# Four parts

<div class="mt-8">
  <div class="space-y-1">
    <div class="grid gap-4 items-baseline rounded px-4 py-2" style="grid-template-columns:34px 1fr;background-color:var(--panel)">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink)">1</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="color:var(--ink)">The questions<span class="text-[10px] font-medium uppercase tracking-[0.16em] ml-3 opacity-70">you are here</span></div>
        <div class="text-[12.5px] leading-snug mt-1" style="color:var(--ink);opacity:0.85">What is asked about an experiment.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">2</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The machinery</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What the record is made of.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">3</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">At a beamline</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What runs at 2-BM today.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">4</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">Proposed next steps</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">Where this path goes.</div>
      </div>
    </div>
  </div>
  <div class="mt-5 mx-auto" style="max-width:560px"><SpineRow :active="0" /></div>
</div>

---

# When the questions arise

<div class="text-base mt-1">

A run of questions

</div>

<div class="mt-6">
<svg viewBox="0 0 1000 66" class="w-full" style="max-height:62px">
  <defs>
    <linearGradient id="fadeafter" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="#8B6914" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#8B6914" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <text x="0" y="12" style="font-size:11px;font-weight:600;letter-spacing:2.2px;fill:var(--ink)">BEFORE</text>
  <text x="0" y="30" style="font-size:11px;fill:currentColor;opacity:0.45">weeks of getting ready</text>
  <line x1="0" y1="52" x2="300" y2="52" stroke="#8B6914" stroke-width="2" stroke-dasharray="4 5" opacity="0.45"/>
  <text x="344" y="12" style="font-size:11px;font-weight:600;letter-spacing:2.2px;fill:var(--ink)">DURING</text>
  <text x="344" y="30" style="font-size:11px;fill:currentColor;opacity:0.45">a few days of beam</text>
  <rect x="344" y="47" width="312" height="9" rx="4.5" fill="#8B6914" opacity="0.55"/>
  <text x="688" y="12" style="font-size:11px;font-weight:600;letter-spacing:2.2px;fill:var(--ink)">AFTER</text>
  <text x="688" y="30" style="font-size:11px;fill:currentColor;opacity:0.45">for as long as the data is used</text>
  <line x1="688" y1="52" x2="1000" y2="52" stroke="#8B6914" stroke-width="2" stroke-dasharray="4 5" opacity="0.45"/>
</svg>
</div>

<div class="grid gap-x-8 mt-4" style="grid-template-columns:1fr 1fr 1fr">
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;What did we propose to measure?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Is this working, or wasting the shift?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;What settings produced this file?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Is the instrument as we left it?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Are we measuring what we came for?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Can I compare these two runs?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Has this sample been run before?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;When did it fail, and why?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Which of these runs are usable?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Who may change the setup?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Do we keep going, or re-plan?&rdquo;</div>
  <div class="text-[13px] leading-snug italic border-t border-[#8B6914]/18 py-2.5 h-full" style="color:var(--ink);opacity:0.88">&ldquo;Could anyone reproduce this in a year?&rdquo;</div>
</div>

<div class="text-base mt-6">

Answered today by a system or by a person still here.

</div>

---

# Who is asking

<div class="text-base mt-1">

One run of beam time

</div>

<div>

  <div class="grid gap-6 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.42fr 1fr 0.58fr">
    <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Division management</div>
    <div class="text-[13.5px] leading-snug italic font-medium" style="color:var(--ink);opacity:0.9">&ldquo;How much of that beam time was science?&rdquo;</div>
    <div class="text-[12px] leading-snug opacity-60">What the next allocation is worth.</div>
  </div>

  <div class="grid gap-6 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.42fr 1fr 0.58fr">
    <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Beamline scientist</div>
    <div>
      <div class="text-[13.5px] leading-snug italic font-medium" style="color:var(--ink);opacity:0.9">&ldquo;Which runs used the old detector distance?&rdquo;</div>
      <div class="text-[13.5px] leading-snug italic font-medium mt-1.5" style="color:var(--ink);opacity:0.9">&ldquo;Is this fault expected?&rdquo;</div>
    </div>
    <div class="text-[12px] leading-snug opacity-60">What has to be re-taken and by whom.</div>
  </div>

  <div class="grid gap-6 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.42fr 1fr 0.58fr">
    <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">The user</div>
    <div class="text-[13.5px] leading-snug italic font-medium" style="color:var(--ink);opacity:0.9">&ldquo;What exactly produced the figure in the paper?&rdquo;</div>
    <div class="text-[12px] leading-snug opacity-60">Whether the result survives a referee.</div>
  </div>

  <div class="grid gap-6 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.42fr 1fr 0.58fr">
    <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Downstream analysis</div>
    <div class="text-[13.5px] leading-snug italic font-medium" style="color:var(--ink);opacity:0.9">&ldquo;Which frames can go in the training set?&rdquo;</div>
    <div class="text-[12px] leading-snug opacity-60">Whether the model can be defended.</div>
  </div>

  <div class="grid gap-6 items-baseline border-t-2 border-[#8B6914]/45 py-2.5" style="grid-template-columns:0.42fr 1fr 0.58fr">
    <div class="text-[11px] font-medium uppercase tracking-[0.14em] font-semibold" style="color:var(--ink)">An agent, at 3am</div>
    <div>
      <div class="text-[13.5px] leading-snug italic font-semibold" style="color:var(--ink)">&ldquo;Am I allowed to change the plan right now?&rdquo;</div>
      <div class="text-[13.5px] leading-snug italic font-semibold mt-1.5" style="color:var(--ink)">&ldquo;Has this condition occurred before, in any earlier run?&rdquo;</div>
      <div class="text-[13.5px] leading-snug italic font-semibold mt-1.5" style="color:var(--ink)">&ldquo;Do earlier runs on this material support what I see?&rdquo;</div>
      <div class="text-[13.5px] leading-snug italic font-semibold mt-1.5" style="color:var(--ink)">&ldquo;Which of my last ten decisions would a person have refused?&rdquo;</div>
    </div>
    <div class="text-[12px] leading-snug opacity-85">Whether it acts or waits for a person.<div class="mt-1.5">The last one can be asked only by the thing that decided and answered only by a record.</div></div>
  </div>

</div>

<div class="text-base mt-6">

The last of these askers is not a person.

</div>

---

# The same asker, a different setup

<div class="text-base mt-1">

The asker held constant

</div>

<div class="grid gap-10 mt-6" style="grid-template-columns:1fr 1fr">
  <div>
    <div class="text-[11px] font-medium uppercase tracking-[0.2em] text-[#8B6914] mb-2">The instrument</div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Tomography</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Did the sample move between projections?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Ptychography</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Was the probe the same across the scan?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Holography</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Were the propagation distances the same?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Spectroscopy</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Was the energy calibrated the same way?&rdquo;</div>
    </div>
  </div>
  <div>
    <div class="text-[11px] font-medium uppercase tracking-[0.2em] text-[#8B6914] mb-2">The sample and the run</div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">In situ</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;What was the cell doing at this frame?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Operando</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Was the device working while we measured?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Large samples</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Which tile is this, and how did they line up?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2.5" style="grid-template-columns:0.46fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Throughput</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Which of the four thousand runs are usable?&rdquo;</div>
    </div>
  </div>
</div>

<div class="text-base mt-6">

Any instrument with any run type in any combination.

</div>

---

# The same setup, a different science

<div class="text-base mt-1">

Instrument and run type held constant

</div>

<div class="grid gap-10 mt-6" style="grid-template-columns:1.15fr 0.85fr">
  <div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2" style="grid-template-columns:0.4fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Batteries</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Where did the lithium go, and on which cycle?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2" style="grid-template-columns:0.4fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Catalysis</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Was the reaction running when this scan was taken?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2" style="grid-template-columns:0.4fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Bone and tissue</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Is this feature the specimen, or the preparation?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2" style="grid-template-columns:0.4fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Printed metal</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Were these pores there before the load, or after?&rdquo;</div>
    </div>
    <div class="grid gap-4 items-baseline border-t border-[#8B6914]/15 py-2" style="grid-template-columns:0.4fr 1fr">
      <div class="text-[11px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/70">Rock and flow</div>
      <div class="text-[12.5px] leading-snug italic" style="color:var(--ink);opacity:0.88">&ldquo;Did the flow path change as the pressure ramped?&rdquo;</div>
    </div>
  </div>
  <div class="rounded border border-[#8B6914]/25 p-4" style="background-color:var(--quiet)">
    <div class="text-[11px] font-medium uppercase tracking-[0.2em] text-[#8B6914] mb-3">So far</div>
    <div class="text-[12.5px] leading-relaxed py-0.5"><span class="font-semibold" style="color:var(--ink)">When</span>: before, during, after.</div>
    <div class="text-[12.5px] leading-relaxed py-0.5"><span class="font-semibold" style="color:var(--ink)">Who</span>: management, staff, users, analysis, software.</div>
    <div class="text-[12.5px] leading-relaxed py-0.5"><span class="font-semibold" style="color:var(--ink)">Which</span>: every instrument on the floor.</div>
    <div class="text-[12.5px] leading-relaxed py-0.5"><span class="font-semibold" style="color:var(--ink)">How</span>: every way a run can be shaped.</div>
    <div class="text-[12.5px] leading-relaxed py-0.5"><span class="font-semibold" style="color:var(--ink)">What</span>: every science those setups serve.</div>
    <div class="text-[12px] leading-snug opacity-70 mt-4 pt-3 border-t border-[#8B6914]/20">These combinations cannot be listed in advance. Next year's science arrives with questions nobody has written down yet.</div>
  </div>
</div>

<div class="text-base mt-6">

Ordinary questions answered today by a person.

</div>

---

# How it is answered today

<div class="text-base mt-1">

One question recorded in twelve places

</div>

<div class="grid gap-2.5 mt-5" style="grid-template-columns:1fr 1fr 1fr 1fr">
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The proposal</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">What science was approved and what it aimed to show.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The safety approval</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">What is permitted with this sample and until when.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The schedule</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Who held the beam that week and in which shift.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The storage ring</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">What the source was doing while the frames were taken.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The control system archive</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Every value second by second, including that distance.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The scan software</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Which scans ran with which parameters into which files.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The electronic logbook</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Detector settings and alignments as they were typed.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">Data movement and storage</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Where those files went and what was kept.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The reconstruction</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">Which settings turned those frames into a volume.</div>
  </div>
  <div class="rounded border border-[#8B6914]/22 p-3">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#8B6914]/75">The analysis code</div>
    <div class="text-[12px] leading-snug opacity-70 mt-1.5">What the group ran on it afterwards and in which version.</div>
  </div>
  <div class="rounded border p-3" style="border-color:rgba(10,126,140,0.6);background-color:var(--panel)">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em]" style="color:var(--ink)">A notebook, or paper</div>
    <div class="text-[12px] leading-snug mt-1.5" style="color:var(--ink);opacity:0.95">What was written down at the time but never typed up.</div>
  </div>
  <div class="rounded border p-3" style="border-color:rgba(10,126,140,0.6);background-color:var(--panel)">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.14em]" style="color:var(--ink)">A person</div>
    <div class="text-[12px] leading-snug mt-1.5" style="color:var(--ink);opacity:0.95">Why the distance was changed and on which day, often known only here.</div>
  </div>
</div>

<div class="text-base mt-6 font-medium">

A person can complete that join in an afternoon. An agent at three in the morning cannot complete it at all.

</div>

---

# Why I built this

<div class="text-base mt-1">

Where I came in

</div>

<div class="grid gap-4 mt-4" style="grid-template-columns:1fr 1fr">
  <div class="pl-4 border-l-2 border-[#8B6914]/45">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.18em] text-[#8B6914]">Autonomy, the prerequisite</div>
    <div class="text-[13.5px] leading-snug italic font-medium mt-1.5" style="color:var(--ink)">&ldquo;An experiment that gets through the night alone has to meet its own failures. What has to be on record for it to recover from them?&rdquo;</div>
  </div>
  <div class="pl-4 border-l-2 border-[#8B6914]/45">
    <div class="text-[10.5px] font-medium uppercase tracking-[0.18em] text-[#8B6914]">Intelligence, what it unlocks</div>
    <div class="text-[13.5px] leading-snug italic font-medium mt-1.5" style="color:var(--ink)">&ldquo;Once the science goal is steering the run, what has to be on record for the next move to be defensible?&rdquo;</div>
  </div>
</div>

<div class="mt-5">
<svg viewBox="0 0 1000 330" class="w-full" style="max-height:296px">
  <line x1="232" y1="272" x2="232" y2="22" stroke="currentColor" stroke-width="1.4" opacity="0.45"/>
  <polygon points="226,22 232,6 238,22" fill="currentColor" opacity="0.45"/>
  <line x1="232" y1="272" x2="806" y2="272" stroke="currentColor" stroke-width="1.4" opacity="0.45"/>
  <polygon points="806,266 822,272 806,278" fill="currentColor" opacity="0.45"/>

  <text transform="rotate(-90 88 147)" x="88" y="147" text-anchor="middle" style="font-size:11px;font-weight:600;letter-spacing:2.4px;fill:var(--ink);opacity:0.85">AUTONOMY</text>
  <text x="522" y="324" text-anchor="middle" style="font-size:11px;font-weight:600;letter-spacing:2.4px;fill:var(--ink);opacity:0.85">INTELLIGENCE</text>

  <text x="220" y="52" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Runs unattended</text>
  <text x="220" y="151" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Recovers on its own</text>
  <text x="220" y="250" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Someone approves</text>

  <text x="326" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">A fixed recipe</text>
  <text x="520" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">Computation steers the run</text>
  <text x="714" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">The science goal steers it</text>

  <rect x="526" y="50" width="252" height="94" rx="8" fill="#8B6914" fill-opacity="0.07" stroke="#8B6914" stroke-width="1.5" stroke-dasharray="5 5" opacity="0.7"/>
  <text x="652" y="92" text-anchor="middle" style="font-size:12.5px;font-weight:600;fill:var(--ink);opacity:0.9">where this is going</text>
  <text x="652" y="113" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.6">19-BM and the reason for the record</text>

  <rect x="260" y="150" width="252" height="94" rx="8" fill="#8B6914" fill-opacity="0.16" stroke="#8B6914" stroke-width="1.8"/>
  <text x="386" y="192" text-anchor="middle" style="font-size:12px;font-weight:700;letter-spacing:1.2px;fill:var(--ink)">2-BM, TODAY</text>
  <text x="386" y="213" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.75">a fixed recipe, a person approving</text>
</svg>
</div>

---

# The machinery

<div class="mt-8">
  <div class="space-y-1">
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">1</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The questions</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What is asked about an experiment.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline rounded px-4 py-2" style="grid-template-columns:34px 1fr;background-color:var(--panel)">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink)">2</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="color:var(--ink)">The machinery<span class="text-[10px] font-medium uppercase tracking-[0.16em] ml-3 opacity-70">you are here</span></div>
        <div class="text-[12.5px] leading-snug mt-1" style="color:var(--ink);opacity:0.85">What the record is made of.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">3</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">At a beamline</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What runs at 2-BM today.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">4</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">Proposed next steps</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">Where this path goes.</div>
      </div>
    </div>
  </div>
  <div class="mt-5 mx-auto" style="max-width:560px"><SpineRow :active="2" /></div>
</div>

---

# Inside the record

<div class="text-base mt-1">

One record across many contexts

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
  <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="261" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <text x="314.33" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who an actor is</text>
    <rect x="261" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <text x="314.33" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who may do what</text>
    <text x="314.33" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and where</text>
    <rect x="261" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <text x="314.33" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">the agents and</text>
    <text x="314.33" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">their grants</text>
    <rect x="261" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <text x="314.33" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">safety forms and</text>
    <text x="314.33" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they cover</text>
    <rect x="261" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <text x="314.33" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">hutch permits</text>
    <text x="314.33" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">as observed</text>
    <rect x="261" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <text x="314.33" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">operator warnings</text>
    <text x="314.33" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">in force</text>
    <rect x="374.67" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <text x="428.0" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">capability down</text>
    <text x="428.0" y="63" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">to plan</text>
    <rect x="374.67" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <text x="428.0" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">many runs as</text>
    <text x="428.0" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one series</text>
    <rect x="374.67" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <text x="428.0" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one execution as</text>
    <text x="428.0" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">it happened</text>
    <rect x="374.67" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <text x="428.0" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">every choice</text>
    <text x="428.0" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and why</text>
    <rect x="374.67" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <text x="428.0" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">the sample being</text>
    <text x="428.0" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">measured</text>
    <rect x="374.67" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.0" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <text x="428.0" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what came out</text>
    <text x="428.0" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and where</text>
    <rect x="488.33" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <text x="541.66" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">instruments and</text>
    <text x="541.66" y="63" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they do</text>
    <rect x="488.33" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <text x="541.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">measured values</text>
    <text x="541.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">with history</text>
    <rect x="488.33" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <text x="541.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">bakeouts,</text>
    <text x="541.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">alignment, upkeep</text>
    <rect x="488.33" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <text x="541.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what a run</text>
    <text x="541.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">consumes</text>
    <rect x="488.33" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <text x="541.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what a beamline</text>
    <text x="541.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">may spend</text>
    <rect x="488.33" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="541.66" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">records across</text>
    <text x="541.66" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">facilities</text>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# The agents, named

<div class="text-base mt-1">

Where people stop and agents begin

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="20" width="108" height="52" rx="10" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="30" cy="40" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 52 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="51" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="4" y="86" width="108" height="244" rx="10" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <rect x="22" y="98" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="105" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="105" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="98" x2="30.5" y2="94" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="92.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="109" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <text x="22" y="126" style="font-size:8px;fill:var(--ink);opacity:0.55">sixteen, seeded</text>
  <text x="22" y="135" style="font-size:8px;fill:var(--ink);opacity:0.55">at start-up</text>
  <rect x="12" y="143.00" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.8"/>
  <text x="58" y="153.50" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">RunWitness</text>
  <rect x="12" y="165.86" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.8"/>
  <text x="58" y="176.36" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">RunSupervisor</text>
  <rect x="12" y="188.71" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.8"/>
  <text x="58" y="199.21" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">ClearanceExpirer</text>
  <rect x="12" y="211.57" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.8"/>
  <text x="58" y="222.07" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">CautionPromoter</text>
  <rect x="12" y="234.43" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.8"/>
  <text x="58" y="244.93" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">ExperimentSteerer</text>
  <rect x="12" y="257.28" width="92" height="15" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1.1" stroke-opacity="0.5" stroke-dasharray="4 3"/>
  <text x="58" y="267.78" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600;opacity:0.8">ProcedureWatcher</text>
  <rect x="12" y="280.14" width="92" height="15" rx="4" fill="var(--amber-panel)" stroke="#5B8AA6" stroke-width="1.1" stroke-opacity="0.7"/>
  <text x="58" y="290.64" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">CautionDrafter</text>
  <rect x="12" y="303.00" width="92" height="15" rx="4" fill="var(--amber-panel)" stroke="#5B8AA6" stroke-width="1.1" stroke-opacity="0.7"/>
  <text x="58" y="313.50" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:600">RunDebriefer</text>
  <line x1="118" y1="46" x2="165" y2="46" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,46 164,42.2 164,49.8" fill="#8B6914"/>
  <line x1="118" y1="208" x2="165" y2="208" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,208 164,204.2 164,211.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="261" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <text x="314.33" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who an actor is</text>
    <rect x="261" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <text x="314.33" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who may do what</text>
    <text x="314.33" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and where</text>
    <rect x="261" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <text x="314.33" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">the agents and</text>
    <text x="314.33" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">their grants</text>
    <rect x="261" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <text x="314.33" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">safety forms and</text>
    <text x="314.33" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they cover</text>
    <rect x="261" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <text x="314.33" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">hutch permits</text>
    <text x="314.33" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">as observed</text>
    <rect x="261" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <text x="314.33" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">operator warnings</text>
    <text x="314.33" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">in force</text>
    <rect x="374.67" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <text x="428.00" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">capability down</text>
    <text x="428.00" y="63" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">to plan</text>
    <rect x="374.67" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <text x="428.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">many runs as</text>
    <text x="428.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one series</text>
    <rect x="374.67" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <text x="428.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one execution as</text>
    <text x="428.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">it happened</text>
    <rect x="374.67" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <text x="428.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">every choice</text>
    <text x="428.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and why</text>
    <rect x="374.67" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <text x="428.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">the sample being</text>
    <text x="428.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">measured</text>
    <rect x="374.67" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <text x="428.00" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what came out</text>
    <text x="428.00" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and where</text>
    <rect x="488.33" y="29" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="43" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <text x="541.66" y="54" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">instruments and</text>
    <text x="541.66" y="63" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they do</text>
    <rect x="488.33" y="79.4" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <text x="541.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">measured values</text>
    <text x="541.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">with history</text>
    <rect x="488.33" y="129.8" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <text x="541.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">bakeouts,</text>
    <text x="541.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">alignment, upkeep</text>
    <rect x="488.33" y="180.2" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <text x="541.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what a run</text>
    <text x="541.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">consumes</text>
    <rect x="488.33" y="230.6" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <text x="541.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what a beamline</text>
    <text x="541.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">may spend</text>
    <rect x="488.33" y="281" width="106.67" height="40" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="295" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="541.66" y="306" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">records across</text>
    <text x="541.66" y="315" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">facilities</text>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# It wakes

<div class="text-base mt-1">

One agent is listening for the entry that says a run went on hold

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;A run went on hold.</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">May it resume?&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.35"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.5">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they cover</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">as observed</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">to plan</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they do</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">consumes</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.2"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.9"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--ink);opacity:0.22">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--ink);opacity:0.22">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--ink);opacity:0.22">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--ink);opacity:0.22">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--ink);opacity:0.22">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--ink);opacity:0.22">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--ink);opacity:0.22">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="230.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--ink);opacity:0.22">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="254.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--ink);opacity:0.22">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="278.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="302.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# Is it stood down?

<div class="text-base mt-1">

It checks first that it may still act at all

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;Am I still an agent</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">that may act?&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.35"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.5">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they cover</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">as observed</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">to plan</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they do</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">consumes</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.2"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.9"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--ink);opacity:0.22">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--ink);opacity:0.22">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--ink);opacity:0.22">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--ink);opacity:0.22">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--ink);opacity:0.22">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--ink);opacity:0.22">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="230.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--ink);opacity:0.22">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="254.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--ink);opacity:0.22">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="278.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="302.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# It reads

<div class="text-base mt-1">

Six contexts answer without a single entry being written

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;What does the</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">envelope say?&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.35"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.5">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they cover</text>
  <circle cx="214.00" cy="192.2" r="7.5" fill="var(--amber-ink2)"/>
  <text x="214.00" y="195.2" text-anchor="middle" fill="var(--amber-panel)" style="font-size:9px;font-weight:700">3</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">as observed</text>
  <circle cx="214.00" cy="242.6" r="7.5" fill="var(--amber-ink2)"/>
  <text x="214.00" y="245.6" text-anchor="middle" fill="var(--amber-panel)" style="font-size:9px;font-weight:700">3</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">to plan</text>
  <circle cx="327.67" cy="41.0" r="7.5" fill="var(--amber-ink2)"/>
  <text x="327.67" y="44.0" text-anchor="middle" fill="var(--amber-panel)" style="font-size:9px;font-weight:700">1</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what they do</text>
  <circle cx="441.33" cy="41.0" r="7.5" fill="var(--amber-ink2)"/>
  <text x="441.33" y="44.0" text-anchor="middle" fill="var(--amber-panel)" style="font-size:9px;font-weight:700">2</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">consumes</text>
  <circle cx="441.33" cy="192.2" r="7.5" fill="var(--amber-ink2)"/>
  <text x="441.33" y="195.2" text-anchor="middle" fill="var(--amber-panel)" style="font-size:9px;font-weight:700">3</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.2"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.9"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--amber-ink2);opacity:1.0">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--amber-ink2);opacity:1.0">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="230.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--ink);opacity:0.22">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="254.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--ink);opacity:0.22">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="278.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="302.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# It concludes

<div class="text-base mt-1">

The choice is written down before anything is acted on

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;Resume: yes,</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">if still safe.&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.35"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.5">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they cover</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">as observed</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">to plan</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="2.2" stroke-opacity="1"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:700;opacity:1.0">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they do</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">consumes</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.9"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.2"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="#8B6914"/>
  <text x="652.5" y="230.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--ink);opacity:1.0">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="254.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--ink);opacity:0.22">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="278.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="302.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# It says why

<div class="text-base mt-1">

The reasoning is recorded beside the choice rather than behind it

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;And here is</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">how I got there.&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.35"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.5">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they cover</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">as observed</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">to plan</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="2.2" stroke-opacity="1"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:700;opacity:1.0">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they do</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">consumes</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.9"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.2"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="var(--mute2)"/>
  <text x="652.5" y="230.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="#8B6914"/>
  <text x="652.5" y="254.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--ink);opacity:1.0">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="278.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.28"/>
  <text x="652.5" y="302.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--ink);opacity:0.28">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--ink);opacity:0.22">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# It acts

<div class="text-base mt-1">

Through the gate to the one context the command belongs to

</div>

<div class="mt-2">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="662" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="90" width="108" height="133" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="106" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.4"/>
  <path d="M 23 118 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round" stroke-opacity="0.4"/>
  <text x="45" y="117" style="font-size:11.5px;fill:var(--ink);opacity:0.4">people</text>
  <line x1="118" y1="112" x2="165" y2="112" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.3"/>
  <polygon points="172,112 164,108.2 164,115.8" fill="#8B6914" fill-opacity="0.3"/>
  <line x1="4" y1="132" x2="112" y2="132" stroke="#8B6914" stroke-width="1" stroke-opacity="0.18"/>
  <rect x="22" y="139" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="146" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="146" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="139" x2="30.5" y2="135" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="133.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="150" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <rect x="12" y="160" width="92" height="15" rx="4" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.4"/>
  <text x="58" y="170.5" text-anchor="middle" style="font-size:8px;fill:var(--ink);font-weight:700">RunSupervisor</text>
  <text x="58" y="190" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">&ldquo;Resume this run,</text>
  <text x="58" y="201" text-anchor="middle" style="font-size:9.5px;fill:var(--ink);opacity:0.88;font-style:italic">by decision 1.&rdquo;</text>
  <line x1="118" y1="175" x2="165" y2="175" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,175 164,171.2 164,178.8" fill="#8B6914"/>
  <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
  <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.10"/>
  <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.6" stroke-opacity="0.9"/>
  <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.9">the same gate</text>
  <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Access</text>
  <text x="254.34" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">who an actor is</text>
  <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.6" stroke-opacity="1"/>
  <text x="254.34" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:1.0">Trust</text>
  <text x="254.34" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">who may do what</text>
  <text x="254.34" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">and where</text>
  <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Agent</text>
  <text x="254.34" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the agents and</text>
  <text x="254.34" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">their grants</text>
  <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Safety</text>
  <text x="254.34" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">safety forms and</text>
  <text x="254.34" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they cover</text>
  <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Enclosure</text>
  <text x="254.34" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">hutch permits</text>
  <text x="254.34" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">as observed</text>
  <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="254.34" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Caution</text>
  <text x="254.34" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">operator warnings</text>
  <text x="254.34" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">in force</text>
  <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Recipe</text>
  <text x="368.00" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">capability down</text>
  <text x="368.00" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">to plan</text>
  <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Campaign</text>
  <text x="368.00" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">many runs as</text>
  <text x="368.00" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">one series</text>
  <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="2.2" stroke-opacity="1"/>
  <text x="368.00" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:700;opacity:1.0">Run</text>
  <text x="368.00" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">one execution as</text>
  <text x="368.00" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.62">it happened</text>
  <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Decision</text>
  <text x="368.00" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">every choice</text>
  <text x="368.00" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and why</text>
  <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Subject</text>
  <text x="368.00" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">the sample being</text>
  <text x="368.00" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured</text>
  <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="368.00" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Data</text>
  <text x="368.00" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what came out</text>
  <text x="368.00" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">and where</text>
  <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="43.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Equipment</text>
  <text x="481.66" y="54.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">instruments and</text>
  <text x="481.66" y="63.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what they do</text>
  <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="93.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Calibration</text>
  <text x="481.66" y="104.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">measured values</text>
  <text x="481.66" y="113.4" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">with history</text>
  <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="143.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Operation</text>
  <text x="481.66" y="154.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">bakeouts,</text>
  <text x="481.66" y="163.8" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">alignment, upkeep</text>
  <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="194.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Supply</text>
  <text x="481.66" y="205.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a run</text>
  <text x="481.66" y="214.2" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">consumes</text>
  <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="244.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Budget</text>
  <text x="481.66" y="255.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">what a beamline</text>
  <text x="481.66" y="264.6" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">may spend</text>
  <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.13"/>
  <text x="481.66" y="295.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600;opacity:0.22">Federation</text>
  <text x="481.66" y="306.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">records across</text>
  <text x="481.66" y="315.0" text-anchor="middle" style="font-size:8px;fill:var(--ink);opacity:0.16">facilities</text>
  <path d="M 314.67 149.8 C 284.67 153.8, 254.34 151.8, 254.34 128.4" fill="none" stroke="#8B6914" stroke-width="1.4"/>
  <polygon points="254.34,119.4 250.53,127.4 258.13,127.4" fill="#8B6914"/>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.9">appends</text>
  <line x1="544" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.9"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914" fill-opacity="0.9"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.2">re-reads</text>
  <line x1="596" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.2"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914" fill-opacity="0.2"/>
  <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
  <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
  <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="645" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">ACROSS ONE TICK</text>
  <rect x="645" y="28" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="38.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">1</text>
  <text x="667" y="39" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">A held run appeared</text>
  <rect x="645" y="52" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="62.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">2</text>
  <text x="667" y="63" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Standing checked, still live</text>
  <rect x="645" y="76" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="86.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="87" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Plan and method read back</text>
  <rect x="645" y="100" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="110.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="111" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Instruments and assemblies read</text>
  <rect x="645" y="124" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="134.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="135" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Clearance still covering</text>
  <rect x="645" y="148" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="158.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="159" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Hutch permits read</text>
  <rect x="645" y="172" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="182.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="183" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Supplies checked, available</text>
  <rect x="645" y="196" width="15" height="15" rx="3.5" fill="none" stroke="var(--mute2)" stroke-width="1.5"/>
  <text x="652.5" y="206.6" text-anchor="middle" style="font-size:8.5px;font-weight:700;fill:var(--mute-ink);opacity:0.55">3</text>
  <text x="667" y="207" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Beam read live from the floor</text>
  <rect x="645" y="220" width="15" height="15" rx="3.5" fill="var(--mute2)"/>
  <text x="652.5" y="230.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">4</text>
  <text x="667" y="231" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Decision recorded with the rule</text>
  <rect x="645" y="244" width="15" height="15" rx="3.5" fill="var(--mute2)"/>
  <text x="652.5" y="254.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">5</text>
  <text x="667" y="255" style="font-size:8px;fill:var(--mute-ink);opacity:0.55">Reasoning recorded, per trace</text>
  <rect x="645" y="268" width="15" height="15" rx="3.5" fill="var(--green-ink)"/>
  <text x="652.5" y="278.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">6</text>
  <text x="667" y="279" style="font-size:8px;fill:var(--green-ink);opacity:1.0">Authority checked, run resumed</text>
  <rect x="645" y="292" width="15" height="15" rx="3.5" fill="var(--red-ink)"/>
  <text x="652.5" y="302.6" text-anchor="middle" fill="#FFFFFF" style="font-size:8.5px;font-weight:700">6</text>
  <text x="667" y="303" style="font-size:8px;fill:var(--red-ink);opacity:1.0">Authority checked, refused</text>
  <text x="645" y="322" style="font-size:7.5px;fill:var(--ink);opacity:0.55;font-style:italic">blue reads, gold writes</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
  </svg>
</div>

---

# The anatomy of one command

<div class="text-base mt-1">

From the door to the record in five files

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
  <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">INSIDE ONE CONTEXT</text>
    <text x="595" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);opacity:0.5;font-family:ui-monospace,Menlo,monospace">run / stop_run</text>
    <g transform="translate(0,6)">
    <rect x="268" y="29" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="48" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">route.py</text>
    <text x="280" y="62" style="font-size:8px;fill:var(--ink);opacity:0.62">the door a person uses</text>
    <text x="280" y="73" style="font-size:8px;fill:var(--ink);opacity:0.5;font-family:ui-monospace,Menlo,monospace">POST /runs/{run_id}/stop</text>
    <rect x="268" y="104" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="123" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">command.py</text>
    <text x="280" y="137" style="font-size:8px;fill:var(--ink);opacity:0.62">the request: which run</text>
    <text x="280" y="148" style="font-size:8px;fill:var(--ink);opacity:0.62">and why</text>
    <rect x="268" y="179" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="198" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">tool.py</text>
    <text x="280" y="212" style="font-size:8px;fill:var(--ink);opacity:0.62">the door an agent uses</text>
    <text x="280" y="223" style="font-size:8px;fill:var(--ink);opacity:0.5;font-family:ui-monospace,Menlo,monospace">stop_run(run_id, reason)</text>
    <line x1="336" y1="89" x2="336" y2="98" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="336,104 332.4,98 339.6,98" fill="#8B6914"/>
    <line x1="336" y1="179" x2="336" y2="170" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="336,164 332.4,170 339.6,170" fill="#8B6914"/>
    <line x1="405" y1="134" x2="411" y2="134" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="419,134 411,130.4 411,137.6" fill="#8B6914"/>
    <rect x="419" y="29" width="170" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="431" y="48" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">decider.py</text>
    <text x="431" y="62" style="font-size:8px;fill:var(--ink);opacity:0.62">the rule.</text>
    <text x="431" y="73" style="font-size:8px;fill:var(--ink);opacity:0.62">decides and nothing else</text>
    <rect x="419" y="104" width="170" height="205" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.6" stroke-opacity="0.9"/>
    <text x="431" y="123" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">handler.py</text>
    <text x="431" y="137" style="font-size:8px;fill:var(--ink);opacity:0.62">the shell. decides nothing itself</text>
    <line x1="464" y1="104" x2="464" y2="95" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="464,89 460.4,95 467.6,95" fill="#8B6914"/>
    <text x="474" y="96.5" dominant-baseline="central" style="font-size:8px;fill:var(--ink);opacity:0.8">asks</text>
    <line x1="562" y1="89" x2="562" y2="98" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="562,104 558.4,98 565.6,98" fill="#8B6914"/>
    <text x="552" y="96.5" text-anchor="end" dominant-baseline="central" style="font-size:8px;fill:var(--ink);opacity:0.8">answers</text>
    <text x="433" y="184" style="font-size:8px;fill:var(--ink);opacity:0.4;font-family:ui-monospace,Menlo,monospace">1</text>
    <text x="445" y="184" style="font-size:8.5px;fill:var(--ink);opacity:0.8">is the caller allowed to ask?</text>
    <text x="433" y="207" style="font-size:8px;fill:var(--ink);opacity:0.4;font-family:ui-monospace,Menlo,monospace">2</text>
    <text x="445" y="207" style="font-size:8.5px;fill:var(--ink);opacity:0.8">has a second person co-signed?</text>
    <text x="433" y="230" style="font-size:8px;fill:var(--ink);opacity:0.4;font-family:ui-monospace,Menlo,monospace">3</text>
    <text x="445" y="230" style="font-size:8.5px;fill:var(--ink);opacity:0.8">read the run back from the record</text>
    <text x="433" y="253" style="font-size:8px;fill:var(--ink);opacity:0.4;font-family:ui-monospace,Menlo,monospace">4</text>
    <text x="445" y="253" style="font-size:8.5px;fill:var(--ink);opacity:0.8">hand it all to the rule</text>
    <text x="433" y="276" style="font-size:8px;fill:var(--ink);opacity:0.4;font-family:ui-monospace,Menlo,monospace">5</text>
    <text x="445" y="276" style="font-size:8.5px;fill:var(--ink);opacity:0.8">write the answer down</text>
    <text x="268" y="263" style="font-size:9.5px;fill:var(--ink);opacity:0.85">five files, one command</text>
    <text x="268" y="279" style="font-size:8px;fill:var(--ink);opacity:0.55">every other slice in the</text>
    <text x="268" y="290" style="font-size:8px;fill:var(--ink);opacity:0.55">system is built the same way</text>
    </g>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="var(--red-ink)" fill-opacity="0.9"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# And how it is proved

<div class="text-base mt-1">

The same five files with what pins each one

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
  <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">INSIDE ONE CONTEXT</text>
    <text x="595" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);opacity:0.5;font-family:ui-monospace,Menlo,monospace">run / stop_run</text>
    <g transform="translate(0,6)">
    <rect x="268" y="29" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="48" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">route.py</text>
    <rect x="280" y="56" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="291" y="62" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">CONTRACT</text>
    <text x="280" y="76" style="font-size:8px;fill:var(--ink);opacity:0.62">exercised from outside</text>
    <rect x="268" y="104" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="123" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">command.py</text>
    <rect x="280" y="131" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="291" y="137" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">CONTRACT</text>
    <text x="280" y="151" style="font-size:8px;fill:var(--ink);opacity:0.62">identical from either door</text>
    <rect x="268" y="179" width="137" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="280" y="198" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">tool.py</text>
    <rect x="280" y="206" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="291" y="212" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">CONTRACT</text>
    <text x="280" y="226" style="font-size:8px;fill:var(--ink);opacity:0.62">and its presence at all</text>
    <line x1="336" y1="89" x2="336" y2="98" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="336,104 332.4,98 339.6,98" fill="#8B6914"/>
    <line x1="336" y1="179" x2="336" y2="170" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="336,164 332.4,170 339.6,170" fill="#8B6914"/>
    <line x1="405" y1="134" x2="411" y2="134" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="419,134 411,130.4 411,137.6" fill="#8B6914"/>
    <rect x="419" y="29" width="170" height="60" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="431" y="48" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">decider.py</text>
    <rect x="431" y="56" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="442" y="62" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">UNIT</text>
    <text x="431" y="76" style="font-size:8px;fill:var(--ink);opacity:0.62">the rule, over generated inputs</text>
    <rect x="419" y="104" width="170" height="205" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.6" stroke-opacity="0.9"/>
    <text x="431" y="123" style="font-size:10.5px;fill:var(--ink);font-weight:700;font-family:ui-monospace,Menlo,monospace">handler.py</text>
    <rect x="431" y="131" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="442" y="137" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">UNIT</text>
    <rect x="478" y="131" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="489" y="137" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">INTEGRATION</text>
    <text x="431" y="148" style="font-size:8px;fill:var(--ink);opacity:0.62">the wiring, first in isolation</text>
    <text x="431" y="159" style="font-size:8px;fill:var(--ink);opacity:0.62">then against a real database</text>
    <text x="431" y="174" style="font-size:7.5px;fill:var(--ink);opacity:0.5;font-weight:600;letter-spacing:0.9px">EVERY ANSWER IT CAN GIVE</text>
    <line x1="464" y1="104" x2="464" y2="95" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="464,89 460.4,95 467.6,95" fill="#8B6914"/>
    <text x="474" y="96.5" dominant-baseline="central" style="font-size:8px;fill:var(--ink);opacity:0.8">asks</text>
    <line x1="562" y1="89" x2="562" y2="98" stroke="#8B6914" stroke-width="1.2"/>
    <polygon points="562,104 558.4,98 565.6,98" fill="#8B6914"/>
    <text x="552" y="96.5" text-anchor="end" dominant-baseline="central" style="font-size:8px;fill:var(--ink);opacity:0.8">answers</text>
    <text x="433" y="190" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">204</text>
    <text x="457" y="190" style="font-size:8.5px;fill:var(--ink);opacity:0.8">accepted, the run is stopped</text>
    <text x="433" y="205" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">401</text>
    <text x="457" y="205" style="font-size:8.5px;fill:var(--ink);opacity:0.8">the caller did not identify itself</text>
    <text x="433" y="220" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">403</text>
    <text x="457" y="220" style="font-size:8.5px;fill:var(--ink);opacity:0.8">the caller is not permitted</text>
    <text x="433" y="235" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">404</text>
    <text x="457" y="235" style="font-size:8.5px;fill:var(--ink);opacity:0.8">no run exists with that id</text>
    <text x="433" y="250" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">409</text>
    <text x="457" y="250" style="font-size:8.5px;fill:var(--ink);opacity:0.8">no independent co-signature</text>
    <text x="433" y="265" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">422</text>
    <text x="457" y="265" style="font-size:8.5px;fill:var(--ink);opacity:0.8">the reason is empty or too long</text>
    <text x="433" y="280" style="font-size:8px;fill:var(--ink);opacity:0.45;font-family:ui-monospace,Menlo,monospace">400</text>
    <text x="457" y="280" style="font-size:8.5px;fill:var(--ink);opacity:0.8">the reason is whitespace only</text>
    <text x="433" y="295" style="font-size:8px;fill:var(--ink);opacity:0.35;font-family:ui-monospace,Menlo,monospace">&hellip;</text>
    <text x="457" y="295" style="font-size:8px;fill:var(--ink);opacity:0.5">five more, from the layers above</text>
    <text x="268" y="263" style="font-size:9.5px;fill:var(--ink);opacity:0.85">395 lines of system</text>
    <text x="268" y="279" style="font-size:9.5px;fill:var(--ink);opacity:0.85">947 lines of proof</text>
    <text x="268" y="294" style="font-size:8px;fill:var(--ink);opacity:0.55">43 cases in six files named</text>
    <text x="268" y="305" style="font-size:8px;fill:var(--ink);opacity:0.55">after this one command</text>
    </g>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="64" y="339" width="7" height="7" rx="1.5" fill="var(--amber-ink2)"/>
    <text x="75" y="345" style="font-size:7px;fill:var(--amber-ink2);font-weight:700;letter-spacing:0.8px">ARCHITECTURE</text>
    <text x="64" y="357" style="font-size:7px;fill:var(--ink);opacity:0.5">every slice, not just this one</text>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="var(--red-ink)" fill-opacity="0.9"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# Every context is built the same way

<div class="text-base mt-1">

One slice measured against the whole system

</div>

<div class="grid gap-7 mt-5" style="grid-template-columns:0.78fr 1.22fr">

<div>

<div class="text-[13px] leading-relaxed" style="opacity:0.9">The same slice, now measured. Line counts include docstrings.</div>

<div class="text-[10.5px] mt-2" style="opacity:0.5;font-family:ui-monospace,Menlo,monospace">run / stop_run</div>

<div class="mt-3 space-y-[7px]">
  <div class="border-l-2 border-[#8B6914]/45 pl-3 flex items-baseline justify-between gap-3">
    <div class="min-w-0">
      <div class="text-[12.5px] font-semibold" style="color:var(--ink)">command.py</div>
      <div class="text-[11px] leading-snug" style="opacity:0.68">the intent, which run and on what grounds</div>
    </div>
    <div class="text-[12.5px] shrink-0" style="opacity:0.6;font-family:ui-monospace,Menlo,monospace">31</div>
  </div>
  <div class="border-l-2 border-[#8B6914]/45 pl-3 flex items-baseline justify-between gap-3">
    <div class="min-w-0">
      <div class="text-[12.5px] font-semibold" style="color:var(--ink)">decider.py</div>
      <div class="text-[11px] leading-snug" style="opacity:0.68">the rule in isolation, neither reading nor writing</div>
    </div>
    <div class="text-[12.5px] shrink-0" style="opacity:0.6;font-family:ui-monospace,Menlo,monospace">83</div>
  </div>
  <div class="border-l-2 border-[#8B6914]/45 pl-3 flex items-baseline justify-between gap-3">
    <div class="min-w-0">
      <div class="text-[12.5px] font-semibold" style="color:var(--ink)">handler.py</div>
      <div class="text-[11px] leading-snug" style="opacity:0.68">authorises, checks the co-signature, then appends</div>
    </div>
    <div class="text-[12.5px] shrink-0" style="opacity:0.6;font-family:ui-monospace,Menlo,monospace">138</div>
  </div>
  <div class="border-l-2 border-[#8B6914]/45 pl-3 flex items-baseline justify-between gap-3">
    <div class="min-w-0">
      <div class="text-[12.5px] font-semibold" style="color:var(--ink)">route.py &middot; tool.py</div>
      <div class="text-[11px] leading-snug" style="opacity:0.68">two entry points, one handler behind both</div>
    </div>
    <div class="text-[12.5px] shrink-0" style="opacity:0.6;font-family:ui-monospace,Menlo,monospace">143</div>
  </div>
</div>

<div class="text-[13px] leading-relaxed mt-4" style="opacity:0.9"><span class="font-semibold" style="color:var(--ink)">395</span> lines in total. The system holds <span class="font-semibold" style="color:var(--ink)">297</span> such slices averaging about 460 lines. Every context is assembled from nothing else.</div>

</div>

<div>
<svg viewBox="0 0 460 300" class="w-full" style="max-height:340px">
  <style>
    .cbxS0{fill:#8B6914} .cbxP0{fill:#5B8AA6}
    .cbxS1{fill:#4CA3AD} .cbxP1{fill:#CA9C53}
    .cbxS2{fill:#8CC4CB} .cbxP2{fill:#DFBE89}
    .cbxS3{fill:#C3E0E4} .cbxP3{fill:#F0DCBA}
    html.dark .cbxS0{fill:#7FE3F1} html.dark .cbxP0{fill:#F6D08A}
    html.dark .cbxS1{fill:#55C3D6} html.dark .cbxP1{fill:#DDAE66}
    html.dark .cbxS2{fill:#3FA4B7} html.dark .cbxP2{fill:#C08D47}
    html.dark .cbxS3{fill:#3A8998} html.dark .cbxP3{fill:#A2793F}
  </style>
  <text x="12.0" y="40" style="font-size:10px;font-weight:700;letter-spacing:1.1px;fill:var(--ink)">THE SYSTEM</text>
  <text x="12.0" y="54" style="font-size:11.5px;font-weight:600;fill:var(--ink);font-family:ui-monospace,Menlo,monospace">310,310 <tspan style="font-size:9.5px;font-weight:400;opacity:0.65">39%</tspan></text>
  <text x="188.3" y="40" style="font-size:10px;font-weight:700;letter-spacing:1.1px;fill:var(--amber-ink2)">THE PROOF</text>
  <text x="188.3" y="54" style="font-size:11.5px;font-weight:600;fill:var(--amber-ink2);font-family:ui-monospace,Menlo,monospace">484,129 <tspan style="font-size:9.5px;font-weight:400;opacity:0.65">61%</tspan></text>
  <rect x="12.0" y="64.0" width="73.0" height="40.0" class="cbxS0"/>
  <rect x="85.0" y="64.0" width="66.8" height="40.0" class="cbxS1"/>
  <rect x="151.8" y="64.0" width="21.9" height="40.0" class="cbxS2"/>
  <rect x="173.7" y="64.0" width="4.8" height="40.0" class="cbxS3"/>
  <rect x="188.3" y="64.0" width="155.0" height="40.0" class="cbxP0"/>
  <rect x="343.4" y="64.0" width="52.6" height="40.0" class="cbxP1"/>
  <rect x="395.9" y="64.0" width="40.1" height="40.0" class="cbxP2"/>
  <rect x="436.1" y="64.0" width="11.9" height="40.0" class="cbxP3"/>
  <rect x="12.0" y="121.5" width="9" height="9" class="cbxS0"/>
  <text x="27.0" y="130" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Feature slices, x297</text>
  <text x="217.0" y="130" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">136,020</text>
  <text x="27.0" y="141" style="font-size:7.5px;fill:var(--ink);opacity:0.55">one folder per command or query, five files each</text>
  <rect x="12.0" y="151.5" width="9" height="9" class="cbxS1"/>
  <text x="27.0" y="160" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Domain internals</text>
  <text x="217.0" y="160" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">124,579</text>
  <text x="27.0" y="171" style="font-size:7.5px;fill:var(--ink);opacity:0.55">what each context is, shared by all its slices</text>
  <rect x="12.0" y="181.5" width="9" height="9" class="cbxS2"/>
  <text x="27.0" y="190" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Infrastructure, API, kernel</text>
  <text x="217.0" y="190" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">40,836</text>
  <text x="27.0" y="201" style="font-size:7.5px;fill:var(--ink);opacity:0.55">event store, permissions, database, start-up</text>
  <rect x="12.0" y="211.5" width="9" height="9" class="cbxS3"/>
  <text x="27.0" y="220" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Schema migrations</text>
  <text x="217.0" y="220" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">8,875</text>
  <text x="27.0" y="231" style="font-size:7.5px;fill:var(--ink);opacity:0.55">171 numbered steps, the database's own history</text>
  <rect x="240.0" y="121.5" width="9" height="9" class="cbxP0"/>
  <text x="255.0" y="130" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Unit</text>
  <text x="445.0" y="130" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">289,034</text>
  <text x="255.0" y="141" style="font-size:7.5px;fill:var(--ink);opacity:0.55">one piece alone, no database</text>
  <rect x="240.0" y="151.5" width="9" height="9" class="cbxP1"/>
  <text x="255.0" y="160" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Integration</text>
  <text x="445.0" y="160" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">98,000</text>
  <text x="255.0" y="171" style="font-size:7.5px;fill:var(--ink);opacity:0.55">several pieces against a real Postgres</text>
  <rect x="240.0" y="181.5" width="9" height="9" class="cbxP2"/>
  <text x="255.0" y="190" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Contract</text>
  <text x="445.0" y="190" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">74,836</text>
  <text x="255.0" y="201" style="font-size:7.5px;fill:var(--ink);opacity:0.55">both doors tested from outside, REST and MCP</text>
  <rect x="240.0" y="211.5" width="9" height="9" class="cbxP3"/>
  <text x="255.0" y="220" style="font-size:9.5px;fill:var(--ink);opacity:0.88">Architecture + end to end</text>
  <text x="445.0" y="220" text-anchor="end" style="font-size:9.5px;fill:var(--ink);opacity:0.72;font-family:ui-monospace,Menlo,monospace">22,259</text>
  <text x="255.0" y="231" style="font-size:7.5px;fill:var(--ink);opacity:0.55">the shape of the code, not its behaviour</text>
  <line x1="12.0" x2="448" y1="246" y2="246" stroke="#8B6914" stroke-width="0.7" stroke-opacity="0.22"/>
  <text x="12.0" y="266" style="font-size:12px;fill:var(--ink);font-weight:600">1.56 lines of test for every line of system</text>
  <text x="12.0" y="284" style="font-size:9.5px;fill:var(--ink);opacity:0.62">794,439 lines total. Inline docstrings counted where they live, inside the code.</text>
</svg>
</div>

</div>

---

# What a decade would add

<div class="text-base mt-1">

Each of these is a question that ten years of record would force

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
  <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <text x="595" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);opacity:0.5;font-family:ui-monospace,Menlo,monospace">a guess, not a plan</text>
    <g transform="translate(0,6)">
    <rect x="268" y="33" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="47" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Access</text>
    <rect x="315" y="33" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="47" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Recipe</text>
    <rect x="362" y="33" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="47" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Equipment</text>
    <rect x="268" y="61" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="75" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Trust</text>
    <rect x="315" y="61" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="75" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Campaign</text>
    <rect x="362" y="61" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="75" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Calibration</text>
    <rect x="268" y="89" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="103" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Agent</text>
    <rect x="315" y="89" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="103" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Run</text>
    <rect x="362" y="89" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="103" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Operation</text>
    <rect x="268" y="117" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="131" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Safety</text>
    <rect x="315" y="117" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="131" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Decision</text>
    <rect x="362" y="117" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="131" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Supply</text>
    <rect x="268" y="145" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="159" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Enclosure</text>
    <rect x="315" y="145" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="159" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Subject</text>
    <rect x="362" y="145" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="159" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Budget</text>
    <rect x="268" y="173" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="289.0" y="187" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Caution</text>
    <rect x="315" y="173" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="336.0" y="187" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Data</text>
    <rect x="362" y="173" width="42" height="22" rx="4" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.16"/>
    <text x="383.0" y="187" text-anchor="middle" style="font-size:6.5px;fill:var(--ink);opacity:0.34;font-weight:600">Federation</text>
    <text x="268" y="219" style="font-size:8.5px;fill:var(--ink);opacity:0.55">the eighteen that exist</text>
    <text x="268" y="231" style="font-size:8px;fill:var(--ink);opacity:0.38">named three slides ago</text>
    <rect x="417" y="29" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="0.85"/>
    <text x="430" y="46" style="font-size:10.5px;fill:var(--ink);font-weight:600">Finding</text>
    <text x="430" y="59" style="font-size:8px;fill:var(--ink);opacity:0.62">a claim and what it rests on</text>
    <rect x="417" y="77" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="-1.15"/>
    <text x="430" y="94" style="font-size:10.5px;fill:var(--ink);font-weight:600">Cohort</text>
    <text x="430" y="107" style="font-size:8px;fill:var(--ink);opacity:0.62">many experiments, one question</text>
    <rect x="417" y="125" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="-3.15"/>
    <text x="430" y="142" style="font-size:10.5px;fill:var(--ink);font-weight:600">Custody</text>
    <text x="430" y="155" style="font-size:8px;fill:var(--ink);opacity:0.62">who owns it, who has held it, and when</text>
    <rect x="417" y="173" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="-5.15"/>
    <text x="430" y="190" style="font-size:10.5px;fill:var(--ink);font-weight:600">Reduction</text>
    <text x="430" y="203" style="font-size:8px;fill:var(--ink);opacity:0.62">what was recomputed and from what</text>
    <rect x="417" y="221" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="-7.15"/>
    <text x="430" y="238" style="font-size:10.5px;fill:var(--ink);font-weight:600">Belief</text>
    <text x="430" y="251" style="font-size:8px;fill:var(--ink);opacity:0.62">what it holds true and since when</text>
    <rect x="417" y="269" width="172" height="40" rx="5" fill="var(--panel)" stroke="#8B6914" stroke-width="1.3" stroke-opacity="-9.15"/>
    <text x="430" y="286" style="font-size:10.5px;fill:var(--ink);font-weight:600">Latitude</text>
    <text x="430" y="299" style="font-size:8px;fill:var(--ink);opacity:0.62">how far an agent may go alone</text>
    </g>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <text x="268" y="264" style="font-size:9px;fill:var(--ink);opacity:0.72">the model today is shaped like</text>
    <text x="268" y="277" style="font-size:9px;fill:var(--ink);opacity:0.72">one experiment.</text>
    <text x="268" y="301" style="font-size:9px;fill:var(--ink);opacity:0.72">ten years of record is shaped</text>
    <text x="268" y="314" style="font-size:9px;fill:var(--ink);opacity:0.72">like a question.</text>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# At a beamline

<div class="mt-8">
  <div class="space-y-1">
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">1</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The questions</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What is asked about an experiment.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">2</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The machinery</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What the record is made of.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline rounded px-4 py-2" style="grid-template-columns:34px 1fr;background-color:var(--panel)">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink)">3</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="color:var(--ink)">At a beamline<span class="text-[10px] font-medium uppercase tracking-[0.16em] ml-3 opacity-70">you are here</span></div>
        <div class="text-[12.5px] leading-snug mt-1" style="color:var(--ink);opacity:0.85">What runs at 2-BM today.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="opacity:0.22">4</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">Proposed next steps</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">Where this path goes.</div>
      </div>
    </div>
  </div>
  <div class="mt-5 mx-auto" style="max-width:560px"><SpineRow :active="3" /></div>
</div>

---

# An agent is tuned on history

<div class="text-base mt-1">

Autonomy is granted in increments against evidence

</div>

<div class="mt-10 grid gap-10" style="grid-template-columns:1fr 1fr">
  <div class="rounded-lg px-7 py-6" style="background-color:var(--amber-panel);border:1.5px solid transparent">
    <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-4" style="color:var(--amber-ink);opacity:0.85">In a demonstration</div>
    <div class="text-[15px] leading-snug py-[9px]" style="color:var(--amber-ink)">The record is assembled for the agent</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--amber-ink);border-color:rgb(var(--amber-rgb)/0.18)">The agent is tuned to that record</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--amber-ink);border-color:rgb(var(--amber-rgb)/0.18)">It is judged on data it helped shape</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--amber-ink);border-color:rgb(var(--amber-rgb)/0.18)">It begins on the day it is shown</div>
  </div>
  <div class="rounded-lg px-7 py-6" style="background-color:var(--panel);border:1.5px solid rgb(var(--ink-rgb)/0.55)">
    <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-4" style="color:var(--ink);opacity:0.85">In a deployment</div>
    <div class="text-[15px] leading-snug py-[9px]" style="color:var(--ink)">The record is written by ordinary operation</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--ink);border-color:rgb(var(--ink-rgb)/0.18)">The agent meets what it finds</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--ink);border-color:rgb(var(--ink-rgb)/0.18)">It is judged on data that predates it</div>
    <div class="text-[15px] leading-snug py-[9px] border-t" style="color:var(--ink);border-color:rgb(var(--ink-rgb)/0.18)">It has been recording since 9 August</div>
  </div>
</div>

---

# What a deployment means

<div class="text-base mt-1">

How much of each context is in use today

</div>

<div class="mt-2">
<svg viewBox="0 -10 815 376" class="w-full" style="max-height:392px">
  <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
  <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
  <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
  <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
  <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
  <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
  <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
  <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
  <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
  <g transform="translate(-60,0)">
    <clipPath id="cvg00"><rect x="261.0" y="29.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg01"><rect x="374.67" y="29.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg02"><rect x="488.33" y="29.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg10"><rect x="261.0" y="79.4" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg11"><rect x="374.67" y="79.4" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg12"><rect x="488.33" y="79.4" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg20"><rect x="261.0" y="129.8" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg21"><rect x="374.67" y="129.8" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg22"><rect x="488.33" y="129.8" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg30"><rect x="261.0" y="180.2" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg31"><rect x="374.67" y="180.2" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg32"><rect x="488.33" y="180.2" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg40"><rect x="261.0" y="230.6" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg41"><rect x="374.67" y="230.6" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg42"><rect x="488.33" y="230.6" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg50"><rect x="261.0" y="281.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg51"><rect x="374.67" y="281.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <clipPath id="cvg52"><rect x="488.33" y="281.0" width="106.67" height="40.0" rx="5"/></clipPath>
    <text x="232" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 242 20 A 10 10 0 0 0 232 30 L 232 320 A 10 10 0 0 0 242 330 L 253 330 L 253 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="253" y1="20" x2="253" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="242.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 242.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="232" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="261.0" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg00)"><rect x="261.0" y="29.0" width="26.67" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="261.0" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="47.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <text x="314.33" y="60.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">25%</text>
    <rect x="374.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg01)"><rect x="374.67" y="29.0" width="21.33" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="374.67" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="47.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <text x="428.00" y="60.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">20%</text>
    <rect x="488.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg02)"><rect x="488.33" y="29.0" width="12.80" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="488.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="47.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <text x="541.66" y="60.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">12%</text>
    <rect x="261.0" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg10)"><rect x="261.0" y="79.4" width="8.89" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="261.0" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="97.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <text x="314.33" y="110.4" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">8%</text>
    <rect x="374.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <rect x="374.67" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="97.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <text x="428.00" y="110.4" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">0%</text>
    <rect x="488.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <rect x="488.33" y="79.4" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="97.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <text x="541.66" y="110.4" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">0%</text>
    <rect x="261.0" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg20)"><rect x="261.0" y="129.8" width="30.48" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="261.0" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="147.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <text x="314.33" y="160.8" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">29%</text>
    <rect x="374.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg21)"><rect x="374.67" y="129.8" width="38.10" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="374.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <circle cx="473.34" cy="137.8" r="2.6" fill="#8B6914"/>
    <text x="428.00" y="147.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <text x="428.00" y="160.8" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">36%</text>
    <rect x="488.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <rect x="488.33" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="147.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <text x="541.66" y="160.8" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">0%</text>
    <rect x="261.0" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg30)"><rect x="261.0" y="180.2" width="60.95" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="261.0" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="198.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <text x="314.33" y="211.2" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">57%</text>
    <rect x="374.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg31)"><rect x="374.67" y="180.2" width="53.34" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="374.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="198.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <text x="428.00" y="211.2" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">50%</text>
    <rect x="488.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg32)"><rect x="488.33" y="180.2" width="45.72" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="488.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <circle cx="587.00" cy="188.2" r="2.6" fill="#8B6914"/>
    <text x="541.66" y="198.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <text x="541.66" y="211.2" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">43%</text>
    <rect x="261.0" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg40)"><rect x="261.0" y="230.6" width="71.11" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="261.0" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <circle cx="359.67" cy="238.6" r="2.6" fill="#8B6914"/>
    <text x="314.33" y="248.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <text x="314.33" y="261.6" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">67%</text>
    <rect x="374.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <rect x="374.67" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="248.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <text x="428.00" y="261.6" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">0%</text>
    <rect x="488.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg42)"><rect x="488.33" y="230.6" width="42.67" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="488.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="248.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <text x="541.66" y="261.6" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">40%</text>
    <rect x="261.0" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <rect x="261.0" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="314.33" y="299.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <text x="314.33" y="312.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">0%</text>
    <rect x="374.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg51)"><rect x="374.67" y="281.0" width="21.33" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="374.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="428.00" y="299.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <text x="428.00" y="312.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">20%</text>
    <rect x="488.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <g clip-path="url(#cvg52)"><rect x="488.33" y="281.0" width="5.33" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="488.33" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="541.66" y="299.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="541.66" y="312.0" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.7;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace">5%</text>
  </g>
  <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
  <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
  <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
  <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
  <g transform="translate(-94,0)">
    <rect x="690" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="698" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="698" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="707,322 702.5,314 711.5,314" fill="#8B6914" fill-opacity="0.55"/>
  </g>
  <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
  <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
  <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
  <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
  <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
  <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
  <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
  <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
  <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
  <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
</svg>
</div>

---

# Enclosure

<div class="text-base mt-1">

The hutch permits as CORA observed them

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcenclos"><rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcenclos)"><rect x="201.00" y="230.6" width="71.11" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="254.34" y="256.6" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Enclosure</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record<span class="ml-3 normal-case tracking-normal font-normal"></span></div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A hutch exists with its two stations</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">twice, 9 Aug, by hand</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">The permit reads locked and what said so</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">86,649, by the interlock</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record<span class="ml-3 normal-case tracking-normal font-normal"></span></div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A hutch has been taken out of service</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">once a decade, if ever</div>
  </div>
</div>
</div>

---

# Run

<div class="text-base mt-1">

One execution recorded as it happened

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcrun"><rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcrun)"><rect x="314.67" y="129.8" width="38.10" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="368.00" y="155.8" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Run</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record<span class="ml-3 normal-case tracking-normal font-normal"></span></div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A run started and whose it was</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">2,024 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A logbook opened to hold what was seen</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">1,950 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A run finished</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">2,021 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A run was abandoned</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">3 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">An agent was asked to explain it</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">2,190 times</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record<span class="ml-3 normal-case tracking-normal font-normal"></span></div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A run was paused and later resumed</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">CORA would have to drive it</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A run was changed, cut short, or halted</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">CORA would have to drive it</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A standing warning was acknowledged</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">no warning exists to accept</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A run joined a series or left one</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">no series exists to join</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">What was being measured</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">the Subject box, 0 of 2,024</div>
  </div>
</div>
</div>

---

# Supply

<div class="text-base mt-1">

What a run consumes

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcsupply"><rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcsupply)"><rect x="428.33" y="180.2" width="45.72" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="481.66" y="206.2" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Supply</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A supply was registered and named</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">5: water, vacuum, disk</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A supply went unavailable</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">twice</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A supply came back</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">once</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A supply was degraded or recovering</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">the trip bit is yes or no</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A supply was restored by an operator</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nobody has been asked</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A supply was deregistered</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">none has been retired</div>
  </div>
</div>
</div>

---

# Data

<div class="text-base mt-1">

What each run produced

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcdata"><rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcdata)"><rect x="314.67" y="281.0" width="21.33" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="368.00" y="307.0" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Data</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A scan was acquired and what made it</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">315 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A dataset exists and this is what it is</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">315 datasets</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A copy exists and this is where it lies</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">315 copies</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A second durable copy was registered</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">the sweep is on, no beam</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A dataset was promoted or discarded</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing has been judged</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">An edition was sealed and published</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">0 of 315 shareable</div>
  </div>
</div>
</div>

---

# Equipment

<div class="text-base mt-1">

What each instrument can do

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcequipm"><rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcequipm)"><rect x="428.33" y="29.0" width="12.80" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="481.66" y="55.0" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Equipment</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A kind of device was defined (Camera)</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">46 families</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A device was registered (Camera_HighRes)</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">7 assets</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A device was decommissioned</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">twice</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A role was defined (Detector, Positioner)</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">6 roles</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">It moved, faulted, or went for repair</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">none has, yet</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">Its model, mount, frame or fixture</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">never materialised</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">It gained an owner or a citable id</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing to cite yet</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">Its settings or its version changed</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing has drifted</div>
  </div>
</div>
</div>

---

# Agent

<div class="text-base mt-1">

What each agent may do

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcagent"><rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcagent)"><rect x="201.00" y="129.8" width="30.48" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="254.34" y="155.8" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Agent</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">An agent was defined with its limits</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">20 agents</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">An agent was given a new version</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">4 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A language model was declared</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">5 models</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A model was approved for use here</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">5 times</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">An agent was suspended or resumed</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing has gone wrong</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">Its budget or its plan was changed</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">set once, not revised</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A tool was granted or taken back</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">these agents hold none</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A model was retired or announced for it</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">no model has aged out</div>
  </div>
</div>
</div>

---

# Budget

<div class="text-base mt-1">

What a beamline may spend

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcbudget"><rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcbudget)"><rect x="428.33" y="230.6" width="42.67" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="481.66" y="256.6" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Budget</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">An envelope was granted with a ceiling</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">25 dollars</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">The envelope was activated</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">0.1s later</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">The ceiling was raised or lowered</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">never needed</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">The envelope was voided</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">never revoked</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">It was sealed with what it cost</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">the period has not ended</div>
  </div>
</div>
</div>

---

# Decision

<div class="text-base mt-1">

Why each choice was made

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fcdecisi"><rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <g clip-path="url(#fcdecisi)"><rect x="314.67" y="180.2" width="53.34" height="40.0" fill="#8B6914" fill-opacity="0.4"/></g>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="368.00" y="206.2" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Decision</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A decision with what it saw and why</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">2,193 times</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug">A logbook holds the reasoning behind it</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">2,191 times</div>
  </div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">Anyone said whether a decision was useful</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">0 of 2,193</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A logbook was closed</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing writes this yet</div>
  </div>
</div>
</div>

---

# Caution

<div class="text-base mt-1">

The operator warnings in force

</div>

<div class="mt-2 mx-auto" style="max-width:700px">
  <svg viewBox="0 -10 815 376" class="w-full" style="max-height:240px">
    <rect x="146" y="-5" width="510" height="363" rx="14" fill="#8B6914" fill-opacity="0.035"/>
    <g opacity="0.2">
    <rect x="4" y="122" width="108" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <circle cx="30" cy="143" r="4.2" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <path d="M 23 155 a 7 7 0 0 1 14 0" fill="none" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <text x="45" y="154" style="font-size:11.5px;fill:var(--ink)">people</text>
    <rect x="22" y="193" width="17" height="14" rx="3.5" fill="none" stroke="#8B6914" stroke-width="1.3"/>
    <circle cx="27" cy="200" r="1.4" fill="#8B6914"/>
    <circle cx="34" cy="200" r="1.4" fill="#8B6914"/>
    <line x1="30.5" y1="193" x2="30.5" y2="189" stroke="#8B6914" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="30.5" cy="187.6" r="1.3" fill="#8B6914"/>
    <text x="45" y="204" style="font-size:11.5px;fill:var(--ink)">agents</text>
    <line x1="118" y1="150" x2="165" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,150 164,146.2 164,153.8" fill="#8B6914"/>
    <line x1="118" y1="200" x2="165" y2="200" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="172,200 164,196.2 164,203.8" fill="#8B6914"/>
    <text x="172" y="14" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">CONTEXTS</text>
    <path d="M 182 20 A 10 10 0 0 0 172 30 L 172 320 A 10 10 0 0 0 182 330 L 193 330 L 193 20 Z" fill="#8B6914" fill-opacity="0.06"/>
    <line x1="193" y1="20" x2="193" y2="330" stroke="#8B6914" stroke-width="1.2" stroke-opacity="0.55"/>
    <text x="182.5" y="175" text-anchor="middle" dominant-baseline="central" transform="rotate(-90 182.5 175)" style="font-size:9.5px;fill:var(--ink);opacity:0.75">the same gate</text>
    <rect x="172" y="20" width="372" height="310" rx="10" fill="none" stroke="#8B6914" stroke-width="1.5" stroke-opacity="0.55"/>
    <rect x="201.00" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Access</text>
    <rect x="201.00" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Trust</text>
    <rect x="201.00" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Agent</text>
    <rect x="201.00" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Safety</text>
    <rect x="201.00" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Enclosure</text>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="254.34" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Caution</text>
    <rect x="314.67" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Recipe</text>
    <rect x="314.67" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Campaign</text>
    <rect x="314.67" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Run</text>
    <rect x="314.67" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Decision</text>
    <rect x="314.67" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Subject</text>
    <rect x="314.67" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="368.00" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Data</text>
    <rect x="428.33" y="29.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="53.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Equipment</text>
    <rect x="428.33" y="79.4" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="103.4" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Calibration</text>
    <rect x="428.33" y="129.8" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="153.8" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Operation</text>
    <rect x="428.33" y="180.2" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="204.2" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Supply</text>
    <rect x="428.33" y="230.6" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="254.6" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Budget</text>
    <rect x="428.33" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF" stroke="#8B6914" stroke-width="1" stroke-opacity="0.32"/>
    <text x="481.66" y="305.0" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);font-weight:600">Federation</text>
    <text x="570" y="112" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">appends</text>
    <line x1="551" y1="124" x2="588" y2="124" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="596,124 588,120.2 588,127.8" fill="#8B6914"/>
    <text x="570" y="208" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">re-reads</text>
    <line x1="588" y1="220" x2="552" y2="220" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="544,220 552,216.2 552,223.8" fill="#8B6914"/>
    <rect x="596" y="20" width="34" height="310" rx="10" fill="#F7F0DE" stroke="#8B6914" stroke-width="1.5"/>
    <rect x="604" y="34.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="42.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="51.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="59.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="68.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="77.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="85.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="94.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="102.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="111.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="120.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="128.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="137.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="145.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="154.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="163.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="171.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="180.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="188.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="197.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="206.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="214.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="223.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="231.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="240.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="249.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="257.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="266.2" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="274.8" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="283.4" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="292.0" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <rect x="604" y="300.6" width="18" height="4" rx="1" fill="#8B6914" fill-opacity="0.35"/>
    <polygon points="613,322 608.5,314 617.5,314" fill="#8B6914" fill-opacity="0.55"/>
    <text x="630" y="14" text-anchor="end" style="font-size:9px;fill:var(--ink);font-weight:600;letter-spacing:1.3px;opacity:0.75">THE RECORD</text>
    <text x="675" y="142" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">witness</text>
    <line x1="694" y1="150" x2="659" y2="150" stroke="#8B6914" stroke-width="1.3"/>
    <polygon points="651,150 659,146.2 659,153.8" fill="#8B6914"/>
    <text x="675" y="212" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.85">conduct</text>
    <line x1="651" y1="200" x2="686" y2="200" stroke="#8B6914" stroke-width="1.3" stroke-dasharray="3 3"/>
    <polygon points="694,200 686,196.2 686,203.8" fill="#8B6914"/>
    <rect x="700" y="122" width="98" height="106" rx="12" fill="none" stroke="#8B6914" stroke-width="1.5"/>
    <text x="749" y="179" text-anchor="middle" style="font-size:11.5px;fill:var(--ink)">the experiment</text>
    <text x="401" y="343" text-anchor="middle" style="font-size:10px;fill:var(--ink);font-weight:600;letter-spacing:3px;opacity:0.42">CORA</text>
    </g>
    <defs><clipPath id="fccautio"><rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5"/></clipPath></defs>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="#FFFFFF"/>
    <rect x="201.00" y="281.0" width="106.67" height="40.0" rx="5" fill="none" stroke="#8B6914" stroke-width="1.6"/>
    <text x="254.34" y="307.0" text-anchor="middle" style="font-size:17px;fill:var(--ink);font-weight:600">Caution</text>
  </svg>
</div>

<div class="mt-3 grid gap-10" style="grid-template-columns:1fr 1fr">
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.75">In the record</div>
  <div class="border-t border-[#8B6914]/12 pt-3 text-[12px] leading-snug" style="color:var(--ink);opacity:0.75">Nothing. This box has never held a single entry.</div>
</div>
<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.5">Not in the record</div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A warning was registered</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">6 proposed by CautionDrafter</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A warning was retired</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing to retire</div>
  </div>
  <div class="grid gap-4 items-baseline py-[3px] border-t border-[#8B6914]/12" style="grid-template-columns:1fr 152px">
    <div class="text-[12px] leading-snug" style="opacity:0.55">A warning was superseded</div>
    <div class="text-[10.5px] leading-snug text-right" style="color:var(--ink);opacity:0.55">nothing to supersede</div>
  </div>
</div>
</div>

---

# Deployment is the beginning

<div class="text-base mt-1">

Two questions follow from a record that is filling

</div>

<div class="mt-4 grid gap-10" style="grid-template-columns:1fr 1fr">
  <div class="rounded-lg px-6 py-4" style="background-color:var(--panel);border:1.5px solid rgb(var(--ink-rgb)/0.55)">
    <div class="text-[15px] leading-snug font-medium" style="color:var(--ink)">What else is worth recording?</div>
  </div>
  <div class="rounded-lg px-6 py-4" style="background-color:var(--panel);border:1.5px solid rgb(var(--ink-rgb)/0.55)">
    <div class="text-[15px] leading-snug font-medium" style="color:var(--ink)">Is this enough for an agent to do science?</div>
  </div>
</div>

---

# The agents with a model behind them

<div class="text-base mt-1">

Both agents run the same model under the same rules

</div>

<div class="mt-4 grid gap-9" style="grid-template-columns:0.95fr 1.05fr">

<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.85">What they share</div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Model</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">phi-4, run on the beamline&rsquo;s own GPU</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">no text leaves the building</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Dials</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">An output cap each and no sampling settings</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">nothing else was set, so nothing else was recorded</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Registered</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">Five models across three routes</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">the local pool, the laboratory gateway, the vendor</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Metering</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">A monthly dollar cap and a daily token cap</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">priced per token from a vendor, measured in GPU time in house</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Standing</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">An operator can stand either down</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">each reads that before it does anything else</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Wakes</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">On every run that ends</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">both of them, independently</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:68px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Confidence</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">A number each states about itself</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">recorded as self-reported, with nothing acting on it</div></div>
  </div>
</div>

<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-[5px]" style="color:var(--ink);opacity:0.85">What each one does</div>
  <div class="flex items-center gap-2 pb-[3px]"><svg viewBox="0 0 21 24" style="width:17px;height:19px" class="flex-shrink-0"><rect x="2" y="8" width="17" height="14" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/><circle cx="7" cy="15" r="1.5" fill="var(--amber-ink2)"/><circle cx="14" cy="15" r="1.5" fill="var(--amber-ink2)"/><line x1="10.5" y1="8" x2="10.5" y2="4" stroke="var(--amber-ink2)" stroke-width="1.5" stroke-linecap="round"/><circle cx="10.5" cy="2.6" r="1.4" fill="var(--amber-ink2)"/></svg><div class="text-[12.5px] font-semibold" style="color:var(--amber-ink)">RunDebriefer</div></div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:58px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Reads</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">The run and the frame counts it declared</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:58px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Writes</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">One verdict on that run</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">NominalCompletion, DataSuspect, DegradedCompletion, DebriefDeferred</div></div>
  </div>
  <div class="mt-3"></div>
  <div class="flex items-center gap-2 pb-[3px]"><svg viewBox="0 0 21 24" style="width:17px;height:19px" class="flex-shrink-0"><rect x="2" y="8" width="17" height="14" rx="3.5" fill="none" stroke="var(--amber-ink2)" stroke-width="1.5"/><circle cx="7" cy="15" r="1.5" fill="var(--amber-ink2)"/><circle cx="14" cy="15" r="1.5" fill="var(--amber-ink2)"/><line x1="10.5" y1="8" x2="10.5" y2="4" stroke="var(--amber-ink2)" stroke-width="1.5" stroke-linecap="round"/><circle cx="10.5" cy="2.6" r="1.4" fill="var(--amber-ink2)"/></svg><div class="text-[12.5px] font-semibold" style="color:var(--amber-ink)">CautionDrafter</div></div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:58px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Reads</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">The run, its plan, and the warnings in force</div></div>
  </div>
  <div class="grid gap-3 items-baseline py-[1px] border-t border-[#8B6914]/12" style="grid-template-columns:58px 1fr">
    <div class="text-[10.5px] leading-snug" style="color:var(--ink);opacity:0.6">Writes</div>
    <div><div class="text-[12.5px] leading-snug" style="color:var(--ink)">One proposal or nothing</div><div class="text-[10.5px] leading-snug mt-[2px]" style="color:var(--ink);opacity:0.55">NoAction, ProposeNotice, ProposeCaution, ProposeWarning, ProposeSupersede</div></div>
  </div>
<div class="mt-4 flex">
<svg viewBox="108 0 320 52" style="width:100%;max-width:330px">
  <rect x="118" y="4" width="32" height="44" rx="5" fill="var(--amber-panel)" stroke="var(--amber-ink2)" stroke-width="1.2"/>
  <rect x="125" y="13" width="18" height="2.6" rx="1.3" fill="var(--amber-ink2)" fill-opacity="0.5"/>
  <rect x="125" y="20" width="18" height="2.6" rx="1.3" fill="var(--amber-ink2)" fill-opacity="0.5"/>
  <rect x="125" y="27" width="18" height="2.6" rx="1.3" fill="var(--amber-ink2)" fill-opacity="0.5"/>
  <rect x="125" y="34" width="11" height="2.6" rx="1.3" fill="var(--amber-ink2)" fill-opacity="0.5"/>
  <text x="159" y="31" style="font-size:12.5px;fill:var(--amber-ink);font-weight:600">a proposal</text>
  <line x1="248" y1="26" x2="304" y2="26" stroke="#8B6914" stroke-width="1.4"/>
  <polygon points="313,26 304,21.6 304,30.4" fill="#8B6914"/>
  <circle cx="337" cy="17" r="6.8" fill="none" stroke="#8B6914" stroke-width="1.4"/>
  <path d="M 325 39 a 12 12 0 0 1 24 0" fill="none" stroke="#8B6914" stroke-width="1.4" stroke-linecap="round"/>
  <text x="359" y="31" style="font-size:12.5px;fill:var(--ink);font-weight:600">approve?</text>
</svg>
</div>
</div>

</div>

---

# When it started

<div class="text-base mt-1">

Francesco asked on 19 August when the missing frames began

</div>

<div class="mt-3 rounded-lg px-7 py-3" style="background-color:var(--quiet);border:1px solid rgb(var(--ink-rgb)/0.25)">
  <div class="text-[13px] leading-relaxed" style="color:var(--ink)">&ldquo;I noticed we had the missing frame problem. It would be good to know when (from which measurement) it started to show up.&rdquo;</div>
  <div class="text-[10.5px] leading-snug mt-2" style="color:var(--ink);opacity:0.6">Francesco, 19 August, 12:34:13. Ten seconds later a restart produced a clean run</div>
</div>

<div class="mt-2">
<svg viewBox="0 0 800 152" class="w-full" style="max-height:186px">
  <text x="214.5" y="14" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);opacity:0.75">no agent running</text>
  <text x="214.5" y="28" text-anchor="middle" style="font-size:11.5px;fill:var(--ink);font-weight:600">350 short runs, none of them seen</text>
  <text x="569.5" y="14" text-anchor="middle" style="font-size:10.5px;fill:var(--ink);opacity:0.75">both agents reading every run</text>
  <text x="569.5" y="28" text-anchor="middle" style="font-size:11.5px;fill:var(--ink);font-weight:600">155 short runs, one called nominal</text>
  <rect x="50.0" y="38" width="710.0" height="22" rx="3" fill="var(--panel)" stroke="#8B6914" stroke-width="1" stroke-opacity="0.4"/>
  <rect x="83.4" y="38" width="70.9" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <rect x="236.4" y="38" width="21.1" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <rect x="303.5" y="38" width="2.5" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <rect x="493.8" y="38" width="40.5" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <rect x="550.6" y="38" width="9.8" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <rect x="647.0" y="38" width="2.5" height="22" fill="var(--amber-fill)" stroke="var(--amber-ink2)" stroke-width="0.8" stroke-opacity="0.7"/>
  <line x1="93.8" y1="60" x2="93.8" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <line x1="210.5" y1="60" x2="210.5" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <line x1="327.2" y1="60" x2="327.2" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <line x1="443.9" y1="60" x2="443.9" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <line x1="560.6" y1="60" x2="560.6" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <line x1="677.3" y1="60" x2="677.3" y2="66" stroke="#8B6914" stroke-width="0.8" stroke-opacity="0.4"/>
  <text x="71.9" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">18 Aug</text>
  <text x="152.1" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">19 Aug</text>
  <text x="268.8" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">20 Aug</text>
  <text x="385.5" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">21 Aug</text>
  <text x="502.3" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">22 Aug</text>
  <text x="619.0" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">23 Aug</text>
  <text x="721.1" y="78" text-anchor="middle" style="font-size:9px;fill:var(--ink);opacity:0.5">24 Aug</text>
  <line x1="154.9" y1="32" x2="154.9" y2="60" stroke="#8B6914" stroke-width="1" stroke-dasharray="2 2" stroke-opacity="0.65"/>
  <line x1="379.0" y1="4" x2="379.0" y2="66" stroke="#8B6914" stroke-width="1.4"/>
  <line x1="83.4" y1="60" x2="83.4" y2="94" stroke="var(--amber-ink2)" stroke-width="1.2"/>
  <text x="52" y="110" style="font-size:11.5px;fill:var(--ink);font-weight:600">18 Aug 21:52:17</text>
  <text x="52" y="124" style="font-size:10px;fill:var(--ink);opacity:0.6">the first short run, 1528 of 1541</text>
  <text x="52" y="137" style="font-size:10px;fill:var(--ink);opacity:0.6">two minutes after a clean one</text>
  <line x1="379.0" y1="66" x2="379.0" y2="94" stroke="#8B6914" stroke-width="1.2"/>
  <text x="371.0" y="110" text-anchor="end" style="font-size:11.5px;fill:var(--ink);font-weight:600">21 Aug 10:39</text>
  <text x="371.0" y="124" text-anchor="end" style="font-size:10px;fill:var(--ink);opacity:0.6">both agents switched on</text>
  <text x="371.0" y="137" text-anchor="end" style="font-size:10px;fill:var(--ink);opacity:0.6">two days after Francesco asked</text>
</svg>
</div>

<div class="mt-3 grid gap-8" style="grid-template-columns:1.05fr 0.95fr">

<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-2" style="color:var(--ink);opacity:0.85">What it was handed</div>
  <div class="text-[10.5px] leading-relaxed" style="color:var(--ink);font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace"><span style="opacity:0.62">run_name</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">run_status</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">plan_id</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">subject_id</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">campaign_id</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">terminal_event_type</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">terminal_event_reason</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">terminal_event_occurred_at</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">adjustment_count</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">effective_parameters</span><span style="opacity:0.35"> &middot; </span><span style="font-weight:600;opacity:1">frames_saved</span><span style="opacity:0.35"> &middot; </span><span style="font-weight:600;opacity:1">frames_saved_expected</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">frames_collected</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">frames_collected_expected</span><span style="opacity:0.35"> &middot; </span><span style="opacity:0.62">reading_age_seconds</span></div>
</div>

<div>
  <div class="text-[10px] font-medium uppercase tracking-[0.2em] pb-2" style="color:var(--ink);opacity:0.85">What it said back</div>
  <div class="rounded-lg px-5 py-3" style="background-color:var(--amber-panel)">
    <div class="text-[12px] leading-relaxed" style="color:var(--amber-ink)">&ldquo;1528 frames saved against an expected count of 1541, leaving a shortfall of 13 frames. The saved frames shortfall suggests possible data loss that warrants further investigation.&rdquo;</div>
    <div class="text-[10.5px] leading-snug mt-2" style="color:var(--amber-ink);opacity:0.75">DataSuspect, confidence 0.82</div>
  </div>
</div>

</div>

---

# What else the record has answered

<div class="mt-6">
  <div class="py-[10px] border-t border-[#8B6914]/12 flex items-start gap-3">
    <svg viewBox="0 0 24 24" style="width:18px;height:18px;flex-shrink:0;opacity:0.6;color:var(--ink);margin-top:2px"><path d="M12 4L3 20h18L12 4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><line x1="12" y1="10" x2="12" y2="14.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="12" cy="17.2" r="0.9" fill="currentColor"/></svg>
    <div>
      <div class="text-[14.5px] leading-snug font-medium" style="color:var(--ink)">It found four faults in software CORA does not own</div>
      <div class="text-[12px] leading-snug mt-1" style="opacity:0.65">A scan stopped early still reported that it had finished.</div>
    </div>
  </div>
  <div class="py-[10px] border-t border-[#8B6914]/12 flex items-start gap-3">
    <svg viewBox="0 0 24 24" style="width:18px;height:18px;flex-shrink:0;opacity:0.6;color:var(--ink);margin-top:2px"><circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 7.5V12l3.2 2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <div>
      <div class="text-[14.5px] leading-snug font-medium" style="color:var(--ink)">The instrument corrected the record four times</div>
      <div class="text-[12px] leading-snug mt-1" style="opacity:0.65">A reading with no clock time was being stored as 1 January 1990.</div>
    </div>
  </div>
  <div class="py-[10px] border-t border-[#8B6914]/12 flex items-start gap-3">
    <svg viewBox="0 0 24 24" style="width:18px;height:18px;flex-shrink:0;opacity:0.6;color:var(--ink);margin-top:2px"><line x1="3" y1="12" x2="8" y2="12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="16" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    <div>
      <div class="text-[14.5px] leading-snug font-medium" style="color:var(--ink)">It records its own gaps</div>
      <div class="text-[12px] leading-snug mt-1" style="opacity:0.65">For three days the abort signal was unreachable, recorded once per attempt.</div>
    </div>
  </div>
  <div class="py-[10px] border-t border-[#8B6914]/12 flex items-start gap-3">
    <svg viewBox="0 0 24 24" style="width:18px;height:18px;flex-shrink:0;opacity:0.6;color:var(--ink);margin-top:2px"><circle cx="10.5" cy="10.5" r="6" fill="none" stroke="currentColor" stroke-width="1.6"/><line x1="15" y1="15" x2="20" y2="20" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    <div>
      <div class="text-[14.5px] leading-snug font-medium" style="color:var(--ink)">The record can be checked by an outsider</div>
      <div class="text-[12px] leading-snug mt-1" style="opacity:0.65">Every kind travels with a row count and a fingerprint, even the kinds with no rows.</div>
    </div>
  </div>
  <div class="py-[10px] border-t border-[#8B6914]/12 flex items-start gap-3">
    <svg viewBox="0 0 24 24" style="width:18px;height:18px;flex-shrink:0;opacity:0.6;color:var(--ink);margin-top:2px"><circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" stroke-width="1.6"/><line x1="6.3" y1="17.7" x2="17.7" y2="6.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    <div>
      <div class="text-[14.5px] leading-snug font-medium" style="color:var(--ink)">It cannot change anything at the beamline</div>
      <div class="text-[12px] leading-snug mt-1" style="opacity:0.65">There is no code path from CORA to a motor, a shutter, or a detector.</div>
    </div>
  </div>
</div>

---

# What a deployment needs

<div class="text-base mt-1">

The five inputs as each looked at 2-BM

</div>

<div class="mt-6 grid gap-10 items-center" style="grid-template-columns:1fr 1fr">

<div class="space-y-[15px]">
  <div class="grid gap-3 items-baseline" style="grid-template-columns:34px 1fr">
    <div class="flex items-center gap-1.5 pt-[1px]"><span class="text-[10px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">1</span><carbon:flow class="text-[16px]" style="color:var(--ink)" /></div>
    <div class="text-[13px] leading-snug"><span class="font-semibold" style="color:var(--ink)">Describe the beamline.</span> One file, source to detector.</div>
  </div>
  <div class="grid gap-3 items-baseline" style="grid-template-columns:34px 1fr">
    <div class="flex items-center gap-1.5 pt-[1px]"><span class="text-[10px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">2</span><carbon:view class="text-[16px]" style="color:var(--ink)" /></div>
    <div class="text-[13px] leading-snug"><span class="font-semibold" style="color:var(--ink)">Say what it may read.</span> Writing stays off.</div>
  </div>
  <div class="grid gap-3 items-baseline" style="grid-template-columns:34px 1fr">
    <div class="flex items-center gap-1.5 pt-[1px]"><span class="text-[10px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">3</span><carbon:locked class="text-[16px]" style="color:var(--ink)" /></div>
    <div class="text-[13px] leading-snug"><span class="font-semibold" style="color:var(--ink)">Name the hutches.</span> Each with its safety signal.</div>
  </div>
  <div class="grid gap-3 items-baseline" style="grid-template-columns:34px 1fr">
    <div class="flex items-center gap-1.5 pt-[1px]"><span class="text-[10px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">4</span><carbon:bare-metal-server class="text-[16px]" style="color:var(--ink)" /></div>
    <div class="text-[13px] leading-snug"><span class="font-semibold" style="color:var(--ink)">Run it once for APS.</span> Not once per beamline.</div>
  </div>
  <div class="grid gap-3 items-baseline" style="grid-template-columns:34px 1fr">
    <div class="flex items-center gap-1.5 pt-[1px]"><span class="text-[10px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">5</span><carbon:power class="text-[16px]" style="color:var(--ink)" /></div>
    <div class="text-[13px] leading-snug"><span class="font-semibold" style="color:var(--ink)">Seed, then switch on.</span> One observer at a time.</div>
  </div>
</div>

<div class="mx-auto w-full" style="max-width:340px">
  <div class="text-[9px] font-medium uppercase tracking-[0.16em] mb-1.5" style="color:var(--ink);opacity:0.65">deployments/2-bm/beamline.yaml</div>
  <div class="rounded px-3 py-2.5" style="background-color:var(--panel)">
<pre class="text-[10.5px] leading-[1.6] m-0" style="font-family:ui-monospace,Menlo,monospace;color:var(--ink)"><span style="opacity:0.55">- name:</span> Camera
  <span style="opacity:0.55">family:</span> Camera
  <span style="opacity:0.55">model:</span> flir_oryx
  <span style="opacity:0.55">sensor:</span> Sony IMX250 CMOS, 2448 x 2048 pixel
  <span style="opacity:0.55">pv:</span> "2bmSP1:"
<span style="opacity:0.55">- name:</span> Hexapod
  <span style="opacity:0.55">family:</span> Hexapod
  <span style="opacity:0.55">pv:</span> "2bmHXP:"
<span style="opacity:0.55">- name:</span> MirrorTable
  <span style="opacity:0.55">family:</span> Table
  <span style="opacity:0.55">pv:</span> "2bma:table1"</pre>
  </div>
  <div class="text-[10.5px] mt-1.5" style="opacity:0.7">Three of 38 devices. The file is 834 lines.</div>
</div>

</div>

---

# Proposed next steps

<div class="mt-8">
  <div class="space-y-1">
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">1</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The questions</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What is asked about an experiment.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">2</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">The machinery</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What the record is made of.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline px-4 py-2" style="grid-template-columns:34px 1fr">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink);opacity:0.5">3</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="opacity:0.5">At a beamline</div>
        <div class="text-[12.5px] leading-snug mt-1" style="opacity:0.4">What runs at 2-BM today.</div>
      </div>
    </div>
    <div class="grid gap-4 items-baseline rounded px-4 py-2" style="grid-template-columns:34px 1fr;background-color:var(--panel)">
      <div class="text-[21px] font-semibold leading-none" style="color:var(--ink)">4</div>
      <div>
        <div class="text-[14.5px] font-semibold" style="color:var(--ink)">Proposed next steps<span class="text-[10px] font-medium uppercase tracking-[0.16em] ml-3 opacity-70">you are here</span></div>
        <div class="text-[12.5px] leading-snug mt-1" style="color:var(--ink);opacity:0.85">Where this path goes.</div>
      </div>
    </div>
  </div>
  <div class="mt-5 mx-auto" style="max-width:560px"><SpineRow :active="4" /></div>
</div>

---

# Beyond 2-BM

<div class="text-base mt-1">

Upward before outward

</div>

<div class="mt-5">
<svg viewBox="0 0 1000 330" class="w-full" style="max-height:296px">
  <line x1="232" y1="272" x2="232" y2="22" stroke="currentColor" stroke-width="1.4" opacity="0.45"/>
  <polygon points="226,22 232,6 238,22" fill="currentColor" opacity="0.45"/>
  <line x1="232" y1="272" x2="806" y2="272" stroke="currentColor" stroke-width="1.4" opacity="0.45"/>
  <polygon points="806,266 822,272 806,278" fill="currentColor" opacity="0.45"/>

  <text transform="rotate(-90 88 147)" x="88" y="147" text-anchor="middle" style="font-size:11px;font-weight:600;letter-spacing:2.4px;fill:var(--ink);opacity:0.85">AUTONOMY</text>
  <text x="522" y="324" text-anchor="middle" style="font-size:11px;font-weight:600;letter-spacing:2.4px;fill:var(--ink);opacity:0.85">INTELLIGENCE</text>

  <text x="220" y="52" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Runs unattended</text>
  <text x="220" y="151" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Recovers on its own</text>
  <text x="220" y="250" text-anchor="end" style="font-size:11.5px;fill:currentColor;opacity:0.7">Someone approves</text>

  <text x="326" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">A fixed recipe</text>
  <text x="520" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">Computation steers the run</text>
  <text x="714" y="298" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.7">The science goal steers it</text>

  <rect x="526" y="50" width="252" height="94" rx="8" fill="#8B6914" fill-opacity="0.07" stroke="#8B6914" stroke-width="1.5" stroke-dasharray="5 5" opacity="0.7"/>
  <text x="652" y="92" text-anchor="middle" style="font-size:12.5px;font-weight:600;fill:var(--ink);opacity:0.9">where this is going</text>
  <text x="652" y="113" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.6">19-BM and the reason for the record</text>

  <rect x="260" y="150" width="252" height="94" rx="8" fill="#8B6914" fill-opacity="0.16" stroke="#8B6914" stroke-width="1.8"/>
  <text x="386" y="192" text-anchor="middle" style="font-size:12px;font-weight:700;letter-spacing:1.2px;fill:var(--ink)">2-BM, TODAY</text>
  <text x="386" y="213" text-anchor="middle" style="font-size:11.5px;fill:currentColor;opacity:0.75">a fixed recipe, a person approving</text>
  <path d="M 386 146 L 386 113 Q 386 97 402 97 L 506 97" fill="none" stroke="#8B6914" stroke-width="2.6" stroke-linecap="round" opacity="0.9"/>
  <polygon points="506,90 522,97 506,104" fill="#8B6914" opacity="0.9"/>
  <text x="376" y="126" text-anchor="end" style="font-size:11px;font-weight:600;letter-spacing:0.6px;fill:#8B6914">1 upward</text>
  <text x="446" y="84" text-anchor="middle" style="font-size:11px;font-weight:600;letter-spacing:0.6px;fill:#8B6914">2 then outward</text>
</svg>
</div>

<div class="grid gap-8 mt-3" style="grid-template-columns:1fr 1fr">
  <div class="pl-4 border-l-2 border-[#8B6914]/60">
    <div class="text-[10px] font-medium uppercase tracking-[0.18em] text-[#8B6914]">1 &middot; Upward, and this is ours</div>
    <div class="text-[12.5px] leading-snug mt-1">A record makes an unattended decision authorizable in the first place and reviewable afterwards.</div>
  </div>
  <div class="pl-4 border-l-2 border-[#8B6914]/30">
    <div class="text-[10px] font-medium uppercase tracking-[0.18em] text-[#8B6914]">2 &middot; Outward, and this is a collaboration</div>
    <div class="text-[12.5px] leading-snug mt-1">Every steering brain is somebody else&rsquo;s work, so CORA offers a single seam for all of them. BoTorch is wired in, and EAA here at APS and gpCAM at Berkeley fit that same seam.</div>
  </div>
</div>

---

# A survey

<div class="text-base mt-1">

Two informal series open across APS

</div>

<div class="grid gap-9 mt-10" style="grid-template-columns:1fr 1fr">

  <div class="rounded px-8 py-9" style="background-color:var(--panel)">
    <svg viewBox="0 0 28 28" width="38" height="38"><path d="M 14 26 L 14 10" fill="none" stroke="#8B6914" stroke-width="2.6" stroke-linecap="round"/><polygon points="7,12 14,3 21,12" fill="#8B6914"/></svg>
    <div class="text-[18px] font-semibold text-[#8B6914] mt-5">Autonomous science</div>
    <div class="text-[16px] leading-snug italic mt-3" style="color:var(--ink)">&ldquo;What would this beamline have to be able to answer before it could run itself?&rdquo;</div>
  </div>

  <div class="rounded px-8 py-9" style="background-color:var(--panel)">
    <svg viewBox="0 0 28 28" width="38" height="38"><path d="M 2 14 L 18 14" fill="none" stroke="#8B6914" stroke-width="2.6" stroke-linecap="round"/><polygon points="16,7 25,14 16,21" fill="#8B6914"/></svg>
    <div class="text-[18px] font-semibold text-[#8B6914] mt-5">Agentic beamlines</div>
    <div class="text-[16px] leading-snug italic mt-3" style="color:var(--ink)">&ldquo;Who is building agents here, what may they do, and who is there when they do it?&rdquo;</div>
  </div>

</div>

---

# What the record cannot answer yet

<div class="mt-8 space-y-6">

<div class="flex gap-4 items-baseline">
  <div class="text-[13.5px] leading-snug italic flex-shrink-0" style="color:var(--ink);width:400px">&ldquo;Show me 2-BM and 12-ID side by side, live.&rdquo;</div>
  <div class="text-[13px] leading-snug opacity-70">Designed but not hardened, with no live link between instances.</div>
</div>

<div class="flex gap-4 items-baseline">
  <div class="text-[13.5px] leading-snug italic flex-shrink-0" style="color:var(--ink);width:400px">&ldquo;Show me the beamline as it was understood last March.&rdquo;</div>
  <div class="text-[13px] leading-snug opacity-70">The model holds it but no endpoint serves it.</div>
</div>

<div class="flex gap-4 items-baseline">
  <div class="text-[13.5px] leading-snug italic flex-shrink-0" style="color:var(--ink);width:400px">&ldquo;What did CORA decide to do?&rdquo;</div>
  <div class="text-[13px] leading-snug opacity-70">Nothing at 2-BM, where the deployment is read only.</div>
</div>

<div class="flex gap-4 items-baseline">
  <div class="text-[13.5px] leading-snug italic flex-shrink-0" style="color:var(--ink);width:400px">&ldquo;How did it behave while driving a beamline?&rdquo;</div>
  <div class="text-[13px] leading-snug opacity-70">It never has. That is the most important row on this slide.</div>
</div>

</div>

<div class="text-lg font-semibold text-[#8B6914] mt-12 text-center">

So: what would you ask it?

</div>

---
layout: cover
background: /hero-typewriter.webp
class: text-white
---

# Thank you
