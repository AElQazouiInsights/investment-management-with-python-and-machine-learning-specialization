# Derivatives track: implementation roadmap

## Placement and priority

Approved sequence: Portfolio Fundamentals → **Derivatives, Options, and Structured Products** → Advanced Portfolio Construction → Machine Learning → Alternative Data. Use D.x for the supplementary track so the four course numbers retain their syllabus mapping. The homepage, sidebar, and Course 1 transitions introduce the new route.

This track is the immediate development priority. Resume Course 3.2 after the derivatives capstone. Follow `TEACHING_GUIDE.md` for every concept: everyday explanation → numbers → worked calculation → explained graph → Python → experiment → exercise with feedback.

## Delivery sequence

| Chapter | Status | Core calculation and experiment |
| --- | --- | --- |
| D.0 — Overview | Delivered | Prerequisites, reading order, and explicit status of each planned chapter |
| D.1 — Forward Contracts | Delivered | Zero-initial-value delivery price, long/short payoffs, both arbitrage directions, existing-contract valuation, and purchase hedge; one current-spot slider |
| D.2 — Futures and Forwards Compared | Next | Same underlying/quantity/maturity as D.1; daily settlement ledger, margin collateral, cash requirements, and forward/futures pricing assumptions |
| D.3 — Options and Replication | Planned | Calls/puts, premiums, payoff versus financed profit, put–call parity, and two-state replication |
| D.4 — Random Motion and Itô's Lemma | Planned | Small curvature example, derivatives and Taylor expansion, Brownian increments/quadratic variation, Itô derivation, and log-price application |
| D.5 — Deriving and Using Black–Scholes | Planned | Self-financing hedge, PDE, pricing-distribution expectation, normal integrals, call/put prices, parity, and dynamic futures hedging |
| D.6 — The Greeks and Hedging | Planned | Finite-difference intuition followed by delta/gamma/theta/vega/rho formulas; units and discrete hedging with a reconciled cash account |
| D.7 — Spreads and Basic Option Combinations | Planned | Bull/bear spreads, covered calls, protective puts, and collars; signed prices, payoff regions, break-even points, and aggregate Greeks |
| D.8 — Straddles, Strangles, Butterflies, and Condors | Planned | Leg-by-leg construction, theoretical value, financed profit, strike spacing, and pre-expiry sensitivity |
| D.9 — Building Structured Products | Planned | Funding plus option budget, participation rates, caps, income enhancement with downside exposure, and issuer/early-sale implications |
| D.10 — Design, Price, and Explain a Product | Planned | Reconciled initial budget, dated cash flows, payoff table, graphs, Greeks, scenarios, and plain-language investor explanation |

Only delivered chapters receive sidebar links. Planned descriptions live in `docs/d.0-overview.md`. D.1 ends at its stable `#futures` anchor until D.2 has its own page.

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

Use the existing VitePress presentation, browser-run Pyodide, ECharts, and selective ipywidgets. Keep small calculations visible in lesson cells. Helpers are for justified reuse or allowlisted callbacks and must match all six toolkit copies. No new runtime packages are needed for D.1.

For each delivered chapter:

1. Execute every Python cell in order. Test independent worked answers, replication identities, signs, quantities, dates, rate conventions, and financial limits relevant to the lesson.
2. Reconcile tables and chart series. Verify widget endpoints, meaningful intermediate values, standalone execution, and isolation from other cells.
3. Build and run Chromium/Firefox audits with off-site requests blocked; check mathematical rendering, links, and charts at 1920, 1440, 390, and 320 pixels. Inspect screenshots.
4. Separately measure axis/legend geometry and rendered series against the dev server. Check homepage and navigation at intermediate widths when adding the track.
5. Update overview/status, README, sidebar, and audit registry. Push reviewed source to `uat` and verify the deployed preview.

## D.0–D.1 validation

- Production build passed. Ten forward-example tests, three existing widget-serialization tests, and all 36 JavaScript tests passed.
- Chromium 156.0.8078.4 and Firefox 157.0 executed all eight D.1 cells and displayed all six charts with off-site requests blocked. The independent widget ran before setup and passed spot-price endpoint/intermediate updates without changing other outputs.
- Both browsers passed measured dev-server axis/legend bounds, mixed-series reconciliation, money tooltip checks, and fixed-contract-term checks. Chapter chart layouts passed at 1920, 1440, 390, and 320 pixels; D.0 also passed both browsers' page-layout audits.
- Homepage and navigation checks covered widths from 320 to 1920 pixels, including intermediate desktop/tablet widths. Desktop/light and mobile/dark screenshots were inspected. All 255 internal links on the homepage, Course 1 overview, ALM chapter, and two new pages resolved, including the next-topic anchor.
