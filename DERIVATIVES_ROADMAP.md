# Derivatives track: implementation roadmap

## Placement and priority

Approved sequence: Portfolio Fundamentals → **Derivatives, Options, and Structured Products** → Advanced Portfolio Construction → Machine Learning → Alternative Data. The derivatives track uses chapter names without a separate letter-prefixed numbering scheme. Cross-chapter references use names, not chapter numbers. The homepage, sidebar, and Portfolio Fundamentals transitions introduce the route.

This track is the immediate development priority. Resume Robust Estimation of Factor Models after the derivatives capstone. Follow `TEACHING_GUIDE.md` for every concept: everyday explanation → numbers → worked calculation → explained graph → Python → experiment → exercise with feedback.

## Delivery sequence

| Chapter | Status | Core calculation and experiment |
| --- | --- | --- |
| Overview | Delivered | Prerequisites, reading order, and explicit status of each planned chapter |
| Forward Contracts | Delivered | Zero-initial-value delivery price, long/short payoffs, both arbitrage directions, existing-contract valuation, and purchase hedge; one current-spot slider |
| Futures and Forwards Compared | Delivered | Same underlying/quantity/maturity as the forward example; daily settlement ledger, margin collateral, cash requirements, funding, and deterministic-rate replication |
| Options and Replication | Delivered | Calls/puts, premiums, payoff versus financed profit, put–call parity, price bounds, pricing weights, and two-state replication |
| Random Motion and Itô's Lemma | Delivered | Curvature, derivatives and Taylor expansion, Brownian increments, nested-grid quadratic variation, Itô derivation, and log-price application |
| Deriving and Using Black–Scholes | Delivered | Self-financing hedge, PDE, pricing-distribution expectation, normal integrals, call/put prices, parity, and explicit stock/futures hedge ledgers |
| The Greeks and Hedging | Next | Finite-difference intuition followed by delta/gamma/theta/vega/rho formulas; units and discrete hedging with a reconciled cash account |
| Spreads and Basic Option Combinations | Planned | Bull/bear spreads, covered calls, protective puts, and collars; signed prices, payoff regions, break-even points, and aggregate Greeks |
| Straddles, Strangles, Butterflies, and Condors | Planned | Leg-by-leg construction, theoretical value, financed profit, strike spacing, and pre-expiry sensitivity |
| Building Structured Products | Planned | Funding plus option budget, participation rates, caps, income enhancement with downside exposure, and issuer/early-sale implications |
| Design, Price, and Explain a Product | Planned | Reconciled initial budget, dated cash flows, payoff table, graphs, Greeks, scenarios, and plain-language investor explanation |

Only delivered chapters receive sidebar links. Planned descriptions live in `docs/d.0-overview.md`. Delivered chapters link directly to the next available lesson; Deriving and Using Black–Scholes links to the stable `#greeks` overview anchor until that lesson is delivered. Existing forward/futures/options URLs and overview anchors remain valid; new lessons use descriptive URLs such as `/random-motion-ito` and `/black-scholes`.

## Financial and teaching conventions

- Begin with GBP, quantities, exact payment dates or elapsed years, and effective annual rates in decimal form. When continuous compounding is introduced, derive the conversion rather than silently changing rate conventions.
- Distinguish spot, a fair quote for a new contract, the fixed terms of an old contract, its current value, and its terminal payoff. An initial zero value does not eliminate future obligations.
- Forwards and futures need separate dated cash-flow ledgers. Distinguish collateral from premium and specify treatment of margin interest and funding. Do not describe every real forward as uncollateralized or every contract as physically settled.
- State the conditions behind forward/futures quote equality, replication, and pricing measures. Futures daily settlement and stochastic-rate effects must not be hidden by identical terminal-payoff diagrams.
- Introduce calculus in small numerical steps before deriving Itô and Black–Scholes. Explain quadratic variation and self-financing rebalancing; do not drop rebalancing cash flows when differentiating a hedge.
- Separate real-world distributions, pricing distributions, and implied inputs. Explain why eliminating drift from a pricing equation does not make a return forecast unnecessary for every investment decision.
- Name Greek units and signs. Theta needs a time-direction/day-count convention; vega and rho need a stated input increment. Check price changes directly as well as with approximations.
- Teach option combinations before funded notes. Sum signed legs with consistent quantities, multipliers, maturities, underlying, volatility, and rate conventions. Distinguish theoretical mid-model values from executable bid/ask costs.
- Compare prices today, payments at maturity, and financed profit at a common date. Explain each condition attached to a structured payoff in the example itself.

## Implementation and acceptance

Use the existing VitePress presentation, browser-run Pyodide, ECharts, and selective ipywidgets. Keep small calculations visible in lesson cells. Helpers are for justified reuse or allowlisted callbacks and must match all six toolkit copies. The delivered derivatives lessons use the existing runtime packages.

For each delivered chapter:

1. Execute every Python cell in order. Test independent worked answers, replication identities, signs, quantities, dates, rate conventions, and financial limits relevant to the lesson.
2. Reconcile tables and chart series. Verify widget endpoints, meaningful intermediate values, standalone execution, and isolation from other cells.
3. Build and run Chromium/Firefox audits with off-site requests blocked; check mathematical rendering, links, and charts at 1920, 1440, 390, and 320 pixels. Inspect screenshots.
4. Separately measure axis/legend geometry and rendered series against the dev server. Check homepage and navigation at intermediate widths when adding the track.
5. Update overview/status, README, sidebar, and audit registry. Push reviewed source to `uat` and verify the deployed preview.

## Overview and Forward Contracts validation

- Production build passed. Ten forward-example tests, three existing widget-serialization tests, and all 36 JavaScript tests passed.
- Chromium 156.0.8078.4 and Firefox 157.0 executed all eight Forward Contracts cells and displayed all six charts with off-site requests blocked. The independent widget ran before setup and passed spot-price endpoint/intermediate updates without changing other outputs.
- Both browsers passed measured dev-server axis/legend bounds, mixed-series reconciliation, money tooltip checks, and fixed-contract-term checks. Chapter chart layouts passed at 1920, 1440, 390, and 320 pixels; the track overview also passed both browsers' page-layout audits.
- Homepage and navigation checks covered widths from 320 to 1920 pixels, including intermediate desktop/tablet widths. Desktop/light and mobile/dark screenshots were inspected. All 255 internal links on the homepage, Course 1 overview, ALM chapter, and two new pages resolved, including the next-topic anchor.

## Futures and Forwards Compared validation

- Production build passed. Twelve futures tests, ten forward-example regression tests, three widget-serialization tests, and all 36 JavaScript tests passed. Checks include exact maintenance boundaries, long/short cash conservation, negative final close-out transfers, losses exceeding initial margin, all 16 slider settings, dated funding, ideal tailing, and six-copy helper parity.
- Chromium 156.0.8078.4 and Firefox 157.0 each ran all nine cells and rendered eight charts with off-origin requests blocked. The widget ran independently before setup, then passed repeated zero/intermediate/deep-drop updates while preserving other outputs.
- Separate dev-server audits passed axis/legend bounds, rendered series, step timing, cash units, and widget updates at 1920, 1440, 390, and 320 pixels in both browsers. Desktop/light, mobile/dark, and chart screenshots were inspected. All 155 internal links on the homepage and derivatives pages resolved; the `#options` next-topic transition and overview-to-futures navigation were checked in the browser.

## Options and Replication validation

- Production build passed. Eleven option-example tests, ten forward-example regression tests, and all 36 JavaScript tests passed. Numerical checks cover signed initial funding, both state replications, financed break-even points, pricing weights versus forecasts, all-price parity, bounds, changed-strike/up-state exercises, all 81 widget settings, and six-copy helper parity.
- Chromium and Firefox each executed all ten cells and rendered eleven charts with off-origin requests blocked. Independent widget execution, zero/maximum final prices, both fractional break-even points, strike crossing, fixed premiums, and other-output isolation passed. Dev-server audits measured axes, legends, and rendered series at 1920, 1440, 390, and 320 pixels in both browsers. Desktop/light, mobile/dark, and chart screenshots were inspected; 206 internal links across the homepage and derivatives pages resolved.
- Navigation with a mounted widget exposed a Lumino detach error: Vue had already disconnected its DOM before `onUnmounted` removed the view. Cleanup now runs in `onBeforeUnmount`. Both final-build browser audits left the options lesson for the Itô overview anchor, returned without reloading, and created one working slider with the shared worker; no browser or Python errors occurred. The full shared-widget browser regression also passed, including saved code, storage failures, input/interruption, runtime failures/retry, and existing chart controls.
- The standalone options widget uses high-contrast outlined payoff/profit markers. The requested forward spot-marker contrast improvement was included with that delivery.

## Random Motion and Itô's Lemma validation

- Twelve scientific-example tests and all 36 JavaScript tests passed. Checks cover curvature scaling, nested sample preservation, normal second/fourth moments, exact discrete left-endpoint and midpoint identities, conditional transformation expectations, zero/doubled diffusion limits, log-price solutions and Gaussian mean integration, half-year units, all nine grid settings, standalone widget serialization, and six-copy helper parity.
- Chromium and Firefox dev-server audits ran all ten cells and reconciled nine chart payloads with the worked calculations. Axes, legends, captions, and canvases fit at 1920, 1440, 390, and 320 pixels. Widget refinement preserves the sample endpoint and other editors; named-link navigation to the next-topic overview and back retains one working widget. Options and Replication also passed its full browser regression using the new direct next-chapter link.
- Production build and Chromium/Firefox execution/layout/control/navigation audits passed. Desktop/light, mobile/dark, refinement, curvature, quadratic-variation, and zoomed-price screenshots were inspected. Mathematical rendering and homepage layouts were checked separately. All 768 internal links across the 16 affected pages resolved.
- The visible derivatives sequence now uses unnumbered chapter names. Numbered cross-chapter references in the lesson Markdown were replaced with linked names, and the naming convention is recorded in `TEACHING_GUIDE.md`.

## Deriving and Using Black–Scholes and cross-course review

- Delivered 11 runnable cells and 10 charts: convention comparison, self-financing replication, PDE, pricing expectation, normal integrals, call/put prices, parity, expiry/zero-volatility limits, and explicit stock/futures hedge ledgers. Trading grids share one fine GBM path. A zero budget residual is distinguished from a nonzero hedge residual.
- All 505 Python scientific/core/lesson tests passed in the full regression suite, including 11 new Black–Scholes tests. Independent checks cover direct payoff integration, finite-difference delta/PDE, bounds and parity at negative/zero/positive rates, deterministic limits, discounted gains identities, zero-rate stock/futures equivalence, all 117 widget settings, serialization, and six-copy helper parity. All 36 JavaScript tests passed.
- Chromium and Firefox dev-server audits passed all cells, rendered chart values, control endpoints, marker contrast, output isolation, and named-link navigation. Layouts passed at 1920, 1440, 390, and 320 pixels. Production build and Chromium execution/control/navigation audit passed; Firefox also passed the Itô-to-Black–Scholes navigation regression. Desktop and mobile/dark views were inspected, including mathematical rendering and the responsive homepage/three overviews.
- All 1,208 internal links across 23 built pages resolved. Existing overview anchors remain valid, with a stable `#greeks` anchor for the next planned lesson.
- `COURSE_CONSISTENCY_REVIEW.md` records the review of fundamentals, advanced portfolios, and delivered derivatives. Existing financial formulas and helper conventions agreed. Added explicit bridges for arithmetic mean/CAGR/GBM drift, effective/continuous rates, simple-return versus diffusion volatility, price versus total-return index, physical/pricing probabilities, statistical/payoff replication, Black–Litterman views, capital weights/hedge quantities, and self-financing costs. Aligned the recommended learning route and remaining numbered course-link labels.
