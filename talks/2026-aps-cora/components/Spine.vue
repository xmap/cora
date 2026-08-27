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
  <!-- THE SPINE. One picture, four zones, one per part of the talk.
       Zone 1 who asks and what comes back, zone 2 the box itself, zone 3
       what it reads off the experiment, zone 4 what it would write back.
       Each number sits against the thing it names. The askers box and the
       experiment box are the same height on purpose: the two ends of the
       picture are peers, and CORA is the only thing between them.
       active=0 draws the whole thing at full strength for the map slide;
       each divider passes its own part number. -->
  <svg viewBox="0 0 300 268" class="w-full" style="overflow:visible">
    <!-- ZONE 1: who asks, and the two directions between them and CORA -->
    <g :opacity="op(1, active)">
      <rect x="44" y="4" width="212" height="44" rx="12" fill="none" :stroke="teal" stroke-width="1.5" />

      <circle cx="66" cy="22" r="4.2" fill="none" :stroke="teal" stroke-width="1.3" />
      <path d="M 59 34 a 7 7 0 0 1 14 0" fill="none" :stroke="teal" stroke-width="1.3" stroke-linecap="round" />
      <text x="79" y="29.5" text-anchor="start" style="font-size:10px;fill:var(--ink)">people</text>

      <rect x="187" y="22" width="17" height="14" rx="3.5" fill="none" :stroke="teal" stroke-width="1.3" />
      <circle cx="192" cy="29" r="1.4" :fill="teal" />
      <circle cx="199" cy="29" r="1.4" :fill="teal" />
      <line x1="195.5" y1="22" x2="195.5" y2="18" :stroke="teal" stroke-width="1.3" stroke-linecap="round" />
      <circle cx="195.5" cy="16.6" r="1.3" :fill="teal" />
      <text x="210" y="29.5" text-anchor="start" style="font-size:10px;fill:var(--ink)">agents</text>

      <line x1="124" y1="56" x2="124" y2="84" :stroke="teal" stroke-width="1.3" />
      <polygon points="124,91 120.2,83 127.8,83" :fill="teal" />
      <line x1="176" y1="91" x2="176" y2="63" :stroke="teal" stroke-width="1.3" />
      <polygon points="176,56 172.2,64 179.8,64" :fill="teal" />

      <text x="116" y="77" text-anchor="end" style="font-size:9.5px;fill:var(--ink)">questions</text>
      <text x="184" y="77" text-anchor="start" style="font-size:9.5px;fill:var(--ink)">answers</text>

      <circle cx="58" cy="73.5" r="8" :fill="badgeFill(1, active)" :stroke="teal" stroke-width="1.1" />
      <text x="58" y="76.9" text-anchor="middle" :style="{fontSize:'9.5px',fontWeight:600,fill:badgeText(1, active)}">1</text>
    </g>

    <!-- ZONE 2: the box. What is inside it is part two. -->
    <g :opacity="op(2, active)">
      <rect x="44" y="99" width="212" height="70" rx="12" fill="var(--panel)" :stroke="teal" stroke-width="1.5" />
      <text x="164" y="140" text-anchor="middle" style="font-size:19px;font-weight:600;letter-spacing:3px;fill:var(--ink)">CORA</text>

      <circle cx="111" cy="134" r="8" :fill="badgeFill(2, active)" :stroke="teal" stroke-width="1.1" />
      <text x="111" y="137.4" text-anchor="middle" :style="{fontSize:'9.5px',fontWeight:600,fill:badgeText(2, active)}">2</text>
    </g>

    <!-- ZONE 3: what it reads off a running experiment -->
    <g :opacity="op(3, active)">
      <line x1="124" y1="212" x2="124" y2="184" :stroke="teal" stroke-width="1.3" />
      <polygon points="124,177 120.2,185 127.8,185" :fill="teal" />
      <text x="116" y="198" text-anchor="end" style="font-size:9.5px;fill:var(--ink)">witness</text>

      <rect x="44" y="220" width="212" height="44" rx="12" fill="none" :stroke="teal" stroke-width="1.5" />
      <text x="150" y="246.5" text-anchor="middle" style="font-size:12.5px;font-weight:500;fill:var(--ink)">the experiment</text>

      <circle cx="66" cy="194.5" r="8" :fill="badgeFill(3, active)" :stroke="teal" stroke-width="1.1" />
      <text x="66" y="197.9" text-anchor="middle" :style="{fontSize:'9.5px',fontWeight:600,fill:badgeText(3, active)}">3</text>
    </g>

    <!-- ZONE 4: what it would write back. Dashed, because it does not yet. -->
    <g :opacity="op(4, active)">
      <line x1="176" y1="177" x2="176" y2="205" :stroke="teal" stroke-width="1.3" stroke-dasharray="3 3" />
      <polygon points="176,212 172.2,204 179.8,204" :fill="teal" />
      <text x="184" y="198" text-anchor="start" style="font-size:9.5px;fill:var(--ink)">conduct</text>

      <circle cx="236" cy="194.5" r="8" :fill="badgeFill(4, active)" :stroke="teal" stroke-width="1.1" />
      <text x="236" y="197.9" text-anchor="middle" :style="{fontSize:'9.5px',fontWeight:600,fill:badgeText(4, active)}">4</text>
    </g>
  </svg>
</template>
