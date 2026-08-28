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
   subjects never leaks a drag/keyboard handler onto stale DOM. */
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

  function buildScale(xmax) {
    const dmin = 0;
    const dmax = xmax > 0 ? xmax : 1;
    const k = (VW - PAD_L - PAD_R) / (dmax - dmin);
    return { dmin, dmax, k };
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
      for (const p of model.primaryLane.points) {
        if (p.secs > t + 1e-6) break;
        point = p;
        if (p.state) state = p.state;
      }
      primary = { point, state };
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

    return { t0, xmax, lanes, primaryLane, omittedSeries };
  }

  function renderTimeline(model, scale) {
    const laneCount = Math.max(1, model.lanes.length);
    const axisY = LANE_START + laneCount * LANE_HEIGHT + 10;
    const vh = axisY + AXIS_MARGIN;
    const X = (secs) => xFor(scale, secs);

    const g = svg("svg", {
      viewBox: `0 0 ${VW} ${vh}`,
      class: "cora-scrubber__svg",
      role: "img",
      "aria-label": "Timeline. Drag the cursor to fold it to any instant.",
    });

    const laneY = new Map();
    model.lanes.forEach((lane, i) => {
      const y = LANE_START + i * LANE_HEIGHT;
      laneY.set(lane.lane_id, y);
      g.appendChild(svg("line", { x1: PAD_L, y1: y, x2: VW - PAD_R, y2: y, class: "cs-baseline" }));
      const t = svg("text", { x: PAD_L - 12, y: y + 4, class: "cs-lane-label", "text-anchor": "end" });
      t.textContent = lane.label;
      g.appendChild(t);
    });

    const timed = [];

    for (const lane of model.lanes) {
      const y = laneY.get(lane.lane_id);
      if (lane.render === "markers") {
        lane.points.forEach((p) => {
          const x = X(p.secs);
          const m = svg("rect", {
            x: x - 4,
            y: y - 4,
            width: 8,
            height: 8,
            class: "cs-mark cs-mark--setpoint",
          });
          g.appendChild(m);
          timed.push({ el: m, t: p.secs });
          const lab = svg("text", { x, y: y - 10, class: "cs-life-label", "text-anchor": "middle" });
          lab.textContent = p.label;
          g.appendChild(lab);
          timed.push({ el: lab, t: p.secs });
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
    const tickStep = model.xmax > 0 ? Math.max(1, Math.round(model.xmax / 12 / 5) * 5) : 1;
    for (let secs = 0; secs <= model.xmax; secs += tickStep) {
      const x = X(secs);
      g.appendChild(svg("line", { x1: x, y1: axisY, x2: x, y2: axisY + 5, class: "cs-tick" }));
      const lab = svg("text", { x, y: axisY + 17, class: "cs-tick-label", "text-anchor": "middle" });
      lab.textContent = `${secs}s`;
      g.appendChild(lab);
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

    return { g, X, axisY, timed, cursorLine, handle };
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
      rows.push(["status", state, state === "paused" ? "warn" : "good"]);
      rows.push([
        "last event",
        folded.primary.point ? `${folded.primary.point.label} @ ${fmtClock(t0, folded.primary.point.secs)}` : "none yet",
        null,
      ]);
    }
    for (const lane of model.lanes) {
      if (lane === model.primaryLane) continue;
      const reading = folded.readings[lane.lane_id];
      const text = reading
        ? `${reading.text != null ? reading.text : reading.value} @ ${fmtClock(t0, reading.secs)}`
        : "no reading yet";
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

  function wireDrag(root, model, scene, state) {
    const svgEl = scene.g;
    const slider = root.querySelector(".cs-slider");

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
      slider.setAttribute("aria-valuenow", String(Math.round(state.cursor)));
      const pct = model.xmax > 0 ? (state.cursor / model.xmax) * 100 : 0;
      const fill = root.querySelector(".cs-slider-fill");
      const thumb = root.querySelector(".cs-slider-thumb");
      if (fill) fill.style.width = `${pct}%`;
      if (thumb) thumb.style.left = `${pct}%`;
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

    const onDown = (e) => {
      e.preventDefault();
      slider.focus();
      stopPlay();
      setCursor(secsFromEvent(e.clientX));
      const onMove = (ev) => setCursor(secsFromEvent(ev.clientX));
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
    svgEl.addEventListener("pointerdown", onDown);

    const track = slider.querySelector(".cs-slider-track");
    const secsFromSlider = (clientX) => {
      const rect = track.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return f * model.xmax;
    };
    let sliderDragging = false;
    slider.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      slider.focus();
      stopPlay();
      sliderDragging = true;
      try {
        slider.setPointerCapture(e.pointerId);
      } catch (err) {
        /* capture is best-effort; the dragging flag drives the move */
      }
      setCursor(secsFromSlider(e.clientX));
    });
    slider.addEventListener("pointermove", (e) => {
      if (sliderDragging) setCursor(secsFromSlider(e.clientX));
    });
    slider.addEventListener("pointerup", () => {
      sliderDragging = false;
    });
    slider.addEventListener("pointercancel", () => {
      sliderDragging = false;
    });

    slider.addEventListener("keydown", (e) => {
      const big = model.xmax / 12;
      const map = {
        ArrowLeft: -2,
        ArrowRight: 2,
        ArrowDown: -2,
        ArrowUp: 2,
        PageDown: -big,
        PageUp: big,
        Home: -1e9,
        End: 1e9,
      };
      if (e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
        state.playing ? stopPlay() : startPlay();
        return;
      }
      if (!(e.key in map)) return;
      e.preventDefault();
      stopPlay();
      if (e.key === "Home") setCursor(0);
      else if (e.key === "End") setCursor(model.xmax);
      else setCursor(state.cursor + map[e.key]);
    });

    return { setCursor, stopPlay, startPlay };
  }

  function scaffold(root, model, opts) {
    const note =
      model.omittedSeries > 0
        ? `<div class="cs-omitted-note">+${model.omittedSeries} more lane(s) not shown</div>`
        : "";
    root.classList.add("cora-scrubber");
    root.innerHTML = `
      <div class="cora-scrubber__chrome">
        <div class="cs-titlebar">
          <span class="cs-dot" aria-hidden="true"></span>
          <span class="cs-title"></span>
          <span class="cs-subtitle"></span>
          <div class="cs-controls">
            <button type="button" class="cs-btn cs-play" aria-pressed="false">Play</button>
            <button type="button" class="cs-btn cs-jump-last">Jump to last event</button>
          </div>
        </div>
        <div class="cs-stage"></div>
        <div class="cs-slider" tabindex="0" role="slider"
             aria-label="${opts.sliderLabel}"
             aria-valuemin="0" aria-valuenow="0" aria-valuemax="${Math.round(model.xmax)}">
          <div class="cs-slider-track">
            <div class="cs-slider-fill"></div>
            <div class="cs-slider-thumb"></div>
          </div>
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
    const scale = buildScale(model.xmax);
    const subtitle =
      (doc.title || "") +
      (doc.title && doc.subtitle ? " · " : "") +
      (doc.subtitle || "") +
      (doc.truncated && doc.truncated.observations ? " · observations truncated" : "");
    scaffold(root, model, {
      chromeTitle: opts.chromeTitle || "Timeline",
      subtitle,
      sliderLabel: opts.sliderLabel || "Fold cursor: time within the window",
    });
    const scene = renderTimeline(model, scale);
    root.querySelector(".cs-stage").appendChild(scene.g);

    const state = { scale, cursor: 0, playing: false, rafId: 0 };
    const controls = wireDrag(root, model, scene, state);

    root.querySelector(".cs-play").addEventListener("click", () => {
      state.playing ? controls.stopPlay() : controls.startPlay();
    });
    root.querySelector(".cs-jump-last").addEventListener("click", () => {
      controls.stopPlay();
      controls.setCursor(model.xmax);
    });

    controls.setCursor(0);

    root._coraScrubberCleanup = () => {
      controls.stopPlay();
    };
  }

  window.CoraScrubber = { mount };
})();
