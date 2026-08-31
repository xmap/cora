/* Subject-neutral timeline scrubber for the status relay's page.

   Copy-and-adapt of docs/javascripts/scrubber-demo.js (the paper's replay
   scrubber for a fixed, already-recorded run), not a shared module: about
   40% of that script is coupled to the paper's own fixed data file
   (beam_loss_at / beam_back_at, iteration convergence, the recipe-
   expansion fidelity badge) and does not apply here. The two are meant to
   diverge over time -- the paper's version stays frozen as published,
   this one grows real edge cases (zero points, one event, a window still
   open with no end).

   What's carried over near-verbatim because it's fiddly and data-shape
   agnostic: svg(), parseT, fmtClock, xFor, buildScale, and especially
   wireDrag (pointer-drag with setPointerCapture, the keyboard map, the
   slider proxy) -- there is no reason to get that logic right twice.

   This module knows nothing about Runs, proposals, or any other CORA
   domain. It renders a "timeline document": a subject-neutral shape with
   a time domain and a list of lanes, each either "markers" (discrete
   events, one of which may carry a `state` that a fold walks forward) or
   "series" (a value over time, numeric or textual). Whatever produced the
   document -- a run's history today, an activity tail or another lens
   later -- is the caller's concern, not this module's. See page.html's
   `runHistoryToTimelineDocument` for the one adapter that exists today,
   bridging the still-unchanged run_history wire shape into this document
   shape; a later step is expected to have the producer emit the document
   directly and retire that adapter.

   Entry point: CoraScrubber.mount(rootEl, doc, opts). No fetch, no mkdocs
   boot hook, no fixed #cora-scrubber id: the caller owns the element and
   hands over an already-fetched document. Idempotent: a second mount on
   the same element tears down its listeners and rebuilds, so switching
   subjects never leaks a drag/keyboard handler onto stale DOM.

   `opts.follow: true` is the one flag that changes this module's own
   behavior rather than just being forwarded: it pins the cursor to the
   document's live edge on mount instead of the start, and disables Play
   / "jump to last event" by default (`opts.showPlay`/`showJumpLast:
   false`), since both assume a closed, already-finished timeline. It does
   NOT make this module re-render on new data by itself: a flowing-window
   caller (page.html) re-fetches its own accumulated buffer and calls
   mount() again on each update, and passes `opts.onScrub` to learn the
   moment a user grabs the cursor, so it can stop doing that until the
   viewer asks to resume. This module still knows nothing about what
   "following" means; it only reports the one signal a caller needs. */
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";

  const VW = 920;
  const PAD_L = 84;
  const PAD_R = 24;
  const LANE_START = 34;
  const LANE_HEIGHT = 40;
  const MAX_SERIES_LANES = 6;
  const AXIS_MARGIN = 44;
  const MARK_W = 8;
  // Two marks closer than this many user units cannot be drawn apart. At a
  // 15-minute window over the 812-unit plot one unit is about 1.1s, so this is
  // roughly 11s -- but it is deliberately a WIDTH, not a duration. What can be
  // separated is a property of the canvas, and a duration constant would
  // silently lie at every other window size.
  const COLLAPSE_GAP = 10;
  const LABEL_CH = 5.6;
  const LABEL_PAD = 5;
  const LANE_LABEL_CH = 6.2;
  // Wide enough for a two-digit count at the badge's 9px mono.
  const CLUSTER_MIN_W = 16;

  function parseT(iso) {
    return Date.parse(iso) / 1000;
  }

  function svg(tag, attrs) {
    const el = document.createElementNS(SVGNS, tag);
    if (attrs) {
      for (const k in attrs) el.setAttribute(k, attrs[k]);
    }
    return el;
  }

  function fmtClock(t0, secs) {
    const d = new Date((t0 + secs) * 1000);
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
  }

  function xFor(scale, secs) {
    return PAD_L + (secs - scale.dmin) * scale.k;
  }

  // Ticks land on round wall-clock boundaries, so they stay put as the window
  // slides instead of renumbering under a moving origin.
  const TICK_STEPS = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
  function pickTickStep(span) {
    const target = span / 9;
    for (const s of TICK_STEPS) {
      if (s >= target) return s;
    }
    return TICK_STEPS[TICK_STEPS.length - 1];
  }

  // The scale now maps a VIEW onto the plot, not the whole domain. When the
  // view equals the domain (REWIND's default) this is the old behaviour
  // exactly; when it is narrower, the chart becomes a window that pans.
  function buildScale(from, to) {
    const dmin = from;
    const dmax = to > from ? to : from + 1;
    const k = (VW - PAD_L - PAD_R) / (dmax - dmin);
    return { dmin, dmax, k };
  }

  // Keep the view inside the domain, and never let it grow past it: panning
  // should run out at the ends rather than drift into blank space that reads
  // like a quiet period.
  function clampView(from, span, domainMax) {
    const width = Math.min(span, domainMax);
    const start = Math.max(0, Math.min(from, domainMax - width));
    return { from: start, to: start + width };
  }

  // Fold every lane forward to time t: for the primary markers lane (if
  // any), the last point at or before t whose `state` is set -- a point
  // with no `state` is a real event but does not change what's "current"
  // (a run's campaign-membership events, for example, sit on the same
  // lifecycle lane as its start/hold/end but say nothing about whether it
  // is running). Every other lane gets its own last-point-at-or-before-t
  // reading, keyed by lane_id.
  function foldTo(model, t) {
    let primary = null;
    if (model.primaryLane) {
      let point = null;
      let state = null;
      let tone = null;
      for (const p of model.primaryLane.points) {
        if (p.secs > t + 1e-6) break;
        point = p;
        if (p.state) state = p.state;
        if (p.tone) tone = p.tone;
      }
      primary = { point, state, tone };
    }
    const readings = {};
    for (const lane of model.lanes) {
      if (lane === model.primaryLane) continue;
      let reading = null;
      for (const p of lane.points) {
        if (p.secs > t + 1e-6) break;
        reading = p;
      }
      readings[lane.lane_id] = reading;
    }
    return { primary, readings };
  }

  // Build the model from a timeline document: `doc.domain.from`/`.to` set
  // the time origin and (absent a later point pushing it out) the right
  // edge; `doc.lanes` becomes an ordered lane list, series lanes capped at
  // MAX_SERIES_LANES by point count, most-populated first. `doc.subject_lane_id`
  // (default: the first markers lane) names the lane `foldTo` treats as
  // the primary state-carrying one.
  function buildModel(doc) {
    const domain = doc.domain || {};
    const t0 = domain.from ? parseT(domain.from) : 0;
    const domainEndSecs = domain.to ? parseT(domain.to) - t0 : null;

    const rawLanes = (doc.lanes || []).map((lane) => ({
      lane_id: lane.lane_id,
      label: lane.label,
      render: lane.render,
      points: (lane.points || [])
        .map((p) => ({
          secs: parseT(p.t) - t0,
          label: p.label,
          state: p.state || null,
          tone: p.tone || null,
          // Severity rank, 0 routine / 1 notable / 2 critical. Supplied by
          // whoever built the document: which event types matter is domain
          // vocabulary, and this module deliberately knows none.
          tier: p.tier || 0,
          value: p.value,
          text: p.text != null ? p.text : null,
        }))
        .sort((a, b) => a.secs - b.secs),
    }));

    const markerLanes = rawLanes.filter((l) => l.render === "markers");
    const seriesLanesAll = rawLanes.filter((l) => l.render === "series");
    const seriesLanes = seriesLanesAll
      .slice()
      .sort((a, b) => b.points.length - a.points.length)
      .slice(0, MAX_SERIES_LANES);
    const omittedSeries = seriesLanesAll.length - seriesLanes.length;

    const orderedSeriesIds = new Set(seriesLanes.map((l) => l.lane_id));
    const lanes = rawLanes.filter(
      (l) => l.render === "markers" || orderedSeriesIds.has(l.lane_id)
    );

    const subjectLaneId = doc.subject_lane_id || (markerLanes[0] && markerLanes[0].lane_id);
    const primaryLane = lanes.find((l) => l.lane_id === subjectLaneId) || null;

    let xmax = domainEndSecs !== null ? domainEndSecs : 0;
    for (const lane of lanes) {
      for (const p of lane.points) xmax = Math.max(xmax, p.secs);
    }

    return { t0, xmax, lanes, primaryLane, omittedSeries, live: !!doc.live };
  }

  // The lane already names the aggregate, so repeating it in every label costs
  // a third of the axis for nothing: on a lane called "Procedures",
  // `ProcedureIterationStarted` says no more than `IterationStarted`. Derived
  // from the lane's own label rather than a table of domain nouns, so this
  // module stays subject-neutral the way its header promises.
  function stripLanePrefix(label, laneLabel) {
    if (!laneLabel) return label;
    const noun = laneLabel.replace(/s$/, "");
    if (noun.length > 2 && label.length > noun.length && label.indexOf(noun) === 0) {
      return label.slice(noun.length);
    }
    return label;
  }

  // Collapse is a RENDERING concern only: `lane.points` keeps every point,
  // because `foldTo` walks the primary lane for the last point carrying a
  // `state` and a merged point would break REWIND's folded readout.
  function clusterPoints(points, X) {
    const out = [];
    let cur = null;
    for (const p of points) {
      const x = X(p.secs);
      if (cur && x - cur.xEnd < COLLAPSE_GAP) {
        cur.items.push(p);
        cur.xEnd = x;
      } else {
        if (cur) out.push(cur);
        cur = { xStart: x, xEnd: x, items: [p] };
      }
    }
    if (cur) out.push(cur);
    return out;
  }

  // The point a cluster is named after: highest tier first, then the rarest
  // name in it, so a lone RunAborted is never spoken for by the six routine
  // events it happens to sit beside.
  function clusterHead(cluster) {
    const counts = {};
    for (const p of cluster.items) counts[p.label] = (counts[p.label] || 0) + 1;
    let best = cluster.items[0];
    let tier = 0;
    for (const p of cluster.items) {
      const t = p.tier || 0;
      if (t > tier) tier = t;
      const bt = best.tier || 0;
      if (t > bt || (t === bt && counts[p.label] < counts[best.label])) best = p;
    }
    return { point: best, tier, uniform: cluster.items.every((p) => p.label === best.label) };
  }

  // Seat labels by severity first, then left to right. A purely left-to-right
  // greedy pass lets a flood of routine traffic take the slot a critical event
  // needed, and that is the one label that must never be the one dropped.
  function seatLabels(candidates) {
    const order = candidates.slice().sort((a, b) => b.tier - a.tier || a.cx - b.cx);
    const placed = [];
    for (const c of order) {
      if (c.skip) continue;
      let l = c.cx - c.w / 2;
      let r = c.cx + c.w / 2;
      if (l < PAD_L) {
        l = PAD_L;
        r = l + c.w;
      }
      if (r > VW - PAD_R) {
        r = VW - PAD_R;
        l = r - c.w;
      }
      if (placed.some((q) => !(r <= q.l - LABEL_PAD || l >= q.r + LABEL_PAD))) continue;
      placed.push({ l, r, c });
    }
    return placed;
  }

  function renderTimeline(model, scale) {
    const laneCount = Math.max(1, model.lanes.length);
    const axisY = LANE_START + laneCount * LANE_HEIGHT + 10;
    const vh = axisY + AXIS_MARGIN;
    const X = (secs) => xFor(scale, secs);

    // Focusable and slider-shaped: the value it announces is the fold cursor's
    // clock time, which `setCursor` keeps in `aria-valuetext`. This replaces
    // the separate slider element that used to be the only keyboard route.
    const g = svg("svg", {
      viewBox: `0 0 ${VW} ${vh}`,
      class: "cora-scrubber__svg",
      tabindex: "0",
      role: "slider",
      "aria-label":
        "Timeline. Arrows move the fold cursor, comma and period step between events, " +
        "shift with arrows pans, Enter pins the nearest event.",
      "aria-valuemin": "0",
      "aria-valuemax": String(Math.round(model.xmax)),
      "aria-valuenow": "0",
    });

    const laneY = new Map();
    model.lanes.forEach((lane, i) => {
      const y = LANE_START + i * LANE_HEIGHT;
      laneY.set(lane.lane_id, y);
      g.appendChild(svg("line", { x1: PAD_L, y1: y, x2: VW - PAD_R, y2: y, class: "cs-baseline" }));
      const t = svg("text", { x: PAD_L - 12, y: y + 4, class: "cs-lane-label", "text-anchor": "end" });
      // SVG has no text-overflow, so a long lane label silently runs under the
      // plot instead of being clipped. Measure in the label's own advance
      // width and keep the full text on hover.
      const room = PAD_L - 12 - 4;
      const maxChars = Math.floor(room / LANE_LABEL_CH);
      t.textContent =
        lane.label.length > maxChars ? `${lane.label.slice(0, Math.max(1, maxChars - 1))}…` : lane.label;
      if (t.textContent !== lane.label) {
        const full = svg("title");
        full.textContent = lane.label;
        t.appendChild(full);
      }
      g.appendChild(t);
    });

    const timed = [];
    const selectable = [];

    for (const lane of model.lanes) {
      const y = laneY.get(lane.lane_id);
      if (lane.render === "markers") {
        // The gate here used to be `points.length <= MAX_MARKER_LABELS`, which
        // tests COUNT while the thing that ruins a lane is DENSITY. Twelve
        // events spread over fifteen minutes read perfectly; twelve inside one
        // burst overprint into a smear, and both took the same branch: every
        // label drawn on top of its neighbours, or past twelve no labels at
        // all and a row of anonymous squares saying only "something happened".
        // Only what the view covers, plus a margin so a cluster straddling an
        // edge still merges with the neighbours that pushed it there instead
        // of splitting into a different shape at the boundary.
        const margin = (scale.dmax - scale.dmin) * 0.05;
        const visible = lane.points.filter(
          (p) => p.secs >= scale.dmin - margin && p.secs <= scale.dmax + margin
        );
        const clusters = clusterPoints(visible, X);
        const candidates = [];
        let prevBase = null;

        clusters.forEach((c) => {
          // The margin above exists so a cluster straddling an edge merges the
          // same way it would mid-view. Its marks must still not be DRAWN
          // outside the plot, or they land on top of the lane labels.
          if (c.xEnd < PAD_L - MARK_W || c.xStart > VW - PAD_R + MARK_W) return;
          const head = clusterHead(c);
          const n = c.items.length;
          const base = stripLanePrefix(head.point.label, lane.label);
          // `xN` only when every member really is that event: a burst of five
          // Adjusted plus one Resumed is not six resumes, so a mixed cluster
          // names the one it is titled after and counts the rest as `+N`.
          const text = n === 1 ? base : base + (head.uniform ? ` ×${n}` : ` +${n - 1}`);
          // A lane that is overwhelmingly one event type repeats that label
          // forever and says nothing after the first. Only a real burst, or
          // anything above routine tier, re-earns it.
          const repeat = head.tier === 0 && n < 3 && base === prevBase;
          if (head.tier === 0) prevBase = base;

          let markEl;
          if (n > 1) {
            // The floor is whatever fits the count digit. A badge too narrow
            // to carry its own number is worse than a plain mark: it is
            // visibly a merged thing that will not say how much it merged.
            const w = Math.max(CLUSTER_MIN_W, c.xEnd - c.xStart + MARK_W + 2);
            markEl = svg("rect", {
              x: c.xStart - MARK_W / 2 - 1,
              y: y - 6,
              width: w,
              height: 12,
              rx: 6,
              class: `cs-mark cs-mark--cluster cs-tier--${head.tier}`,
            });
            g.appendChild(markEl);
            timed.push({ el: markEl, t: c.items[0].secs });
            // Unreachable given CLUSTER_MIN_W, kept so a future change to the
            // floor degrades to a bare badge rather than clipped digits.
            if (w >= CLUSTER_MIN_W) {
              const ct = svg("text", {
                x: c.xStart - MARK_W / 2 - 1 + w / 2,
                y: y + 3.2,
                class: "cs-cluster-count",
                "text-anchor": "middle",
              });
              ct.textContent = String(n);
              g.appendChild(ct);
              timed.push({ el: ct, t: c.items[0].secs });
            }
          } else {
            markEl = svg("rect", {
              x: c.xStart - MARK_W / 2,
              y: y - MARK_W / 2,
              width: MARK_W,
              height: MARK_W,
              class: `cs-mark cs-mark--setpoint cs-tier--${head.tier}`,
            });
            g.appendChild(markEl);
            timed.push({ el: markEl, t: c.items[0].secs });
          }

          // A count is only honest if its contents are recoverable. The folded
          // readout answers at the cursor; this answers on hover, and is the
          // only route for a viewer who never moves the cursor at all.
          const title = svg("title");
          title.textContent = c.items
            .map((p) => `${p.label} @ ${fmtClock(model.t0, p.secs)}`)
            .join("\n");
          markEl.appendChild(title);
          // A press on a mark selects it rather than starting a pan, so the
          // whole chart is not one big drag surface. The hit area is wider
          // than the mark because an 8-unit square is a hard pointer target.
          markEl.classList.add("cs-mark--hit");
          markEl._csCluster = c;
          const hit = svg("rect", {
            x: c.xStart - MARK_W,
            y: y - 11,
            width: Math.max(MARK_W * 2, c.xEnd - c.xStart + MARK_W * 2),
            height: 22,
            class: "cs-hit",
          });
          hit._csCluster = c;
          g.appendChild(hit);
          selectable.push({ el: markEl, point: c.items[0] });

          candidates.push({
            cx: (c.xStart + c.xEnd) / 2,
            tier: head.tier,
            text,
            skip: repeat,
            w: text.length * LABEL_CH + 4,
            t: c.items[0].secs,
          });
        });

        seatLabels(candidates).forEach((slot) => {
          const lab = svg("text", {
            x: (slot.l + slot.r) / 2,
            y: y - 11,
            class: `cs-life-label cs-tier--${slot.c.tier}`,
            "text-anchor": "middle",
          });
          lab.textContent = slot.c.text;
          g.appendChild(lab);
          timed.push({ el: lab, t: slot.c.t });
        });
      } else {
        const numeric = lane.points.filter((p) => p.value !== null && p.value !== undefined);
        if (numeric.length > 1) {
          const values = numeric.map((p) => p.value);
          const vmin = Math.min(...values);
          const vmax = Math.max(...values);
          const span = vmax - vmin || 1;
          const yFor = (v) => y + 14 - ((v - vmin) / span) * 24;
          const points = numeric.map((p) => `${X(p.secs)},${yFor(p.value)}`).join(" ");
          g.appendChild(svg("polyline", { points, class: "cs-run-line" }));
        }
        lane.points.forEach((p) => {
          const x = X(p.secs);
          const mark =
            p.text != null
              ? svg("circle", { cx: x, cy: y, r: 3.5, class: "cs-mark cs-mark--check" })
              : svg("circle", { cx: x, cy: y, r: 2.5, class: "cs-mark cs-mark--acquire" });
          g.appendChild(mark);
          timed.push({ el: mark, t: p.secs });
        });
      }
    }

    g.appendChild(svg("line", { x1: PAD_L, y1: axisY, x2: VW - PAD_R, y2: axisY, class: "cs-axis" }));
    // Wall clock, not `0s..900s`. In a flowing window `t0` slides on every
    // re-render, so a relative label renames the same physical event every
    // time and the eye has nothing fixed to measure motion against. Ticks
    // span the VIEW, so they stay put under the pointer while panning.
    const tickStep = pickTickStep(scale.dmax - scale.dmin);
    const firstTick = Math.ceil((model.t0 + scale.dmin) / tickStep) * tickStep - model.t0;
    for (let secs = firstTick; secs <= scale.dmax; secs += tickStep) {
      const x = X(secs);
      g.appendChild(svg("line", { x1: x, y1: axisY, x2: x, y2: axisY + 5, class: "cs-tick" }));
      const lab = svg("text", { x, y: axisY + 17, class: "cs-tick-label", "text-anchor": "middle" });
      lab.textContent = fmtClock(model.t0, secs).slice(0, tickStep < 60 ? 8 : 5);
      g.appendChild(lab);
    }

    // Only a flowing window has a live edge, and only when the view actually
    // reaches it: panned into the past, the right edge of the plot is just
    // wherever you stopped, and labelling that LIVE would be a lie.
    if (model.live && model.xmax <= scale.dmax + 1e-6) {
      const liveX = X(model.xmax);
      g.appendChild(
        svg("line", { x1: liveX, y1: LANE_START - 18, x2: liveX, y2: axisY, class: "cs-live" })
      );
      const liveLab = svg("text", {
        x: liveX - 4,
        y: LANE_START - 22,
        class: "cs-live-label",
        "text-anchor": "end",
      });
      liveLab.textContent = `LIVE ${fmtClock(model.t0, model.xmax).slice(0, 5)}`;
      g.appendChild(liveLab);
    }

    const cursorLine = svg("line", {
      x1: X(0),
      y1: LANE_START - 14,
      x2: X(0),
      y2: axisY,
      class: "cs-cursor",
    });
    g.appendChild(cursorLine);
    const handle = svg("polygon", { points: "0,-9 7,0 0,9 -7,0", class: "cs-cursor-handle" });
    handle.setAttribute("transform", `translate(${X(0)} ${axisY})`);
    g.appendChild(handle);

    return { g, X, axisY, timed, cursorLine, handle, selectable };
  }

  function applyFold(model, scene, cursor) {
    const X = scene.X;
    scene.cursorLine.setAttribute("x1", X(cursor));
    scene.cursorLine.setAttribute("x2", X(cursor));
    scene.handle.setAttribute("transform", `translate(${X(cursor)} ${scene.axisY})`);
    for (const { el, t } of scene.timed) {
      el.classList.toggle("cs-future", t > cursor + 1e-6);
    }
  }

  function renderReadout(root, model, folded, t0, cursor) {
    const r = root.querySelector(".cs-readout-body");
    r.innerHTML = "";
    const rows = [["clock", fmtClock(t0, cursor), null]];
    if (folded.primary) {
      const state = folded.primary.state || "not started";
      // A point-supplied `tone` (e.g. an enclosure's NotPermitted) wins;
      // absent one, the only vocabulary this module itself knows is the
      // Run lifecycle's "paused" -> warn convention.
      const tone = folded.primary.tone || (state === "paused" ? "warn" : "good");
      rows.push(["status", state, tone]);
      rows.push([
        "last event",
        folded.primary.point ? `${folded.primary.point.label} @ ${fmtClock(t0, folded.primary.point.secs)}` : "none yet",
        null,
      ]);
    }
    for (const lane of model.lanes) {
      if (lane === model.primaryLane) continue;
      const reading = folded.readings[lane.lane_id];
      let text;
      if (!reading) {
        text = "no reading yet";
      } else if (lane.render === "markers") {
        // A non-primary markers lane (every domain lane in a flowing
        // window with no single subject, see mount()'s `follow` option):
        // there is no value to show, only the most recent event's label.
        text = `${reading.label} @ ${fmtClock(t0, reading.secs)}`;
      } else {
        text = `${reading.text != null ? reading.text : reading.value} @ ${fmtClock(t0, reading.secs)}`;
      }
      rows.push([lane.label, text, null]);
    }
    for (const [k, v, tone] of rows) {
      const row = document.createElement("div");
      row.className = "cs-row";
      const key = document.createElement("span");
      key.className = "cs-row-key";
      key.textContent = k;
      const val = document.createElement("span");
      val.className = "cs-row-val" + (tone ? ` cs-tone--${tone}` : "");
      val.textContent = v;
      row.append(key, val);
      r.appendChild(row);
    }
  }

  function wireDrag(root, model, scene, state, opts) {
    const svgEl = scene.g;
    const onScrub = opts && opts.onScrub;
    // Fired once per user-initiated move, never from a programmatic
    // setCursor (mount()'s own initial positioning, or a caller re-
    // rendering a still-followed live window): this is how a flowing-mode
    // caller learns "pause following, the viewer grabbed the cursor"
    // without this module knowing anything about what "following" means.
    const notifyScrub = () => {
      if (onScrub) onScrub();
    };

    const secsFromEvent = (clientX) => {
      const rect = svgEl.getBoundingClientRect();
      const xUser = ((clientX - rect.left) / rect.width) * VW;
      return (xUser - PAD_L) / state.scale.k + state.scale.dmin;
    };

    const setCursor = (secs) => {
      state.cursor = Math.max(0, Math.min(model.xmax, secs));
      applyFold(model, scene, state.cursor);
      const folded = foldTo(model, state.cursor);
      renderReadout(root, model, folded, model.t0, state.cursor);
      svgEl.setAttribute("aria-valuenow", String(Math.round(state.cursor)));
      svgEl.setAttribute("aria-valuetext", fmtClock(model.t0, state.cursor));
    };
    state.setCursor = setCursor;

    const stopPlay = () => {
      state.playing = false;
      if (state.rafId) cancelAnimationFrame(state.rafId);
      state.rafId = 0;
      const btn = root.querySelector(".cs-play");
      if (btn) {
        btn.setAttribute("aria-pressed", "false");
        btn.textContent = "Play";
      }
    };
    state.stopPlay = stopPlay;

    const startPlay = () => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) {
        setCursor(model.xmax);
        return;
      }
      state.playing = true;
      const btn = root.querySelector(".cs-play");
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "Pause";
      if (state.cursor >= model.xmax) setCursor(0);
      let prev = null;
      const step = (ts) => {
        if (!state.playing) return;
        if (prev === null) prev = ts;
        const dt = (ts - prev) / 1000;
        prev = ts;
        setCursor(state.cursor + dt * Math.max(1, model.xmax / 12));
        if (state.cursor >= model.xmax) {
          stopPlay();
          return;
        }
        state.rafId = requestAnimationFrame(step);
      };
      state.rafId = requestAnimationFrame(step);
    };
    state.startPlay = startPlay;

    // ---- Three gestures, no overlap.
    //
    // Press on a MARK selects it. Press on EMPTY CHART pans the view. Hover
    // moves the fold cursor. Previously a press anywhere started a scrub,
    // which meant a mark could never receive one, so nothing on the chart was
    // clickable and the only way to read a cluster's contents was the native
    // tooltip. Selection is the prerequisite for pinning a causal chain.
    const CLICK_SLOP = 4;

    const setSelection = (cluster) => {
      state.selected = cluster || null;
      const ids = new Set();
      if (cluster) for (const p of cluster.items) ids.add(p);
      for (const { el, point } of scene.selectable) {
        el.classList.toggle("cs-selected", !!point && ids.has(point));
      }
      if (opts && opts.onSelect) opts.onSelect(cluster);
      // A selected cluster fixes the readout at its own instant, so what the
      // panel says and what is highlighted cannot disagree.
      if (cluster) setCursor(cluster.items[0].secs);
    };
    state.setSelection = setSelection;

    const clusterFor = (target) => {
      let node = target;
      while (node && node !== svgEl) {
        if (node._csCluster) return node._csCluster;
        node = node.parentNode;
      }
      return null;
    };

    let pan = null;
    const onDown = (e) => {
      const cluster = clusterFor(e.target);
      if (cluster) {
        e.preventDefault();
        stopPlay();
        notifyScrub();
        setSelection(cluster);
        return;
      }
      if (!state.canPan) return;
      e.preventDefault();
      svgEl.focus();
      stopPlay();
      // Panning is leaving the live edge, so the caller has to stop following.
      // Without this the next re-slide snaps the view forward again and the
      // drag fights the clock.
      notifyScrub();
      pan = { x0: e.clientX, from0: state.view.from, moved: false };
      svgEl.classList.add("cs-grabbing");
      const onMove = (ev) => {
        if (!pan) return;
        if (Math.abs(ev.clientX - pan.x0) > CLICK_SLOP) pan.moved = true;
        const rect = svgEl.getBoundingClientRect();
        const perPx = (state.view.to - state.view.from) / ((rect.width * (VW - PAD_L - PAD_R)) / VW);
        state.panTo(pan.from0 - (ev.clientX - pan.x0) * perPx);
      };
      const onUp = () => {
        // A press that never moved is a click on empty space: clear any pinned
        // selection rather than leaving it stranded with nothing highlighted.
        if (pan && !pan.moved) setSelection(null);
        pan = null;
        svgEl.classList.remove("cs-grabbing");
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
    svgEl.addEventListener("pointerdown", onDown);

    // Hover drives the fold cursor. It needs no press, so it never competes
    // with pan or select, and a viewer reads the folded state just by moving
    // across the chart. A pinned selection wins: the cursor stays put.
    svgEl.addEventListener("pointermove", (e) => {
      if (pan || state.selected) return;
      setCursor(secsFromEvent(e.clientX));
    });

    // Keyboard parity. The slider used to be the only focusable control and
    // the only keyboard route; the chart itself now carries both, so removing
    // the slider does not remove keyboard access.
    svgEl.addEventListener("keydown", (e) => {
      const span = state.view.to - state.view.from;
      if (e.key === " " || e.key === "Spacebar") {
        if (opts && opts.showPlay === false) return;
        e.preventDefault();
        state.playing ? stopPlay() : startPlay();
        return;
      }
      // Arrows move the VALUE, because the element carries slider semantics
      // and announces the cursor's clock time; panning the viewport is a
      // different act and takes Shift or the Page keys. `,` and `.` walk real
      // events, which is the only way to reach a mark without hunting.
      if (e.key === "," || e.key === ".") {
        e.preventDefault();
        const step = stepToAdjacentPoint(model, state.cursor, e.key === "." ? 1 : -1);
        if (step !== null) {
          notifyScrub();
          setSelection(null);
          setCursor(step);
          state.revealCursor();
        }
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const near = nearestCluster(scene, state.cursor);
        if (near) setSelection(near);
        return;
      }
      if (e.key === "Escape") {
        if (!state.selected) return;
        e.preventDefault();
        setSelection(null);
        return;
      }
      const panBy = { PageDown: -span, PageUp: span };
      if (e.shiftKey && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
        e.preventDefault();
        if (!state.canPan) return;
        notifyScrub();
        state.panTo(state.view.from + (e.key === "ArrowRight" ? span / 4 : -span / 4));
        return;
      }
      if (e.key in panBy) {
        e.preventDefault();
        if (!state.canPan) return;
        notifyScrub();
        state.panTo(state.view.from + panBy[e.key]);
        return;
      }
      const nudge = { ArrowLeft: -1, ArrowRight: 1, ArrowDown: -1, ArrowUp: 1 };
      if (e.key === "Home" || e.key === "End") {
        e.preventDefault();
        notifyScrub();
        setSelection(null);
        setCursor(e.key === "Home" ? 0 : model.xmax);
        state.revealCursor();
        return;
      }
      if (!(e.key in nudge)) return;
      e.preventDefault();
      stopPlay();
      notifyScrub();
      setSelection(null);
      setCursor(state.cursor + nudge[e.key] * ((state.view.to - state.view.from) / 100));
      state.revealCursor();
    });

    return { setCursor, stopPlay, startPlay, setSelection };
  }

  // The rendered cluster closest to the cursor, so Enter can pin what the
  // readout is already describing without a pointer.
  function nearestCluster(scene, cursor) {
    let best = null;
    let bestGap = Infinity;
    for (const { el } of scene.selectable) {
      const c = el._csCluster;
      if (!c) continue;
      const gap = Math.abs(c.items[0].secs - cursor);
      if (gap < bestGap) {
        bestGap = gap;
        best = c;
      }
    }
    return best;
  }

  // Nearest point in any lane strictly before or after `from`, so `,` and `.`
  // walk real events rather than arbitrary time steps.
  function stepToAdjacentPoint(model, from, dir) {
    let best = null;
    for (const lane of model.lanes) {
      for (const p of lane.points) {
        if (dir > 0 ? p.secs > from + 1e-6 : p.secs < from - 1e-6) {
          if (best === null || (dir > 0 ? p.secs < best : p.secs > best)) best = p.secs;
        }
      }
    }
    return best;
  }

  function scaffold(root, model, opts) {
    const note =
      model.omittedSeries > 0
        ? `<div class="cs-omitted-note">+${model.omittedSeries} more lane(s) not shown</div>`
        : "";
    // Play (a synthetic-rate replay) and "jump to last event" both assume
    // a closed, already-finished timeline; neither means anything for an
    // open-ended flowing window, so a caller opts out of both rather than
    // this module guessing from the document shape. `jumpLabel` still
    // lets a caller keep the button under a different label, but flowing
    // mode's caller (page.html) opts out entirely and owns its own
    // "Resume following" control instead.
    const showPlay = opts.showPlay !== false;
    const showJumpLast = opts.showJumpLast !== false;
    const controlsHtml =
      (showPlay ? '<button type="button" class="cs-btn cs-play" aria-pressed="false">Play</button>' : "") +
      (showJumpLast
        ? `<button type="button" class="cs-btn cs-jump-last">${opts.jumpLabel || "Jump to last event"}</button>`
        : "");
    root.classList.add("cora-scrubber");
    root.innerHTML = `
      <div class="cora-scrubber__chrome">
        <div class="cs-titlebar">
          <span class="cs-dot" aria-hidden="true"></span>
          <span class="cs-title"></span>
          <span class="cs-subtitle"></span>
          <div class="cs-controls">${controlsHtml}</div>
        </div>
        <div class="cs-stage"></div>
        <div class="cs-hint">
          Drag to pan &middot; click an event to pin it &middot; hover to fold &middot;
          <kbd>&larr;</kbd><kbd>&rarr;</kbd> cursor,
          <kbd>shift</kbd> to pan, <kbd>,</kbd><kbd>.</kbd> step events,
          <kbd>enter</kbd> pin
        </div>
        ${note}
        <div class="cs-panels">
          <div class="cs-readout">
            <div class="cs-readout-head">Folded state at cursor</div>
            <div class="cs-readout-body"></div>
          </div>
        </div>
      </div>`;
    // Title and subtitle are set via textContent, never interpolated into
    // the innerHTML template above: `opts.title`/`opts.subtitle` can carry
    // caller-controlled strings sourced from network JSON (a run's own
    // name, for example), so this is the one place on the page an
    // injection would otherwise land.
    root.querySelector(".cs-title").textContent = opts.chromeTitle;
    root.querySelector(".cs-subtitle").textContent = opts.subtitle;
  }

  function mount(root, doc, opts) {
    if (root._coraScrubberCleanup) root._coraScrubberCleanup();
    opts = opts || {};

    const model = buildModel(doc);
    // `opts.viewSpanSecs` narrower than the domain turns the chart into a
    // window that pans. Absent, the view is the whole domain and panning is a
    // no-op, which is REWIND's behaviour unchanged.
    const domainMax = model.xmax > 0 ? model.xmax : 1;
    const span = opts.viewSpanSecs && opts.viewSpanSecs > 0 ? opts.viewSpanSecs : domainMax;
    const initialFrom = opts.follow ? domainMax - span : 0;
    let view = clampView(initialFrom, span, domainMax);
    const scale = buildScale(view.from, view.to);
    // Generic over WHAT truncated (`observations` for a run, `events` for
    // an enclosure, ...): report every truthy key by name rather than
    // hardcoding one domain's vocabulary.
    const truncatedKeys = doc.truncated
      ? Object.keys(doc.truncated).filter((k) => doc.truncated[k])
      : [];
    const subtitle =
      (doc.title || "") +
      (doc.title && doc.subtitle ? " · " : "") +
      (doc.subtitle || "") +
      (truncatedKeys.length ? ` · ${truncatedKeys.join(", ")} truncated` : "");
    scaffold(root, model, {
      chromeTitle: opts.chromeTitle || "Timeline",
      subtitle,
      showPlay: opts.showPlay,
      showJumpLast: opts.showJumpLast,
      jumpLabel: opts.jumpLabel,
    });
    const stage = root.querySelector(".cs-stage");
    let scene = renderTimeline(model, scale);
    stage.appendChild(scene.g);

    const state = {
      scale,
      view,
      cursor: 0,
      playing: false,
      rafId: 0,
      selected: null,
      canPan: span < domainMax - 1e-6,
    };

    // Panning changes which events are visible, so the clusters and the axis
    // both have to be rebuilt: a plain transform would slide stale tick labels
    // along with the marks. Coalesced onto a frame so a drag rebuilds once per
    // paint rather than once per pointermove.
    let panFrame = 0;
    state.panTo = (from) => {
      const next = clampView(from, span, domainMax);
      if (Math.abs(next.from - state.view.from) < 1e-9) return;
      state.view = next;
      if (panFrame) return;
      panFrame = requestAnimationFrame(() => {
        panFrame = 0;
        rerender();
      });
    };
    // Bring the cursor back into view after a keyboard step walked it past an
    // edge, so `,` and `.` can cross the whole domain without a manual pan.
    state.revealCursor = () => {
      if (!state.canPan) return;
      const margin = (state.view.to - state.view.from) * 0.1;
      if (state.cursor < state.view.from + margin) state.panTo(state.cursor - margin);
      else if (state.cursor > state.view.to - margin) {
        state.panTo(state.cursor - (state.view.to - state.view.from) + margin);
      }
    };

    let controls;
    function rerender() {
      const wasSelected = state.selected;
      state.scale = buildScale(state.view.from, state.view.to);
      const next = renderTimeline(model, state.scale);
      stage.replaceChildren(next.g);
      scene = next;
      controls = wireDrag(root, model, scene, state, opts);
      // A selection survives a pan: re-resolve it against the freshly built
      // clusters by first point, since the cluster objects are new each render.
      if (wasSelected) {
        const head = wasSelected.items[0];
        const match = scene.selectable.find((s) => s.point === head);
        state.selected = match ? wasSelected : null;
        if (match) match.el.classList.add("cs-selected");
      }
      controls.setCursor(state.cursor);
    }

    controls = wireDrag(root, model, scene, state, opts);

    const playBtn = root.querySelector(".cs-play");
    if (playBtn) {
      playBtn.addEventListener("click", () => {
        state.playing ? controls.stopPlay() : controls.startPlay();
      });
    }
    const jumpBtn = root.querySelector(".cs-jump-last");
    if (jumpBtn) {
      jumpBtn.addEventListener("click", () => {
        controls.stopPlay();
        controls.setCursor(model.xmax);
      });
    }

    // `opts.follow`: pin the cursor to the live edge (this is a flowing
    // window, not a fixed replay with a natural "start"); otherwise the
    // existing REWIND behavior of starting at the beginning is unchanged.
    controls.setCursor(opts.follow ? model.xmax : 0);

    root._coraScrubberCleanup = () => {
      controls.stopPlay();
    };
  }

  window.CoraScrubber = { mount };
})();
