---
title: "Deriving and Using Black–Scholes"
permalink: /black-scholes
description: "Derive European option prices from a self-financing hedge, evaluate the normal integrals, and reconcile stock and futures hedge cash flows in Python."
---

# Deriving and Using Black–Scholes

**Question:** how much should we pay today for the right to buy an asset for £100 in one year, when its price can move continuously?

In [Options and Replication](./d.3-options.md), an asset holding and a cash balance reproduced an option's payment in two possible states. [Random Motion and Itô's Lemma](./random-motion-ito.md) supplied the calculus for continuously changing prices. We now join those ideas: adjust the holding as the price moves, pay for each adjustment from the cash account, and derive the initial cost of that strategy.

Our benchmark is **one European option on one unit of a non-income-paying asset**. Its current price is $S=£100$, strike is $K=£100$, and remaining life is $\tau=1$ year. European means exercise is permitted only at expiry. Prices and cash amounts are in GBP; option values are per one-unit contract. The effective annual cash rate is still $R=5\%$, so the continuous rate is $r=\log(1.05)=0.048790164$ per year. Volatility is $\sigma=0.20$ per square-root year.

Assume a frictionless market with a constant borrowing/lending rate, constant volatility, continuous trading, divisible positions, short selling, and no default. The asset follows geometric Brownian motion (GBM), without dividends. These assumptions define the replication benchmark. Our finite-grid experiments later deliberately trade only at observation dates and therefore leave hedge error.

Run cells in order. The expiry/volatility widget is also self-contained. All paths and parameters are synthetic teaching inputs.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.integrate import quad

S0, K, T, sigma = 100., 100., 1., 0.20
effective_rate = 0.05
r = np.log1p(effective_rate)
mu = 0.08
```
<Editor id="bs-setup" />

## 1. Connect the Portfolio and Pricing Conventions

The portfolio courses ask how wealth may perform. Pricing asks what a replicable contractual payment costs. Keep the inputs' meanings explicit:

| Quantity | Portfolio interpretation | Use here |
| --- | --- | --- |
| Simple return | Price change plus distributions, divided by starting capital | Our asset pays no distributions, so price and total return coincide |
| Arithmetic mean | Mean one-period simple return; often multiplied by observations per year | Not automatically the instantaneous GBM drift $\mu$ |
| CAGR | Constant annual compound growth matching a realized wealth path | Neither $\mu$ nor a guaranteed outcome |
| Volatility | Dispersion of specified returns, with a stated annualization rule | $\sigma$ is the GBM diffusion parameter |
| Cash rate | May be quoted effectively or on an annualized arithmetic basis | Convert effective $R$ to continuous $r=\log(1+R)$ |
| Probability | Historical or assumed real-world distribution, denoted $\mathbb P$ | A replication-derived pricing distribution, denoted $\mathbb Q$ |

For GBM with real-world drift $\mu=0.08$, the expected one-year simple return is $e^{0.08}-1=8.3287\%$. Expected log return is $0.08-0.20^2/2=0.06$, or 6%. The population monthly simple mean, annualized arithmetically, is $12(e^{0.08/12}-1)=8.0267\%$. These are three different summaries of the **same model**.

Likewise, the exact monthly simple-return standard deviation is $e^{\mu/12}\sqrt{e^{\sigma^2/12}-1}$. Multiplying it by $\sqrt{12}$ gives about **20.1506%**, close to but not exactly the 20% diffusion input. Historical estimates add sampling uncertainty. The exact GBM and annualization treatments in [Strategies Beyond Diversification](./1.3-diversification.md) and [Covariance Matrix Estimation for Portfolio Construction](./2.2-covariance.md) use these same distinctions.

The graph compares **mean price** under an assumed real-world drift of 8% with mean price under the pricing drift $r$. The endpoints are £108.328707 and £105. The second curve will emerge from replication; it is not a prediction that the asset earns cash. The vertical axis is price, not a percentage return.

```python:line-numbers
times = np.linspace(0., T, 101)
print(f"Effective cash rate: {effective_rate:.6%}; continuous rate: {r:.6%}")
print(f"Expected one-year simple return: {np.expm1(mu):.6%}")
print(f"Expected one-year log return: {mu - sigma**2 / 2:.6%}")
print(f"Annualized monthly simple mean: {12 * np.expm1(mu / 12):.6%}")
print(f"Annualized monthly simple SD: {np.sqrt(12) * np.exp(mu / 12) * np.sqrt(np.expm1(sigma**2 / 12)):.6%}")
print("<ECHARTS_DATA>" + json.dumps({"bsMeanConventions": {
    "type": "line", "title": "Different Distributions Answer Different Questions",
    "xAxis": {"type": "value", "name": "Elapsed time (years)"},
    "yAxisName": "Mean asset price (GBP/unit)",
    "series": {"Real-world assumption": np.column_stack([times, S0 * np.exp(mu * times)]).tolist(),
               "Pricing distribution": np.column_stack([times, S0 * np.exp(r * times)]).tolist()},
    "seriesOptions": {"Pricing distribution": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"type": "dashed", "color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="bs-conventions" />

**Experiment:** change `mu` to 0.12 and rerun this cell. The real-world curve changes; the pricing curve does not. Restore 0.08. **Check:** does a Black–Litterman expected-return view replace $r$ in an option formula? No. A view concerns the investment distribution; $r$ here is the rate at which the replicating cash account accrues.

## 2. Build a Self-Financing Replication

Let $V(t,S)$ be the option's value at calendar time $t$, with expiry date $T$ and $\tau=T-t$. Hold $\Delta_t$ asset units and a signed cash balance $B_t$:

$$V_t=\Delta_t S_t+B_t.$$

Positive cash is a deposit; negative cash is borrowing. **Delta**, $\Delta=V_S=\partial V/\partial S$, measures how much option value changes per small one-unit price change. It has asset-unit-per-option units. It is not a percentage capital weight.

For our call, the formula derived below will give $V=£10.386279$ and $\Delta=0.634558$. Buying that many asset units costs £63.455836. The remaining cash is $10.386279-63.455836=-£53.069557$: the strategy borrows the difference. Its asset capital weight is approximately $63.455836/10.386279=6.11$, not 0.634558. Long-only portfolio constraints would exclude this leveraged replication.

**Self-financing** means that, after the initial investment, no money is injected or withdrawn. At a rebalance, buying another 0.05 units at £102 costs £5.10; cash must fall by £5.10. Interest accrues between trades. For an interval of length $h$ years, holding the old quantity $\Delta_i$ through the move gives:

$$V^-_{i+1}=\Delta_i S_{i+1}+B_i e^{rh},\qquad
B_{i+1}=B_i e^{rh}-(\Delta_{i+1}-\Delta_i)S_{i+1}.$$

The superscript minus means just before rebalancing. The new holdings have the same total value as $V^-_{i+1}$. In continuous-time notation the gains equation is:

$$dV_t=\Delta_t\,dS_t+rB_t\,dt.$$

This is a **trading rule plus a budget condition**, not the ordinary product rule with changing holdings ignored. Changes in the number of units are financed by cash. Keeping $B$ fixed while freely changing $\Delta$ would introduce external funding and invalidate the derivation.

**Check:** if you sell 0.03 units at £90, what happens to cash at that instant? It rises by £2.70, before interest or costs. Total account value is unchanged by a frictionless rebalance.

## 3. Derive the Black–Scholes Pricing Equation

Under the real-world model, $dS=\mu S\,dt+\sigma S\,dW^{\mathbb P}$. Itô's formula gives, before expiry where $V$ is smooth:

$$dV=\left(V_t+\mu S V_S+\tfrac12\sigma^2S^2V_{SS}\right)dt
+\sigma S V_S\,dW^{\mathbb P}.$$

$V_t$ is the partial derivative with respect to **calendar time**, holding $S$ fixed; $V_{SS}$ measures curvature with respect to price. Matching the random term of the replicating account requires $\Delta=V_S$. Substituting $B=V-SV_S$ in its drift then gives:

$$V_t+\mu S V_S+\tfrac12\sigma^2S^2V_{SS}
=\mu S V_S+r(V-SV_S).$$

The real-world drift terms cancel. Rearranging yields the **partial differential equation (PDE)**:

$$\boxed{V_t+\tfrac12\sigma^2S^2V_{SS}+rS V_S-rV=0.}$$

A PDE relates derivatives of a function of several variables. Here the final condition specifies the contract: $V(T,S)=(S-K)_+$ for a call and $(K-S)_+$ for a put, where $x_+=\max(x,0)$. For a call, the boundary behaviors are $V(t,0)=0$ and $V(t,S)\sim S-Ke^{-r\tau}$ at very large $S$. The terminal payoff has a kink; the smooth Itô calculation applies at $t<T$, with the payoff imposed as the expiry limit.

Why is matching enough? In this one-source-of-risk model, asset plus cash can replicate the claim under the stated continuous-trading assumptions. Different prices for identical future payments would permit buying the cheaper side and selling the dearer side. A pricing solution satisfying the terminal condition and the appropriate growth conditions is therefore the replication cost.

For the benchmark call, we will verify the four PDE terms, all in **GBP per year**:

$$-6.349560+3.760288+3.096021-0.506748=0\quad\text{(up to rounding)}.$$

The curvature term does not disappear. Delta removes the random first-order exposure; cash financing and time decay balance the remaining drift. **Experiment:** mentally replace $\mu$ by 0.12 in the two sides before cancellation. Both acquire the same extra $0.04SV_S$, leaving the same pricing equation.

## 4. Turn the PDE into a Pricing Expectation

Consider an auxiliary GBM with drift $r$:

$$dS=rS\,dt+\sigma S\,dW^{\mathbb Q}.$$

Applying Itô to the discounted value $e^{-rt}V(t,S_t)$ makes its drift zero precisely when the PDE holds. Under the model's integrability conditions this discounted process is a **martingale**: its conditional future mean equals its current value. With terminal payoff $H(S_T)$, this gives the pricing representation:

$$V(t,S)=e^{-r\tau}\mathbb E^{\mathbb Q}[H(S_T)\mid S_t=S],\qquad
S_T=S\exp[(r-\sigma^2/2)\tau+\sigma\sqrt{\tau}Z],\quad Z\sim N(0,1).$$

This is the expectation solution of the replication PDE, often called the Feynman–Kac representation. It is not a rule that any risky payoff can be valued by discounting its real-world mean at cash. For our inputs, the pricing log drift is $0.048790164-0.02=0.028790164$ per year, distinct from the 0.06 real-world log drift in the previous lesson.

The **standard normal density** is $\phi(z)=e^{-z^2/2}/\sqrt{2\pi}$. Its cumulative distribution is $N(x)=\int_{-\infty}^{x}\phi(z)\,dz$. Density is height; probability is area. For example, $N(0)=0.5$ and $N(1)\approx0.841345$, so the area between 0 and 1 is about 0.341345.

A call pays only when $S_T>K$. Rearrange the exponential expression:

$$Z>\frac{\log(K/S)-(r-\sigma^2/2)\tau}{\sigma\sqrt\tau}=-d_2,\qquad
d_2=\frac{\log(S/K)+(r-\sigma^2/2)\tau}{\sigma\sqrt\tau}.$$

Here $d_2=0.143950821$, so the cutoff is −0.143950821 and the pricing exercise probability is $N(d_2)=0.557230348$. The chart marks the cutoff on the bell curve. The area **to its right**, not the height of the diamond, is the exercise probability.

```python:line-numbers
d2 = (np.log(S0 / K) + (r - sigma**2 / 2) * T) / (sigma * np.sqrt(T))
z_grid = np.linspace(-4., 4., 321)
print(f"N(0) = {norm.cdf(0):.6f}; N(1) = {norm.cdf(1):.6f}")
print(f"Exercise cutoff: {-d2:.9f}; pricing exercise probability: {norm.cdf(d2):.9f}")
print("<ECHARTS_DATA>" + json.dumps({"bsNormalCutoff": {
    "type": "line", "title": "Exercise Probability Is an Area Under the Density",
    "xAxis": {"type": "value", "name": "Standardized normal outcome Z", "min": -4, "max": 4},
    "yAxisName": "Standard normal density",
    "series": {"Density": np.column_stack([z_grid, norm.pdf(z_grid)]).tolist(),
               "Exercise cutoff": [[-d2, float(norm.pdf(d2))]]},
    "seriesOptions": {"Exercise cutoff": {"type": "scatter", "symbol": "diamond", "symbolSize": 18,
        "itemStyle": {"color": "#ea580c", "borderColor": "#ffffff", "borderWidth": 2, "opacity": 1}}},
}}, allow_nan=False))
```
<Editor id="bs-normal" />

**Check:** is 55.72% our real-world forecast of exercise? No. With $\mu=0.08$, the corresponding real-world probability would be $N((0.08-0.02)/0.20)=N(0.3)\approx61.79\%$. This changes forecast probabilities, not the replication price.

## 5. Evaluate the Call Integral

Split the discounted expected payoff into the asset received and the strike paid, only in exercising states:

$$C=e^{-r\tau}\int_{-d_2}^{\infty}
\left(S e^{(r-\sigma^2/2)\tau+\sigma\sqrt\tau z}-K\right)\phi(z)\,dz.$$

The constant-strike part is $Ke^{-r\tau}N(d_2)$. For the asset part, set $a=\sigma\sqrt\tau$ and complete the square:

$$e^{az-a^2/2}\phi(z)=\phi(z-a).$$

For example, with $a=0.2$ and $z=1$, the exponential multiplier is $e^{0.18}$; multiplying $\phi(1)$ by it gives $\phi(0.8)$. Set $u=z-a$ in the integral. Its lower limit becomes $-d_2-a=-d_1$, where $d_1=d_2+\sigma\sqrt\tau$. Symmetry of the normal distribution gives:

$$\boxed{C=S N(d_1)-Ke^{-r\tau}N(d_2)},\qquad
d_1=\frac{\log(S/K)+(r+\sigma^2/2)\tau}{\sigma\sqrt\tau}.$$

Numerically, $d_1=0.343950821$, $N(d_1)=0.634558364$, and the two terms are **£63.455836** and **£53.069557**. Subtraction gives **£10.386279**. $N(d_1)$ is the call delta; it is not the exercise probability, which is $N(d_2)$.

The next chart shows the **discounted payoff times density** as a function of $z$. Its total area is the call price. The numerical integration below uses a range ending at 12 standard deviations; the omitted positive tail is negligible at these inputs. It independently checks the normal-CDF formula without simulating random paths.

```python:line-numbers
def discounted_call_integrand(z):
    terminal = S0 * np.exp((r - sigma**2 / 2) * T + sigma * np.sqrt(T) * z)
    return np.exp(-r * T) * max(terminal - K, 0.) * norm.pdf(z)

integral_call, integration_error = quad(discounted_call_integrand, -d2, 12., epsabs=1e-11)
print(f"Numerical discounted expectation: {integral_call:.9f} GBP")
print(f"Integrator's estimated error on the chosen interval: {integration_error:.2e} GBP")
print(f"Square-completion check: {np.exp(.18) * norm.pdf(1):.9f} = {norm.pdf(.8):.9f}")
print("<ECHARTS_DATA>" + json.dumps({"bsPayoffIntegral": {
    "type": "line", "title": "The Area of the Weighted Payoff Gives Today's Price",
    "xAxis": {"type": "value", "name": "Standardized normal outcome Z"},
    "yAxisName": "Discounted payoff times density (GBP)",
    "series": {"Weighted payoff": [[float(z), float(discounted_call_integrand(z))] for z in z_grid]},
}}, allow_nan=False))
```
<Editor id="bs-integral" />

**Experiment:** integrate only up to $z=1$. You exclude large positive payoffs and obtain a smaller area. This is a truncated calculation, not a cheaper version of the same full-distribution option. **Check:** multiplying the mean terminal price by exercise probability would miss the dependence between exercise and price; exercising states have higher-than-average prices.

## 6. Price Calls and Puts, Then Check the Hedge

For a put, integrate over $Z<-d_2$. The strike contribution is $Ke^{-r\tau}N(-d_2)$; the same square-completion step makes the asset contribution $S N(-d_1)$:

$$\boxed{P=Ke^{-r\tau}N(-d_2)-S N(-d_1).}$$

At our inputs this is approximately $42.168538-36.544164=£5.624375$. Differentiating the call formula gives $C_S=N(d_1)$: the derivatives of the CDF terms cancel because $S\phi(d_1)=Ke^{-r\tau}\phi(d_2)$. Differentiating once more gives curvature $C_{SS}=\phi(d_1)/(S\sigma\sqrt\tau)$.

The function below returns call value, put value, and call delta. At zero remaining life it returns the payoffs; at zero volatility it returns the discounted deterministic payoff. Delta at the exact boundary $S=Ke^{-r\tau}$ is undefined in that limit, so the code reports `nan`. We will not use such a delta for trading.

The graph varies **current spot price**, holding strike, remaining life, rate, and volatility fixed. It is a pre-expiry valuation graph, not a realized path or a payoff graph. The call rises and the put falls as spot increases.

```python:line-numbers
def bs_values(spot, strike, remaining, rate, volatility):
    if not np.isfinite([spot, strike, remaining, rate, volatility]).all():
        raise ValueError("Inputs must be finite")
    if spot <= 0 or strike <= 0 or remaining < 0 or volatility < 0:
        raise ValueError("Positive spot/strike and nonnegative time/volatility required")
    discounted_strike = strike * np.exp(-rate * remaining)
    if remaining == 0 or volatility == 0:
        difference = spot - discounted_strike
        delta = float(difference > 0) if difference != 0 else np.nan
        return max(difference, 0.), max(-difference, 0.), delta
    scale = volatility * np.sqrt(remaining)
    first = (np.log(spot / strike) + (rate + volatility**2 / 2) * remaining) / scale
    second = first - scale
    call = spot * norm.cdf(first) - discounted_strike * norm.cdf(second)
    put = discounted_strike * norm.cdf(-second) - spot * norm.cdf(-first)
    return call, put, norm.cdf(first)

call, put, delta = bs_values(S0, K, T, r, sigma)
cash = call - delta * S0
print(f"Call: {call:.9f}; put: {put:.9f} GBP; call delta: {delta:.9f} units")
print(f"Asset holding: {delta*S0:.9f} GBP; cash: {cash:.9f} GBP")
spot_grid = np.linspace(50., 150., 101)
price_grid = np.array([bs_values(s, K, T, r, sigma)[:2] for s in spot_grid])
print("<ECHARTS_DATA>" + json.dumps({"bsSpotPrices": {
    "type": "line", "title": "Current Option Values Across Current Asset Prices",
    "xAxis": {"type": "value", "name": "Current spot (GBP/unit)"},
    "yAxisName": "Option value (GBP/contract)",
    "series": {"Call": np.column_stack([spot_grid, price_grid[:, 0]]).tolist(),
               "Put": np.column_stack([spot_grid, price_grid[:, 1]]).tolist()},
    "seriesOptions": {"Put": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="bs-prices" />

### Verify the PDE Numerically

For a call, the calendar-time derivative is
$C_t=-S\phi(d_1)\sigma/(2\sqrt\tau)-rKe^{-r\tau}N(d_2)$.
It is the negative of the remaining-life derivative at fixed spot. Here its two contributions are −3.760288 and −2.589272 GBP/year, totaling −6.349560. The next lesson will examine these sensitivities systematically; here we need them to check replication.

The bars show the four signed terms of the PDE. Their sum should be near zero, while individual terms are substantial. A negative time term alone is not a realized daily loss: the asset also moves and the hedge earns or pays interest.

```python:line-numbers
d1 = d2 + sigma * np.sqrt(T)
gamma = norm.pdf(d1) / (S0 * sigma * np.sqrt(T))
theta = -S0 * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r*K*np.exp(-r*T)*norm.cdf(d2)
pde_terms = [theta, 0.5 * sigma**2 * S0**2 * gamma, r*S0*delta, -r*call]
print(f"Gamma: {gamma:.9f}; calendar-time derivative: {theta:.9f} GBP/year")
print(f"PDE residual: {sum(pde_terms):.2e} GBP/year")
print("<ECHARTS_DATA>" + json.dumps({"bsPDEBalance": {
    "type": "bar", "title": "Time, Curvature, Asset Carry, and Value Carry Balance",
    "xAxis": {"type": "category", "name": "Pricing-equation term", "data": ["Time", "Curvature", "Asset carry", "Value carry"]},
    "yAxisName": "Contribution (GBP/year)", "series": {"PDE term": pde_terms},
}}, allow_nan=False))
```
<Editor id="bs-pde" />

**Check:** the account's local real-world expected gain is $\mu S\Delta+rB$. With the benchmark numbers it is about £2.487 GBP/year, which matches the Itô drift $C_t+\mu S\Delta+\sigma^2S^2C_{SS}/2$. That is a local conditional mean, not a promise about the option's one-year return.

## 7. Reconcile Parity, Bounds, and Financed Profit

At expiry, call minus put pays $S_T-K$ in every state. Therefore:

$$C-P=S-Ke^{-r\tau}.$$

Here $10.386279-5.624375=100-100/1.05=£4.761905$. This is exactly the parity difference from [Options and Replication](./d.3-options.md), although the individual option prices differ because the continuous lognormal model and the two-state model have different payoff distributions. Different models must preserve parity when they share the same contract and cash assumptions.

For nonnegative rates and no dividends, the earlier bounds remain $\max(S-Ke^{-r\tau},0)\le C\le S$ and $\max(Ke^{-r\tau}-S,0)\le P\le Ke^{-r\tau}$. At £100 spot, the call lower bound is £4.761905 and the put lower bound is zero. Our values satisfy both. The same displayed European bounds also hold at negative rates, with the discounted strike then exceeding the strike.

To calculate **financed profit**, move the premium to expiry. At $S_T=£120$, call payoff is £20, while financed profit is $20-10.386279(1.05)=£9.094407$. The graph compares the financed call-minus-put profit with the fair forward payoff $S_T-105$. Both lines coincide. Neither should be compared with an unfunded payoff using a different initial budget.

```python:line-numbers
final_spots = np.linspace(50., 150., 101)
call_payoffs = np.maximum(final_spots - K, 0.)
put_payoffs = np.maximum(K - final_spots, 0.)
synthetic_profit = call_payoffs - put_payoffs - (call - put) * np.exp(r*T)
fair_forward_payoff = final_spots - S0*np.exp(r*T)
print(f"Parity difference: {call-put:.9f} GBP; asset minus discounted strike: {S0-K*np.exp(-r*T):.9f} GBP")
print(f"Call financed profit at 120: {20-call*np.exp(r*T):.9f} GBP")
print("<ECHARTS_DATA>" + json.dumps({"bsForwardParity": {
    "type": "line", "title": "Financed Call Minus Put Reproduces a Fair Forward",
    "xAxis": {"type": "value", "name": "Final spot (GBP/unit)"},
    "yAxisName": "Maturity profit or payoff (GBP)",
    "series": {"Financed call minus put": np.column_stack([final_spots, synthetic_profit]).tolist(),
               "Fair forward": np.column_stack([final_spots, fair_forward_payoff]).tolist()},
    "seriesOptions": {"Fair forward": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"type": "dashed", "color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="bs-parity" />

**Check:** why is the new forward delivery price £105 while both option strikes are £100? Financing the £4.761905 cost of call-minus-put adds £5 at maturity. That converts its £100-strike payoff into the fair £105 forward payoff.

## 8. Experiment: Approach Expiry or Remove Uncertainty

At expiry, $\tau=0$, both option values equal their payoffs. With zero volatility but positive remaining life, the future asset price is deterministic **under the pricing model**, so:

$$C=\max(S-Ke^{-r\tau},0),\qquad P=\max(Ke^{-r\tau}-S,0).$$

Thus at £100 spot and one year, zero-volatility call value is **£4.761905**, not zero; the put is zero. At expiry and £100 spot, both are zero. The limits differ because financing has time to operate in the first case.

Move the remaining-years and volatility controls. Blue and orange curves show current call and put values across spot. Matching outlined diamonds mark the fixed **£100 current spot**. Grey and purple dashed curves show the corresponding zero-volatility bounds. The helper reproduces the visible formulas above and handles zero time and zero volatility explicitly.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_black_scholes_echart,
    remaining=widgets.FloatSlider(value=1., min=0., max=2., step=0.25,
                                  description="Years left", continuous_update=False),
    volatility=widgets.FloatSlider(value=0.20, min=0., max=0.60, step=0.05,
                                   description="Volatility", continuous_update=False),
)
widget_instance
```
<Editor id="bs-limits-widget" />

**Try it:** set volatility to zero before reducing remaining life to zero. Explain the £4.761905-to-zero change at the diamond. Restore one year and raise volatility to 0.40: both options become more valuable, but call minus put is unchanged. This follows from convex payoffs under the model and from parity, not from a higher forecast drift.

## 9. Trade the Stock Hedge and Account for Every Pound

Continuous replication is a limiting strategy. On a finite grid, hold the old delta through each interval, accrue cash, and rebalance only at its endpoint. Start with the call premium as the hedge account's wealth. For an option seller, **hedge account minus call liability** is the net position; the hedge itself is long delta.

For an explicit first interval, take a quarter-year move from £100 to £105. The starting cash −£53.069557 becomes approximately −£53.720839 after interest. The old asset holding becomes £66.628628. Pre-trade wealth is approximately £12.907789. Recalculate delta with 0.75 years left, buy or sell the difference at £105, and deduct that trade from cash. The code prints the exact ledger so the example can be checked at full precision.

We then simulate one real-world GBM path on **1,024 equal intervals**, with seed `20261101`. Coarser grids select observations of this same path. They do not redraw it. The two charts compare hedge wealth with the option liability at 16 rebalancing intervals, then show signed terminal error at several frequencies. Error is measured in GBP, not as return on a zero-value short-option-plus-hedge position. A particular path's error need not shrink monotonically.

```python:line-numbers
def stock_hedge(spots, dates):
    initial_call, _, holding = bs_values(spots[0], K, T, r, sigma)
    balance = initial_call - holding * spots[0]
    rows = [[dates[0], spots[0], holding, balance, initial_call, initial_call, 0., 0.]]
    for i in range(1, len(dates)):
        accrued = balance * np.exp(r * (dates[i] - dates[i-1]))
        wealth = holding * spots[i] + accrued
        option, _, new_holding = bs_values(spots[i], K, max(T-dates[i], 0.), r, sigma)
        if i == len(dates)-1:
            new_holding = 0.  # liquidate at expiry; no undefined expiry delta is traded
        trade = (new_holding - holding) * spots[i]
        balance = accrued - trade
        budget_error = new_holding * spots[i] + balance - wealth
        rows.append([dates[i], spots[i], new_holding, balance, wealth, option, trade, budget_error])
        holding = new_holding
    return pd.DataFrame(rows, columns=["Time", "Spot", "Units", "Cash", "Wealth", "Call", "Trade", "Budget error"])

hand_ledger = stock_hedge(np.array([100., 105., 110.]), np.array([0., .25, 1.]))
print("Hand-built path ledger (positive Trade means a purchase):")
print(hand_ledger.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
fine_times = np.linspace(0., T, 1025)
fine_dw = np.random.default_rng(20261101).standard_normal(1024) * np.sqrt(T/1024)
fine_w = np.r_[0., np.cumsum(fine_dw)]
fine_spots = S0 * np.exp((mu-sigma**2/2)*fine_times + sigma*fine_w)
counts = [4, 16, 64, 256, 1024]
stock_ledgers = {n: stock_hedge(fine_spots[::1024//n], fine_times[::1024//n]) for n in counts}
stock_errors = [float((stock_ledgers[n]["Wealth"]-stock_ledgers[n]["Call"]).iloc[-1]) for n in counts]
ledger = stock_ledgers[16]
print(pd.DataFrame({"Intervals": counts, "Terminal stock hedge error (GBP)": stock_errors}).to_string(index=False))
print("<ECHARTS_DATA>" + json.dumps({
    "bsStockHedge": {"type": "line", "title": "A Finite-Grid Stock Hedge Leaves a Residual",
        "xAxis": {"type": "value", "name": "Elapsed time (years)"}, "yAxisName": "Value (GBP)",
        "series": {"Hedge account": ledger[["Time", "Wealth"]].values.tolist(),
                   "Call liability": ledger[["Time", "Call"]].values.tolist()},
        "seriesOptions": {"Call liability": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"type": "dashed", "color": "#ea580c"}}}},
    "bsStockErrors": {"type": "line", "title": "Refine Trading Dates on the Same Sample Path",
        "xAxis": {"type": "category", "name": "Rebalancing intervals", "data": [str(n) for n in counts]},
        "yAxisName": "Terminal hedge minus payoff (GBP)",
        "series": {"Stock hedge error": stock_errors, "Exact replication target": [0.] * len(counts)},
        "seriesOptions": {"Exact replication target": {"itemStyle": {"color": "#64748b"}, "lineStyle": {"type": "dashed", "color": "#64748b"}}}},
}, allow_nan=False))
```
<Editor id="bs-stock-hedge" />

The ledger's **Budget error** should be near zero at every trade even though terminal hedge error is not zero. Budget balance checks accounting; hedge error checks how well the strategy covers the liability. Replacing actual cash with `option - delta * spot` at each rebalance would reset wealth to the model price by adding or removing money and conceal the replication error.

**Experiment:** use seed `20261102` and rerun. Compare all grid sizes on that new shared path. Restore the original seed afterwards. **Check:** would transaction costs disappear in the continuous-trading limit? No. Our frictionless convergence argument does not carry over unchanged to a costly strategy; [Robust Portfolio Construction: Diversification and Risk Budgets](./2.4-robust-portfolios.md) shows how fees consume portfolio wealth.

## 10. Replace the Stock Holding with a Futures Hedge

A futures quote is not its purchase price. Use a one-unit-multiplier futures contract maturing with the option. With deterministic $r$ and no income, its quote is $F_t=S_t e^{r(T-t)}$. Its marked-to-market value is reset to zero at settlement, while its gain is paid to cash.

Differentiating the quote gives $dF=e^{r(T-t)}(dS-rS\,dt)$. To reproduce the stock delta's local exposure, the number of long futures is:

$$h_t=\Delta_t e^{-r(T-t)}.$$

At inception, $F_0=£105$ and $h_0=0.634558364/1.05=0.604341299$ contracts. The futures account holds the **entire £10.386279 premium in cash**; it does not buy £63.46 of stock. Its continuous gains are:

$$dA=rA\,dt+h\,dF
=\Delta\,dS+r(A-\Delta S)dt,$$

the same gains equation as the stock hedge. This is dynamic hedging of an option on spot using futures, not the pricing formula for an option whose underlying contract is a futures contract.

For our finite-grid illustration, settle variation at each grid endpoint, immediately before resetting the hedge. Hold $h_i$ between dates. Cash evolves as:

$$A_{i+1}=A_i e^{r\Delta t}+h_i(F_{i+1}-F_i).$$

For the quarter-year move to £105 spot, the new quote is $105(1.05)^{0.75}\approx£108.913389$. The first cash balance becomes $10.386279(1.05)^{0.25}+0.604341299(108.913389-105)\approx£12.878765$. It differs slightly from the stock hedge's £12.907789 because the finite-grid strategies hold different exposures between settlements. Both approach the continuous gains equation as the grid is refined.

This idealized ledger assumes no separate initial-margin requirement and permits a negative cash balance funded at the same rate. It treats the futures as a zero-value gains instrument. An exchange implementation must additionally account for collateral, borrowing spreads, and actual settlement dates as in [Futures and Forwards Compared](./d.2-futures.md). An external margin top-up would be a new contribution unless financed within the account.

The graph compares signed stock and futures terminal errors on the same path and grids. Neither finite-grid line is required to be zero or to dominate the other.

```python:line-numbers
def futures_hedge(spots, dates):
    account, _, initial_delta = bs_values(spots[0], K, T, r, sigma)
    quotes = spots * np.exp(r*(T-dates))
    contracts = initial_delta * np.exp(-r*T)
    rows = [[dates[0], quotes[0], contracts, account, 0.]]
    for i in range(1, len(dates)):
        variation = contracts * (quotes[i]-quotes[i-1])
        account = account*np.exp(r*(dates[i]-dates[i-1])) + variation
        remaining = max(T-dates[i], 0.)
        contracts = bs_values(spots[i], K, remaining, r, sigma)[2]*np.exp(-r*remaining) if i < len(dates)-1 else 0.
        rows.append([dates[i], quotes[i], contracts, account, variation])
    return pd.DataFrame(rows, columns=["Time", "Quote", "Contracts", "Cash", "Variation"])

print(futures_hedge(np.array([100., 105., 110.]), np.array([0., .25, 1.])).to_string(index=False))
futures_ledgers = {n: futures_hedge(fine_spots[::1024//n], fine_times[::1024//n]) for n in counts}
terminal_payoff = max(fine_spots[-1]-K, 0.)
futures_errors = [float(futures_ledgers[n]["Cash"].iloc[-1]-terminal_payoff) for n in counts]
print(pd.DataFrame({"Intervals": counts, "Stock error": stock_errors, "Futures error": futures_errors}).to_string(index=False))
print("<ECHARTS_DATA>" + json.dumps({"bsFuturesErrors": {
    "type": "line", "title": "Two Discrete Implementations of the Continuous Hedge",
    "xAxis": {"type": "category", "name": "Rebalancing and settlement intervals", "data": [str(n) for n in counts]},
    "yAxisName": "Terminal hedge minus payoff (GBP)",
    "series": {"Stock hedge": stock_errors, "Futures hedge": futures_errors, "Zero error": [0.] * len(counts)},
    "seriesOptions": {"Futures hedge": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"type": "dashed", "color": "#ea580c"}},
                      "Zero error": {"itemStyle": {"color": "#64748b"}, "lineStyle": {"type": "dashed", "color": "#64748b"}}},
}}, allow_nan=False))
```
<Editor id="bs-futures-hedge" />

**Experiment:** compare the first-period settlements in the hand-built ledger with the stock ledger, then change the intermediate spot from £105 to £95 in both calls. **Check:** for a multiplier of ten asset units per futures contract, divide $h$ by ten; multiply the variation payment per contract by ten. The money exposure stays the same.

## 11. Worked Exercise: Change Spot, Strike, and Horizon

Use $S=£80$, $K=£85$, $\tau=0.5$ years, $\sigma=0.30$, and the same 5% effective annual financing rate.

1. Calculate $d_1$, $d_2$, the call, and the put.
2. Find the call's asset units, cash balance, and initial futures contracts for a one-unit multiplier.
3. Check parity and calculate financed call profit if expiry spot is £90.
4. Would changing the real-world drift from 6% to 10% change these prices?

::: details Hint
Use $r=\log(1.05)$, not 0.05. The square-root scale is $0.30\sqrt{0.5}$. Discount the strike for half a year and finance the premium for the same half-year.
:::

::: details Worked answer
The log spot/strike ratio is $\log(80/85)\approx-0.060625$. Adding $(r+0.30^2/2)(0.5)\approx0.046895$ and dividing by $0.30\sqrt{0.5}\approx0.212132$ gives $d_1\approx-0.064722$; subtracting 0.212132 gives $d_2\approx-0.276854$.

The call is approximately **£5.506246**, and the put is approximately **£8.457753**. Delta is approximately **0.474198 units**. Asset cost is about £37.935824, so cash is about **−£32.429578**. The futures quantity is about **0.462770 contracts**, with the full call premium left in cash.

Parity gives $C-P=80-85/\sqrt{1.05}\approx-£2.951506$. At £90, call payoff is £5 and financed profit is $5-5.506246\sqrt{1.05}\approx-£0.642224$. Exercise does not imply profit after paying and financing the premium.

The drift change affects real-world outcome probabilities, not these replication prices under the fixed pricing assumptions.
:::

```python:line-numbers
exercise_s, exercise_k, exercise_t, exercise_sigma = 80., 85., .5, .30
exercise_call, exercise_put, exercise_delta = bs_values(exercise_s, exercise_k, exercise_t, r, exercise_sigma)
exercise_d1 = (np.log(exercise_s/exercise_k)+(r+exercise_sigma**2/2)*exercise_t)/(exercise_sigma*np.sqrt(exercise_t))
exercise_d2 = exercise_d1-exercise_sigma*np.sqrt(exercise_t)
exercise_cash = exercise_call-exercise_delta*exercise_s
exercise_futures = exercise_delta*np.exp(-r*exercise_t)
exercise_profit = 5-exercise_call*np.exp(r*exercise_t)
print(f"d1: {exercise_d1:.9f}; d2: {exercise_d2:.9f}")
print(f"Call: {exercise_call:.9f}; put: {exercise_put:.9f} GBP")
print(f"Delta: {exercise_delta:.9f} units; cash: {exercise_cash:.9f} GBP; futures: {exercise_futures:.9f}")
print(f"Parity difference: {exercise_call-exercise_put:.9f}; financed call profit at 90: {exercise_profit:.9f} GBP")
```
<Editor id="bs-exercise" />

## Chapter Summary

- Replication matches the option's local exposure and finances each rebalance from a cash account. Delta is a quantity, not a capital weight.
- Itô's formula and the self-financing condition produce the Black–Scholes PDE. Real-world drift cancels; volatility remains.
- The pricing expectation solves that PDE. Completing the square in the normal integral gives the European call and put formulas.
- Parity links both option values to asset minus discounted strike, independently of the chosen payoff distribution when replication applies.
- Finite-grid stock and futures hedges require explicit cash accounting and retain hedge error. Statistical portfolio replication and an exact contractual hedge are different claims.

Continue with [Futures Basis, Dividends, and Implied Financing](./futures-basis.md) to infer carry inputs from traded prices and reconcile settlement funding. For the portfolio connections, revisit [Portfolio Management Fundamentals](./1.0-overview.md) and [Advanced Portfolio Construction and Analysis](./2.0-overview.md).
