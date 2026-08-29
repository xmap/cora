# Frontend

For implementers picking the browser-side runtime.

## What actually shipped first, and why it isn't the pick below

The first browser-facing surface, `infra/status-relay/page.html` (the live
2-BM status page; see `docs/stack/deployment.md#live-status-feed`), is one
static HTML file with a `<script>` tag, no framework, no build step. It gets
its data from a live WebSocket the relay pushes to, renders a handful of
tables, and that's it. A second file, `infra/status-relay/scrubber.js`
(copy-and-adapted from the paper demo's `docs/javascripts/scrubber-demo.js`,
deliberately not shared with it), renders a rewind view fetched with a
plain `fetch()` against the relay's own REST reads rather than the live
socket. Still no framework, no build step, no bundler: two plain scripts.

`scrubber.js` itself knows nothing about Runs or any other CORA domain: it
renders a subject-neutral "timeline document" (a time domain plus a list of
marker/series lanes), so a later lens over a different kind of subject is a
server-side change, not a frontend one. Two document producers exist in
`page.html` today, both client-side adapters rather than the producer
emitting documents directly (each is expected to move server-side and
disappear eventually): `runHistoryToTimelineDocument`, bridging the still-
Run-shaped `run_history` wire payload for REWIND, and
`activityToTimelineDocument`, bucketing the relay's `"activity"` messages
into a rolling 2-hour window across seven domains plus an "Other" catch-
all, for the page's "Live activity" section. The two share the renderer via
`mount()`'s `follow` option, which pins the cursor to the live edge instead
of the start and disables replay controls that assume a closed timeline
(Play, jump-to-last), and via an `onScrub` callback the caller uses to
learn a viewer grabbed the cursor and pause its own re-rendering rather
than fight the drag.

Next.js was picked below for a real multi-page application with routing,
shared component state, and a build pipeline; this page has none of those.
Its whole surface is one route, its data arrives already pushed rather than
fetched, and a build step would mean it can't be edited on the relay host at
3am. Adopting Next.js for it would fire four of the five rows in "To be
picked" below at once, for one page: type checker, component library,
state management, and accessibility tooling all become live questions the
moment a framework is in play, none of which this page needs an answer to.

The Next.js pick stands for whenever CORA's first real multi-page
application lands (an authenticated operator console, a multi-surface
dashboard); it just isn't what shipped first, and this page is not expected
to migrate to it later, since nothing about its shape asks for a framework.

## Picks

| Role | Pick | Why |
| --- | --- | --- |
| Framework | Next.js 15 PWA | Server components, RSC + streaming, mature ecosystem. For the first REAL multi-page app; see above for why the first shipped page is not this |
| Lint + format | Biome | One tool for JS/TS; faster than ESLint + Prettier |

## To be picked

| Category | Trigger |
| --- | --- |
| Type checker | First TypeScript file lands (likely `tsc`, strict) |
| Component library | First production-bound UI surface |
| State management | First multi-component shared state |
| Testing | First component or page worth a regression test |
| Accessibility tooling | First user-facing surface |
