<script setup>
defineProps({
  active: { type: Number, default: 0 },
})

const teal = 'var(--ink)'

function op(n, active) {
  if (!active) return 1
  return n === active ? 1 : 0.24
}

function badgeFill(n, active) {
  return !active || n === active ? teal : 'var(--card)'
}

function badgeText(n, active) {
  return !active || n === active ? 'var(--card)' : teal
}
</script>

<template>
  <!-- THE SPINE, LAID IN A ROW. Same four zones as Spine.vue, read left to
       right instead of top to bottom, so a chapter whose slides run question
       then contexts then record has a divider of the same shape. Zone 1 who
       asks and what comes back, zone 2 the box itself, zone 3 what it reads
       off the experiment, zone 4 what it would write back. The askers box and
       the experiment box are the same size on purpose: the two ends of the
       picture are peers, and CORA is the only thing between them.
       active=0 draws the whole thing at full strength for the map slide;
       each divider passes its own part number. -->
  <svg viewBox="0 0 720 152" class="w-full" style="overflow:visible">
    <!-- ZONE 1: who asks, and the two directions between them and CORA -->
    <g :opacity="op(1, active)">
      <rect x="4" y="30" width="180" height="92" rx="12" fill="none" :stroke="teal" stroke-width="1.5" />

      <circle cx="42" cy="57" r="4.6" fill="none" :stroke="teal" stroke-width="1.3" />
      <path d="M 34.5 70 a 7.5 7.5 0 0 1 15 0" fill="none" :stroke="teal" stroke-width="1.3" stroke-linecap="round" />
      <text x="60" y="66" text-anchor="start" style="font-size:11px;fill:var(--ink)">people</text>

      <rect x="33" y="88" width="18" height="15" rx="3.5" fill="none" :stroke="teal" stroke-width="1.3" />
      <circle cx="38.4" cy="95.5" r="1.5" :fill="teal" />
      <circle cx="45.6" cy="95.5" r="1.5" :fill="teal" />
      <line x1="42" y1="88" x2="42" y2="83.5" :stroke="teal" stroke-width="1.3" stroke-linecap="round" />
      <circle cx="42" cy="82" r="1.4" :fill="teal" />
      <text x="60" y="100" text-anchor="start" style="font-size:11px;fill:var(--ink)">agents</text>

      <line x1="190" y1="62" x2="254" y2="62" :stroke="teal" stroke-width="1.3" />
      <polygon points="262,62 254,58.2 254,65.8" :fill="teal" />
      <line x1="262" y1="94" x2="198" y2="94" :stroke="teal" stroke-width="1.3" />
      <polygon points="190,94 198,90.2 198,97.8" :fill="teal" />

      <text x="226" y="52" text-anchor="middle" style="font-size:9.5px;fill:var(--ink)">questions</text>
      <text x="226" y="110" text-anchor="middle" style="font-size:9.5px;fill:var(--ink)">answers</text>

      <circle cx="16" cy="16" r="8.5" :fill="badgeFill(1, active)" :stroke="teal" stroke-width="1.1" />
      <text x="16" y="19.6" text-anchor="middle" :style="{fontSize:'10px',fontWeight:600,fill:badgeText(1, active)}">1</text>
    </g>

    <!-- ZONE 2: the box. What is inside it is part two. -->
    <g :opacity="op(2, active)">
      <rect x="268" y="30" width="180" height="92" rx="12" fill="var(--panel)" :stroke="teal" stroke-width="1.5" />
      <text x="358" y="83" text-anchor="middle" style="font-size:20px;font-weight:600;letter-spacing:3px;fill:var(--ink)">CORA</text>

      <circle cx="280" cy="16" r="8.5" :fill="badgeFill(2, active)" :stroke="teal" stroke-width="1.1" />
      <text x="280" y="19.6" text-anchor="middle" :style="{fontSize:'10px',fontWeight:600,fill:badgeText(2, active)}">2</text>
    </g>

    <!-- ZONE 3: what it reads off a running experiment -->
    <g :opacity="op(3, active)">
      <line x1="526" y1="62" x2="462" y2="62" :stroke="teal" stroke-width="1.3" />
      <polygon points="454,62 462,58.2 462,65.8" :fill="teal" />
      <text x="490" y="52" text-anchor="middle" style="font-size:9.5px;fill:var(--ink)">witness</text>

      <rect x="532" y="30" width="184" height="92" rx="12" fill="none" :stroke="teal" stroke-width="1.5" />
      <text x="624" y="80" text-anchor="middle" style="font-size:12.5px;font-weight:500;fill:var(--ink)">the experiment</text>

      <circle cx="472" cy="16" r="8.5" :fill="badgeFill(3, active)" :stroke="teal" stroke-width="1.1" />
      <text x="472" y="19.6" text-anchor="middle" :style="{fontSize:'10px',fontWeight:600,fill:badgeText(3, active)}">3</text>
    </g>

    <!-- ZONE 4: what it would write back. Dashed, because it does not yet. -->
    <g :opacity="op(4, active)">
      <line x1="454" y1="94" x2="518" y2="94" :stroke="teal" stroke-width="1.3" stroke-dasharray="3 3" />
      <polygon points="526,94 518,90.2 518,97.8" :fill="teal" />
      <text x="490" y="110" text-anchor="middle" style="font-size:9.5px;fill:var(--ink)">conduct</text>

      <circle cx="508" cy="16" r="8.5" :fill="badgeFill(4, active)" :stroke="teal" stroke-width="1.1" />
      <text x="508" y="19.6" text-anchor="middle" :style="{fontSize:'10px',fontWeight:600,fill:badgeText(4, active)}">4</text>
    </g>
  </svg>
</template>
