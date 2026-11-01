# Financial consistency review

## Scope

Reviewed the four Portfolio Management Fundamentals lessons, four Advanced Portfolio Construction and Analysis lessons and its capstone, and the delivered derivatives sequence through Deriving and Using Black–Scholes. Compared visible calculations with toolkit interfaces and executable lesson checks. This review addresses financial definitions, assumptions, timing, and learning-sequence connections; the teaching guide remains the standard for subsequent lessons.

## Findings and resolutions

| Area | Finding | Resolution / evidence |
| --- | --- | --- |
| Learning route | Overviews described parallel routes without stating the approved recommended order. | Overviews now consistently recommend fundamentals → derivatives → advanced portfolios, while explaining that allocation readers can enter the advanced course directly. |
| Named references | Portfolio overviews and the ALM exit still used course-number link labels. | Replaced with names; delivered derivatives transitions lead directly to Black–Scholes. |
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
| Discrete trading | CPPI can breach floors; duration matching is local; frictionless continuous option replication does not imply exact finite-grid hedging. | Nested-path stock/futures experiments preserve the accounting identity while showing nonzero hedge residuals. The next Greeks lesson will extend sensitivity and trading-frequency analysis. |

## Validation record

Validation commands and results are recorded in `DERIVATIVES_ROADMAP.md` with this delivery. The new scientific checks independently integrate lognormal payoffs, use finite differences to verify delta and the PDE, verify global discounted-gains identities for both hedge implementations, and reconcile the portfolio helper conventions. Existing lesson and core suites cover historical examples, covariance, Black–Litterman, risk budgets, CPPI, GBM, CIR, rates, and liability hedges.
