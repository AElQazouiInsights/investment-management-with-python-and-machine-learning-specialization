# Futures Basis, Dividends, and Implied Financing: teaching and implementation specification

## Status and purpose

Expanded curriculum specification following the user's request for accessible explanation at institutional research depth, including fitting implied financing, dividends, volatility, and related inputs. The core basis lesson is implemented in `docs/futures-basis.md`. The broader requirements below span subsequent lessons; their presence here does not imply delivery in the basis chapter.

### Agreed scope and acceptance by delivery

The later sequencing agreement takes precedence over the original combined specification below:

| Delivery | Scope and acceptance |
| --- | --- |
| Futures Basis, Dividends, and Implied Financing | Carry and date accounting; executable directional thresholds; both cash/futures funding ledgers; flat and dated implied-rate roots; identification widget; independently anchored financing/dividend recovery; quote-scaled residuals, smoothing and held-out maturity; option-parity extraction and stale-quote diagnostics; calendar P&L, sensitivity units, stress attribution, and elementary execution examples. Validate these numerical results, every chart, standalone control, and navigation. |
| The Greeks and Hedging | Systematic sensitivity derivations, units, discrete hedging, and cash accounting. |
| Spreads and Basic Option Combinations | Signed option combinations, parity boxes, fixed payments, and financing interpretation. |
| Reading the Options Market: Implied Volatility and Surfaces | Full bid/mid/ask IV inversion, vega conditioning, carry-input error, smile/surface fitting, strike and cross-maturity price consistency, and anchored staged/joint calibration. Requirements below concerning IV repricing and surface acceptance apply here. ATM total-variance differences require explicit model assumptions and are not automatically tradable forward variance. |
| Butterfly strategies, then Butterflies, Implied Distributions, and Tail Pricing | Payoff construction followed by local distribution inference, tails, truncation, and moments. Risk reversals are not statistical skewness; smile butterflies are not kurtosis. |
| Later Futures Relative Value application | Full point-in-time temporal validation, fill/latency simulation, funding renewal and forced-exit/roll studies, portfolio integration, and residual forecasting. The core lesson supplies small accounting and execution examples, not an implemented trading backtest. |

The current basis core has 13 runnable cells and 13 charts. It compares a weighted-mid fit with a regularized fit and explains interval-distance fitting. The delivered `docs/implied-volatility-surfaces.md` extends this with a bounded volatility surface, weighted-mid/interval/prior comparisons, and a small jointly fitted forward, discount factor, and smile anchored by independent observations. It does not infer unrestricted equity-financing and dividend curves from those option inputs. Margin-rule changes and liquidation remain scenario extensions; the implemented basis stress changes financing and dividends with the original margin rule held fixed.

**User clarification: “fitting” means listening to traded derivative prices to take the market's temperature.** The central learning question is: what volatility, dividend amounts, financing conditions, and related risk prices are embedded in the current quote set? Build the lesson around reverse-engineering those readings, with calibration serving their extraction and reconciliation. Preserve the distinction between a market-implied reading, a research forecast, and an executable trade.

The core lesson precedes The Greeks and Hedging. Readers already have Forward Contracts, Futures and Forwards Compared, Options and Replication, and Deriving and Using Black–Scholes. Introduce any additional derivative, regression, or numerical method beside a small worked example rather than assuming the later Greeks or machine-learning lessons.

The full subject has three connected layers: pricing from contractual cash flows; calibration from market observations; and executable trading/accounting. Every layer needs the complete teaching cycle in `TEACHING_GUIDE.md`. Plain language must preserve the financial and numerical reasoning.

Use `docs/futures-basis.md` for the core lesson, with a descriptive URL and named references. Preserve the linked route and apply the acceptance criteria below to the corresponding delivery in the scope table. Advanced statistical trading and execution research remains a subsequent application rather than a prerequisite for understanding the core calculations.

## Questions a reader must be able to answer

1. What exactly is being bought, sold, financed, received, or settled, and on what date?
2. Which input is observed, forecast, calibrated, or selected by the researcher?
3. Which parameters do the available quotes identify, and which remain dependent on assumptions?
4. Is a fitted price inside the executable quote interval, and is its fit stable?
5. What trade captures the proposed discrepancy, and what cash flows and exposures remain?
6. Does a reduction in model residual actually produce profit after changes in fair value, funding, and execution?

## Contract and data conventions

- Begin with a small invented price index and a replicating basket. An index level is not itself a purchasable asset. Show share quantities, divisor, basket currency value, contract multiplier, and the conversion between index points and currency P&L.
- Use one clearly specified price-index convention for the principal examples. Explain why reinvested-performance indices such as the headline DAX require different dividend treatment. Distinguish price, gross-return, and net-return indices and verify the exact contract underlying.
- A private agreement to buy apples later illustrates a forward. Recall clearing, daily settlement, and collateral when moving to futures.
- Define basis as futures minus spot throughout. Distinguish basis, model residual, calendar spread, and executable edge.
- Define valuation time, expiry, settlement reference, day-count convention, calendars, units, and compounding. Retain the existing distinction between effective annual and continuous rates.
- Distinguish dividend announcement time, ex-date, record date, and payment date. The ex-date determines entitlement; the payment date determines cash availability. Account explicitly for entitlements whose payments occur after futures expiry. Identify ordinary/special dividends, index adjustments, applicable tax conventions, and corporate actions rather than assuming all payments reduce the index identically.
- Label source timestamps and bid/ask prices. Explain stale or asynchronous basket/futures quotes, cash-market closures, settlement-index differences, crossed quotes, missing observations, and incorrect multipliers.
- Use synthetic, reproducible quote snapshots and point-in-time revisions for the teaching experiments. Any historical extension needs stated provenance, availability dates, licensing, and reproducible inputs.

## Layer one: explain and reproduce the pricing economics

### Basis and cost of carry

Start with money borrowed to buy a basket, dividends received, and debt repaid. Derive the continuous-yield formula only after the cash-flow intuition. Explain that a continuous yield is a model convention, not an assertion that companies pay continuously.

Then derive the dated-dividend expression using a deterministic common financing curve and known payments. Work through at least two dividends at different dates and a non-flat curve. Show the discount-factor ratios, not only an opaque pricing helper. Extend the calculation carefully to ex-date entitlement and a later payment date.

State when the model is a replication benchmark and when substituting forecasts produces only a conditional valuation. Recall the assumptions permitting forward/futures quote equality. Settlement funding must remain visible even when the quoted fair prices agree.

### Financing curves and execution bands

Teach OIS discounting, secured equity financing/repo, unsecured borrowing, stock-loan fees, short-sale rebates, collateral remuneration, and haircut funding as distinct economic quantities. Identify which are used by each actual account. Desk funding costs can differ across trade directions; a private funding curve is not automatically a universal market discount curve.

Use executable cash-basket ask/futures bid for cash-and-carry, and cash-basket bid/futures ask for reverse cash-and-carry. Derive separate cost-adjusted entry thresholds with borrowing/lending and shorting assumptions. Show why costs and financing frictions generate a band rather than a single universally tradable price.

Provide long-cash/short-futures and short-cash/long-futures dated ledgers. Include dividends or manufactured dividend payments, financing, variation margin, collateral, fees, and liquidation. Separate margin principal from its financing expense. Explain ordinary fixed-quantity futures hedges versus any idealized tailed hedge used to obtain an exact terminal financing identity. Avoid declaring the fixed-quantity terminal price difference a path-independent locked futures profit.

### Inversion and calendar spreads

First invert a single flat-rate example by hand, comparing simple, effective, and continuous quotations. Then solve the full dated-dividend equation by a bracketed numerical root finder with visible bounds, residual checks, and a clear failure result when no admissible root exists.

For S=5,000, F=5,040, T=0.25 years and 30 dividend points paid at expiry, the simple implied rate is 5.6%; the continuous rate is log(5,070/5,000)/0.25 = 5.561162%. Comparing the latter with a 4% continuous financing quote gives 156.1162 basis points, not 160.

Derive the P&L of long-near/short-far futures before discussing residual mean reversion. For equal multipliers M and unchanged quantities, with C=F_far−F_near=C_fair+epsilon, undiscounted settlement P&L over a common holding interval is −M(Delta C_fair+Delta epsilon). Put dated settlements on a common date separately to include funding.

Work the counterexample in which epsilon falls by eight points but C_fair rises by ten: the position loses two points times its multiplier before costs. Define the holding horizon and exit/roll before the near contract expires. A calendar spread between distinct expiries does not have a generic obligation to converge to zero.

Calculate spot sensitivity and multiplier-adjusted hedge quantities, rather than assuming one contract against one contract is exactly neutral. Calculate financing and dividend sensitivities with units and direct repricing checks.

## Layer two: identify and fit the market inputs

### Read the market: an implied-input dashboard

Introduce inverse pricing in everyday terms: a known thermometer converts its reading into temperature; a derivative pricing relationship converts a quote into an implied quantity conditional on the other inputs. Unlike a physical thermometer, several economic inputs can move the same quote. Explain this limitation with the financing/dividend example below before presenting a multi-panel dashboard.

Each panel must show the source contracts, as-of time, units, maturity or dividend period, bid/ask-derived range, conditioning assumptions, and repricing residual:

- **Volatility:** option-implied levels, skew, and term structure conditional on the forward, discount curve, exercise style, and settlement. Price both sides of the quote; distinguish an IV range from a physical volatility forecast.
- **Dividends:** prices of appropriately matched dividend derivatives, plus dividend amounts inferred from futures/options when financing is independently anchored. Show period and tax/index conventions. Annual dividend contracts do not directly reveal a quarterly ex-date schedule.
- **Equity financing/repo:** carry implied by futures given the dividend input, compared with independent funding observations. Call it an implied financing rate under those assumptions, not an observed repo quote.
- **Option-implied forward and discounting:** matched European call/put pairs and fixed-payment parity combinations. Identify the option discount rate separately from equity financing or the desk's borrowing cost.
- **Relative pricing:** futures-basis and calendar residuals relative to an explicitly selected benchmark; executable bid/ask distances and freshness flags. These are price differences, not automatically expected alpha.
- **Subsequent extensions:** event-related option pricing, risk-neutral distribution/tail diagnostics, and index-versus-constituent implied dependence, each with additional instrument requirements and its own derivation. Do not treat these quantities as interchangeable with historical risk statistics.

Use two timestamped synthetic market snapshots to show changes in the readings. Explain what is directly observed and what was held fixed when attributing each change. A futures price increase alone does not tell us whether financing rose or expected dividends fell; additional instruments or anchors are required. A smile change can reflect carry-input error, liquidity, or an actual change in option relative prices.

The culmination is a market-implied diagnostic report that reproduces its source quotes. Trade construction follows from that report as a separate financial decision requiring forecasts, execution, and funding accounting.

### Explain identification before optimization

Fitting means choosing model inputs to reproduce observations under specified assumptions. A solver finding a small residual is not evidence of unique or economically correct inputs.

With one dividend at expiry, F=S exp(rT)−D. For S=5,000, F=5,040 and T=0.25, continuous rates of 4%, 5%, and 6% require dividends of approximately 10.250835, 22.892258, and 35.565323 points, respectively. All three combinations reproduce the same futures quote. Plot the entire compatible rate/dividend curve and verify each point by repricing.

One futures term structure cannot independently identify an unrestricted financing curve and unrestricted dividend schedule. The identity q_eff=r−log(F/S)/T is an aggregate continuous-yield representation conditional on r; it does not recover individual dividend dates or amounts.

### Market-input map

| Quantity | Candidate observations | Identification limits |
| --- | --- | --- |
| Cash basket and spot | Synchronized constituent quotes and index methodology | Basket execution and the published index level differ; index changes and stale observations matter |
| Benchmark discount curve | Appropriate collateral/rate instruments | Instrument conventions and collateral basis must match; benchmark rates are not automatically desk repo |
| Equity financing curve/spread | Repo quotes, futures with independently anchored dividends, relevant total-return financing instruments | Financing inferred from futures inherits dividend error and contract basis |
| Dividend expectations by bucket | Announcements, point-in-time estimates, dividend futures/swaps where available | Physical forecasts, pricing-measure expectations, and listed dividend contract definitions differ |
| Option-implied forward and discount factor | European call/put pairs with common expiry and settlement | Requires synchronized comparable contracts; forward and discount estimates are sensitive to quote noise and strike coverage |
| Implied volatility | Option bid/ask with specified forward and discount inputs | Wrong carry inputs distort inferred volatility; low price sensitivity makes inversion unstable |
| Borrow and funding frictions | Actual stock-loan and financing observations | Do not identify these separately by allocating an unexplained pricing residual to arbitrary cost labels |

Dividend futures generally settle on a defined accrual period, not an arbitrary near/far futures interval. Hedge the correct dividend bucket, multiplier, and eligible distributions. Any remaining timing or tax mismatch is an exposure. Market-implied dividend prices are not automatically unbiased real-world dividend forecasts.

### Option parity and forward extraction

For comparable European options under a specified deterministic discount/carry model, use C(K,T)−P(K,T)=P_d(0,T)[F(0,T)−K]. Derive the intercept and slope with two strikes first, then fit across several strikes using bid/ask-aware diagnostics. P_d is a discount factor, not a put price; use distinct notation in prose and code.

The slope identifies −P_d and the intercept identifies P_d F in the idealized model. The recovered option discount factor must not be relabeled equity repo when funding/discount conventions differ. Futures/forward equality also requires the earlier deterministic-rate assumptions or an explicitly modeled adjustment.

A consistent synthetic illustration uses S=5,000, T=0.25, r=4%, 30 known dividend points at expiry, F=5,020.250835, P_d=0.990049834, and flat Black implied volatility 20%. At strikes 4,900 and 5,100, call-minus-put is approximately 119.054320 and −78.955647 points. Their difference divided by 200 recovers the discount factor; either observation then recovers F. At strike 5,000, the call is approximately 207.989968 and the put 187.940632 points.

These are synthetic forward-Black quotes under the stated parameterization. A flat forward-Black volatility specification is not derived here as an exact stock-GBM model with fixed cash dividend jumps. Explain the pricing parameterization and its assumptions.

Show how a stale put quote or a single incompatible settlement contract distorts the fit. Screen model-price differences against bid/ask intervals. Introduce parity boxes as differences of call-minus-put positions, deriving their fixed terminal payment before discussing their financing interpretation. Full option-combination construction remains in the subsequent spreads lesson.

### Financing-curve calibration

Start with independent dividend assumptions and fit a parsimonious financing curve to several maturities. Represent discount factors as exponentials of integrated piecewise-constant forward rates, ensuring positive discount factors and P(0,0)=1. Positive discount factors do not require nonnegative interest rates or a monotonically decreasing discount curve in all environments.

Explain why an independently inverted flat rate at each maturity is a zero-equivalent rate, not automatically a forward financing rate between maturities. Derive the between-maturity rate from discount-factor ratios. Introduce interpolation and curve smoothness with worked numbers, then expose the effect of the choice on intermediate prices.

### Dividend calibration

With financing anchored, invert for aggregate dividends, then fit a dated/bucketed schedule using only as many independent parameters as the data support. Show how a prior forecast allocates an otherwise unidentified aggregate across dates. Fit bounds and event constraints should match the contract; do not invent negative ordinary dividends merely to absorb stale quotes.

Compare historical/analyst forecasts, announced payments, and market-implied amounts, explaining information dates, risk premia, and measurement error. Change a dividend forecast and show the corresponding change in inferred financing. Separate an input revision from an observed trading gain.

### Implied volatility and smile fitting

Using the calibrated forward and discount factor, invert the European forward-Black call or put price. Check intrinsic and upper bounds, maturity, input positivity, and whether an admissible root can be bracketed. At expiry there is no unique implied volatility; quotes outside model bounds must not be silently clipped into an answer.

Reprice every recovered volatility. Explain vega as price sensitivity to volatility before using it to diagnose conditioning. In the synthetic at-the-money illustration above, vega is approximately 987.386534 index points per unit volatility, or 9.873865 points per one percentage-point volatility change. A 0.5-point half-spread corresponds locally to about 0.05064 volatility percentage points. This is a quote-resolution diagnostic, not a statistical confidence interval.

Invert bid and ask where admissible to obtain quote-consistent volatility ranges. Compare price-space residuals and volatility-space residuals. Demonstrate that a wrong forward can create apparent strike-dependent volatility differences.

Progress from flat volatility to a smile over log-moneyness log(K/F), then total variance sigma^2 T across maturities. Explain each coordinate numerically. Avoid unconstrained polynomial extrapolation. Validate call-price bounds, strike monotonicity, strike convexity, and cross-maturity consistency under the chosen carry/dividend model. A smooth-looking volatility plot alone does not establish absence of arbitrage. Any parametric surface extension must document its parameter restrictions and validation; it must not be presented as a complete institutional surface merely because optimization converged.

### Staged and joint calibration

Implement and compare a staged baseline: aligned inputs → discount/forward checks → financing or dividends conditional on independent anchors → volatility inversion → repricing diagnostics.

Then introduce a small joint fit whose parameter count is supportable by independent observations. Use quote-width scaling, sensible numerical floors, bounds, and explicit smoothness/prior penalties. Explain that prices inside a bid/ask interval can all be consistent with the observation; fitting every mid exactly is not a necessary goal.

Derive a least-squares example by hand before using a solver. Show the residual vector, objective components, parameter scaling, initial values, and convergence result. Compare weighted mid fitting with a bid/ask interval-distance objective. Report market fit and prior/regularization penalty separately.

Compute the sensitivity matrix of model prices to parameters, singular values/rank, and condition diagnostics on a small numerical example. Explain the meanings before displaying them. Regularization can select one point from an underidentified family; it does not create market information. Quote-feasible parameter ranges and sensitivity scenarios must not be labeled statistical confidence intervals without a statistical model.

Use held-out maturities/strikes for cross-sectional validation and later snapshots for temporal validation. Preserve a truly unchanged test set when choosing smoothness strength or other settings. Independent evidence must anchor joint funding/dividend estimates; adding option parity observations that only repeat the same forward does not resolve their decomposition.

## Layer three: translate calibration into decisions

### Trade ledger and attribution

Compare fair values, market mids, executable entry/exit prices, and realized settlements. Report currency P&L, committed capital, margin, and borrowing explicitly. A zero-entry-value futures position has no meaningful percentage return on its contract value.

Attribute scenario/revaluation changes to spot, financing, dividend revisions, volatility where relevant, passage of time, and residual repricing. Explain the order dependence of sequential attribution and retain an interaction/remainder term; check that the parts reconcile to total change.

Avoid double-counting financing included in the carry model and again as an incremental cost. Distinguish actual cash expenses from risk or capital-allocation penalties. A cost-adjusted expected profit and a penalized optimizer objective are different outputs.

Stress synchronized dividend cuts, financing/borrow spread changes, cash/futures liquidity deterioration, increased initial margin, and adverse variation margin. Reconcile both terminal P&L and peak cash need. Explain which outcomes are pricing scenarios and which are forecasts, without calling either a guaranteed strategy return.

### Two execution horizons

Provide separate worked cases sharing the pricing inputs:

- Intraday: timestamp alignment, stale-quote rejection, executable basket/spread, quote lifetime, queue/fill assumptions, partial fills, adverse selection, latency, fees, and temporary exposure. Mid-price bars cannot validate a high-frequency execution strategy.
- Days/weeks: point-in-time dividend/funding revisions, roll schedule, carry, borrow renewal, collateral requirements, portfolio exposures, costs, and walk-forward evaluation.

A listed calendar-spread execution may reduce legging risk but does not erase spread risk, liquidity limits, or residual exposure. Explain these mechanisms through a small fill ledger rather than only a warning list.

The later Futures Relative Value application can add residual forecasting, an elementary AR(1)/OU relationship with estimated half-life, regime diagnostics, then Kalman filtering or regime models if justified by held-out evidence. Name the economic meaning and units of every predictor. An attractive z-score alone is not expected currency P&L.

## Experiments and worked exercises

Required demonstrations across the mapped curriculum include (volatility experiments 7–8 belong to the surface lesson; full joint-fit and execution research extensions follow their prerequisites):

1. Change dividend date while keeping amount fixed; reconcile financing effects.
2. Compare both executable carry directions and the no-trade band.
3. Reconcile an interim margin call with terminal profit and peak financing need.
4. Produce several financing/dividend pairs with identical futures prices.
5. Recover known synthetic curve/dividend inputs when independent anchors are supplied.
6. Contaminate an option quote and diagnose parity inconsistency.
7. Invert option bid/mid/ask into volatility ranges and reprice all three.
8. Perturb the assumed forward and observe changed implied volatilities.
9. Compare an underidentified joint fit with an anchored fit and report diagnostics.
10. Obtain residual convergence with a losing calendar position; reconcile the loss.
11. Compare a clean pricing signal with a stale or partially filled intraday signal.
12. Complete a worked calibration-and-trade case with exact budget, cost, and scenario checks.

Every experiment has a stated prediction, a numerical result, an explained chart, and an interpretation. Selected controls must run independently, use high-contrast colors/markers, and preserve unrelated editor output. Most first calculations remain visible rather than hidden in toolkit helpers.

## Acceptance and integration

Apply each criterion to its mapped delivery above. The basis chapter's numerical acceptance covers carry, financing/dividend inversion, parity, calibration diagnostics, funding ledgers, and position attribution; volatility-surface and distribution tests accompany their later implementations.

- Verify closed-form cases, discount-factor ratios, implied-rate roots, parity extraction, calibration identifiability, synthetic recovery, quote bounds, implied-volatility repricing, and sensitivity units with independent checks.
- Verify each cash ledger and P&L attribution, including signs, dividends, short-sale payments, settlement timing, funding, and contract multipliers. Avoid tests that only repeat the implementation.
- Include malformed/misaligned/expired quote examples with explained outcomes, and exact deterministic limits where appropriate.
- Reconcile every chart/table with its calculation; execute all cells in order and selected widgets from a fresh session.
- Follow the established sequential production build, Chromium/Firefox audits, mobile/desktop geometry and screenshots, internal links, commit/push, and deployed-preview verification workflow.
- Update overview, sidebar, README, audit registry, and direct transitions only when lessons are delivered. Preserve existing published URLs and anchors.
- Cross-link the portfolio convention review, factor/covariance methods, and self-financing cost treatment by chapter name. Add calibration findings to `COURSE_CONSISTENCY_REVIEW.md` when implemented.

## Source curation

Use exchange specifications and index methodology for actual products; use dated primary research only for institutional context. Do not imply knowledge of named funds' proprietary models or profitability.

- Federal Reserve, *Decomposing Hedge Funds' U.S. Treasury Exposures*, June 22, 2026: https://www.federalreserve.gov/econres/notes/feds-notes/decomposing-hedge-funds-u-s-treasury-exposures-20260622.html. The approximate $830 billion estimate refers to Treasury basis positions in September 2025 and 35% of sampled large hedge funds' long Treasury exposures. It is not equity-index basis volume or strategy profit.
- Eurex EURO STOXX 50 futures specifications: https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Futures-160088.
- Eurex EURO STOXX 50 dividend futures specifications: https://www.eurex.com/ex-en/markets/did/eqt-idx-div-fut/EURO-STOXX-50-Index-Dividend-Futures-946316.
- STOXX DAX calculation methodology: https://www.stoxx.com/document/Indices/Common/Indexguide/DAX_Equity_Calculation_Guide.pdf.
- CME, *Understanding Stock Index Futures*: https://www.cmegroup.com/content/dam/cmegroup/education/files/understanding-stock-index-futures.pdf.

Verify the applicable contract version, dividend period, settlement terms, and data date during lesson implementation. Treasury delivery options, cheapest-to-deliver selection, and conversion factors require a distinct treatment and must not be collapsed into the equity-index model.
