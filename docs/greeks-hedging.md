---
title: "The Greeks and Hedging"
permalink: /greeks-hedging
description: "Derive first-, second-, and higher-order option sensitivities; explain their units; and reconcile Greek-based P&L, multi-instrument hedges, funding, and rebalancing costs."
---

# The Greeks and Hedging

**Question:** you have sold an option. The share price rises, implied volatility changes, and another day passes. How much did the liability change, what could you hedge, and where did the money go?

Think of an option valuation as a measuring instrument with several input dials. A **Greek** measures how its reading changes when one dial moves, holding specified other dials fixed. A hedge uses positions whose changes offset some of those sensitivities. It does not freeze every input or remove the need to fund the positions.

[Deriving and Using Black–Scholes](./black-scholes.md) explained the price and replication argument. [Futures Basis, Dividends, and Implied Financing](./futures-basis.md) explained carry inputs and settlement funding. Here we derive the sensitivities, including the less familiar cross-effects, then test them against exact repricing and a cash ledger.

All examples use synthetic prices and scenarios. Run the cells in order; the approximation widget can also run first in a fresh session. We use fractional hedge quantities to expose the mathematics; actual contract lots and bid/ask prices constrain execution.

## 1. Fix the Contract, Units, and Held-Fixed Inputs

Start with a European call on **one share**, with share price $S=£100$, strike $K=£100$, remaining life $\tau=1$ year, annual volatility $\sigma=0.20$, and no dividends. Keep the previous chapter's 5% **effective** cash rate: its continuous equivalent is $r=\log(1.05)=0.048790164$. An option on 100 shares costs 100 times the one-share quote and has 100 times each currency sensitivity.

Use calendar time $t$, fixed expiry $T$, and $\tau=T-t$. Calendar-time derivatives therefore have the **opposite sign** to remaining-life derivatives. We divide annual time sensitivities by **365** for a one-calendar-day approximation. This is a reporting convention, not a claim that business-day trading and calendar-time decay are identical.

We also allow a known constant continuous dividend yield $q$. This idealized reinvestable yield is different from the dated cash dividends in the basis lesson. Let $A=e^{-q\tau}$, $B=e^{-r\tau}$, and:

$$d_1=\frac{\log(S/K)+(r-q+\sigma^2/2)\tau}{\sigma\sqrt\tau},\qquad d_2=d_1-\sigma\sqrt\tau.$$

Then $C=SA N(d_1)-KB N(d_2)$ and $P=KB N(-d_2)-SA N(-d_1)$. As before, $N$ is the normal cumulative distribution and $\phi$ its density. At the baseline, $d_1=0.343950821$, $d_2=0.143950821$, call value is **£10.386279497**, and put value is **£5.624374735**.

| Sensitivity | Derivative of one-share option value $V$ | Reporting scale |
| --- | --- | --- |
| Delta, $\Delta$ | $V_S$ | Shares per option; multiply by a GBP/share move |
| Gamma, $\Gamma$ | $V_{SS}$ | Delta change per GBP/share move |
| Theta, $\Theta$ | $V_t=-V_\tau$ | GBP per year of calendar time; divide by 365 for per day |
| Vega, $\nu$ | $V_\sigma$ | GBP per unit decimal volatility; multiply by 0.01 for one volatility point |
| Rho, $\rho$ | $V_r$ | GBP per unit continuous annual rate; multiply by 0.0001 for one basis point |
| Yield sensitivity, $\psi$ | $V_q$ | GBP per unit continuous annual dividend yield |

A volatility move from 20% to 21% is **one percentage point**, or 0.01 in the code. A 1% *relative* increase from 20% is only 20.2%. A rate move of one basis point is 0.0001, not 0.01.

The first cell makes the pricing and core sensitivity formulas visible. The following sections derive and test them. Smooth Greeks require positive time and volatility. Prices still have sensible zero-time/zero-volatility limits, but a payoff kink has no ordinary gamma, and we will not report a smooth-Greek formula there.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

S, K, tau, r, sigma, q = 100., 100., 1., np.log1p(.05), .20, 0.

def option_price(s, k, t, rate, vol, yield_rate=0., kind="call"):
    if kind not in ("call", "put") or not np.isfinite([s, k, t, rate, vol, yield_rate]).all():
        raise ValueError("Use finite inputs and call or put")
    if s <= 0 or k <= 0 or t < 0 or vol < 0:
        raise ValueError("Positive spot/strike and nonnegative time/volatility required")
    a, b = np.exp(-yield_rate*t), np.exp(-rate*t)
    sign = 1 if kind == "call" else -1
    if t == 0 or vol == 0:
        return max(sign*(s*a-k*b), 0.)
    d1 = (np.log(s/k)+(rate-yield_rate+vol**2/2)*t)/(vol*np.sqrt(t))
    d2 = d1-vol*np.sqrt(t)
    return sign*(s*a*norm.cdf(sign*d1)-k*b*norm.cdf(sign*d2))

def core_greeks(s, k, t, rate, vol, yield_rate=0., kind="call"):
    value = option_price(s, k, t, rate, vol, yield_rate, kind)
    if t == 0 or vol == 0:
        raise ValueError("Smooth Greeks require positive remaining time and volatility")
    a, b, root = np.exp(-yield_rate*t), np.exp(-rate*t), np.sqrt(t)
    d1 = (np.log(s/k)+(rate-yield_rate+vol**2/2)*t)/(vol*root)
    d2 = d1-vol*root
    sign = 1 if kind == "call" else -1
    delta = sign*a*norm.cdf(sign*d1)
    gamma = a*norm.pdf(d1)/(s*vol*root)
    vega = s*a*norm.pdf(d1)*root
    theta = -s*a*norm.pdf(d1)*vol/(2*root)+yield_rate*s*delta-sign*rate*k*b*norm.cdf(sign*d2)
    return dict(value=value, delta=delta, gamma=gamma, theta=theta, vega=vega,
                rho=sign*t*k*b*norm.cdf(sign*d2), yield_sensitivity=-t*s*delta,
                d1=d1, d2=d2)

g = core_greeks(S, K, tau, r, sigma, q)
p = core_greeks(S, K, tau, r, sigma, q, "put")
print(pd.DataFrame({"Call": g, "Put": p}).to_string(float_format=lambda x: f"{x:.9f}"))
print(f"Call vega per volatility point: {g['vega']*.01:.9f} GBP")
print(f"Call theta per calendar day: {g['theta']/365:.9f} GBP")
print(f"Call rho per basis point: {g['rho']*.0001:.9f} GBP")
```
<Editor id="greeks-setup" />

**Check:** if a desk reports vega as £37.60, can you assume a one-point volatility move earns £37.60? No. First ask whether the report is per unit volatility, per volatility point, per option, or for the entire position. Here one volatility point gives approximately **£0.376029 per one-share option**.

## 2. Delta and Gamma: Slope, Curvature, and Hedge Quantity

An option whose delta is 0.634558 gains approximately £0.634558 when a £100 share rises by £1. For a short position in ten 100-share call contracts, position delta is $-10(100)(0.634558)=-634.558$ shares. Buying 634.558 shares offsets that **local** exposure.

Estimate slope before differentiating the formula. With a small symmetric bump $h$:

$$\Delta\approx\frac{V(S+h)-V(S-h)}{2h},\qquad
\Gamma\approx\frac{V(S+h)-2V(S)+V(S-h)}{h^2}.$$

For $h=£0.01$, evaluate prices at 100.01, 100, and 99.99. The first quotient estimates how much value changes per pound; the second compares the two slopes. A smaller bump reduces truncation error initially, but subtracting almost equal floating-point numbers eventually makes roundoff dominate.

The cancellation identity $SA\phi(d_1)=KB\phi(d_2)$ removes the extra CDF derivatives in the call's first derivative. Since $\partial d_1/\partial S=1/(S\sigma\sqrt\tau)$:

$$\Delta_C=A N(d_1),\qquad \Delta_P=A[N(d_1)-1],\qquad
\Gamma_C=\Gamma_P=\frac{A\phi(d_1)}{S\sigma\sqrt\tau}.$$

Delta is a hedge quantity, **not generally an exercise probability**. Even at $q=0$, exercise probability under the Black–Scholes pricing distribution is $N(d_2)$ rather than $N(d_1)$. With dividends, delta also includes $A$.

For a finite move $x$, Taylor expansion gives:

$$V(S+x)-V(S)\approx\Delta x+\tfrac12\Gamma x^2.$$

At $x=£5$, the delta contribution is $0.634558364(5)=£3.172792$. Gamma is about 0.018801439, adding $0.5(0.018801439)(25)=£0.235018$. Their sum is approximately £3.407810, compared with the exact **£3.396539** change. Exact repricing remains the reference; higher-order terms need not be small for a large move.

The chart shows option value **changes**, not values, against the spot move. The tangent agrees locally; curvature captures gains from either sign of movement for a long vanilla option. Financing and time are held fixed in this experiment.

```python:line-numbers
bump = .01
up = option_price(S+bump, K, tau, r, sigma)
down = option_price(S-bump, K, tau, r, sigma)
fd_delta = (up-down)/(2*bump)
fd_gamma = (up-2*g["value"]+down)/bump**2
spot_moves = np.linspace(-20., 20., 81)
spot_exact = np.array([option_price(S+x, K, tau, r, sigma)-g["value"] for x in spot_moves])
spot_linear = g["delta"]*spot_moves
spot_quadratic = spot_linear+.5*g["gamma"]*spot_moves**2
print(f"Prices at 99.99 / 100 / 100.01: {down:.9f}, {g['value']:.9f}, {up:.9f}")
print(f"Finite-difference delta: {fd_delta:.9f}; gamma: {fd_gamma:.9f}")
print(f"Five-pound move: exact {spot_exact[50]:.9f}; delta {spot_linear[50]:.9f}; delta-gamma {spot_quadratic[50]:.9f} GBP")
print("<ECHARTS_DATA>"+json.dumps({"greeksSpot": {
    "type": "line", "title": "A Delta Hedge Removes Slope, Not Curvature",
    "xAxis": {"type": "value", "name": "Spot change (GBP/share)"}, "yAxisName": "One-share call value change (GBP)",
    "series": {name: np.column_stack([spot_moves, values]).tolist() for name, values in
               (("Exact repricing", spot_exact), ("Delta", spot_linear), ("Delta + gamma", spot_quadratic))},
    "seriesOptions": {"Delta": {"lineStyle": {"type": "dashed", "color": "#64748b"}, "itemStyle": {"color": "#64748b"}},
                      "Delta + gamma": {"lineStyle": {"type": "dashed", "color": "#ea580c"}, "itemStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="greeks-spot" />

**Experiment:** compare £1, £5, and £20 moves. Predict where the approximation deteriorates. **Check:** a stock position has zero gamma. Buying stock against a short call removes initial delta but leaves negative gamma: the required stock hedge tends to increase after a rise and decrease after a fall.

## 3. Theta: Time Passing Is Not the Whole Trading Result

For a call, differentiating with respect to calendar time gives:

$$\Theta_C=-\frac{SA\phi(d_1)\sigma}{2\sqrt\tau}+qSA N(d_1)-rKB N(d_2).$$

For a put:

$$\Theta_P=-\frac{SA\phi(d_1)\sigma}{2\sqrt\tau}-qSA N(-d_1)+rKB N(-d_2).$$

The common first term represents the loss of uncertainty-related value as time disappears; the other terms reflect underlying income and strike financing. At our no-dividend baseline, call theta is approximately $-3.760288-2.589272=-£6.349560$ per year, or **−£0.017396 per calendar day**. The actual one-day change is $C(\tau-1/365)-C(\tau)$, holding spot, rate, yield, and volatility fixed.

A put can have **positive theta**, for example when it is sufficiently deep in the money at positive rates: the approach of the strike payment can outweigh lost uncertainty value. Thus “all bought options decay at a negative rate” is false even within this European model.

The chart plots the exact one-day change in call and put values across current spot. It is a controlled time experiment, not a forecast of tomorrow's P&L. The pricing equation reconciles the local terms:

$$\Theta+\tfrac12\sigma^2 S^2\Gamma+(r-q)S\Delta-rV=0.$$

At the baseline, the four terms are about −6.349560, +3.760288, +3.096021, and −0.506748 GBP/year. A hedged position still receives or pays funding and experiences spot curvature. Theta alone is not its profit.

```python:line-numbers
day = 1/365
theta_spots = np.linspace(60., 140., 81)
day_changes = {kind: [option_price(s, K, tau-day, r, sigma, q, kind)-option_price(s, K, tau, r, sigma, q, kind)
                      for s in theta_spots] for kind in ("call", "put")}
actual_day_change = option_price(S, K, tau-day, r, sigma)-g["value"]
pde_terms = [g["theta"], .5*sigma**2*S**2*g["gamma"], (r-q)*S*g["delta"], -r*g["value"]]
print(f"One day: theta estimate {g['theta']*day:.9f}; exact {actual_day_change:.9f} GBP")
print("PDE terms (GBP/year):", pde_terms, "; sum:", sum(pde_terms))
print("<ECHARTS_DATA>"+json.dumps({"greeksTime": {
    "type": "line", "title": "One Day Passes with Every Other Input Held Fixed",
    "xAxis": {"type": "value", "name": "Current spot (GBP/share)"}, "yAxisName": "Exact one-calendar-day option change (GBP)",
    "series": {name.title(): np.column_stack([theta_spots, values]).tolist() for name, values in day_changes.items()},
    "seriesOptions": {"Put": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="greeks-time" />

**Experiment:** change the elapsed interval from one to 30 calendar days. Exact time repricing need not equal 30 times today's daily theta. **Check:** a platform using $V_\tau$ reports the opposite sign to our $V_t$. Inspect the derivative definition before comparing reports.

## 4. Vega and Volga: Moving the Volatility Input

Differentiate the price with respect to the decimal volatility input. Using the same normal-density cancellation:

$$\nu_C=\nu_P=SA\phi(d_1)\sqrt\tau.$$

At the baseline this is **37.602877 GBP per unit volatility**. It is positive for both long options: more uncertainty increases the value of their convex payoff under the stated model. This is a change in the **pricing volatility input**, not the P&L from observing a historically volatile day.

Vega itself changes when volatility moves. Its derivative, **volga**, also called **vomma**, is:

$$\operatorname{Volga}=V_{\sigma\sigma}=\nu\frac{d_1d_2}{\sigma}.$$

To see why, $\partial d_1/\partial\sigma=-d_2/\sigma$ and $\phi'(d_1)=-d_1\phi(d_1)$, so differentiating vega multiplies it by $d_1d_2/\sigma$. Unlike vega, volga can be negative. For example, at zero carry and $S=K$, $d_1=\sigma\sqrt\tau/2$ and $d_2=-\sigma\sqrt\tau/2$, making their product negative.

For a volatility change $z$, use $\nu z+\tfrac12\operatorname{Volga}z^2$. Moving from 20% to 22% means $z=0.02$: the first contribution is $37.602877(0.02)=£0.752058$. Volga is 9.308969, adding approximately £0.001862; exact repricing gives £0.753706. The chart compares the approximation across volatility changes measured in **percentage points** on the horizontal axis.

```python:line-numbers
volga = g["vega"]*g["d1"]*g["d2"]/sigma
vol_moves = np.linspace(-.10, .20, 61)
vol_exact = np.array([option_price(S, K, tau, r, sigma+z)-g["value"] for z in vol_moves])
vol_linear = g["vega"]*vol_moves
vol_quadratic = vol_linear+.5*volga*vol_moves**2
print(f"Volga per unit volatility squared: {volga:.9f}")
print(f"Two-vol-point move: vega {g['vega']*.02:.9f}; volga adjustment {.5*volga*.02**2:.9f}; exact {option_price(S,K,tau,r,.22)-g['value']:.9f} GBP")
print("<ECHARTS_DATA>"+json.dumps({"greeksVolatility": {
    "type": "line", "title": "Vega Is a Local Volatility Exposure",
    "xAxis": {"type": "value", "name": "Volatility change (percentage points)"}, "yAxisName": "One-share call value change (GBP)",
    "series": {name: np.column_stack([100*vol_moves, values]).tolist() for name, values in
               (("Exact repricing", vol_exact), ("Vega", vol_linear), ("Vega + volga", vol_quadratic))},
    "seriesOptions": {"Vega": {"lineStyle": {"type": "dashed", "color": "#64748b"}, "itemStyle": {"color": "#64748b"}},
                      "Vega + volga": {"lineStyle": {"type": "dashed", "color": "#ea580c"}, "itemStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="greeks-volatility" />

**Experiment:** price at $r=q=0$, retaining spot=strike, and recompute volga. **Check:** does negative volga mean vega is negative? No. It means vega is decreasing with volatility at that point. The option can still become more valuable as volatility rises.

## 5. Rho, Dividends, and the Financing Inputs Behind Them

Classical Black–Scholes rho bumps the single rate $r$ in **both** the forward carry and the discount factor, holding spot, yield, volatility, and remaining life fixed:

$$\rho_C=\tau KB N(d_2),\qquad \rho_P=-\tau KB N(-d_2).$$

At the baseline, call rho is **53.069557 GBP per unit rate**. One basis point gives approximately £0.005307. Yield sensitivity is:

$$\psi_C=-\tau SA N(d_1),\qquad \psi_P=\tau SA N(-d_1)=-\tau S\Delta_P.$$

Increasing dividend yield lowers the modeled forward and therefore lowers a call's value. For a +10-basis-point yield change, the call estimate is $-63.455836(0.001)=-£0.063456$.

### Separate Discounting from Equity Financing

The basis lesson distinguished option discounting, equity financing, and actual desk borrowing. To expose the difference, use a quotation model with $F=S e^{(b-q)\tau}$ and discount $P_d=e^{-r_d\tau}$, where $b$ is the carry-financing rate and $r_d$ the option discount rate. With forward-Black call value $C=P_d[F N(d_1)-K N(d_2)]$:

$$C_{r_d}\big|_F=-\tau C,\qquad C_b\big|_{r_d}=\tau P_d F N(d_1).$$

At the baseline $b=r_d=r$, these are −10.386279 and +63.455836 GBP per unit rate. Their sum is +53.069557, the classical rho. A one-basis-point **discount-only** bump lowers the call by approximately £0.001039, while a **carry-only** bump raises it by approximately £0.006346. The graph shows exact ten-basis-point bumps beside these first-order estimates.

For dated cash dividends, bump the relevant amount/date and rebuild the forward instead of applying a continuous-yield sensitivity. For multiple curve nodes, specify which curve and which maturity bucket moves. A parallel-rate rho cannot describe every curve twist. These independent input bumps are quotation scenarios; a particular market's coherent curve model and instrument constraints determine which joint changes are meaningful.

```python:line-numbers
def forward_call(f, k, t, discount_rate, vol):
    z = vol*np.sqrt(t)
    first = (np.log(f/k)+z*z/2)/z
    return np.exp(-discount_rate*t)*(f*norm.cdf(first)-k*norm.cdf(first-z))

forward = S*np.exp((r-q)*tau)
rate_bump = .001
carry_sensitivity = tau*S*np.exp(-q*tau)*norm.cdf(g["d1"])
discount_sensitivity = -tau*g["value"]
rate_predictions = rate_bump*np.array([discount_sensitivity, carry_sensitivity, g["rho"], g["yield_sensitivity"]])
rate_actual = np.array([
    forward_call(forward,K,tau,r+rate_bump,sigma)-g["value"],
    forward_call(forward*np.exp(rate_bump*tau),K,tau,r,sigma)-g["value"],
    option_price(S,K,tau,r+rate_bump,sigma,q)-g["value"],
    option_price(S,K,tau,r,sigma,q+rate_bump)-g["value"],
])
print(f"Discount rho {discount_sensitivity:.9f} + carry rho {carry_sensitivity:.9f} = {g['rho']:.9f}")
print(pd.DataFrame({"Exact GBP": rate_actual, "Linear GBP": rate_predictions},
      index=["Discount only", "Carry only", "Classical rate", "Dividend yield"]).to_string())
print("<ECHARTS_DATA>"+json.dumps({"greeksCarry": {
    "type": "bar", "title": "Different Rate Bumps Answer Different Questions",
    "xAxis": {"type": "category", "name": "Input increased by ten basis points", "data": ["Discount", "Carry", "Both rates", "Yield"]},
    "yAxisName": "One-share call value change (GBP)", "series": {"Exact": rate_actual.tolist(), "Linear": rate_predictions.tolist()},
    "seriesOptions": {"Linear": {"itemStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="greeks-carry" />

**Experiment:** double the rate bump and compare approximation errors. **Check:** can a desk use its unsecured borrowing rate as the option discount rate without justification? No. Actual hedge financing is a cash-account input; it does not automatically replace a collateral-consistent pricing input.

## 6. Vanna and Charm: Delta Moves Without a Spot Move

You have neutralized delta at the current spot. Volatility changes while spot stays fixed. The option's delta changes, so the hedge can become unbalanced anyway. **Vanna** measures this cross-effect:

$$\operatorname{Vanna}=V_{S\sigma}=\frac{\partial\Delta}{\partial\sigma}
=\frac{\partial\nu}{\partial S}=-A\phi(d_1)\frac{d_2}{\sigma}.$$

For the first equality, differentiate $A N(d_1)$ using $d_{1,\sigma}=-d_2/\sigma$. Equality of the two mixed derivatives follows from smoothness in the interior. Call and put vanna agree because their delta difference $A$ is independent of volatility. At the baseline $d_2>0$, so vanna is negative: increasing volatility slightly **reduces** call delta here. Its sign can change elsewhere.

**Charm** is delta's calendar-time derivative at fixed spot, volatility, and rates. Define the intermediate derivative:

$$h=d_{1,\tau}=\frac{(r-q+\sigma^2/2)\tau-\log(S/K)}{2\sigma\tau^{3/2}}.$$

Since $\Delta_C=A N(d_1)$, its remaining-life derivative is $-q\Delta_C+A\phi(d_1)h$. Reversing the sign for calendar time gives, for either call or put:

$$\operatorname{Charm}=\Delta_t=q\Delta-A\phi(d_1)h.$$

At our baseline, $h=d_1/(2\tau)=0.171975410$, vanna is −0.270648252, and charm is −0.064667702 per calendar year. A one-day change in delta is approximately $\operatorname{Charm}/365=-0.000177172$; a two-volatility-point change is approximately $\operatorname{Vanna}(0.02)=-0.005412965$. Their exact changes are −0.000177308 and −0.004588522 respectively, in **shares per one-share option**.

The first chart holds spot/time fixed and varies volatility. The second holds spot/volatility fixed and lets calendar days pass. Both compare exact recalculated delta with a first-order estimate from today's sensitivities; the vertical axes are zoomed to show these small changes. A delta-neutral position needs monitoring even during an unchanged spot quote.

```python:line-numbers
def cross_greeks(s, k, t, rate, vol, yield_rate=0., kind="call"):
    base = core_greeks(s,k,t,rate,vol,yield_rate,kind)
    d1, d2 = base["d1"], base["d2"]
    density = np.exp(-yield_rate*t)*norm.pdf(d1)
    h = ((rate-yield_rate+vol**2/2)*t-np.log(s/k))/(2*vol*t**1.5)
    return dict(vanna=-density*d2/vol, charm=yield_rate*base["delta"]-density*h,
                volga=base["vega"]*d1*d2/vol, h=h)

cross = cross_greeks(S,K,tau,r,sigma,q)
elapsed_days = np.linspace(0., 90., 31)
delta_vol = np.array([core_greeks(S,K,tau,r,sigma+z)["delta"] for z in vol_moves])
delta_time = np.array([core_greeks(S,K,tau-d/365,r,sigma)["delta"] for d in elapsed_days])
print("Cross sensitivities:", cross)
print(f"Delta change, +2 vol points: predicted {cross['vanna']*.02:.9f}; exact {core_greeks(S,K,tau,r,.22)['delta']-g['delta']:.9f}")
print(f"Delta change, one day: predicted {cross['charm']/365:.9f}; exact {core_greeks(S,K,tau-day,r,sigma)['delta']-g['delta']:.9f}")
print("<ECHARTS_DATA>"+json.dumps({
    "greeksVanna": {"type": "line", "title": "Volatility Can Change the Required Stock Hedge",
        "xAxis": {"type": "value", "name": "Volatility change (percentage points)"}, "yAxisName": "Call delta (shares per one-share option)",
        "yAxis": {"type": "value", "scale": True},
        "series": {"Exact delta": np.column_stack([100*vol_moves,delta_vol]).tolist(),
                   "Vanna estimate": np.column_stack([100*vol_moves,g["delta"]+cross["vanna"]*vol_moves]).tolist()},
        "seriesOptions": {"Vanna estimate": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}}},
    "greeksCharm": {"type": "line", "title": "Calendar Time Can Change Delta at Unchanged Spot",
        "xAxis": {"type": "value", "name": "Calendar days elapsed"}, "yAxisName": "Call delta (shares per one-share option)",
        "yAxis": {"type": "value", "scale": True},
        "series": {"Exact delta": np.column_stack([elapsed_days,delta_time]).tolist(),
                   "Charm estimate": np.column_stack([elapsed_days,g["delta"]+cross["charm"]*elapsed_days/365]).tolist()},
        "seriesOptions": {"Charm estimate": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}}},
}, allow_nan=False))
```
<Editor id="greeks-cross" />

**Experiment:** repeat at spot £90 and £110, recalculating the base delta and cross sensitivities each time. **Check:** does a zero delta guarantee zero vanna or charm? No. Cancellation of the initial stock exposure says nothing about how that exposure changes with another input.

## 7. Speed, Zomma, Color, Veta, and Ultima

These names describe derivatives of sensitivities already introduced. They are useful when monitoring a hedge's stability, especially near expiry or after a large input change. We use the following definitions explicitly because time-related naming/sign conventions differ between systems.

| Greek | Definition | Approximate sensitivity change |
| --- | --- | --- |
| Speed | $\Gamma_S$ | $\Delta\Gamma\approx\operatorname{Speed}\,\Delta S$ |
| Zomma | $\Gamma_\sigma$ | $\Delta\Gamma\approx\operatorname{Zomma}\,\Delta\sigma$ |
| Color | $\Gamma_t=-\Gamma_\tau$ | $\Delta\Gamma\approx\operatorname{Color}\,\Delta t$ |
| Veta | $\nu_t=-\nu_\tau$ | $\Delta\nu\approx\operatorname{Veta}\,\Delta t$ |
| Ultima | $V_{\sigma\sigma\sigma}$ | $\Delta\operatorname{Volga}\approx\operatorname{Ultima}\,\Delta\sigma$ |

Their units follow by dividing the original sensitivity's units by the bumped input's units. For example, color is gamma per calendar year. Ultima is GBP per unit decimal volatility cubed; the cubic **price** term is $\operatorname{Ultima}(\Delta\sigma)^3/6$, not ultima times a one-point volatility move.

### Derive the Formulas from Logarithmic Changes

Because $\Gamma=A\phi(d_1)/(S\sigma\sqrt\tau)$, differentiate its logarithm. The spot derivative has the explicit $-1/S$ term and the density term $-d_1/(S\sigma\sqrt\tau)$. Multiply their sum by gamma:

$$\operatorname{Speed}=-\frac{\Gamma}{S}\left(1+\frac{d_1}{\sigma\sqrt\tau}\right),\qquad
\operatorname{Zomma}=\frac{\Gamma}{\sigma}(d_1d_2-1).$$

For zomma, the explicit $1/\sigma$ contributes $-1/\sigma$ and the density contributes $d_1d_2/\sigma$. Differentiating the time factors and reversing the sign gives:

$$\operatorname{Color}=\Gamma\left(q+\frac{1}{2\tau}+d_1h\right),\qquad
\operatorname{Veta}=\nu\left(q-\frac{1}{2\tau}+d_1h\right).$$

The square root of time occurs in the **denominator** of gamma but the **numerator** of vega, producing the different half-time terms. At $S=K$, $r=q=0$, and short maturity, gamma can become very large while vega approaches zero. Small absolute option value does not imply a stable delta hedge.

Finally differentiate $\operatorname{Volga}=\nu d_1d_2/\sigma$. Use $d_{1,\sigma}=-d_2/\sigma$, $d_{2,\sigma}=-d_1/\sigma$, and $\nu_\sigma=\operatorname{Volga}$:

$$\operatorname{Ultima}=-\frac{\nu}{\sigma^2}
\left[d_1d_2(1-d_1d_2)+d_1^2+d_2^2\right].$$

For a numerical substitution, baseline speed is $-\Gamma/100\,[1+0.343950821/0.2]$. Multiply it by a £1 spot move to predict the gamma change. Baseline color is $\Gamma[0.5+0.343950821(0.171975410)]$; divide by 365 to predict one day's gamma change. The table below works all five examples, printing the coefficient, scaled prediction, and exact sensitivity change.

The two charts follow gamma and vega through time at fixed spot. Near expiry their behavior is strongly strike-dependent. The plotted constant starting color/veta approximations are deliberately local; extend them far enough and they can become implausible.

```python:line-numbers
def higher_greeks(s, k, t, rate, vol, yield_rate=0., kind="call"):
    base = core_greeks(s,k,t,rate,vol,yield_rate,kind)
    mixed = cross_greeks(s,k,t,rate,vol,yield_rate,kind)
    d1, d2, h = base["d1"], base["d2"], mixed["h"]
    gamma, vega = base["gamma"], base["vega"]
    return dict(speed=-gamma/s*(1+d1/(vol*np.sqrt(t))),
                zomma=gamma*(d1*d2-1)/vol,
                color=gamma*(yield_rate+1/(2*t)+d1*h),
                veta=vega*(yield_rate-1/(2*t)+d1*h),
                ultima=-vega/vol**2*(d1*d2*(1-d1*d2)+d1*d1+d2*d2))

higher = higher_greeks(S,K,tau,r,sigma,q)
higher_examples = pd.DataFrame([
    ["Speed", higher["speed"], higher["speed"]*1., core_greeks(S+1,K,tau,r,sigma)["gamma"]-g["gamma"]],
    ["Zomma", higher["zomma"], higher["zomma"]*.01, core_greeks(S,K,tau,r,.21)["gamma"]-g["gamma"]],
    ["Color", higher["color"], higher["color"]*day, core_greeks(S,K,tau-day,r,sigma)["gamma"]-g["gamma"]],
    ["Veta", higher["veta"], higher["veta"]*day, core_greeks(S,K,tau-day,r,sigma)["vega"]-g["vega"]],
    ["Ultima", higher["ultima"], higher["ultima"]*.01, cross_greeks(S,K,tau,r,.21)["volga"]-cross["volga"]],
], columns=["Greek", "Unscaled coefficient", "Predicted change", "Exact change"])
print(higher_examples.to_string(index=False, float_format=lambda x:f"{x:.9f}"))
longer_days = np.linspace(0., 350., 71)
time_risks = [core_greeks(S,K,tau-d/365,r,sigma) for d in longer_days]
time_charts = {}
for name, sensitivity, title, unit in [("gamma", "color", "Gamma Can Grow as Expiry Approaches", "Gamma (delta change per GBP/share)"),
                                       ("vega", "veta", "Vega and Gamma Need Not Move Together", "Vega (GBP per unit decimal volatility)")]:
    time_charts["greeks"+sensitivity.title()] = {
        "type": "line", "title": title, "xAxis": {"type": "value", "name": "Calendar days elapsed"}, "yAxisName": unit,
        "series": {"Exact sensitivity": [[float(d), float(x[name])] for d,x in zip(longer_days,time_risks)],
                   "Initial time-sensitivity estimate": np.column_stack([longer_days,g[name]+higher[sensitivity]*longer_days/365]).tolist()},
        "seriesOptions": {"Initial time-sensitivity estimate": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}},
    }
print("<ECHARTS_DATA>"+json.dumps(time_charts, allow_nan=False))
```
<Editor id="greeks-higher" />

**Experiment:** change spot to £120 throughout this cell, including the baseline risk dictionary. Gamma need not increase toward expiry for an option already well in the money. **Check:** why not calculate these smooth formulas at exactly zero days? They describe a smooth pre-expiry price, not the strike kink of the terminal payoff. Report the payoff and scenario exposure instead of an infinite or fabricated Greek.

## 8. Experiment: When Does a Local Hedge Approximation Work?

The independent widget repeats the visible call-pricing, delta, and gamma formulas at spot=strike=£100, one year, no dividends, and $r=\log(1.05)$. The volatility control changes the **baseline** volatility at which the price and sensitivities are calculated. The spot-move control selects a scenario on the horizontal axis. It does not change time or volatility during that scenario.

Blue is exact option repricing; grey is delta alone; orange adds gamma. A blue outlined circle marks exact repricing and a smaller orange outlined diamond marks the delta–gamma estimate. Their different shapes remain distinguishable when the values nearly coincide. At a zero move both changes are zero. A larger initial volatility generally spreads the transition of delta across a wider range of spot prices; examine the curve rather than assuming gamma always rises with volatility.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_greeks_hedge_echart,
    spot_move=widgets.FloatSlider(value=5., min=-20., max=20., step=1., description="Spot move (£)", continuous_update=False),
    volatility_percent=widgets.FloatSlider(value=20., min=10., max=60., step=5., description="Volatility (%)", continuous_update=False),
)
widget_instance
```
<Editor id="greeks-approximation-widget" />

**Try it:** compare ±£1 and ±£20 at 10% and 40% volatility. **Check:** does adding gamma make an approximation exact? No. Higher-order spot terms remain, and mixed/time/volatility terms are absent from this particular experiment.

## 9. Attribute a Joint Move Without Calling the Approximation Exact

For a short interval, a useful selected-term price expansion is:

$$\Delta V\approx\Delta\,\Delta S+\Theta\,\Delta t+\nu\,\Delta\sigma
+\tfrac12\Gamma(\Delta S)^2
+\operatorname{Vanna}\,\Delta S\Delta\sigma
+\tfrac12\operatorname{Volga}(\Delta\sigma)^2.$$

The repeated delta symbol has two roles: the unadorned $\Delta$ is the Greek, while $\Delta S$ is an input change. Vanna has coefficient **one**, not one half: the two symmetric mixed terms in the multivariate Taylor expansion combine. This displayed selection omits time–spot, time–volatility, second-time, rate, and higher-order terms. The remainder is measured, not assumed zero.

Take a £2 spot rise, a one-volatility-point increase, and one calendar day elapsed. Delta contributes $0.634558364(2)=£1.269117$; vega contributes about £0.376029; theta contributes about −£0.017396; gamma adds approximately £0.037603. Vanna and volga refine the estimate. Exact repricing uses spot 102, volatility 0.21, and time $1-1/365$ together.

The graph prints each signed contribution and a **remainder equal to exact change minus their sum**. A second experiment scales every input move down together. A sensible local approximation should improve as the move shrinks. Another scenario has larger shocks and a much longer interval; a small-shock formula is not a replacement for its full repricing.

### A Smile Changes What “Hold Volatility Fixed” Means

Our delta is a partial derivative with the option's implied volatility fixed. Suppose a scenario rule makes that volatility rise by 0.001 for every £1 spot rise. The **total** spot sensitivity along that rule is $\Delta+\nu(0.001)\approx0.672161$, rather than 0.634558. That rule is an assumed surface response, not a Black–Scholes prediction. Later [Reading the Options Market: Implied Volatility and Surfaces](./d.0-overview.md#volatility-surfaces) will distinguish fixed-strike, moneyness, and delta-coordinate surface conventions.

```python:line-numbers
def price_attribution(ds, dv, dt):
    terms = np.array([g["delta"]*ds, g["theta"]*dt, g["vega"]*dv,
                      .5*g["gamma"]*ds*ds, cross["vanna"]*ds*dv, .5*cross["volga"]*dv*dv])
    exact = option_price(S+ds,K,tau-dt,r,sigma+dv)-g["value"]
    return exact, terms, exact-terms.sum()

exact_joint, joint_terms, joint_remainder = price_attribution(2., .01, day)
scales = np.array([1., .5, .25, .125])
joint_errors = [price_attribution(2*a,.01*a,day*a)[2] for a in scales]
print(f"Joint exact change: {exact_joint:.9f}; explained: {joint_terms.sum():.9f}; remainder: {joint_remainder:.9f} GBP")
print("Remainders as all moves shrink:", joint_errors)
print("Large-move exact / terms / remainder:", price_attribution(15., .10, 30/365))
surface_slope = .001
surface_delta = g["delta"]+g["vega"]*surface_slope
surface_fd = (option_price(S+.01,K,tau,r,sigma+surface_slope*.01)-option_price(S-.01,K,tau,r,sigma-surface_slope*.01))/.02
print(f"Assumed-surface total delta: {surface_delta:.9f}; bumped-price check: {surface_fd:.9f}")
print("<ECHARTS_DATA>"+json.dumps({"greeksAttribution": {
    "type": "bar", "title": "Reconcile Local Greek Contributions with Exact Repricing",
    "xAxis": {"type": "category", "name": "Contribution to option price change", "data": ["Delta", "Theta", "Vega", "Gamma", "Vanna", "Volga", "Remainder", "Exact"]},
    "yAxisName": "One-share call value change (GBP)", "series": {"Amount": [*joint_terms.tolist(), float(joint_remainder), float(exact_joint)]},
}}, allow_nan=False))
```
<Editor id="greeks-attribution" />

**Experiment:** reverse the spot move but retain the volatility rise. The gamma and volga terms keep their signs, but delta and vanna contributions reverse. **Check:** is the remainder trading alpha? No. Here it is omitted Taylor terms and numerical approximation. A real P&L explain can also contain model/input changes, execution, fees, and data differences, which need separate reconciliation.

## 10. Hedge More Than Delta: A Small Option Book

Suppose you are short one one-share baseline call. Stock can neutralize delta, but its gamma and vega are zero. To offset curvature and volatility exposure, consider two other European calls on the same non-dividend-paying share: one with strike £95 and 0.5 years left, and one with strike £110 and two years left. All are quoted at the same synthetic 20% volatility. Their time horizons differ deliberately.

Let $a$ and $b$ be signed numbers of these hedge options, positive for purchases. To neutralize gamma and a **parallel** volatility bump:

$$\begin{bmatrix}\Gamma_1&\Gamma_2\\\nu_1&\nu_2\end{bmatrix}
\begin{bmatrix}a\\b\end{bmatrix}=
\begin{bmatrix}\Gamma_{\mathrm{target}}\\\nu_{\mathrm{target}}\end{bmatrix}.$$

The right side is positive because it offsets a **short** target. After solving, use stock quantity $n=\Delta_{\mathrm{target}}-a\Delta_1-b\Delta_2$; a negative quantity means selling stock short. For zero initial net wealth, the cash balance is $B_0=C_{\mathrm{target}}-aC_1-bC_2-nS$. Negative cash means borrowing. This is a signed position budget, not a long-only portfolio allocation.

Why different expiries? Under our common-volatility model, $\nu=S^2\sigma\tau\Gamma$. At the same expiry every vanilla option has the same vega/gamma ratio, whatever its strike. Two same-expiry options cannot provide two independent gamma/vega directions. A solver cannot manufacture the missing rank. With expiries 0.5 and 2 years, the ratios differ and the two-row system can be solved.

Work the solution by hand first. Here the vega/gamma ratios are 1,000 for the short-dated hedge, 4,000 for the long-dated hedge, and 2,000 for the target. Write $x=a\Gamma_1$ and $y=b\Gamma_2$. Then $x+y=\Gamma_{\mathrm{target}}$ and $1000x+4000y=2000\Gamma_{\mathrm{target}}$, giving $x=2\Gamma_{\mathrm{target}}/3$ and $y=\Gamma_{\mathrm{target}}/3$. Dividing by the individual gammas produces **0.533857** short-dated calls and **0.449319** long-dated calls. The remaining hedge is approximately **−0.005285 shares** and **£0.565913 cash**, under frictionless stock borrowing. The numerical solver below should reproduce this allocation.

The cell prints each hedge quantity and budget. The chart compares the short target with the entire hedged book after scaling delta by a £1 move, gamma by half a £1 move squared, and vega by a one-point parallel move. All bars are **GBP local contributions under different illustrative shocks**; they are not numbers to sum as one scenario. The total book's vanna, volga, and charm generally remain nonzero.

```python:line-numbers
hedge_specs = [(95., .5), (110., 2.)]
hedge_risks = [core_greeks(S,k,t,r,sigma) for k,t in hedge_specs]
risk_matrix = np.array([[x["gamma"] for x in hedge_risks], [x["vega"] for x in hedge_risks]])
option_units = np.linalg.solve(risk_matrix, [g["gamma"],g["vega"]])
stock_units = g["delta"]-sum(n*x["delta"] for n,x in zip(option_units,hedge_risks))
book_cash = g["value"]-sum(n*x["value"] for n,x in zip(option_units,hedge_risks))-stock_units*S
book_exposures = {name: -g[name]+sum(n*x[name] for n,x in zip(option_units,hedge_risks))+(stock_units if name=="delta" else 0)
                  for name in ("delta","gamma","vega")}
book_cross = {name: -cross[name]+sum(n*cross_greeks(S,k,t,r,sigma)[name] for n,(k,t) in zip(option_units,hedge_specs))
              for name in ("vanna","volga","charm")}
same_expiry = [core_greeks(S,k,1.,r,sigma) for k in (95.,110.)]
same_expiry_matrix = np.array([[x["gamma"] for x in same_expiry], [x["vega"] for x in same_expiry]])
print("Hedge option quantities:", option_units, "; stock:", stock_units, "; cash GBP:", book_cash)
print("Remaining core exposures:", book_exposures, "; cross exposures:", book_cross)
print("Same-expiry matrix rank:", np.linalg.matrix_rank(same_expiry_matrix))
# Scale by illustrative GBP shocks before inspecting conditioning; raw rows have different units.
scaled_risk_matrix = np.diag([.5,.01])@risk_matrix
print("Shock-scaled sensitivity condition ratio:", np.linalg.cond(scaled_risk_matrix))
def book_value(ds=0., dv=0., elapsed=0., hedge_vol_moves=None):
    moves = [dv,dv] if hedge_vol_moves is None else hedge_vol_moves
    options = sum(n*option_price(S+ds,k,t-elapsed,r,sigma+z) for n,(k,t),z in zip(option_units,hedge_specs,moves))
    return -option_price(S+ds,K,tau-elapsed,r,sigma+dv)+options+stock_units*(S+ds)+book_cash*np.exp(r*elapsed)

book_scenarios = {"Spot +1":book_value(ds=1), "Parallel vol +1 point":book_value(dv=.01),
                  "Target-only vol +1 point":book_value(dv=.01,hedge_vol_moves=[0.,0.]),
                  "Joint move and one day":book_value(ds=2,dv=.01,elapsed=day)}
print("Exact funded book revaluations (GBP):", book_scenarios)
print("<ECHARTS_DATA>"+json.dumps({"greeksBook": {
    "type": "bar", "title": "Use Different Instruments for Independent Risk Directions",
    "xAxis": {"type": "category", "name": "Separate illustrative local shocks", "data": ["Delta: spot +1", "Gamma: spot +1", "Vega: vol +1pt"]},
    "yAxisName": "Local position contribution (GBP)",
    "series": {"Short target": [-g["delta"],-.5*g["gamma"],-.01*g["vega"]],
               "Hedged book": [book_exposures["delta"],.5*book_exposures["gamma"],.01*book_exposures["vega"]]},
    "seriesOptions": {"Hedged book": {"itemStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="greeks-book" />

**Experiment:** increase only the target's implied volatility, leaving the hedge options' implied volatilities unchanged. The book loses value even though aggregate vega for a parallel bump is zero. **Check:** what if hedge expiries become almost equal? The independent directions become poorly conditioned; small quote or Greek errors can produce unstable quantities. Inspect economically scaled sensitivities, liquidity, and lot sizes before accepting a numerical solution.

The gamma/vega-neutral book is a local illustration, not a complete hedge policy. It has unmatched maturities, residual surface exposures, and future rebalancing needs. The subsequent [Spreads and Basic Option Combinations](./d.0-overview.md#option-spreads) will build and explain signed option positions systematically.

## 11. Trade a Delta Hedge and Reconcile the Cash Account

Return to one short one-share call and a stock hedge. Receive the call premium, buy delta shares, and borrow the balance. We now include **five basis points of stock notional traded** as a proportional execution cost, at entry, every rebalance, and final stock liquidation. We assume the option premium itself is received at model value and no separate collateral requirement; the basis chapter explains how margin funding would add account terms. Cash, including any debt, accrues at the same continuous rate $r$.

Hold old quantity $n_i$ over an interval. Immediately before rebalancing:

$$W^-_{i+1}=n_i S_{i+1}+B_i e^{r\Delta t}.$$

After calculating new delta $n_{i+1}$, let trade value $X=(n_{i+1}-n_i)S_{i+1}$ and cost $c=0.0005|X|$. Then:

$$B_{i+1}=B_i e^{r\Delta t}-X-c,\qquad
W^+_{i+1}=W^-_{i+1}-c.$$

For the first move from £100 to £102 after a quarter-year, initial stock is worth $0.634558364(100)=£63.455836$ and its entry fee is £0.031728. Initial cash is $10.386279497-63.4558364-0.0317279\approx-£53.101285$. Accrue that actual balance before buying the next hedge quantity. Do not reset cash to model option value minus stock: that would inject or withdraw money and erase the hedge error.

Use observation dates 0, 0.25, 0.5, 0.75, and 1 year and the invented spot path [100, 102, 97, 105, 103]. At expiry, sell all stock and pay the £3 call payoff. The resulting cash is the short-option-plus-hedge profit from a zero initial net position. It is not a percentage return on zero invested capital.

After the first rebalance, the account holds approximately 0.659904 shares and −£56.339486 cash. Its £10.970704 hedge wealth exceeds the £10.001555 option liability by £0.969149. At expiry, after paying the liability, this particular low-movement path produces **£5.165924** with costs, versus **£5.258807** without costs. The difference, **£0.092883**, is all stock fees accumulated to expiry. These are path-specific outcomes, not expected profits from selling an option.

The first chart compares hedge wealth **before paying the liability** with the remaining option value/payoff. The second compares that gap with and without stock costs. The cell also reconciles every interval into old stock gain, cash interest, negative option change, and negative execution cost. The components add exactly; Greek approximations are not used to force the cash identity.

```python:line-numbers
def delta_hedge(spots, dates, pricing_vol=.20, fee_rate=.0005, funding_rate=r):
    spots, dates = np.asarray(spots,dtype=float), np.asarray(dates,dtype=float)
    if len(spots)!=len(dates) or len(spots)<2 or dates[0]!=0 or dates[-1]!=tau or np.any(np.diff(dates)<=0) or np.any(spots<=0):
        raise ValueError("Use positive spots and increasing dates from zero to option expiry")
    initial = core_greeks(spots[0],K,tau,r,pricing_vol)
    holding = initial["delta"]
    fee = fee_rate*abs(holding*spots[0])
    cash = initial["value"]-holding*spots[0]-fee
    rows = [[0.,spots[0],holding,cash,initial["value"]-fee,initial["value"],fee,0.,0.,0.,0.,-fee]]
    previous_option = initial["value"]
    for i in range(1,len(dates)):
        dt = dates[i]-dates[i-1]
        interest = cash*np.expm1(funding_rate*dt)
        stock_gain = holding*(spots[i]-spots[i-1])
        accrued = cash+interest
        before = holding*spots[i]+accrued
        remaining = tau-dates[i]
        option = option_price(spots[i],K,remaining,r,pricing_vol)
        new_holding = core_greeks(spots[i],K,remaining,r,pricing_vol)["delta"] if remaining>0 else 0.
        trade = (new_holding-holding)*spots[i]
        fee = fee_rate*abs(trade)
        cash = accrued-trade-fee
        wealth = cash+new_holding*spots[i]
        budget_error = wealth-before+fee
        option_change = option-previous_option
        rows.append([dates[i],spots[i],new_holding,cash,wealth,option,fee,stock_gain,interest,option_change,budget_error,wealth-option])
        holding, previous_option = new_holding, option
    return pd.DataFrame(rows,columns=["Time","Spot","Units","Cash","Hedge wealth","Option","Fee","Stock gain","Interest","Option change","Budget error","Net P&L"])

hand_spots, hand_dates = [100.,102.,97.,105.,103.], np.linspace(0.,tau,5)
costly_ledger = delta_hedge(hand_spots,hand_dates)
free_ledger = delta_hedge(hand_spots,hand_dates,fee_rate=0.)
funded_fees = np.sum(costly_ledger.Fee*np.exp(r*(tau-costly_ledger.Time)))
print(costly_ledger.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(f"Net terminal P&L: no costs {free_ledger['Net P&L'].iloc[-1]:.9f}; with costs {costly_ledger['Net P&L'].iloc[-1]:.9f} GBP")
print(f"Fees accumulated to expiry: {funded_fees:.9f} GBP")
interval_explain = costly_ledger["Stock gain"]+costly_ledger.Interest-costly_ledger["Option change"]-costly_ledger.Fee
print("Interval explain minus net P&L changes:", (interval_explain-costly_ledger["Net P&L"].diff().fillna(costly_ledger["Net P&L"].iloc[0])).to_numpy())
print("<ECHARTS_DATA>"+json.dumps({
    "greeksLedger": {"type": "line", "title": "Fund the Trades Instead of Resetting Wealth to the Model",
        "xAxis": {"type": "value", "name": "Elapsed years"}, "yAxisName": "Hedge assets or option liability (GBP)",
        "series": {"Hedge wealth": costly_ledger[["Time","Hedge wealth"]].values.tolist(), "Call liability": costly_ledger[["Time","Option"]].values.tolist()},
        "seriesOptions": {"Call liability": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}}},
    "greeksLedgerCosts": {"type": "line", "title": "Execution Costs Consume the Same Account's Wealth",
        "xAxis": {"type": "value", "name": "Elapsed years"}, "yAxisName": "Hedge assets minus option liability (GBP)",
        "series": {"Without costs": free_ledger[["Time","Net P&L"]].values.tolist(), "With costs": costly_ledger[["Time","Net P&L"]].values.tolist()},
        "seriesOptions": {"With costs": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}}}},
}, allow_nan=False))
```
<Editor id="greeks-ledger" />

**Experiment:** increase only `funding_rate` by 0.02 while retaining the original pricing rate. The hedge must finance borrowing at worse terms without retroactively receiving a higher option premium. **Check:** is the stock purchase itself a loss? No. It exchanges cash for stock; the fee reduces wealth. Interest and subsequent price changes alter wealth separately.

### Stock Delta and Futures Delta Use Different Quantities

For an idealized no-dividend future expiring with the option, $F=S e^{r\tau}$ and $F_S=e^{r\tau}$. A futures contract with multiplier $M$ therefore requires $n_F=\Delta/(M e^{r\tau})$ to match one option's local stock exposure. At $M=10$, the baseline is $0.634558364/(10\times1.05)=0.060434130$ futures contracts. For an option covering 100 shares, multiply the numerator by 100.

The quote is not a premium paid for the future. Variation payments, collateral, and borrowing need their own dates and rates. Revisit the explicit futures ledgers in [Deriving and Using Black–Scholes](./black-scholes.md) and [Futures Basis, Dividends, and Implied Financing](./futures-basis.md) before replacing a stock hedge with an exchange implementation.

## 12. Rebalancing Frequency, Costs, and Realized Movement

More frequent trading reduces discretization error under the frictionless model in an appropriate limiting sense. It does **not** guarantee smaller absolute error on every path, nor better profit after costs. We need repeated controlled paths, not one favorable chart.

Generate 256 synthetic GBM paths on 256 equally spaced annual intervals with fixed seed `20261102`, physical drift 8%, and realized-path diffusion volatility 20%. Sample 4, 16, 64, and 256 hedge dates from the **same** fine paths. The option premium and hedge deltas use 20% pricing volatility, and cash uses $r=\log(1.05)$. Drift is an investment scenario assumption, not a replacement for the pricing rate.

For each frequency, compute the root mean squared terminal replication error $\sqrt{\frac1N\sum_i E_i^2}$, in GBP per one-share option, and mean funded stock fees. This RMS combines dispersion and bias; it is not a return volatility or a statistical confidence interval. The first chart compares RMS with and without costs. The second shows average total fees accumulated to expiry.

To understand the mechanism, a long option delta-hedged with short stock and a financing account has approximate short-interval gain:

$$\tfrac12\Gamma\left[(\Delta S)^2-\sigma_{\mathrm{impl}}^2S^2\Delta t\right],$$

when pricing inputs stay fixed apart from time, $q=0$, and higher-order/discrete funding terms are neglected. This follows by combining the price expansion with the pricing PDE and subtracting stock/cash carry. At our baseline over one day, a £2 move gives about $0.5(0.018801440)[4-400/365]=£0.027301$ for the long-option hedged side. The short-option hedge has the opposite sign. It is a local approximation, not a path-independent variance trade.

Repeat the path experiment at 30% diffusion volatility while still selling and hedging options at 20%. The simulated mean short-side result should deteriorate in this experiment. The exposure is gamma-weighted through time; quote revisions, jumps, costs, and dynamic hedging make it different from a plain realized-variance payoff. A gap can also overwhelm a pre-gap delta hedge: rerun the hand ledger with a sudden £20 move to inspect the actual account.

```python:line-numbers
path_count, fine_count = 256, 256
normal_increments = np.random.default_rng(20261102).standard_normal((fine_count,path_count))*np.sqrt(tau/fine_count)
times = np.linspace(0.,tau,fine_count+1)
brownian = np.vstack([np.zeros(path_count),np.cumsum(normal_increments,axis=0)])
def simulated_paths(realized_vol):
    return S*np.exp((.08-realized_vol**2/2)*times[:,None]+realized_vol*brownian)

def hedge_sample(paths, count, fee_rate):
    sampled = paths[::fine_count//count]
    dt = tau/count
    units = np.full(path_count,g["delta"])
    fees = fee_rate*units*S
    cash = np.full(path_count,g["value"])-units*S-fees
    accumulated_fees = fees*np.exp(r*tau)
    for i in range(1,count+1):
        cash *= np.exp(r*dt)
        remaining = max(tau-i*dt,0.)
        if i == count:
            new_units = np.zeros(path_count)
        else:
            d1 = (np.log(sampled[i]/K)+(r+sigma**2/2)*remaining)/(sigma*np.sqrt(remaining))
            new_units = norm.cdf(d1)
        trade = (new_units-units)*sampled[i]
        fees = fee_rate*np.abs(trade)
        cash -= trade+fees
        accumulated_fees += fees*np.exp(r*remaining)
        units = new_units
    return cash-np.maximum(sampled[-1]-K,0.), accumulated_fees

paths = simulated_paths(.20)
frequencies = [4,16,64,256]
frequency_results = {}
for count in frequencies:
    no_cost, _ = hedge_sample(paths,count,0.)
    with_cost, fees = hedge_sample(paths,count,.0005)
    frequency_results[count] = dict(no_cost=no_cost, with_cost=with_cost, fees=fees)
frequency_table = pd.DataFrame([
    [n,np.sqrt(np.mean(x["no_cost"]**2)),np.sqrt(np.mean(x["with_cost"]**2)),np.mean(x["fees"]),np.mean(x["with_cost"])]
    for n,x in frequency_results.items()],columns=["Rebalances","RMS no cost","RMS with cost","Mean funded fees","Mean net P&L"])
misspecified_pnl, _ = hedge_sample(simulated_paths(.30),256,.0005)
print(frequency_table.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(f"30% path volatility / 20% pricing volatility, mean net P&L: {misspecified_pnl.mean():.9f} GBP")
print(f"Local long-option gamma/variance illustration: {.5*g['gamma']*(4-sigma**2*S**2/365):.9f} GBP")
print("<ECHARTS_DATA>"+json.dumps({
    "greeksFrequency": {"type": "line", "title": "Compare Hedge Error on the Same Ensemble of Paths",
        "xAxis": {"type": "category", "name": "Rebalancing intervals per year", "data": [str(n) for n in frequencies]},
        "yAxisName": "Root mean squared terminal hedge error (GBP)",
        "series": {"No costs": frequency_table["RMS no cost"].tolist(), "With costs": frequency_table["RMS with cost"].tolist()},
        "seriesOptions": {"With costs": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}}}},
    "greeksTurnover": {"type": "bar", "title": "Frequent Rebalancing Also Accumulates Trading Costs",
        "xAxis": {"type": "category", "name": "Rebalancing intervals per year", "data": [str(n) for n in frequencies]},
        "yAxisName": "Mean fees accumulated to expiry (GBP)", "series": {"Funded fees": frequency_table["Mean funded fees"].tolist()}},
}, allow_nan=False))
```
<Editor id="greeks-frequency" />

**Experiment:** increase the stock fee from five to 25 basis points. Compare the RMS and mean profit; do not choose a supposedly optimal frequency from this one synthetic sample and call it validated. **Check:** does delta hedging eliminate implied-volatility risk? No. A stock hedge has no vega, and its next trade cannot undo an already incurred option-price jump.

## 13. Worked Exercise: A Short Call Position

Use spot £80, strike £85, half a year remaining, volatility 30%, no dividends, and the same 5% effective annual cash rate. You are short **two contracts, each on 100 shares**.

1. Calculate the one-share call price, delta, gamma, vega per volatility point, and theta per calendar day.
2. How many shares neutralize the short position's delta? If the hedge uses futures expiring with the options and a ten-share multiplier, what is the idealized futures quantity instead?
3. Ignoring time and volatility changes, estimate the **short-option plus initially fixed stock hedge** P&L for a £2 spot rise. Compare with exact option repricing and the stock gain.
4. Estimate the short position's P&L for a two-volatility-point rise at unchanged spot/time. Include volga, then reprice exactly.
5. Explain why zero initial delta is not a complete hedge, and which quantities change when the position is doubled.

::: details Hint
Multiply one-share option sensitivities by −200 for the short position. The stock hedge cancels the first-order spot term, leaving a leading $-200\times\tfrac12\Gamma(2)^2$ curvature term. Use 0.02, not 2, for the volatility change.
:::

::: details Worked answer
The call price is about **£5.506246474 per share**, and delta is **0.474197804**. Buy approximately **94.839561 shares**. The matching idealized futures quantity is $94.839561/[10\sqrt{1.05}]\approx9.255393$ contracts; real lot rounding leaves residual delta.

One-share gamma is **0.023458715**, vega is **£0.225203662 per volatility point**, and theta is **−£0.022844806 per calendar day**. The short option has negative gamma, so a stock hedge fixed at inception loses on a finite spot move to second order. For the £2 rise, the leading loss is $-400\Gamma=-£9.383486$. The exact result is $-200[C(82)-C(80)]+94.839561(2)=-£9.319140$, with no elapsed-time funding in this instantaneous scenario.

At unchanged spot/time, stock gains nothing from a volatility rise. The short-option estimate is $-200[\nu(0.02)+\tfrac12\operatorname{Volga}(0.02)^2]=-£90.135269$; exact repricing gives $-200[C(\sigma=0.32)-C(\sigma=0.30)]=-£90.129060$.

Delta neutrality leaves gamma, vega, time, rate, dividend, and other model/market exposures. Doubling quantities doubles the currency sensitivities, hedge shares, cash requirements under proportional assumptions, and scenario P&Ls. It does not change the one-share price or Greeks. Actual financing/impact can be nonlinear in trade size.
:::

```python:line-numbers
exercise = core_greeks(80.,85.,.5,r,.30)
exercise_cross = cross_greeks(80.,85.,.5,r,.30)
exercise_shares = 200*exercise["delta"]
exercise_futures = exercise_shares/(10*np.exp(r*.5))
exercise_spot_approx = -200*.5*exercise["gamma"]*2**2
exercise_spot_exact = -200*(option_price(82.,85.,.5,r,.30)-exercise["value"])+exercise_shares*2
exercise_vol_approx = -200*(exercise["vega"]*.02+.5*exercise_cross["volga"]*.02**2)
exercise_vol_exact = -200*(option_price(80.,85.,.5,r,.32)-exercise["value"])
print(f"One-share call {exercise['value']:.9f}; delta {exercise['delta']:.9f}; gamma {exercise['gamma']:.9f}")
print(f"Vega per vol point {exercise['vega']*.01:.9f}; theta per calendar day {exercise['theta']/365:.9f} GBP")
print(f"Hedge shares {exercise_shares:.9f}; idealized futures contracts {exercise_futures:.9f}")
print(f"Spot-move net P&L: gamma estimate {exercise_spot_approx:.9f}; exact {exercise_spot_exact:.9f} GBP")
print(f"Vol-move net P&L: vega-volga estimate {exercise_vol_approx:.9f}; exact {exercise_vol_exact:.9f} GBP")
```
<Editor id="greeks-exercise" />

## Chapter Summary

- Greeks are derivatives with specified units and held-fixed inputs. Position Greeks include signed quantities and contract multipliers.
- Delta offsets a local spot move; gamma explains curvature. Theta, vega, rho, and dividend sensitivity describe other input changes, not standalone forecasts of profit.
- Vanna, volga, and charm explain why a hedge changes as volatility and time change. Speed, zomma, color, veta, and ultima describe further changes in those sensitivities.
- Rate bumps must distinguish discounting from carry. A surface-response rule changes total spot exposure relative to fixed-volatility delta.
- Local P&L attribution must retain a remainder and be checked against exact repricing. A delta/gamma/parallel-vega hedge can retain material surface and cross-risk.
- A hedge is a sequence of funded trades. Preserve the budget at every rebalance, pay costs from cash, and measure the terminal liability separately.

Continue with [Spreads and Basic Option Combinations](./d.0-overview.md#option-spreads), currently planned, to construct and explain option positions leg by leg. For the portfolio connection, [Robust Portfolio Construction: Diversification and Risk Budgets](./2.4-robust-portfolios.md) distinguishes uncertainty-aware allocation from a local derivative hedge and keeps costs inside wealth accounting.
