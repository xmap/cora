# Frontend

For implementers picking the browser-side runtime.

## What actually shipped first, and why it isn't the pick below

The first browser-facing surface, `infra/status-relay/page.html` (the live
2-BM status page; see `docs/stack/deployment.md#live-status-feed`), is one
static HTML file with a `<script>` tag, no framework, no build step. It gets
its data from a live WebSocket the relay pushes to, renders a handful of
tables, and that's it.

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
