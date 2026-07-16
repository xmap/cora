/* Interactive replay scrubber for the "Scrubbing the Run" paper.

   A draggable time cursor folds one recorded agent-supervised APS 2-BM run to
   any instant and reconstructs what the run knew: alignment verdict, projection
   states, who was driving, the beam permit, and a content-addressed fidelity
   badge that recomputes a SHA-256 over the reconstructed recipe expansion and
   compares it to the digest recorded at run start.

   Data: javascripts/lights_out_run.json (mirrors the paper figure data file).
   No dependencies; vanilla JS + SVG + SubtleCrypto. Inert unless #cora-scrubber
   is on the page. Re-inits on instant navigation like the other docs scripts. */
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  // Resolve the run data relative to this script's own URL (it sits next to the
  // JSON in javascripts/), not the page URL, so the fetch works from any page
  // depth (the demo page is served at /scrubber/, not the site root).
  const SELF = document.currentScript && document.currentScript.src;
  const DATA_URL = SELF
    ? new URL("lights_out_run.json", SELF).href
    : "../javascripts/lights_out_run.json";

  // Lane geometry (SVG user units). The viewBox is fixed; CSS scales it.
  const VW = 920;
  const VH = 380;
  const PAD_L = 84;
  const PAD_R = 24;
  const LANE = {
    phase: 26,
    run: 78,
    permit: 116,
    setpoint: 168,
    acquire: 212,
    check: 256,
    output: 300,
  };
  const AXIS_Y = 338;
  const BAND_TOP = LANE.setpoint - 22;
  const BAND_BOT = LANE.check + 18;

  let root = null;
  let state = null; // { run, t0, xmax, scale, els, ... }
  let playing = false;
  let rafId = 0;
  let tampered = false;

  function parseT(s) {
    return Date.parse(s.replace("Z", "+00:00")) / 1000;
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

  // Canonical JSON with sorted keys, so the digest is stable across runs.
  function canonical(value) {
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    if (value && typeof value === "object") {
      return (
        "{" +
        Object.keys(value)
          .sort()
          .map((k) => JSON.stringify(k) + ":" + canonical(value[k]))
          .join(",") +
        "}"
      );
    }
    return JSON.stringify(value);
  }

  async function sha256Hex(text) {
    const buf = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(text),
    );
    return Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // The recipe expansion: the resolved plan steps and their parameter bindings.
  // Content-addressed at run start; the fold reconstructs it identically at any
  // cursor, which is exactly what the fidelity badge proves.
  function recipeExpansion(run) {
    return {
      procedure: run.procedure.name,
      kind: run.procedure.kind,
      steps: run.activities.map((a) => ({
        seq: a.seq,
        kind: a.step_kind,
        binding: a.payload,
      })),
    };
  }

  // Fold the event stream to time t: reconstruct the run's state at that instant.
  function foldTo(run, t) {
    const ev = run.run.events
      .map((e) => ({ ...e, secs: parseT(e.at) - run.t0 }))
      .filter((e) => e.secs <= t + 1e-6);
    const last = ev[ev.length - 1];
    let driver = "not started";
    let driverRole = "muted";
    if (last) {
      if (last.type === "RunStarted") {
        driver = "running (operator)";
        driverRole = "operator";
      } else if (last.type === "RunHeld") {
        driver = "held by supervisor";
        driverRole = "agent";
      } else if (last.type === "RunResumed") {
        driver = "running (resumed by supervisor)";
        driverRole = "agent";
      } else if (last.type === "RunCompleted") {
        driver = "completed";
        driverRole = "operator";
      }
    }

    const lastIter = run.iterations
      .filter((it) => parseT(it.ended_at) - run.t0 <= t + 1e-6)
      .pop();
    let alignment = "in progress";
    if (lastIter && lastIter.converged) alignment = "converged (0.30 px)";
    else if (lastIter) alignment = `searching (${lastIter.iteration_index}/4)`;

    // Projection state per index: latest acquire event at or before t wins.
    const projs = run.activities.filter(
      (a) => a.payload.action_name === "acquire_projection",
    );
    const byIndex = new Map();
    for (const a of projs) {
      const s = parseT(a.sampled_at) - run.t0;
      if (s > t + 1e-6) continue;
      const idx = a.payload.params.index;
      byIndex.set(idx, a.result);
    }
    let done = 0;
    let inflightIdx = null;
    for (const [idx, res] of byIndex) {
      if (res === "ok") done += 1;
      else if (res === "in_flight") inflightIdx = idx;
    }

    const permitLost = t >= run.beamLoss && t < run.beamBack;

    return { driver, driverRole, alignment, done, inflightIdx, permitLost };
  }

  function xFor(s, secs) {
    return PAD_L + (secs - s.dmin) * s.k;
  }

  function buildScale(run) {
    // The axis runs a true 0 to xmax: 0s maps to PAD_L (the slider's left edge)
    // and xmax maps to VW - PAD_R, so the slider and the timeline share the
    // same 0-origin. PAD_L / PAD_R supply the visual margin, not negative time.
    const dmin = 0;
    const dmax = run.xmax;
    const k = (VW - PAD_L - PAD_R) / (dmax - dmin);
    return { dmin, dmax, k };
  }

  // Render the static timeline once. Time-tagged marks are dimmed past the
  // cursor on each fold; nothing is destroyed and rebuilt during a drag.
  function renderTimeline(run, s) {
    const g = svg("svg", {
      viewBox: `0 0 ${VW} ${VH}`,
      class: "cora-scrubber__svg",
      role: "img",
      "aria-label":
        "Replay timeline of an agent-supervised APS 2-BM run. Use the cursor slider below to fold the run to any instant.",
    });
    const X = (secs) => xFor(s, secs);
    const timed = []; // { el, t } dimmed past the cursor

    // Held band across the hold window.
    g.appendChild(
      svg("rect", {
        x: X(run.beamLoss),
        y: 8,
        width: X(run.beamBack) - X(run.beamLoss),
        height: VH - 8 - 34,
        class: "cs-held",
      }),
    );

    // Phase bars: alignment, scan, save.
    const alignEnd = parseT(run.iterations[run.iterations.length - 1].ended_at) - run.t0 + 1.5;
    const saveAct = run.activities.find((a) => a.payload.action_name === "write_dataset");
    const saveT = saveAct ? parseT(saveAct.sampled_at) - run.t0 : run.xmax;
    const phases = [
      ["Alignment", 0, alignEnd, "align"],
      ["Scan", alignEnd, saveT - 6, "scan"],
      ["Save", saveT - 6, saveT + 6, "save"],
    ];
    for (const [name, x0, x1, cls] of phases) {
      g.appendChild(
        svg("rect", {
          x: X(x0),
          y: LANE.phase - 11,
          width: X(x1) - X(x0),
          height: 22,
          rx: 4,
          class: `cs-phase cs-phase--${cls}`,
        }),
      );
      const tx = svg("text", {
        x: (X(x0) + X(x1)) / 2,
        y: LANE.phase + 4,
        class: `cs-phase-label cs-phase-label--${cls}`,
        "text-anchor": "middle",
      });
      tx.textContent = name;
      g.appendChild(tx);
    }

    // Iteration bands tinted by verdict, capped with a colored rule.
    run.iterations.forEach((it) => {
      const a = parseT(it.started_at) - run.t0;
      const b = parseT(it.ended_at) - run.t0;
      const cls = it.converged ? "good" : "warn";
      g.appendChild(
        svg("rect", {
          x: X(a),
          y: BAND_TOP,
          width: X(b) - X(a),
          height: BAND_BOT - BAND_TOP,
          class: `cs-band cs-band--${cls}`,
        }),
      );
      const rule = svg("line", {
        x1: X(a),
        y1: BAND_TOP,
        x2: X(b),
        y2: BAND_TOP,
        class: `cs-band-rule cs-band-rule--${cls}`,
      });
      g.appendChild(rule);
      const lab = svg("text", {
        x: (X(a) + X(b)) / 2,
        y: BAND_TOP - 4,
        class: `cs-itlabel cs-itlabel--${cls}`,
        "text-anchor": "middle",
      });
      lab.textContent = `i${it.iteration_index}`;
      g.appendChild(lab);
    });

    // Lane baselines and left labels.
    const laneRows = [
      ["run", "Run"],
      ["permit", "Beam permit"],
      ["setpoint", "Setpoint"],
      ["acquire", "Acquire"],
      ["check", "Check"],
      ["output", "Output"],
    ];
    for (const [key, label] of laneRows) {
      g.appendChild(
        svg("line", {
          x1: PAD_L,
          y1: LANE[key],
          x2: VW - PAD_R,
          y2: LANE[key],
          class: "cs-baseline",
        }),
      );
      const t = svg("text", {
        x: PAD_L - 12,
        y: LANE[key] + 4,
        class: "cs-lane-label",
        "text-anchor": "end",
      });
      t.textContent = label;
      g.appendChild(t);
    }

    // Beam-permit lane: satisfied (solid green) except across the hold (dashed).
    const permitSeg = (x0, x1, lost) =>
      svg("line", {
        x1: X(x0),
        y1: LANE.permit,
        x2: X(x1),
        y2: LANE.permit,
        class: `cs-permit ${lost ? "cs-permit--lost" : "cs-permit--ok"}`,
      });
    g.appendChild(permitSeg(0, run.beamLoss, false));
    g.appendChild(permitSeg(run.beamLoss, run.beamBack, true));
    g.appendChild(permitSeg(run.beamBack, run.xmax, false));

    // Run-lifecycle state line: solid while active, dashed while held, absent
    // before start and after completion, mirroring the beam-permit lane so the
    // run state is legible at every cursor position (not only at the markers).
    // Neutral tone, not the beam-permit green, so the two lanes read distinct.
    const runAt = {};
    run.run.events.forEach((e) => {
      runAt[e.type] = parseT(e.at) - run.t0;
    });
    const runSeg = (x0, x1, held) =>
      svg("line", {
        x1: X(x0),
        y1: LANE.run,
        x2: X(x1),
        y2: LANE.run,
        class: `cs-run-line ${held ? "cs-run-line--held" : "cs-run-line--active"}`,
      });
    if (
      runAt.RunStarted != null &&
      runAt.RunHeld != null &&
      runAt.RunResumed != null &&
      runAt.RunCompleted != null
    ) {
      g.appendChild(runSeg(runAt.RunStarted, runAt.RunHeld, false));
      g.appendChild(runSeg(runAt.RunHeld, runAt.RunResumed, true));
      g.appendChild(runSeg(runAt.RunResumed, runAt.RunCompleted, false));
    }

    // Run-lifecycle markers: operator square, agent diamond, with labels.
    const labelFor = {
      RunStarted: ["started", "operator"],
      RunHeld: ["held", "supervisor"],
      RunResumed: ["resumed", "supervisor"],
      RunCompleted: ["completed", "operator"],
    };
    run.run.events.forEach((e) => {
      const x = X(parseT(e.at) - run.t0);
      const agent = e.role === "agent";
      const m = agent
        ? svg("rect", {
            x: x - 5,
            y: LANE.run - 5,
            width: 10,
            height: 10,
            transform: `rotate(45 ${x} ${LANE.run})`,
            class: "cs-life cs-life--agent",
          })
        : svg("rect", {
            x: x - 5,
            y: LANE.run - 5,
            width: 10,
            height: 10,
            class: "cs-life cs-life--operator",
          });
      g.appendChild(m);
      const [word, who] = labelFor[e.type];
      const lab = svg("text", {
        x,
        y: LANE.run - 12,
        class: `cs-life-label cs-life-label--${agent ? "agent" : "operator"}`,
        "text-anchor": "middle",
      });
      lab.textContent = `${word} (${who})`;
      g.appendChild(lab);
    });

    // Alignment swim-lane marks: setpoint squares, acquire triangles, check
    // circles with residual labels.
    const markFor = (kind, x, y) => {
      if (kind === "setpoint")
        return svg("rect", { x: x - 4, y: y - 4, width: 8, height: 8, class: "cs-mark cs-mark--setpoint" });
      if (kind === "check")
        return svg("circle", { cx: x, cy: y, r: 4.5, class: "cs-mark cs-mark--check" });
      return svg("polygon", {
        points: `${x},${y - 5} ${x - 5},${y + 4} ${x + 5},${y + 4}`,
        class: "cs-mark cs-mark--acquire",
      });
    };
    run.activities.forEach((a) => {
      const an = a.payload.action_name;
      if (a.payload.role === "taxi" || an === "acquire_projection" || an === "fly_scan_prep" || an === "write_dataset")
        return;
      if (a.payload.role === "fly_scan") return;
      const x = X(parseT(a.sampled_at) - run.t0);
      const y = a.step_kind === "action" ? LANE.acquire : LANE[a.step_kind];
      const m = markFor(a.step_kind, x, y);
      g.appendChild(m);
      timed.push({ el: m, t: parseT(a.sampled_at) - run.t0 });
      if (a.step_kind === "check") {
        const lab = svg("text", {
          x,
          y: y + 16,
          class: "cs-residual",
          "text-anchor": "middle",
        });
        lab.textContent = a.payload.actual.toFixed(2);
        g.appendChild(lab);
        timed.push({ el: lab, t: parseT(a.sampled_at) - run.t0 });
      }
    });

    // Science projections: completed (solid triangles) and the interrupted #3
    // as an open dashed interval whose end tracks the cursor while it stays open.
    const projs = run.activities.filter((a) => a.payload.action_name === "acquire_projection");
    const yA = LANE.acquire;
    const inflight = projs.find((a) => a.result === "in_flight");
    const inflightT = parseT(inflight.sampled_at) - run.t0;
    const reacq = projs
      .filter((a) => a.result === "ok")
      .map((a) => parseT(a.sampled_at) - run.t0)
      .filter((tt) => tt > inflightT)
      .sort((p, q) => p - q)[0];

    projs.forEach((a) => {
      if (a.result !== "ok") return;
      const x = X(parseT(a.sampled_at) - run.t0);
      const tt = parseT(a.sampled_at) - run.t0;
      const tri = svg("polygon", {
        points: `${x},${yA - 5} ${x - 5},${yA + 4} ${x + 5},${yA + 4}`,
        class: "cs-mark cs-mark--projection",
      });
      g.appendChild(tri);
      timed.push({ el: tri, t: tt });
      // Index label under each projection: the count makes the interrupted #3
      // legible as a retry (its number reappears after the hold), mirroring the
      // i# caps on the iteration bands above.
      const lab = svg("text", {
        x,
        y: yA + 16,
        class: "cs-projlabel",
        "text-anchor": "middle",
      });
      lab.textContent = String(a.payload.params.index);
      g.appendChild(lab);
      timed.push({ el: lab, t: tt });
    });

    // Open interval for the in-flight projection (drawn dynamically on fold).
    const openLine = svg("line", {
      x1: X(inflightT),
      y1: yA,
      x2: X(inflightT),
      y2: yA,
      class: "cs-open-interval",
    });
    g.appendChild(openLine);
    const openTip = svg("polygon", {
      points: `${X(inflightT)},${yA - 5} ${X(inflightT) - 5},${yA + 4} ${X(inflightT) + 5},${yA + 4}`,
      class: "cs-mark cs-mark--inflight",
    });
    g.appendChild(openTip);
    const openLab = svg("text", {
      x: X(inflightT),
      y: yA - 12,
      class: "cs-open-label",
      "text-anchor": "middle",
    });
    openLab.textContent = "#3 in flight";
    g.appendChild(openLab);

    // Data save marker on the output lane.
    if (saveAct) {
      const x = X(saveT);
      const y = LANE.output;
      const pent = svg("polygon", {
        points: `${x},${y - 5} ${x + 5},${y - 1} ${x + 3},${y + 5} ${x - 3},${y + 5} ${x - 5},${y - 1}`,
        class: "cs-mark cs-mark--save",
      });
      g.appendChild(pent);
      timed.push({ el: pent, t: saveT });
      const lab = svg("text", { x, y: y + 16, class: "cs-save-label", "text-anchor": "middle" });
      lab.textContent = "HDF5";
      g.appendChild(lab);
      timed.push({ el: lab, t: saveT });
    }

    // Time axis ticks.
    g.appendChild(
      svg("line", { x1: PAD_L, y1: AXIS_Y, x2: VW - PAD_R, y2: AXIS_Y, class: "cs-axis" }),
    );
    for (let secs = 0; secs <= run.xmax; secs += 30) {
      const x = X(secs);
      g.appendChild(svg("line", { x1: x, y1: AXIS_Y, x2: x, y2: AXIS_Y + 5, class: "cs-tick" }));
      const lab = svg("text", { x, y: AXIS_Y + 17, class: "cs-tick-label", "text-anchor": "middle" });
      lab.textContent = `${secs}s`;
      g.appendChild(lab);
    }

    // Fold cursor: a full-height line with a grab handle at the axis.
    const cursorLine = svg("line", {
      x1: X(run.cursor),
      y1: LANE.phase - 12,
      x2: X(run.cursor),
      y2: AXIS_Y,
      class: "cs-cursor",
    });
    g.appendChild(cursorLine);
    const handle = svg("polygon", {
      points: "0,-9 7,0 0,9 -7,0",
      class: "cs-cursor-handle",
    });
    handle.setAttribute("transform", `translate(${X(run.cursor)} ${AXIS_Y})`);
    g.appendChild(handle);

    return { g, X, timed, openLine, openTip, openLab, cursorLine, handle, inflightT, reacq, yA };
  }

  function applyFold(run, scene) {
    const t = run.cursor;
    const X = scene.X;
    const folded = foldTo(run, t);

    // Cursor position.
    scene.cursorLine.setAttribute("x1", X(t));
    scene.cursorLine.setAttribute("x2", X(t));
    scene.handle.setAttribute("transform", `translate(${X(t)} ${AXIS_Y})`);

    // Dim everything after the cursor (the future the run has not reached).
    for (const { el, t: et } of scene.timed) {
      el.classList.toggle("cs-future", et > t + 1e-6);
    }

    // The in-flight open interval: the dashed line and label appear only while
    // #3 is open at the cursor. The triangle itself stays on the lane as a
    // future-faded mark before the cursor reaches it (like every other
    // projection), and is hidden only after re-acquire, when the solid #3 takes
    // over. Toggling it via cs-hidden for the whole pre-flight span was the bug:
    // it vanished instead of dimming for earlier cursor positions.
    const showOpen = t >= scene.inflightT && t < scene.reacq;
    [scene.openLine, scene.openLab].forEach((el) =>
      el.classList.toggle("cs-hidden", !showOpen),
    );
    scene.openTip.classList.toggle("cs-hidden", t >= scene.reacq);
    scene.openTip.classList.toggle("cs-future", t < scene.inflightT - 1e-6);
    if (showOpen) {
      scene.openLine.setAttribute("x2", X(t));
      scene.openLab.setAttribute("x", (X(scene.inflightT) + X(t)) / 2);
    }

    // Readout card.
    const r = root.querySelector(".cs-readout-body");
    const projText =
      folded.inflightIdx !== null
        ? `${folded.done} done, #${folded.inflightIdx} in flight`
        : `${folded.done} done`;
    r.innerHTML = "";
    const rows = [
      ["clock", fmtClock(run.t0, t), null],
      ["alignment", folded.alignment, folded.alignment.startsWith("converged") ? "good" : "warn"],
      ["projections", projText, folded.inflightIdx !== null ? "alarm" : "good"],
      ["run", folded.driver, folded.driverRole],
      ["beam permit", folded.permitLost ? "lost" : "satisfied", folded.permitLost ? "alarm" : "good"],
    ];
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

    updateFidelity(run);
  }

  let fidelitySeq = 0;
  async function updateFidelity(run) {
    const seq = ++fidelitySeq;
    const expansion = recipeExpansion(run);
    // The reconstructed expansion always matches the recorded plan (the recipe
    // is content-addressed at run start). Tampering perturbs the recorded copy,
    // so the recomputed digest honestly diverges.
    const recomputed = await sha256Hex(canonical(expansion));
    const recorded = tampered
      ? await sha256Hex(canonical({ ...expansion, tamper: 1 }))
      : recomputed;
    if (seq !== fidelitySeq) return; // a newer fold superseded this one
    const ok = recomputed === recorded;
    const badge = root.querySelector(".cs-badge");
    const digestEl = root.querySelector(".cs-digest");
    const noteEl = root.querySelector(".cs-fidelity-note");
    badge.textContent = ok ? "verified" : "altered";
    badge.classList.toggle("cs-badge--ok", ok);
    badge.classList.toggle("cs-badge--bad", !ok);
    badge.classList.remove("cs-pulse");
    void badge.offsetWidth; // restart the pulse animation
    badge.classList.add("cs-pulse");
    const short = `${recorded.slice(0, 8)}…${recorded.slice(-2)}`;
    digestEl.textContent = `sha256 ${short}`;
    noteEl.textContent = ok
      ? "recipe expansion matches the digest recorded at run start"
      : "recomputed digest does not match the recorded record";
  }

  function setCursor(run, scene, secs) {
    run.cursor = Math.max(0, Math.min(run.xmax, secs));
    applyFold(run, scene);
    const slider = root.querySelector(".cs-slider");
    slider.setAttribute("aria-valuenow", String(Math.round(run.cursor)));
    slider.setAttribute(
      "aria-valuetext",
      `${fmtClock(run.t0, run.cursor)}, ${Math.round(run.cursor)} seconds`,
    );
    const pct = run.xmax > 0 ? (run.cursor / run.xmax) * 100 : 0;
    const fill = root.querySelector(".cs-slider-fill");
    const thumb = root.querySelector(".cs-slider-thumb");
    if (fill) fill.style.width = `${pct}%`;
    if (thumb) thumb.style.left = `${pct}%`;
  }

  function stopPlay() {
    playing = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    const btn = root.querySelector(".cs-play");
    if (btn) btn.setAttribute("aria-pressed", "false"), (btn.textContent = "Play run");
  }

  function startPlay(run, scene) {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setCursor(run, scene, run.xmax);
      return;
    }
    playing = true;
    const btn = root.querySelector(".cs-play");
    btn.setAttribute("aria-pressed", "true");
    btn.textContent = "Pause";
    if (run.cursor >= run.xmax) setCursor(run, scene, 0);
    let prev = null;
    const step = (ts) => {
      if (!playing) return;
      if (prev === null) prev = ts;
      const dt = (ts - prev) / 1000;
      prev = ts;
      setCursor(run, scene, run.cursor + dt * 18); // ~12s of run per real second
      if (run.cursor >= run.xmax) {
        stopPlay();
        return;
      }
      rafId = requestAnimationFrame(step);
    };
    rafId = requestAnimationFrame(step);
  }

  function wireDrag(run, scene) {
    const svgEl = scene.g;
    const slider = root.querySelector(".cs-slider");

    const secsFromEvent = (clientX) => {
      const rect = svgEl.getBoundingClientRect();
      const xUser = ((clientX - rect.left) / rect.width) * VW;
      return scene.X.invert
        ? scene.X.invert(xUser)
        : (xUser - PAD_L) / run.scale.k + run.scale.dmin;
    };

    const onMove = (e) => {
      stopPlay();
      setCursor(run, scene, secsFromEvent(e.clientX));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    const onDown = (e) => {
      e.preventDefault();
      slider.focus();
      stopPlay();
      setCursor(run, scene, secsFromEvent(e.clientX));
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
    svgEl.addEventListener("pointerdown", onDown);

    // The slider proxy under the timeline is itself draggable: map the pointer
    // across the slider's own width to a time, so it works without scrolling
    // the timeline. Pointer capture keeps the drag alive past the thumb edge.
    const track = slider.querySelector(".cs-slider-track");
    const secsFromSlider = (clientX) => {
      const rect = track.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return f * run.xmax;
    };
    let sliderDragging = false;
    const onSliderDown = (e) => {
      e.preventDefault();
      slider.focus();
      stopPlay();
      sliderDragging = true;
      try {
        slider.setPointerCapture(e.pointerId);
      } catch (err) {
        /* capture is best-effort; the dragging flag drives the move */
      }
      setCursor(run, scene, secsFromSlider(e.clientX));
    };
    const onSliderMove = (e) => {
      if (!sliderDragging) return;
      setCursor(run, scene, secsFromSlider(e.clientX));
    };
    const onSliderUp = () => {
      sliderDragging = false;
    };
    slider.addEventListener("pointerdown", onSliderDown);
    slider.addEventListener("pointermove", onSliderMove);
    slider.addEventListener("pointerup", onSliderUp);
    slider.addEventListener("pointercancel", onSliderUp);

    slider.addEventListener("keydown", (e) => {
      const big = run.xmax / 12;
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
        playing ? stopPlay() : startPlay(run, scene);
        return;
      }
      if (!(e.key in map)) return;
      e.preventDefault();
      stopPlay();
      if (e.key === "Home") setCursor(run, scene, 0);
      else if (e.key === "End") setCursor(run, scene, run.xmax);
      else setCursor(run, scene, run.cursor + map[e.key]);
    });
  }

  function buildControls(run, scene) {
    const bar = root.querySelector(".cs-controls");
    const play = bar.querySelector(".cs-play");
    play.addEventListener("click", () => (playing ? stopPlay() : startPlay(run, scene)));
    const beam = bar.querySelector(".cs-jump-beam");
    beam.addEventListener("click", () => {
      stopPlay();
      setCursor(run, scene, run.beamLoss);
    });
    const tamper = bar.querySelector(".cs-tamper");
    tamper.addEventListener("click", () => {
      tampered = !tampered;
      tamper.setAttribute("aria-pressed", String(tampered));
      tamper.textContent = tampered ? "Restore record" : "Tamper with record";
      updateFidelity(run);
    });
  }

  function scaffold() {
    root.innerHTML = `
      <div class="cora-scrubber__chrome">
        <div class="cs-titlebar">
          <span class="cs-dot" aria-hidden="true"></span>
          <span class="cs-title">Replay scrubber</span>
          <span class="cs-subtitle">APS 2-BM lights-out run</span>
          <div class="cs-controls">
            <button type="button" class="cs-btn cs-play" aria-pressed="false">Play run</button>
            <button type="button" class="cs-btn cs-jump-beam">Jump to beam loss</button>
            <button type="button" class="cs-btn cs-tamper" aria-pressed="false">Tamper with record</button>
          </div>
        </div>
        <div class="cs-stage"></div>
        <div class="cs-slider" tabindex="0" role="slider"
             aria-label="Fold cursor: time within the run"
             aria-valuemin="0" aria-valuenow="0">
          <div class="cs-slider-track">
            <div class="cs-slider-fill"></div>
            <div class="cs-slider-thumb"></div>
          </div>
        </div>
        <div class="cs-panels">
          <div class="cs-readout">
            <div class="cs-readout-head">Folded state at cursor</div>
            <div class="cs-readout-body"></div>
          </div>
          <div class="cs-fidelity">
            <div class="cs-readout-head">Fidelity</div>
            <div class="cs-fidelity-row">
              <span class="cs-digest">sha256 …</span>
              <span class="cs-badge cs-badge--ok">verified</span>
            </div>
            <div class="cs-fidelity-note"></div>
          </div>
        </div>
      </div>`;
  }

  async function init() {
    root = document.getElementById("cora-scrubber");
    if (!root || root.dataset.ready === "1") return;
    root.dataset.ready = "1";
    root.classList.add("cora-scrubber");
    stopPlay();
    tampered = false;

    let raw;
    try {
      raw = await (await fetch(DATA_URL)).json();
    } catch (err) {
      root.textContent = "Could not load the run data for the demo.";
      return;
    }

    const run = raw;
    run.t0 = parseT(run.run.events[0].at);
    run.xmax = Math.max(...run.run.events.map((e) => parseT(e.at) - run.t0));
    run.beamLoss = parseT(run.provenance.beam_loss_at) - run.t0;
    run.beamBack = parseT(run.provenance.beam_back_at) - run.t0;
    run.cursor = parseT(run.provenance.cursor_at) - run.t0;
    run.scale = buildScale(run);

    scaffold();
    const scene = renderTimeline(run, run.scale);
    root.querySelector(".cs-stage").appendChild(scene.g);

    const slider = root.querySelector(".cs-slider");
    slider.setAttribute("aria-valuemax", String(Math.round(run.xmax)));

    buildControls(run, scene);
    wireDrag(run, scene);
    setCursor(run, scene, run.cursor);
  }

  function boot() {
    if (window.document$ && typeof window.document$.subscribe === "function") {
      window.document$.subscribe(() => {
        root = null;
        init();
      });
    } else if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  boot();
})();
