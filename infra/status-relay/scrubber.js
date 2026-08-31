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
  // One event is one square. A group is those squares PACKED side by side, so
  // a burst adds up into a bar whose length is how many happened rather than a
  // badge carrying a number, and every member stays its own shape with its own
  // severity colour and its own hit target. That is what makes an individual
  // event inside a burst pickable at all: there is no merged mark to drill
  // into, only neighbours that stopped overlapping.
  const MARK_S = 9;
  const MARK_GAP = 2;
  const MARK_STEP = MARK_S + MARK_GAP;
  // Past this many, packing would run a single burst across a third of the
  // plot and shove its neighbours out of true. Beyond it the group draws as
  // one bar of that width and takes a count back, which is the one case a
  // number is worth more than the shape.
  const PACK_MAX = 8;
  const MARK_H = MARK_S;
  // Two marks closer than this many user units cannot be drawn apart. Derived
  // from the mark, not chosen: at exactly MARK_H two circles touch, so the
  // extra 2 is the surface gap that keeps neighbours legible as two. At a
  // 15-minute window over the 812-unit plot one unit is about 1.1s, so this
  // lands near 15s -- but it is deliberately a WIDTH, not a duration. What can
  // be separated is a property of the canvas, and a duration constant would
  // silently lie at every other window size.
  const COLLAPSE_GAP = MARK_STEP;
  const LABEL_CH = 5.6;
  const LABEL_PAD = 5;
  const LANE_LABEL_CH = 6.2;
  // Extra time rendered either side of the view, as a multiple of its span.
  // A drag TRANSLATES the rendered content instead of rebuilding it, and this
  // buffer is what gives the translation something to reveal. Rebuilding per
  // frame was the whole reason panning felt stepped: every move reclustered,
  // reseated labels and refolded the readout, so marks and text jumped
  // between two valid layouts many times a second.
  const OVERSCAN = 1;

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
  // `bmin`/`bmax` bound what is RENDERED; `dmin`/`dmax` bound what is VISIBLE.
  // The buffer is clamped to the domain, so a view that already covers the
  // whole domain (REWIND) renders exactly the domain and nothing more.
  function buildScale(from, to, domainMax) {
    const dmin = from;
    const dmax = to > from ? to : from + 1;
    const k = (VW - PAD_L - PAD_R) / (dmax - dmin);
    const pad = (dmax - dmin) * OVERSCAN;
    const cap = Math.max(dmax, domainMax || 0);
    return { dmin, dmax, k, bmin: Math.max(0, dmin - pad), bmax: Math.min(cap, dmax + pad) };
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
          // Relationships, all optional. A document that carries none renders
          // exactly as it did before they existed.
          id: p.id || null,
          corr: p.corr || null,
          cause: p.cause || null,
          cause_at: p.cause_at || null,
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

    // Indexed once per mount, not per selection: a hover that traced the chain
    // by scanning every lane would do it at pointer rate.
    const byId = new Map();
    const childrenOf = new Map();
    let hasCausation = false;
    for (const lane of lanes) {
      for (const p of lane.points) {
        if (p.id) byId.set(p.id, p);
        if (p.id || p.cause) hasCausation = true;
      }
    }
    for (const lane of lanes) {
      for (const p of lane.points) {
        if (!p.cause) continue;
        const kids = childrenOf.get(p.cause);
        if (kids) kids.push(p);
        else childrenOf.set(p.cause, [p]);
      }
    }

    return {
      t0,
      xmax,
      lanes,
      primaryLane,
      omittedSeries,
      // A FLOWING window and a CLOSED history want opposite things at the
      // right edge, and the document already knows which it is. Live: a rule
      // marking the present, and no roaming cursor -- there is no "state at a
      // time you point at" to read, only what is current. Closed: a fold
      // cursor the viewer drives, and no live rule, because nothing about that
      // document is live. Deriving it here rather than from a caller option
      // means every mount agrees, including the dev harness, which had been
      // getting the roaming cursor because it never passed the flag.
      live: !!doc.live,
      byId,
      childrenOf,
      // Whether this document carries causation AT ALL. A REWIND run history
      // has none, so every point there looks causeless -- and calling that "an
      // operator acted directly" would state a fact the document never
      // supplied. Absent data must not read as a positive finding.
      hasCausation,
    };
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
  // `separate` holds points that must not be merged into a neighbour: the
  // members of a traced chain. An arrow pointing at a badge would claim it
  // caused the whole badge when it caused one event inside it, so a focused
  // chain un-collapses and every edge lands on a real event. Everything not in
  // the chain stays merged, so focusing does not explode the whole chart.
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

  // How wide a group draws once its members are packed, and where it starts.
  // Centred on the time the group occupies, so the bar sits over its events
  // rather than growing off one end of them.
  function packWidth(count) {
    return Math.min(count, PACK_MAX) * MARK_STEP - MARK_GAP;
  }
  function packStart(cluster) {
    return (cluster.xStart + cluster.xEnd) / 2 - packWidth(cluster.items.length) / 2;
  }

  // Packing makes a group WIDER than the span that formed it, so two groups
  // that did not overlap as points can overlap as bars. Merge until they do
  // not: without this the packed bars collide and the thing this whole
  // rendering exists to prevent comes back in a new shape.
  function packClusters(points, X) {
    let groups = clusterPoints(points, X);
    for (let pass = 0; pass < 8; pass++) {
      const merged = [];
      let changed = false;
      for (const g of groups) {
        const prev = merged[merged.length - 1];
        if (prev && packStart(prev) + packWidth(prev.items.length) + MARK_GAP > packStart(g)) {
          prev.items = prev.items.concat(g.items);
          prev.xEnd = g.xEnd;
          changed = true;
        } else {
          merged.push({ xStart: g.xStart, xEnd: g.xEnd, items: g.items.slice() });
        }
      }
      groups = merged;
      if (!changed) break;
    }
    return groups;
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
  //
  // Candidates now span the whole rendered buffer, most of it off screen. Only
  // a label whose mark is IN VIEW gets nudged off the canvas edge: doing it to
  // the rest would stack the buffer's labels into a pile just outside the
  // plot, which the next pan would slide into view as a solid block of text.
  function seatLabels(candidates) {
    const order = candidates.slice().sort((a, b) => b.tier - a.tier || a.cx - b.cx);
    const placed = [];
    for (const c of order) {
      if (c.skip) continue;
      let l = c.cx - c.w / 2;
      let r = c.cx + c.w / 2;
      if (c.cx >= PAD_L && c.cx <= VW - PAD_R) {
        if (l < PAD_L) {
          l = PAD_L;
          r = l + c.w;
        }
        if (r > VW - PAD_R) {
          r = VW - PAD_R;
          l = r - c.w;
        }
      }
      if (placed.some((q) => !(r <= q.l - LABEL_PAD || l >= q.r + LABEL_PAD))) continue;
      placed.push({ l, r, c });
    }
    return placed;
  }

  function renderChainEdges(g, model, focus, pointPos, scale) {
    const layer = svg("g", { class: "cs-edges" });

    // One marker per direction. Causation is a strict parent pointer in an
    // append-only log, so the head always sits at the EFFECT and the arrow is
    // always single: a double head would assert mutual causation, which cannot
    // happen. Upstream and downstream answer different questions ("why did
    // this happen" against "what did it set off") and differ in hue, never in
    // direction.
    const defs = svg("defs");
    for (const [id, fill] of [["cs-arrow-up", "#f0644b"], ["cs-arrow-down", "#e6b24a"]]) {
      const marker = svg("marker", {
        id,
        viewBox: "0 0 8 8",
        refX: "6.5",
        refY: "4",
        markerWidth: "4.5",
        markerHeight: "4.5",
        orient: "auto",
      });
      marker.appendChild(svg("path", { d: "M0,4 L0,4 M0,0 L8,4 L0,8 z", fill }));
      defs.appendChild(marker);
    }
    layer.appendChild(defs);

    const edges = [];
    for (const [point, hop] of focus.dist) {
      if (!point.cause) continue;
      const parent = model.byId.get(point.cause);
      if (!parent || !focus.dist.has(parent)) continue;
      edges.push({ from: parent, to: point, up: hop <= 0 });
    }
    fanEdges(edges, (p) => pointPos.get(p));

    for (const e of edges) {
      const a = pointPos.get(e.from);
      const b = pointPos.get(e.to);
      if (!a || !b) continue;
      const hop = Math.abs(focus.dist.get(e.to));
      const path = svg("path", {
        d: edgePath(a, b, e.fan || 0),
        class: `cs-edge cs-edge--${e.up ? "up" : "down"}`,
        "marker-end": `url(#cs-arrow-${e.up ? "up" : "down"})`,
      });
      // Thickness carries distance: the immediate cause is heaviest and each
      // further hop thinner, so the near story reads before the far one.
      path.style.strokeWidth = String(Math.max(0.7, 2.1 - 0.42 * Math.max(0, hop - 1)));
      layer.appendChild(path);
    }

    // A null causation_id means an operator acted directly. Ring it, so a root
    // never reads as an orphan the trace merely failed to reach. Only where the
    // document actually carries causation: in one that does not, everything is
    // causeless and every mark would be ringed as an operator action.
    if (model.hasCausation) {
      for (const point of focus.dist.keys()) {
        if (point.cause) continue;
        const pt = pointPos.get(point);
        if (pt) {
          layer.appendChild(svg("circle", { cx: pt.x, cy: pt.y, r: 6.5, class: "cs-root-ring" }));
        }
      }
    }

    // The cause fell out of the retained window. Drawing nothing would claim
    // the event was uncaused; the stub says a cause exists and when it was,
    // which is why `cause_occurred_at` rides the wire beside the id.
    if (focus.unresolved) {
      const pt = pointPos.get(focus.unresolved);
      if (pt) {
        // Anchored to the MARK, not to the plot's left edge. The edge layer
        // is clipped to the plot now, so a stub pinned to that edge would be
        // sliced in half the moment the view panned; hung off the mark it
        // runs out toward the past and is clipped there, which is where its
        // cause actually is. The readout carries the same timestamp in words,
        // so nothing is lost when the note itself scrolls out.
        layer.appendChild(
          svg("path", {
            d: `M${pt.x - 46},${pt.y} L${pt.x - 7},${pt.y}`,
            class: "cs-edge cs-edge--up cs-edge--stub",
            "marker-end": "url(#cs-arrow-up)",
          })
        );
        const note = svg("text", {
          x: pt.x - 48,
          y: pt.y - 6,
          class: "cs-edge-note",
          "text-anchor": "end",
        });
        note.textContent = focus.unresolved.cause_at
          ? fmtClock(model.t0, parseT(focus.unresolved.cause_at) - model.t0)
          : "before this window";
        layer.appendChild(note);
      }
    }

    g.appendChild(layer);
  }

  // Clip paths are referenced by id, and two scrubbers can be mounted on one
  // page (the flowing window and REWIND), so the id has to be unique per
  // render or the second mount clips against the first one's rect.
  let clipSeq = 0;

  function renderTimeline(model, scale, focus) {
    const laneCount = Math.max(1, model.lanes.length);
    const axisY = LANE_START + laneCount * LANE_HEIGHT + 10;
    const vh = axisY + AXIS_MARGIN;
    const X = (secs) => xFor(scale, secs);

    // Focusable and slider-shaped: the value it announces is the fold cursor's
    // clock time, which `setCursor` keeps in `aria-valuetext`. This replaces
    // the separate slider element that used to be the only keyboard route.
    // Slider semantics only where there is a value to move. A live window has
    // no cursor to announce, so claiming a slider role would promise a control
    // that is not there.
    const g = svg("svg", {
      viewBox: `0 0 ${VW} ${vh}`,
      class: "cora-scrubber__svg",
      tabindex: "0",
      ...(model.live
        ? {
            role: "group",
            "aria-label":
              "Live activity timeline. Comma and period step between events, arrows pan, " +
              "Escape releases a pinned event.",
          }
        : {
            role: "slider",
            "aria-label":
              "Timeline. Arrows move the fold cursor, comma and period step between events, " +
              "shift with arrows pans, Enter pins the nearest event.",
            "aria-valuemin": "0",
            "aria-valuemax": String(Math.round(model.xmax)),
            "aria-valuenow": "0",
          }),
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

    // Everything positioned by TIME lives in one clipped group, so a pan can
    // be a single translate on it. The clip is what makes that safe: the group
    // holds a buffer wider than the view, and without it those extra marks
    // would draw straight over the lane labels.
    const seq = ++clipSeq;
    const defs = svg("defs");
    const clipRect = (id, box) => {
      const c = svg("clipPath", { id });
      c.appendChild(svg("rect", box));
      defs.appendChild(c);
      return `url(#${id})`;
    };
    const plotClip = clipRect(`cs-plot-${seq}`, {
      x: PAD_L,
      y: 0,
      width: VW - PAD_R - PAD_L,
      height: vh,
    });
    const axisClip = clipRect(`cs-axis-${seq}`, { x: 0, y: axisY, width: VW, height: vh - axisY });
    g.appendChild(defs);
    // The clip must sit OUTSIDE the transform. `clip-path` resolves in the
    // element's own user space, so a clip on the group that carries the
    // translate slides along with the content it is meant to be windowing:
    // the marks move, the window moves with them, and the same slice stays on
    // screen shifted sideways. Window first, then pan what is inside it.
    const plotWindow = svg("g", { "clip-path": plotClip });
    const axisWindow = svg("g", { "clip-path": axisClip });
    const plot = svg("g", { class: "cs-pan cs-plot" });
    const axisRow = svg("g", { class: "cs-pan cs-axis-row" });
    // Filled later, appended first: an arrow leaving a solid mark has to pass
    // BEHIND it, or its tail sits on top of the very thing it starts from.
    const edgeLayer = svg("g", { class: "cs-edge-layer" });
    plot.appendChild(edgeLayer);
    plotWindow.appendChild(plot);
    axisWindow.appendChild(axisRow);
    g.appendChild(plotWindow);
    g.appendChild(axisWindow);
    // One offset, applied to both strips: they are windowed differently but
    // they show the same instant, so they can never be panned apart.
    const setPan = (dx) => {
      const t = `translate(${dx} 0)`;
      plot.setAttribute("transform", t);
      axisRow.setAttribute("transform", t);
    };

    const timed = [];
    const selectable = [];
    const pointPos = new Map();
    const chain = focus ? focus.dist : null;

    for (const lane of model.lanes) {
      const y = laneY.get(lane.lane_id);
      if (lane.render === "markers") {
        // The gate here used to be `points.length <= MAX_MARKER_LABELS`, which
        // tests COUNT while the thing that ruins a lane is DENSITY. Twelve
        // events spread over fifteen minutes read perfectly; twelve inside one
        // burst overprint into a smear, and both took the same branch: every
        // label drawn on top of its neighbours, or past twelve no labels at
        // all and a row of anonymous squares saying only "something happened".
        // The whole buffer, not just the view: what a pan translates into
        // sight has to have been drawn already, and a cluster straddling the
        // view edge must merge the same way it would mid-view rather than
        // splitting into a different shape at the boundary.
        const visible = lane.points.filter((p) => p.secs >= scale.bmin && p.secs <= scale.bmax);
        const clusters = packClusters(visible, X);
        const candidates = [];
        let prevBase = null;

        clusters.forEach((c) => {
          const head = clusterHead(c);
          const n = c.items.length;
          const base = stripLanePrefix(head.point.label, lane.label);
          // `xN` only when every member really is that event: a burst of five
          // Adjusted plus one Resumed is not six resumes, so a mixed cluster
          // names the one it is titled after and counts the rest as `+N`.
          const text = n === 1 ? base : base + (head.uniform ? ` ×${n}` : ` +${n - 1}`);

          // Lit if it is in the traced chain, or shares the pinned event's
          // correlation. Correlation is a SET, not a sequence, so its members
          // are highlighted and never joined by a line: N-1 edges would assert
          // an order the record does not claim.
          const inChain = !!focus && c.items.some((p) => chain.has(p));
          const inCorr =
            !!focus && !!focus.corr && c.items.some((p) => p.corr === focus.corr);
          const dim = !!focus && !inChain && !inCorr;

          // A lane that is overwhelmingly one event type repeats that label
          // forever and says nothing after the first. Only a real burst, or
          // anything above routine tier, re-earns it -- and never a member of
          // the chain being traced, which would otherwise strip the label off
          // the very event the viewer just pinned.
          const repeat = !inChain && head.tier === 0 && n < 3 && base === prevBase;
          if (head.tier === 0) prevBase = base;

          // One event or six, the mark is the same pill at the same height: a
          // rounded rect whose corner radius is half its height, so a single
          // event is exactly a circle and a group is that circle stretched
          // over the span its members occupy. Width therefore means elapsed
          // time and nothing else, and the count inside says how many sit in
          // it. The floor is whatever fits two digits, because a badge too
          // narrow to carry its own number is worse than a plain mark: it is
          // visibly a merged thing that will not say how much it merged.
          //
          // The pair this replaces differed in shape AND height -- an 8-unit
          // square against a 12-unit rounded badge -- so a group read as a
          // different kind of thing rather than as more of the same thing.
          const x0 = packStart(c);
          const wide = n > PACK_MAX;
          // Under the cap, one square per event: the bar IS the events, so
          // each carries its own severity colour and its own hit target and
          // any one of them can be picked out of a burst. Over it, a single
          // bar takes the count back as a number, because a hundred squares
          // is a smear and a smear that cannot say how many is worse than a
          // number.
          const cells = wide ? [{ point: c.items[0], span: c.items }] : c.items.map((q) => ({ point: q }));
          cells.forEach((cell, i) => {
            const q = cell.point;
            const cw = wide ? packWidth(n) : MARK_S;
            const cx = wide ? x0 : x0 + i * MARK_STEP;
            const tier = wide ? head.tier : q.tier || 0;
            const markEl = svg("rect", {
              x: cx,
              y: y - MARK_S / 2,
              width: cw,
              height: MARK_S,
              rx: 1.5,
              class: `cs-mark cs-mark--${wide ? "many" : n > 1 ? "packed" : "single"} cs-tier--${tier}`,
            });
            const title = svg("title");
            title.textContent = wide
              ? c.items.map((z) => `${z.label} @ ${fmtClock(model.t0, z.secs)}`).join("\n")
              : `${q.label} @ ${fmtClock(model.t0, q.secs)}`;
            markEl.appendChild(title);
            markEl.classList.add("cs-mark--hit");
            plot.appendChild(markEl);
            timed.push({ el: markEl, t: q.secs });

            // One cluster object per CELL, so hovering or pinning resolves to
            // the one event under the pointer rather than to whatever the
            // group is named after. `group` keeps the neighbours reachable so
            // the card can still say which of how many this is.
            const cell_c = { xStart: cx, xEnd: cx + cw, items: [q], group: c.items, index: i };
            markEl._csCluster = cell_c;
            const hit = svg("rect", {
              x: cx - MARK_GAP,
              y: y - 11,
              width: cw + MARK_GAP * 2,
              height: 22,
              class: "cs-hit",
            });
            hit._csCluster = cell_c;
            plot.appendChild(hit);
            selectable.push({ el: markEl, point: q });
            if (focus && dim) markEl.classList.add("cs-dim");
          });

          if (wide) {
            const ct = svg("text", {
              x: x0 + packWidth(n) / 2,
              y: y + 3.2,
              class: "cs-cluster-count",
              "text-anchor": "middle",
            });
            ct.textContent = String(n);
            plot.appendChild(ct);
            timed.push({ el: ct, t: c.items[0].secs });
          }

          if (focus) {
            // Edges land on the SQUARE, not on the event's true x: the pack
            // moved it, and an arrow pointing at empty chart beside the mark
            // it means would be worse than one pointing slightly off-time.
            c.items.forEach((q, i) => {
              if (!chain.has(q)) return;
              const cx = wide ? x0 + packWidth(n) / 2 : x0 + i * MARK_STEP + MARK_S / 2;
              pointPos.set(q, { x: cx, y });
            });
          }

          candidates.push({
            // Over the BAR, not over the span that formed it. Packing widens
            // a group and shifts its centre, and a label anchored to the old
            // centre sits off its own mark -- and near the plot edge is left
            // unclamped and clipped, because the clamp only fires for a
            // centre that is itself on screen.
            cx: x0 + packWidth(n) / 2,
            tier: head.tier,
            text,
            skip: repeat,
            dim,
            w: text.length * LABEL_CH + 4,
            t: c.items[0].secs,
          });
        });

        seatLabels(candidates).forEach((slot) => {
          const lab = svg("text", {
            x: (slot.l + slot.r) / 2,
            y: y - 11,
            // A label must recede with its own mark. Dimming one and not the
            // other leaves the loudest thing on screen belonging to the part
            // that is not the story.
            class: `cs-life-label cs-tier--${slot.c.tier}${slot.c.dim ? " cs-dim" : ""}`,
            "text-anchor": "middle",
          });
          lab.textContent = slot.c.text;
          plot.appendChild(lab);
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
          plot.appendChild(svg("polyline", { points, class: "cs-run-line" }));
        }
        lane.points.forEach((p) => {
          const x = X(p.secs);
          const mark =
            p.text != null
              ? svg("circle", { cx: x, cy: y, r: 3.5, class: "cs-mark cs-mark--check" })
              : svg("circle", { cx: x, cy: y, r: 2.5, class: "cs-mark cs-mark--acquire" });
          plot.appendChild(mark);
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
    const firstTick = Math.ceil((model.t0 + scale.bmin) / tickStep) * tickStep - model.t0;
    for (let secs = firstTick; secs <= scale.bmax; secs += tickStep) {
      const x = X(secs);
      axisRow.appendChild(svg("line", { x1: x, y1: axisY, x2: x, y2: axisY + 5, class: "cs-tick" }));
      const lab = svg("text", { x, y: axisY + 17, class: "cs-tick-label", "text-anchor": "middle" });
      lab.textContent = fmtClock(model.t0, secs).slice(0, tickStep < 60 ? 8 : 5);
      axisRow.appendChild(lab);
    }

    if (focus) renderChainEdges(edgeLayer, model, focus, pointPos, scale);

    // Both mark an INSTANT, so both belong to the pannable group and travel
    // with the events they sit between. Only one is ever drawn.
    let cursorLine = null;
    let handle = null;
    if (model.live) {
      // The present. Drawn only when the view actually reaches it: panned into
      // the past the right edge is just wherever the viewer stopped, and
      // labelling that LIVE would be a lie, so the rule leaves rather than
      // following the edge.
      if (model.xmax >= scale.bmin && model.xmax <= scale.bmax) {
        const lx = X(model.xmax);
        plot.appendChild(
          svg("line", { x1: lx, y1: LANE_START - 18, x2: lx, y2: axisY, class: "cs-now" })
        );
        const lab = svg("text", {
          x: lx - 5,
          y: LANE_START - 22,
          class: "cs-now-label",
          "text-anchor": "end",
        });
        lab.textContent = "LIVE";
        plot.appendChild(lab);
      }
    } else {
      cursorLine = svg("line", {
        x1: X(0),
        y1: LANE_START - 14,
        x2: X(0),
        y2: axisY,
        class: "cs-cursor",
      });
      plot.appendChild(cursorLine);
      handle = svg("polygon", { points: "0,-9 7,0 0,9 -7,0", class: "cs-cursor-handle" });
      handle.setAttribute("transform", `translate(${X(0)} ${axisY})`);
      plot.appendChild(handle);
    }

    return { g, setPan, X, axisY, timed, cursorLine, handle, selectable };
  }

  function applyFold(model, scene, cursor) {
    const X = scene.X;
    if (scene.cursorLine) {
      scene.cursorLine.setAttribute("x1", X(cursor));
      scene.cursorLine.setAttribute("x2", X(cursor));
      scene.handle.setAttribute("transform", `translate(${X(cursor)} ${scene.axisY})`);
    }
    for (const { el, t } of scene.timed) {
      el.classList.toggle("cs-future", t > cursor + 1e-6);
    }
  }

  // The card that follows the pointer. Hovering an event is the whole
  // interaction now, so this has to answer on its own: what it is, when, what
  // caused it and what it set off. Where the pointer is over one square of a
  // packed burst the card names that square's own event and says which of how
  // many it is; where the burst was too big to pack and drew as one bar, it
  // lists the contents, because the number on that bar is a promise that they
  // are recoverable.
  function tipHtml(model, cluster, focus) {
    const esc = (v) =>
      String(v).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
    const row = (k, v, cls) =>
      `<div class="cs-tip-row${cls ? ` ${cls}` : ""}"><span class="cs-tip-k">${esc(k)}</span>` +
      `<span class="cs-tip-v">${esc(v)}</span></div>`;

    const head = focus.point;
    const group = cluster.group || cluster.items;
    const listed = cluster.items.length > 1 ? cluster.items : null;
    const out = [];
    out.push(`<div class="cs-tip-head">${esc(head.label)}</div>`);
    out.push(row("occurred", fmtClock(model.t0, head.secs)));
    if (listed) {
      out.push(row("in a burst of", `${listed.length}, too many to separate`));
      out.push(
        '<div class="cs-tip-list">' +
          listed
            .map(
              (p) =>
                `<div class="cs-tip-item${p === head ? " cs-tip-item--head" : ""}">` +
                `<span class="cs-tip-k">${esc(p.label)}</span>` +
                `<span class="cs-tip-v">${esc(fmtClock(model.t0, p.secs))}</span></div>`
            )
            .join("") +
          "</div>"
      );
    } else if (group.length > 1) {
      out.push(row("in a burst of", `${group.length}, this is #${(cluster.index || 0) + 1}`));
    }

    // Silent where the document records no relations at all, rather than
    // reporting their absence as an operator having acted directly.
    if (model.hasCausation) {
      let cause;
      if (!head.cause) {
        cause = "nothing, an operator acted directly";
      } else {
        const parent = model.byId.get(head.cause);
        cause = parent
          ? `${parent.label} @ ${fmtClock(model.t0, parent.secs)}`
          : head.cause_at
            ? `outside this window, @ ${fmtClock(model.t0, parseT(head.cause_at) - model.t0)}`
            : "outside this window";
      }
      out.push(row("caused by", cause, head.cause ? "cs-tip-row--up" : ""));
      let effects = 0;
      for (const hop of focus.dist.values()) if (hop > 0) effects += 1;
      out.push(row("set off", effects ? `${effects} event${effects === 1 ? "" : "s"}` : "nothing",
        effects ? "cs-tip-row--down" : ""));
      if (focus.corr) {
        let n = 0;
        for (const lane of model.lanes) for (const q of lane.points) if (q.corr === focus.corr) n += 1;
        out.push(row("correlated with", `${n} event${n === 1 ? "" : "s"}`));
      }
      if (focus.truncatedUp || focus.truncatedDown) {
        const cut = [];
        if (focus.truncatedUp) cut.push("earlier causes");
        if (focus.truncatedDown) cut.push("later effects");
        out.push(row("not shown", `${cut.join(" and ")} beyond ${MAX_CHAIN_HOPS} steps`));
      }
    }
    return out.join("");
  }

  // What the trace found, in words, for the panel that has room for them.
  function chainRows(model, focus) {
    const rows = [];
    const point = focus.point;
    rows.push(["pinned", point.label, `tier${point.tier || 0}`]);

    // Say nothing about causation where the document records none, rather than
    // reporting its absence as an operator action.
    if (!model.hasCausation) return rows;

    let causeText;
    if (!point.cause) {
      causeText = "nothing, an operator acted directly";
    } else {
      const parent = model.byId.get(point.cause);
      if (parent) {
        causeText = `${parent.label} @ ${fmtClock(model.t0, parent.secs)}`;
      } else if (point.cause_at) {
        causeText = `outside this window, @ ${fmtClock(model.t0, parseT(point.cause_at) - model.t0)}`;
      } else {
        causeText = "outside this window";
      }
    }
    rows.push(["caused by", causeText, point.cause ? "warn" : null]);

    let effects = 0;
    for (const hop of focus.dist.values()) if (hop > 0) effects += 1;
    rows.push(["set off", effects ? `${effects} event${effects === 1 ? "" : "s"}` : "nothing", null]);

    // The chain is walked a bounded number of hops. Say when it was cut, or a
    // trimmed story reads as a complete one.
    if (focus.truncatedUp || focus.truncatedDown) {
      const cut = [];
      if (focus.truncatedUp) cut.push("earlier causes");
      if (focus.truncatedDown) cut.push("later effects");
      rows.push(["not shown", `${cut.join(" and ")} beyond ${MAX_CHAIN_HOPS} steps`, "warn"]);
    }
    return rows;
  }

  function renderReadout(root, model, folded, t0, cursor, focus) {
    const r = root.querySelector(".cs-readout-body");
    r.innerHTML = "";
    const rows = [["clock", fmtClock(t0, cursor), null]];
    if (focus) rows.push(...chainRows(model, focus));
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

    // `state.scale` describes what was RENDERED. Between rebuilds a pan only
    // translates that content, so the pointer has to be moved back into
    // rendered space before it can be read as a time -- without this the
    // hover cursor drifts away from the pointer by exactly the pan distance.
    const secsFromEvent = (clientX) => {
      const rect = svgEl.getBoundingClientRect();
      const xUser = ((clientX - rect.left) / rect.width) * VW - state.panDx;
      return (xUser - PAD_L) / state.scale.k + state.scale.dmin;
    };

    const setCursor = (secs) => {
      state.cursor = Math.max(0, Math.min(model.xmax, secs));
      applyFold(model, scene, state.cursor);
      const folded = foldTo(model, state.cursor);
      renderReadout(root, model, folded, model.t0, state.cursor, state.pinned);
      if (!model.live) {
        svgEl.setAttribute("aria-valuenow", String(Math.round(state.cursor)));
        svgEl.setAttribute("aria-valuetext", fmtClock(model.t0, state.cursor));
      }
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
      if (opts && opts.onSelect) opts.onSelect(cluster);
      // Selecting rebuilds, because tracing a chain un-collapses its members
      // and that changes what the clusters are. `state.refocus` is owned by
      // mount(), which holds the view and the render loop.
      state.refocus();
      if (!cluster) return;
      // A chain can be pinned from off screen, by keyboard or by a selection
      // that survived a pan, and then every visible mark dims with nothing lit
      // to show for it. Bring the pinned event in either way.
      state.reveal(cluster.items[0].secs);
      state.anchorTip();
      // Where the cursor answers for the pointer, a pin fixes it at its own
      // instant so the panel and the highlight cannot disagree. Where the
      // cursor is parked (a flowing window), it stays parked: dropping a
      // dashed rule across every lane is exactly what the pin is trying to
      // avoid, and the card plus the panel's pinned rows already say which
      // event it is. `state.setCursor` and not this closure's, because
      // refocus() above replaced the scene the local one writes to.
      if (!model.live) state.setCursor(cluster.items[0].secs);
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
      state.stopGlide();
      pan = { x0: e.clientX, from0: state.view.from, moved: false, v: 0, x: e.clientX, at: e.timeStamp };
      svgEl.classList.add("cs-grabbing");
      const onMove = (ev) => {
        if (!pan) return;
        if (Math.abs(ev.clientX - pan.x0) > CLICK_SLOP) pan.moved = true;
        const rect = svgEl.getBoundingClientRect();
        const perPx = (state.view.to - state.view.from) / ((rect.width * (VW - PAD_L - PAD_R)) / VW);
        // Velocity in seconds-of-record per millisecond, smoothed so one
        // jittery sample cannot decide how far the release throws.
        const dt = ev.timeStamp - pan.at;
        if (dt > 0) {
          const inst = (-(ev.clientX - pan.x) * perPx) / dt;
          pan.v = pan.v * 0.7 + inst * 0.3;
          pan.x = ev.clientX;
          pan.at = ev.timeStamp;
        }
        state.panTo(pan.from0 - (ev.clientX - pan.x0) * perPx);
      };
      const onUp = (ev) => {
        // A press that never moved is a click on empty space: clear any pinned
        // selection rather than leaving it stranded with nothing highlighted.
        if (pan && !pan.moved) setSelection(null);
        // Stale velocity throws the view after the hand has already stopped,
        // so a release that follows a pause coasts nowhere.
        const idle = pan && ev && ev.timeStamp - pan.at > 90;
        const v = pan && pan.moved && !idle ? pan.v : 0;
        pan = null;
        svgEl.classList.remove("cs-grabbing");
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        state.glide(v);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
    svgEl.addEventListener("pointerdown", onDown);

    // Hover is the primary act: moving onto an event shows its card, lights
    // its causal chain and its correlation group, and draws the edges. No
    // press, so it never competes with pan or select, and nothing has to be
    // clicked to read a relation. A pinned selection wins and hover stops
    // changing anything until it is released.
    //
    // Driven from `pointermove` and never `pointerover`: focusing rebuilds the
    // scene, which destroys and recreates the element under the pointer, and
    // the browser fires a fresh `pointerover` for that. Reacting to it would
    // focus the same event again and again. A rebuild generates no
    // `pointermove`, so this loop cannot start.
    svgEl.addEventListener("pointermove", (e) => {
      if (pan) return;
      const cluster = clusterFor(e.target);
      if (state.selected) return;
      state.setHover(cluster, e.clientX, e.clientY);
      // The fold cursor follows the pointer only where the caller wants it to.
      // In a flowing window it stays parked at the live edge: a dashed rule
      // roaming across every lane is one more thing between the pointer and
      // the event it is trying to reach.
      if (cluster || model.live) return;
      setCursor(secsFromEvent(e.clientX));
    });
    svgEl.addEventListener("pointerleave", () => {
      if (pan || state.selected) return;
      state.setHover(null);
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
        const dir = e.key === "." ? 1 : -1;
        if (model.live) {
          // No cursor to walk, so step the SELECTION: the ring and the card
          // are then what say where the keyboard is, which is more than an
          // invisible caret ever said.
          const from = state.selected ? state.selected.items[0].secs : dir > 0 ? -1 : model.xmax + 1;
          const next = stepToAdjacentPoint(model, from, dir);
          if (next === null) return;
          notifyScrub();
          state.reveal(next);
          const near = nearestCluster(scene, next);
          if (near) setSelection(near);
          return;
        }
        const step = stepToAdjacentPoint(model, state.cursor, dir);
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
        if (model.live) return;
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
      if (model.live && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
        e.preventDefault();
        if (!state.canPan) return;
        notifyScrub();
        state.panTo(state.view.from + (e.key === "ArrowRight" ? span / 4 : -span / 4));
        return;
      }
      if (model.live && (e.key === "Home" || e.key === "End")) {
        e.preventDefault();
        if (!state.canPan) return;
        notifyScrub();
        state.panTo(e.key === "Home" ? 0 : model.xmax);
        return;
      }
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

  // A quadratic with one far-offset control leaves the source at a sharp angle
  // and whips back, which reads as a 90-degree kink rather than a curve. A
  // cubic whose controls extend along the dominant axis leaves and enters
  // smoothly, and the lateral offset rides on BOTH controls so the whole curve
  // bows instead of bending.
  function edgePath(a, b, fan) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const shrink = 7;
    if (Math.abs(dy) < 5) {
      const dir = dx >= 0 ? 1 : -1;
      const bx = b.x - dir * shrink;
      const lift = 13 + Math.abs(fan) * 0.5;
      return `M${a.x},${a.y} C${a.x + dx * 0.28},${a.y - lift} ${bx - dx * 0.28},${b.y - lift} ${bx},${b.y}`;
    }
    const by = b.y - (dy > 0 ? shrink : -shrink);
    const k = (by - a.y) * 0.45;
    return `M${a.x},${a.y} C${a.x + fan},${a.y + k} ${b.x + fan},${by - k} ${b.x},${by}`;
  }

  // Separate edges that share an x corridor.
  //
  // Fanning per SOURCE is not enough: a reacting subscriber fires within the
  // same second as its cause, so two edges with DIFFERENT causes routinely
  // occupy the same corridor and were each centred independently on it. Every
  // offset is also stepped away from zero, because an offset of exactly zero
  // draws a dead-straight vertical that collides with any other zero-offset
  // edge and reads as a grid rule rather than an arrow.
  function fanEdges(edges, posOf) {
    const corridors = new Map();
    for (const e of edges) {
      const a = posOf(e.from);
      const b = posOf(e.to);
      if (!a || !b) continue;
      const key = Math.round((a.x + b.x) / 2 / 14);
      const bucket = corridors.get(key);
      if (bucket) bucket.push(e);
      else corridors.set(key, [e]);
    }
    for (const bucket of corridors.values()) {
      bucket.sort((x, z) => posOf(x.to).y - posOf(z.to).y);
      bucket.forEach((e, i) => {
        let step = i - (bucket.length - 1) / 2;
        step = step >= 0 ? step + 0.5 : step - 0.5;
        const a = posOf(e.from);
        const b = posOf(e.to);
        e.fan = step * Math.max(13, Math.abs(b.y - a.y) * 0.07);
      });
    }
  }

  // How far a chain is walked in each direction before it is cut. A long chain
  // drawn in full is a hairball, and the cut is reported in the readout rather
  // than silently trimming the story.
  const MAX_CHAIN_HOPS = 4;

  // Ancestors and descendants of `point`, with hop distance from it.
  //
  // Both walks are bounded and both carry a seen-set. An append-only log cannot
  // contain a causal cycle, but nothing in this module enforces that: the ids
  // arrive over a socket, and a malformed or self-referencing causation_id
  // would spin `while (cur.cause)` forever and hang the page. Trusting the
  // shape of remote data is not a guarantee, it is a hope.
  function traceChain(model, point) {
    const dist = new Map([[point, 0]]);
    let truncatedUp = false;
    let truncatedDown = false;
    let unresolved = null;

    let cur = point;
    let hops = 0;
    while (cur && cur.cause) {
      const parent = model.byId.get(cur.cause);
      if (!parent) {
        unresolved = cur;
        break;
      }
      if (dist.has(parent)) break;
      hops += 1;
      if (hops > MAX_CHAIN_HOPS) {
        truncatedUp = true;
        break;
      }
      dist.set(parent, -hops);
      cur = parent;
    }

    let frontier = [point];
    for (let depth = 1; depth <= MAX_CHAIN_HOPS && frontier.length; depth += 1) {
      const next = [];
      for (const node of frontier) {
        if (!node.id) continue;
        for (const kid of model.childrenOf.get(node.id) || []) {
          if (dist.has(kid)) continue;
          dist.set(kid, depth);
          next.push(kid);
        }
      }
      frontier = next;
      if (depth === MAX_CHAIN_HOPS && next.length) truncatedDown = true;
    }

    return { dist, unresolved, truncatedUp, truncatedDown };
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
        <div class="cs-stage"><div class="cs-tip" data-on="0" aria-hidden="true"></div></div>
        <div class="cs-hint">${
          opts.live
            ? "Hover an event for its relations &middot; drag to pan &middot; click to pin &middot; " +
              "<kbd>&larr;</kbd><kbd>&rarr;</kbd> pan, <kbd>,</kbd><kbd>.</kbd> step events, " +
              "<kbd>esc</kbd> release"
            : "Hover an event for its relations &middot; drag to pan &middot; click to pin &middot; " +
              "<kbd>&larr;</kbd><kbd>&rarr;</kbd> cursor, <kbd>shift</kbd> to pan, " +
              "<kbd>,</kbd><kbd>.</kbd> step events, <kbd>enter</kbd> pin"
        }</div>
        ${note}
        <div class="cs-panels">
          <div class="cs-readout">
            <div class="cs-readout-head">${
              opts.live ? "Current state" : "Folded state at cursor"
            }</div>
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
    const scale = buildScale(view.from, view.to, domainMax);
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
      live: model.live,
      showPlay: opts.showPlay,
      showJumpLast: opts.showJumpLast,
      jumpLabel: opts.jumpLabel,
    });
    const stage = root.querySelector(".cs-stage");
    // The card lives outside the SVG and survives every rebuild, so a hover
    // that re-renders the scene underneath it does not make it flicker.
    const tip = stage.querySelector(".cs-tip");
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

    // What the DOM currently holds, which after a translate-only pan is no
    // longer what `state.view` says. Every pan decision is made against this.
    let shown = { from: view.from, bmin: scale.bmin, bmax: scale.bmax, k: scale.k };
    state.panDx = 0;

    // Panning is a translate on the one clipped group, not a rebuild. The
    // rebuild is what made dragging feel stepped: it recomputed clusters,
    // reseated every label and refolded the readout on each frame, so marks
    // and text hopped between two equally valid layouts many times a second.
    // Content outside the view is already drawn (see OVERSCAN), so sliding it
    // in costs one attribute write and the motion tracks the hand exactly.
    state.panTo = (from) => {
      const next = clampView(from, span, domainMax);
      if (Math.abs(next.from - state.view.from) < 1e-9) return;
      state.view = next;
      // Past the buffer there is genuinely nothing drawn to reveal, so this
      // is the one case that must rebuild.
      if (next.from < shown.bmin - 1e-6 || next.to > shown.bmax + 1e-6) {
        rerender();
        return;
      }
      state.panDx = -(next.from - shown.from) * shown.k;
      scene.setPan(state.panDx);
    };

    // Release carries on for a moment instead of stopping dead. Travel is
    // bounded by the buffer so a throw can never outrun what is drawn, which
    // is what keeps a mid-glide rebuild -- and the reseat that comes with it
    // -- off the screen entirely.
    let glideId = 0;
    state.stopGlide = () => {
      if (glideId) cancelAnimationFrame(glideId);
      glideId = 0;
    };
    state.glide = (v0) => {
      state.stopGlide();
      const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (still || !state.canPan || Math.abs(v0) < 0.005) {
        settle();
        return;
      }
      const lo = shown.bmin;
      const hi = shown.bmax - (state.view.to - state.view.from);
      let v = v0;
      let prev = null;
      const step = (ts) => {
        if (prev === null) prev = ts;
        const dt = Math.min(50, ts - prev);
        prev = ts;
        v *= Math.pow(0.9, dt / 16.7);
        const want = state.view.from + v * dt;
        const to = Math.max(lo, Math.min(hi, want));
        state.panTo(to);
        if (Math.abs(v) < 0.005 || to !== want) {
          glideId = 0;
          settle();
          return;
        }
        glideId = requestAnimationFrame(step);
      };
      glideId = requestAnimationFrame(step);
    };

    // Once the motion has stopped, rebuild at where it stopped. The buffer
    // recentres, and -- the reason this is unconditional -- the labels reseat
    // against the plot's real edges. A label is seated for the position it was
    // DRAWN at, so one that pans in from the buffer arrives centred on its
    // mark and can hang half outside the plot; only a rebuild puts it right.
    // Doing it here rather than per frame is the whole point: it costs one
    // frame after the hand has let go, where a jump is invisible.
    function settle() {
      if (Math.abs(state.view.from - shown.from) > 1e-6) rerender();
    }
    // Bring an instant into view: after a keyboard step walked the cursor past
    // an edge, so `,` and `.` can cross the whole domain without a manual pan,
    // or after a pin landed on something off screen. Takes the instant rather
    // than reading the cursor, because a flowing window parks the cursor and a
    // pin there has nothing to do with where it sits.
    state.reveal = (secs) => {
      if (!state.canPan) return;
      const margin = (state.view.to - state.view.from) * 0.1;
      if (secs < state.view.from + margin) state.panTo(secs - margin);
      else if (secs > state.view.to - margin) {
        state.panTo(secs - (state.view.to - state.view.from) + margin);
      }
    };
    state.revealCursor = () => state.reveal(state.cursor);

    // The selection anchors on a POINT, not a cluster: clusters are rebuilt on
    // every render and tracing a chain changes which ones exist at all, so a
    // cluster object cannot survive its own selection. `hover` is the same
    // thing with a shorter life; a pin outranks it.
    let anchor = null;
    let hover = null;

    function traceFor(point) {
      if (!point) return null;
      const traced = traceChain(model, point);
      return {
        point,
        corr: point.corr || null,
        dist: traced.dist,
        unresolved: traced.unresolved,
        truncatedUp: traced.truncatedUp,
        truncatedDown: traced.truncatedDown,
      };
    }
    const focusFor = () => traceFor(anchor || hover);

    // Hovering rebuilds, because tracing a chain un-collapses its members and
    // that changes which clusters exist. Guarded on the anchor POINT so
    // sweeping within one mark costs nothing, and so the rebuild's own
    // re-entry cannot recurse.
    state.setHover = (cluster, clientX, clientY) => {
      const point = cluster ? cluster.items[0] : null;
      if (point !== hover) {
        hover = point;
        rerender();
      }
      if (!cluster) {
        tip.setAttribute("data-on", "0");
        return;
      }
      tip.innerHTML = tipHtml(model, cluster, traceFor(point));
      tip.setAttribute("data-on", "1");
      placeTip(clientX, clientY);
    };

    // Kept inside the stage and flipped to the other side of the pointer near
    // an edge, so the card never leaves the panel or covers the mark it
    // describes.
    function placeTip(clientX, clientY) {
      if (clientX === undefined) return;
      const sb = stage.getBoundingClientRect();
      const tb = tip.getBoundingClientRect();
      let x = clientX - sb.left + 16;
      let y = clientY - sb.top - tb.height - 12;
      if (x + tb.width > sb.width - 6) x = clientX - sb.left - tb.width - 16;
      if (y < 4) y = clientY - sb.top + 20;
      tip.style.left = `${Math.max(4, x)}px`;
      tip.style.top = `${Math.max(4, y)}px`;
    }

    let controls;
    function rerender() {
      state.scale = buildScale(state.view.from, state.view.to, domainMax);
      const focus = focusFor();
      const next = renderTimeline(model, state.scale, focus);
      stage.replaceChildren(tip, next.g);
      scene = next;
      shown = {
        from: state.view.from,
        bmin: state.scale.bmin,
        bmax: state.scale.bmax,
        k: state.scale.k,
      };
      state.panDx = 0;
      state.pinned = anchor ? focus : null;
      controls = wireDrag(root, model, scene, state, opts);
      if (anchor) {
        const match = scene.selectable.find((s) => s.point === anchor);
        if (match) match.el.classList.add("cs-selected");
      }
      controls.setCursor(state.cursor);
    }

    state.refocus = () => {
      anchor = state.selected ? state.selected.items[0] : null;
      // A pin supersedes whatever was hovered; releasing one leaves the chart
      // clear rather than snapping back to whatever the pointer is over.
      hover = null;
      if (!anchor) {
        tip.setAttribute("data-on", "0");
        rerender();
        return;
      }
      rerender();
    };

    // Re-anchor the card to the pinned MARK, not to wherever the pointer
    // happened to be: a pin outlives the pointer. Separate from refocus and
    // called LAST, because pinning can also pan (`reveal`) and a card placed
    // before that pan is left pointing at where the mark used to be.
    state.anchorTip = () => {
      if (!anchor || !state.selected) return;
      const seat = scene.selectable.find((x) => x.point === anchor);
      if (!seat) return;
      const r = seat.el.getBoundingClientRect();
      tip.innerHTML = tipHtml(model, state.selected, focusFor());
      tip.setAttribute("data-on", "1");
      placeTip(r.left + r.width / 2, r.top);
    };

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
      state.stopGlide();
    };
  }

  window.CoraScrubber = { mount };
})();
