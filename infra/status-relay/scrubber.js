/* REWIND-mode replay scrubber for the status relay's page.

   Copy-and-adapt of docs/javascripts/scrubber-demo.js (the paper's replay
   scrubber for a fixed, already-recorded run), not a shared module: about
   40% of that script is coupled to the paper's own fixed data file
   (beam_loss_at / beam_back_at, iteration convergence, the recipe-
   expansion fidelity badge) and does not apply to an arbitrary real Run's
   pushed history. The two are meant to diverge over time -- the paper's
   version stays frozen as published, this one grows real-run edge cases
   (zero observations, one event, a run still open with no end).

   What's carried over near-verbatim because it's fiddly and data-shape
   agnostic: svg(), parseT, fmtClock, xFor, buildScale, and especially
   wireDrag (pointer-drag with setPointerCapture, the keyboard map, the
   slider proxy) -- there is no reason to get that logic right twice.

   Entry point: CoraScrubber.mount(rootEl, history). No fetch, no mkdocs
   boot hook, no fixed #cora-scrubber id: the relay page owns the element
   and hands over already-fetched data. Idempotent: a second mount on the
   same element tears down its listeners and rebuilds, so switching runs
   in the picker never leaks a drag/keyboard handler onto a stale DOM. */
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";

  const VW = 920;
  const PAD_L = 84;
  const PAD_R = 24;
  const LANE_LIFECYCLE = 34;
  const LANE_STATUS = 74;
  const LANE_CHANNEL_START = 114;
  const LANE_CHANNEL_HEIGHT = 40;
  const MAX_CHANNEL_LANES = 6;
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

  // Fold the lifecycle events forward to time t: which status band is
  // "current" at the cursor, and the last event at or before it.
  function foldTo(model, t) {
    let lastEvent = null;
    for (const e of model.lifecycle) {
      if (e.secs <= t + 1e-6) lastEvent = e;
      else break;
    }
    let status = "not started";
    if (lastEvent) {
      if (lastEvent.event_type === "RunHeld") status = "Held";
      else if (
        lastEvent.event_type === "RunCompleted" ||
        lastEvent.event_type === "RunAborted" ||
        lastEvent.event_type === "RunStopped" ||
        lastEvent.event_type === "RunTruncated"
      )
        status = "terminal";
      else status = "Running";
    }
    const channelReadings = {};
    for (const lane of model.channelLanes) {
      let reading = null;
      for (const p of lane.points) {
        if (p.secs <= t + 1e-6) reading = p;
        else break;
      }
      channelReadings[lane.channel_name] = reading;
    }
    return { lastEvent, status, channelReadings };
  }

  // Build the model: lifecycle events + up to MAX_CHANNEL_LANES channel
  // lanes, each a time-ordered list of points, from a get_run_history-
  // shaped `history` object. Numeric and categorical rows on the same
  // channel both land on that channel's lane.
  function buildModel(history) {
    const t0 = history.events.length ? parseT(history.events[0].occurred_at) : 0;
    const lifecycle = history.events.map((e) => ({
      event_type: e.event_type,
      secs: parseT(e.occurred_at) - t0,
    }));

    const byChannel = new Map();
    for (const o of history.observations) {
      if (!byChannel.has(o.channel_name)) byChannel.set(o.channel_name, []);
      byChannel.get(o.channel_name).push(o);
    }
    const channelNames = Array.from(byChannel.keys())
      .sort((a, b) => byChannel.get(b).length - byChannel.get(a).length)
      .slice(0, MAX_CHANNEL_LANES);
    const channelLanes = channelNames.map((name) => ({
      channel_name: name,
      points: byChannel
        .get(name)
        .map((o) => ({
          secs: parseT(o.sampled_at) - t0,
          value: o.value,
          categorical_value: o.categorical_value,
        }))
        .sort((a, b) => a.secs - b.secs),
    }));
    const omittedChannels = byChannel.size - channelLanes.length;

    let xmax = 0;
    for (const e of lifecycle) xmax = Math.max(xmax, e.secs);
    for (const lane of channelLanes) {
      for (const p of lane.points) xmax = Math.max(xmax, p.secs);
    }

    return { t0, xmax, lifecycle, channelLanes, omittedChannels };
  }

  function renderTimeline(model, scale) {
    const laneCount = Math.max(1, model.channelLanes.length);
    const axisY = LANE_CHANNEL_START + laneCount * LANE_CHANNEL_HEIGHT + 10;
    const vh = axisY + AXIS_MARGIN;
    const X = (secs) => xFor(scale, secs);

    const g = svg("svg", {
      viewBox: `0 0 ${VW} ${vh}`,
      class: "cora-scrubber__svg",
      role: "img",
      "aria-label": "Replay timeline of a CORA Run. Drag the cursor to fold it to any instant.",
    });

    const laneRows = [["Lifecycle", LANE_LIFECYCLE], ["Status", LANE_STATUS]];
    model.channelLanes.forEach((lane, i) => {
      laneRows.push([lane.channel_name, LANE_CHANNEL_START + i * LANE_CHANNEL_HEIGHT]);
    });
    for (const [label, y] of laneRows) {
      g.appendChild(svg("line", { x1: PAD_L, y1: y, x2: VW - PAD_R, y2: y, class: "cs-baseline" }));
      const t = svg("text", { x: PAD_L - 12, y: y + 4, class: "cs-lane-label", "text-anchor": "end" });
      t.textContent = label;
      g.appendChild(t);
    }

    const timed = [];
    model.lifecycle.forEach((e) => {
      const x = X(e.secs);
      const m = svg("rect", {
        x: x - 4,
        y: LANE_LIFECYCLE - 4,
        width: 8,
        height: 8,
        class: "cs-mark cs-mark--setpoint",
      });
      g.appendChild(m);
      timed.push({ el: m, t: e.secs });
      const lab = svg("text", { x, y: LANE_LIFECYCLE - 10, class: "cs-life-label", "text-anchor": "middle" });
      lab.textContent = e.event_type;
      g.appendChild(lab);
      timed.push({ el: lab, t: e.secs });
    });

    model.channelLanes.forEach((lane, i) => {
      const y = LANE_CHANNEL_START + i * LANE_CHANNEL_HEIGHT;
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
          p.categorical_value != null
            ? svg("circle", { cx: x, cy: y, r: 3.5, class: "cs-mark cs-mark--check" })
            : svg("circle", { cx: x, cy: y, r: 2.5, class: "cs-mark cs-mark--acquire" });
        g.appendChild(mark);
        timed.push({ el: mark, t: p.secs });
      });
    });

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
      y1: LANE_LIFECYCLE - 14,
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
    const rows = [
      ["clock", fmtClock(t0, cursor), null],
      ["status", folded.status, folded.status === "Held" ? "warn" : "good"],
      [
        "last event",
        folded.lastEvent ? `${folded.lastEvent.event_type} @ ${fmtClock(t0, folded.lastEvent.secs)}` : "none yet",
        null,
      ],
    ];
    for (const [channelName, reading] of Object.entries(folded.channelReadings)) {
      const text = reading
        ? `${reading.categorical_value != null ? reading.categorical_value : reading.value} @ ${fmtClock(t0, reading.secs)}`
        : "no reading yet";
      rows.push([channelName, text, null]);
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

  function scaffold(root, model, subtitle) {
    const note =
      model.omittedChannels > 0
        ? `<div class="cs-omitted-note">+${model.omittedChannels} more channel(s) not shown</div>`
        : "";
    root.innerHTML = `
      <div class="cora-scrubber__chrome">
        <div class="cs-titlebar">
          <span class="cs-dot" aria-hidden="true"></span>
          <span class="cs-title">Rewind</span>
          <span class="cs-subtitle">${subtitle}</span>
          <div class="cs-controls">
            <button type="button" class="cs-btn cs-play" aria-pressed="false">Play</button>
            <button type="button" class="cs-btn cs-jump-last">Jump to last event</button>
          </div>
        </div>
        <div class="cs-stage"></div>
        <div class="cs-slider" tabindex="0" role="slider"
             aria-label="Fold cursor: time within the run"
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
  }

  function mount(root, history) {
    if (root._coraScrubberCleanup) root._coraScrubberCleanup();

    const model = buildModel(history);
    const scale = buildScale(model.xmax);
    const subtitle = `${history.name} · ${history.status}${history.observations_truncated ? " · observations truncated" : ""}`;
    scaffold(root, model, subtitle);
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
