# Financial consistency review

## Scope

Reviewed the four Portfolio Management Fundamentals lessons, four Advanced Portfolio Construction and Analysis lessons and its capstone, and the delivered derivatives sequence through Reading the Options Market: Implied Volatility and Surfaces. Compared visible calculations with toolkit interfaces and executable lesson checks. This review addresses financial definitions, assumptions, timing, and learning-sequence connections; the teaching guide remains the standard for subsequent lessons.

## Findings and resolutions

| Area | Finding | Resolution / evidence |
| --- | --- | --- |
| Learning route | Overviews described parallel routes without stating the approved recommended order. | Overviews now consistently recommend fundamentals → derivatives → advanced portfolios, while explaining that allocation readers can enter the advanced course directly. |
| Named references | Portfolio overviews and the ALM exit still used course-number link labels. | Replaced with names; delivered derivatives transitions now continue through Black–Scholes and basis to the Greeks lesson. |
| Arithmetic mean, CAGR, diffusion drift | Existing implementations agree, but the same symbol `mu` is used for different quantities in optimization and GBM. | Explicit local bridge and Black–Scholes comparison: drift 8%, expected annual simple return 8.3287%, annualized monthly simple mean 8.0267%, expected annual log return 6% at volatility 20%. |
| Volatility | Portfolio square-root annualization is a reporting convention; GBM sigma is an instantaneous parameter. Neither existing course claims exact finite-horizon simple-return equivalence. | Added bridge: annualized monthly simple-return SD is 20.1506% for the same GBM. Linked covariance estimation to nonlinear repricing. |
| Rate conventions | ALM present value and return-series Sharpe accept effective rates; continuous GBM/pricing uses log(1+R). Scalar Sharpe expects already matched annual inputs. | Preserved these documented interfaces; cross-course tests compare discount factors, deterministic GBM growth, and both Sharpe interfaces. No formula correction was needed. |
| Price versus total-return index | Portfolio GBM can represent a reinvested wealth index; the basic option contract is on a non-income-paying tradable asset. | Explicit warning against substituting a dividend-reinvested index for a dividend-paying share in the no-dividend formula. |
| Probability and risk | CPPI GBM uses assumed investment dynamics; CIR bond scenarios explicitly use Q. Historical VaR/ES and floor shortfall are already distinguished. | Added connections explaining why pricing probabilities and CIR scenario frequencies are not physical forecasts. Black–Scholes derives Q from replication instead of asserting that risky expected returns equal cash. |
| Statistical versus contractual replication | Style replication fits historical returns with residuals; derivative replication matches contractual payments under a model. | Added the distinction in the factor lesson and advanced overview, with a residual-volatility example. |
| Black–Litterman | Investment views and mean-uncertainty covariance are distinct from conditional/predictive return covariance; the existing chapter already labels each. | Added explicit connection: posterior expected-return views do not replace the financing rate or volatility in Black–Scholes. |
| Capital weights versus hedge units | Long-only allocation constraints do not describe the leveraged stock/cash option hedge; futures have zero marked-to-market value at reset. | Worked asset quantity, signed cash, capital-weight, futures quantity, and multiplier examples. Returns lesson now explains the zero-capital denominator problem. |
| Self-financing and costs | Advanced backtests correctly use drifted holdings and fund fees from wealth. | Connected that budget condition to stock rebalancing and futures settlement. New ledgers retain hedge error rather than reset cash to force agreement with model option value. |
| Distribution-dependent prices and parity | The two-state and lognormal models give different individual option prices at shared spot, strike, and financing inputs. | Both give call minus put = 100−100/1.05. Tests compare this identity and financed forward profit directly. |
| Discrete trading | CPPI can breach floors; duration matching is local; frictionless continuous option replication does not imply exact finite-grid hedging. | Nested-path stock/futures experiments preserve the accounting identity while showing nonzero hedge residuals. The Greeks lesson extends sensitivity analysis and compares shared-path hedge errors with funded trading costs. |

## Validation record

### Futures basis extension

- Kept continuous financing rates distinct from the portfolio toolkit's effective-rate inputs; tested the conversion used in implied-rate extraction.
- Added price/gross/net-return index and entitlement/payment-date distinctions. The dated-dividend test independently accumulates debt and values a post-expiry receivable.
- Reconciled long-cash/short-futures and reverse-carry ledgers against a global terminal cash-flow identity. Margin transfers preserve wealth; their lost interest or borrowed funding changes financed profit. A fixed-quantity futures position is not silently treated as a terminal-settled forward.
- Bootstrapped the synthetic financing curve independently from quote/dividend cash flows and recovered known dividend buckets with financing anchored. Rank, smoothing, bid/ask diagnostics, and held-out repricing remain distinct from a physical forecasting claim.
- Verified option parity without equating option discounting, equity repo, and desk borrowing. Synthetic forward-Black quotes are explicitly a quotation model rather than exact cash-dividend stock GBM.
- Checked calendar-leg revaluation and local spot/rate sensitivity units. Model-residual convergence is not equated with realized profit, consistent with the advanced course's estimation and cost accounting.

### Greeks and hedging extension

- Retained the previous Black–Scholes effective 5% / continuous log(1.05) convention. Explicitly scaled volatility points, rate basis points, calendar days, signed quantities, and option/futures multipliers.
- Differentiated continuous-yield call/put prices and checked all core, cross-, and higher-order Greeks numerically, including negative rates, positive yield, and near-expiry cases. Calendar-time charm/color/veta use the opposite sign to remaining-life derivatives.
- Decomposed classical rho into separate carry and discount bumps; retained the basis lesson's distinction between market pricing inputs and actual borrowing costs. Surface-response total delta is labeled an assumed chain-rule scenario, not a fixed-volatility partial derivative.
- Exposed the same-expiry gamma/vega rank limitation, paralleling the earlier calibration-identification lesson. A two-expiry hedge neutralizes a parallel volatility bump, not each option's independent implied-volatility change.
- Kept rebalancing costs inside the cash account and verified global discounted gains. The simulated frequency comparison uses common paths, explicit physical/pricing assumptions, and GBP hedge errors rather than returns on zero initial net wealth.

### Practical Greek interpretation revision

- Converted core and higher-order risk readings into signed 100-share-contract exposures, currency changes, and changes in other risk readings. Finite differences independently verify the scaled desk units. Cash delta is distinguished from premium and P&L for a specified percentage move.
- Added an explicit delta-neutral rebalancing example and a single-option gamma hedge before the combined hedge. Neutrality refers to one stated risk factor at current inputs; option gamma, residual vega, contract rounding, hedge expiry, and funding remain visible.
- Distinguished a future's unit sensitivity to its own quote from multiplier-adjusted spot sensitivity under fixed carry. Explained delta-one products separately from delta-neutral positions and preserved the daily-settlement cash-account interpretation.
- Inverted two different premiums into the same implied volatility under agreed contract/model/carry inputs. Separate funded delta-neutral scenarios show spot curvature, implied-volatility repricing, and time decay; realized movement and dynamic hedging P&L remain distinct from implied-volatility quotes.
- Replaced visible em dashes in published Markdown with sentence-appropriate punctuation and retained existing overview heading anchors explicitly.

### Option combinations extension

- Kept the one-share option baseline, European exercise, no-dividend share, and 5% effective / log(1.05) continuous rates. Signed instrument value plus an opposite entry cash balance reconciles every debit and credit construction; the worked collar scales both options and stock to 100 shares.
- Verified all four vertical spread payoff regions and the funded bull-call/bull-put and bear-put/bear-call equivalences at negative, zero, and positive rates. Their unfunded values and terminal payments differ by a bond, so their theta and rho need not match before including cash.
- Distinguished terminal wealth floors from financed profit floors, covered delivery from protection, and an offsetting option premium from a costless stock position. Synthetic covered calls, protective puts, and collars agree with parity at expiry, zero volatility, and zero spot as well as smooth pre-expiry inputs.
- Priced the fixed-payment European box as a discount bond, retaining calendar accrual and discount-rate sensitivity after spot and volatility exposures cancel. A hypothetical executable £9.60 debit implies a 4.1667% lending return, not a profit when borrowed funding costs 5%; entry bid/ask costs reduce the ideal box profit further.
- Independently integrated signed basket payoffs under the pricing distribution and differentiated basket values to check aggregate Greek units. A bullish spread's negative baseline gamma and parallel vega are explained separately from its positive delta; independent strike-volatility shifts remain for the next lesson.
- Reconciled early exits with elapsed financing and remaining option life. Independent bid/ask ledgers verify buy-at-ask and sell-at-bid entry costs in both directions, with fees and stock costs scaled consistently. Defined margin funding and exercise/settlement differences as additional implementation cash flows rather than free theoretical arbitrage.

### Implied volatility and surface extension

- Retained the GBP-per-share convention and 5% effective / log(1.05) continuous baseline, but made the forward and option discount factor explicit independent inputs. Forward-Black volatility remains a quotation coordinate rather than an assertion that a smile is a single constant-volatility stock process.
- Independently integrated call/put payoffs and checked inverse price/forward sensitivities. Inversion rejects expiry, nonfinite data, crossed quotes, incompatible timestamps, inadmissible premiums, and failure to bracket a finite root. Synthetic wing quote widths are constructed from admissible time value; invalid observed prices are not clipped into an IV.
- Explained fixed strike, log-forward-moneyness, undiscounted versus discounted forward delta, and the need to specify premium-adjusted conventions. A change of coordinate or assumed surface dynamics is not an observed change in premium.
- Compared weighted-mid, interval-distance, and soft prior-penalized surface fits with separate market and preference objectives. The zero-error interval plateau admits several parameter readings. The independently anchored forward/discount/smile joint fit includes moneyness changes in its analytic Jacobian and scaled-rank checks; neither anchors nor regularization are mislabeled as a financing/dividend decomposition.
- Kept held-out strikes and maturity separate from fitting and used a later synthetic snapshot with unchanged contract strikes and aged expiries. Old-model residuals are not called forecasts or realized trading P&L.
- Checked strike bounds, discounted vertical-spread slopes, convexity, and normalized calendar behavior on a stated finite domain. Calendar comparisons use fixed forward moneyness and normalized martingale payoffs under deterministic no-dividend carry. An ATM total-variance slope is not equated to a smile-aware variance-swap price or an automatically tradable forward variance.
- Distinguished a midpoint butterfly inconsistency from an executable negative-cost basket by applying the correct bid/ask side and signed quantities. Continuous interpolation, tails, alternative contract conventions, and actual funding remain separate from the finite-grid acceptance result.

Validation commands and results are recorded in `DERIVATIVES_ROADMAP.md` with this delivery. The new scientific checks independently integrate lognormal payoffs, use finite differences to verify delta and the PDE, verify global discounted-gains identities for both hedge implementations, and reconcile the portfolio helper conventions. Existing lesson and core suites cover historical examples, covariance, Black–Litterman, risk budgets, CPPI, GBM, CIR, rates, and liability hedges.
