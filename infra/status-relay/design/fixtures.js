/* Synthetic activity for the scrubber harness, plus the measurements
   `check.mjs` asserts on. Shared by the browser harness and the headless
   check, so both exercise identical documents.

   Weights follow the measured 2-BM record (2026-08-28): Run and Decision are
   91% of all events, the rest share 9%. The default shape is BURSTY, because
   that is what the real feed does and it is the only shape that reproduces the
   overprinting this renderer exists to fix; a uniform sprinkle at the same
   rate looks fine under the old code too and would have hidden the bug.

   Event names are the real vocabulary, not placeholders, because label WIDTH
   is the constrained resource: `ProcedureActivitiesLogbookOpened` is 32
   characters, roughly a quarter of the plot. */
(function (root) {
  "use strict";

  var CATALOG = {
    Runs: [["RunAdjusted", 46], ["RunStarted", 7], ["RunCompleted", 6],
           ["RunObservationLogbookOpened", 5], ["RunResumed", 3], ["RunStopped", 2],
           ["RunTruncated", 2], ["RunAborted", 1]],
    Procedures: [["ProcedureIterationStarted", 9], ["ProcedureIterationEnded", 9],
           ["ProcedureStarted", 4], ["ProcedureCompleted", 4], ["ProcedureRegistered", 3],
           ["ProcedureActivitiesLogbookOpened", 2], ["ProcedureAborted", 1]],
    Subjects: [["SubjectMounted", 4], ["SubjectMeasured", 4], ["SubjectDismounted", 3],
           ["SubjectStored", 2], ["SubjectDiscarded", 1]],
    Campaigns: [["CampaignRunAdded", 4], ["CampaignSteeringDeclared", 2], ["CampaignHeld", 1]],
    Datasets: [["AcquisitionRecorded", 10], ["DatasetRegistered", 4], ["DatasetPromoted", 3],
           ["DatasetDemoted", 1], ["DatasetDiscarded", 1]],
    Clearances: [["ClearanceReviewStepAppended", 3], ["ClearanceApproved", 2],
           ["ClearanceExpired", 1], ["ClearanceRejected", 1]],
    Cautions: [["CautionRegistered", 2], ["CautionRetired", 1]],
    Enclosures: [["EnclosurePermitObserved", 8], ["EnclosureDecommissioned", 1]],
    Decisions: [["DecisionRegistered", 40], ["DecisionRated", 8], ["DecisionLogbookOpened", 3],
           ["DecisionDebriefRequested", 1]],
    Other: [["ActorRegistered", 3], ["CalibrationRecorded", 4], ["AllocationGranted", 2]],
  };
  var LANE_WEIGHT = { Runs: 47, Decisions: 44, Procedures: 2.4, Datasets: 2.2, Subjects: 1.2,
                      Enclosures: 1.1, Campaigns: 0.8, Clearances: 0.6, Other: 0.5, Cautions: 0.2 };
  var LANE_ORDER = ["Runs", "Procedures", "Subjects", "Campaigns", "Datasets",
                    "Clearances", "Cautions", "Enclosures", "Decisions", "Other"];

  // Mirrors page.html's own EVENT_TIER. Duplicated deliberately: the harness
  // must be able to disagree with the page, so a tier accidentally dropped
  // there shows up here as a failing assertion rather than as a matching
  // change on both sides.
  var TIER = {
    RunAborted: 2, ProcedureAborted: 2, CautionRegistered: 2, ClearanceExpired: 2,
    ClearanceRejected: 2, DatasetDiscarded: 2, EnclosureDecommissioned: 2,
    RunStopped: 1, RunTruncated: 1, RunResumed: 1, CampaignHeld: 1,
    SubjectDiscarded: 1, DatasetDemoted: 1, CautionRetired: 1, DecisionDebriefRequested: 1,
  };

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function pick(rng, pairs, idx) {
    var total = 0, i;
    for (i = 0; i < pairs.length; i++) total += pairs[i][idx];
    var r = rng() * total;
    for (i = 0; i < pairs.length; i++) { r -= pairs[i][idx]; if (r <= 0) return pairs[i]; }
    return pairs[pairs.length - 1];
  }

  function activityDocument(windowSec, perHour, shape, seed) {
    var rng = mulberry32(seed || 7);
    var n = Math.max(0, Math.round((perHour * windowSec) / 3600));
    if (shape === "empty") n = 0;
    if (shape === "single") n = 1;
    if (shape === "pileup") n = 14;

    var laneList = LANE_ORDER.map(function (k) { return [k, LANE_WEIGHT[k]]; });
    var byLane = {}, anchors = [], all = [];
    LANE_ORDER.forEach(function (k) { byLane[k] = []; });

    for (var i = 0; i < n; i++) {
      var t;
      if (shape === "pileup") {
        t = windowSec * 0.5 + rng() * 1.5;
      } else if (shape === "uniform") {
        t = (i / Math.max(1, n)) * windowSec;
      } else if (anchors.length && rng() < 0.62) {
        t = anchors[Math.floor(rng() * anchors.length)] + rng() * 2.2;
      } else {
        t = rng() * windowSec;
        anchors.push(t);
        if (anchors.length > 16) anchors.shift();
      }
      t = Math.max(0, Math.min(windowSec, t));
      var lane = shape === "pileup" ? "Runs" : pick(rng, laneList, 1)[0];
      var name = pick(rng, CATALOG[lane], 1)[0];
      var e = { lane: lane, name: name, t: t, tier: TIER[name] || 0 };
      byLane[lane].push(e);
      all.push(e);
    }

    var base = Date.UTC(2026, 7, 31, 14, 47, 0) - windowSec * 1000;
    var iso = function (secs) { return new Date(base + secs * 1000).toISOString(); };

    return {
      subject_lane_id: "__no_subject__",
      title: "Live activity",
      subtitle: all.length + " events",
      live: true,
      domain: { from: iso(0), to: iso(windowSec) },
      _events: all,
      lanes: LANE_ORDER.map(function (k) {
        byLane[k].sort(function (a, b) { return a.t - b.t; });
        return {
          lane_id: "domain:" + k.toLowerCase(),
          label: k,
          render: "markers",
          points: byLane[k].map(function (e) {
            return { t: iso(e.t), label: e.name, tier: e.tier };
          }),
        };
      }),
    };
  }

  /* Read the rendered SVG back. Overlap is measured from real getBBox output,
     not from the estimate the seating pass used, so a wrong advance-width
     constant surfaces as an overlap rather than hiding inside the maths. */
  function measure(stageEl, doc) {
    var svg = stageEl.querySelector("svg");
    if (!svg) return { events: 0, marks: 0, clusters: 0, labels: 0, overlaps: 0, tier2: 0, tier2Labelled: 0 };
    var labels = [].slice.call(svg.querySelectorAll("text.cs-life-label"));
    var rows = {};
    labels.forEach(function (l) {
      var b = l.getBBox();
      var y = Math.round(b.y);
      (rows[y] = rows[y] || []).push([b.x, b.x + b.width, l.textContent]);
    });
    var overlaps = 0;
    Object.keys(rows).forEach(function (y) {
      var xs = rows[y].sort(function (a, b) { return a[0] - b[0]; });
      for (var i = 1; i < xs.length; i++) if (xs[i][0] < xs[i - 1][1]) overlaps++;
    });

    var events = doc && doc._events ? doc._events : [];
    var tier2 = events.filter(function (e) { return e.tier === 2; });
    var text = labels.map(function (l) { return l.textContent; }).join(" | ");
    var tier2Labelled = 0;
    var seen = {};
    tier2.forEach(function (e) {
      if (seen[e.name]) return;
      seen[e.name] = true;
      var noun = e.lane.replace(/s$/, "");
      var short = e.name.indexOf(noun) === 0 ? e.name.slice(noun.length) : e.name;
      if (text.indexOf(short) !== -1) tier2Labelled++;
    });

    return {
      events: events.length,
      marks: svg.querySelectorAll("rect.cs-mark").length,
      clusters: svg.querySelectorAll("rect.cs-mark--cluster").length,
      labels: labels.length,
      overlaps: overlaps,
      tier2: Object.keys(seen).length,
      tier2Labelled: tier2Labelled,
    };
  }

  root.ScrubberFixtures = { activityDocument: activityDocument, measure: measure, TIER: TIER };
})(typeof window !== "undefined" ? window : globalThis);
