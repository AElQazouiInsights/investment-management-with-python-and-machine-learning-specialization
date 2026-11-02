---
title: "Reading the Options Market: Implied Volatility and Surfaces"
permalink: /implied-volatility-surfaces
description: "Recover bid/mid/ask implied volatility, diagnose vega and carry sensitivity, fit a small quote-aware surface, and check strike and calendar price consistency with worked Python examples."
---

# Reading the Options Market: Implied Volatility and Surfaces

**Question:** an option screen shows prices at several strikes and expiries. How can we turn those prices into comparable volatility readings, and how do we know whether the resulting picture is consistent with the quotes?

Think of changing the units on a measuring instrument. A premium in pounds becomes an implied-volatility quote through a pricing formula. Unlike a physical thermometer, this instrument also needs a forward price, discount factor, expiry, and contract convention. Changing one of those inputs changes the reading even if the observed premium stays fixed.

[The Greeks and Hedging](./greeks-hedging.md) introduced volatility quoting and vega. [Spreads and Basic Option Combinations](./option-combinations.md) showed how signed option payments constrain prices. Here we invert prices, build a small volatility map, fit its shape, and check it back in pounds. [Futures Basis, Dividends, and Implied Financing](./futures-basis.md) supplies the carry and identification background.

## 1. Fix the Contract and the Inputs Being Held Constant

Begin with a European option on one share, cash-equivalent settlement at expiry, no default, and premiums in **GBP per share**. Our initial no-dividend example has spot £100, one year left, and a 5% effective annual rate. Thus $r=\log(1.05)$, the forward is $F=100e^{rT}=£105$, and the discount factor is $D=e^{-rT}=1/1.05$.

We write the call price in **forward-Black form**:

$$C=D\{F N(d_1)-K N(d_2)\},\qquad
d_1=\frac{\log(F/K)+\tfrac12\sigma^2T}{\sigma\sqrt T},\quad d_2=d_1-\sigma\sqrt T.$$

Here $K$ is the strike, $T$ remaining years, $\sigma$ annual decimal volatility, and $N$ the standard normal cumulative distribution function. The put formula is $P=D\{K N(-d_2)-F N(-d_1)\}$. Both give $C-P=D(F-K)$.

The forward and discount factor are separate inputs. In this simple example, one rate determines both. In a market application, equity carry, option discounting, and a trader's borrowing rate need not agree. A forward-Black volatility quote is a pricing coordinate; a strike-dependent volatility is not a single constant-volatility stock process. Discrete dividends, American exercise, and incompatible settlement terms require additional treatment.

For nonnegative terminal share prices, model bounds are:

$$D\max(F-K,0)\le C<DF,\qquad D\max(K-F,0)\le P<DK.$$

The lower bound corresponds to zero Black volatility. The upper bound is approached as volatility grows without limit; it has no finite implied-volatility solution. At expiry, payoff does not depend on volatility, so there is no unique implied volatility to recover.

The code supports prices at zero volatility, but the inversion rejects expired contracts and inadmissible premiums. It expands a numerical bracket up to a stated 1,600% annual volatility ceiling. Failure to find a root is reported; the quote is never silently clipped into a solution. Run cells in order. The later forward/quote widget also runs independently.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq, least_squares

S0, r = 100., np.log1p(.05)
F0, D0, T0, K0 = 105., 1/1.05, 1., 100.

def black_price(forward, strike, maturity, discount, vol, kind="call"):
    if kind not in ("call","put"):
        raise ValueError("Use call or put")
    f,k,t,d,v = np.broadcast_arrays(*[np.asarray(x,dtype=float) for x in (forward,strike,maturity,discount,vol)])
    if not all(np.isfinite(x).all() for x in (f,k,t,d,v)) or np.any(f<=0) or np.any(k<=0) or np.any(d<=0) or np.any(t<0) or np.any(v<0):
        raise ValueError("Use positive forward, strike, discount and nonnegative time and volatility")
    scale = v*np.sqrt(t)
    d1 = np.divide(np.log(f/k)+.5*scale**2,scale,out=np.zeros_like(scale),where=scale>0)
    if kind == "call":
        result = d*(f*norm.cdf(d1)-k*norm.cdf(d1-scale))
        result = np.where(scale==0,d*np.maximum(f-k,0),result)
    else:
        result = d*(k*norm.cdf(scale-d1)-f*norm.cdf(-d1))
        result = np.where(scale==0,d*np.maximum(k-f,0),result)
    return float(result) if result.ndim==0 else result

def implied_vol(premium, forward, strike, maturity, discount, kind="call"):
    if kind not in ("call","put") or not np.isfinite([premium,forward,strike,maturity,discount]).all():
        raise ValueError("Use finite inputs and call or put")
    if min(forward,strike,discount)<=0 or maturity<=0:
        raise ValueError("Positive inputs and an unexpired option are required")
    lower = discount*max(forward-strike if kind=="call" else strike-forward,0.)
    upper = discount*(forward if kind=="call" else strike)
    if premium<lower or premium>=upper:
        raise ValueError("Premium outside finite-volatility bounds")
    if premium==lower:
        return 0.
    residual = lambda vol:black_price(forward,strike,maturity,discount,vol,kind)-premium
    high = .5
    while residual(high)<0 and high<16:
        high *= 2
    if residual(high)<0:
        raise ValueError("No root within the stated volatility bracket")
    return brentq(residual,0.,high,xtol=1e-12)

def black_vega(forward,strike,maturity,discount,vol):
    d1 = (np.log(forward/strike)+.5*vol**2*maturity)/(vol*np.sqrt(maturity))
    return discount*forward*norm.pdf(d1)*np.sqrt(maturity)

def quote_ivs(frame):
    frame = frame.copy()
    fields = ["F","K","T","D","Bid","Mid","Ask"]
    if frame.empty or frame["As of"].isna().any() or frame["As of"].nunique()!=1:
        raise ValueError("Use one nonempty, synchronized quote snapshot")
    if not np.isfinite(frame[fields].to_numpy(dtype=float)).all():
        raise ValueError("Quote inputs must be finite")
    if ((frame["Bid"]>frame["Mid"]) | (frame["Mid"]>frame["Ask"])).any():
        raise ValueError("Require bid <= mid <= ask")
    for side in ("Bid","Mid","Ask"):
        frame[side+" IV"] = [implied_vol(p,f,k,t,d) for p,f,k,t,d in zip(frame[side],frame["F"],frame["K"],frame["T"],frame["D"])]
    return frame

def line_chart(name,title,x,series,xname,yname):
    return {name:{"type":"line","title":title,"xAxis":{"type":"value","name":xname},"yAxisName":yname,
                  "series":{label:np.column_stack([x,y]).tolist() for label,y in series.items()}}}

def publish(charts):
    print("<ECHARTS_DATA>"+json.dumps(charts,allow_nan=False))

base_premium = black_price(F0,K0,T0,D0,.2)
print(f"Call premium at 20%: {base_premium:.9f} GBP/share")
```
<Editor id="iv-setup" />

## 2. Turn One Premium Back into Volatility

Our £100-strike call costs **£10.386279 per share**. To invert it, ask which volatility makes the formula reproduce that premium. A trial of 10% prices it too low; 30% prices it too high. The answer lies between them. Trying the midpoint, 20%, reproduces the quote.

This bracket-and-refine idea is safer than an unconstrained search that can jump to a negative volatility. The implementation uses Brent's method, which combines bracketing with faster interpolation. Its result must still pass a **repricing check**: input the recovered volatility into the price formula and subtract the observed premium.

Suppose the bid is £10.286279 and the ask £10.486279. Inverting each gives approximately **19.7340% bid IV**, **20.0000% mid IV**, and **20.2659% ask IV**. These are prices expressed in another coordinate, not a statistical confidence interval for future realized volatility. The graph zooms to 18–22% volatility so the three marked readings remain visible on the price curve.

```python:line-numbers
quote_premiums = base_premium+np.array([-.10,0.,.10])
quote_vols = np.array([implied_vol(p,F0,K0,T0,D0) for p in quote_premiums])
quote_repriced = black_price(F0,K0,T0,D0,quote_vols)
quote_table = pd.DataFrame({"Side":["Bid","Mid","Ask"],"Premium GBP":quote_premiums,
                           "IV percent":100*quote_vols,"Repricing error GBP":quote_repriced-quote_premiums})
print(quote_table.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(pd.DataFrame({"Trial vol %":[10,20,30],"Call GBP":black_price(F0,K0,T0,D0,np.array([.1,.2,.3]))}).to_string(index=False))
vol_grid = np.linspace(.18,.22,81)
inversion_chart = line_chart("ivInversion","Read a Premium Across to the Volatility Axis",100*vol_grid,
    {"Call price":black_price(F0,K0,T0,D0,vol_grid)},"Annual volatility (%)","Call premium (GBP/share)")
inversion_chart["ivInversion"]["xAxis"].update({"min":18,"max":22})
inversion_chart["ivInversion"]["series"]["Bid, mid, ask"] = np.column_stack([100*quote_vols,quote_premiums]).tolist()
inversion_chart["ivInversion"]["seriesOptions"] = {"Bid, mid, ask":{"type":"scatter","symbol":"diamond","symbolSize":16,
    "itemStyle":{"color":"#ea580c","borderColor":"#ffffff","borderWidth":2}}}
publish(inversion_chart)
invalid_examples = []
for label,p,t in [("Below intrinsic",D0*(F0-K0)-.01,1.),("At upper bound",D0*F0,1.),("Expired",5.,0.)]:
    try:
        implied_vol(p,F0,K0,t,D0)
    except ValueError as error:
        invalid_examples.append([label,str(error)])
print(pd.DataFrame(invalid_examples,columns=["Quote issue","Reported result"]).to_string(index=False))
```
<Editor id="iv-inversion" />

**Check:** does twice the premium imply twice the volatility? No. The price curve is nonlinear. Also, the mid of bid and ask **prices** need not invert to the arithmetic mid of bid and ask **volatilities**. Keep the original quote convention visible.

## 3. Vega Tells Us How Precisely a Quote Can Locate Volatility

Recall that vega is $\nu=\partial C/\partial\sigma=DF\phi(d_1)\sqrt T$, with $\phi$ the standard normal density. For the first call it is **£37.602877 per unit decimal volatility**, or **£0.376029 per volatility percentage point**, per share.

A small price uncertainty $\Delta C$ implies a local volatility uncertainty:

$$\Delta\sigma\approx\frac{\Delta C}{\nu}.$$

A £0.10 half-spread therefore corresponds to $0.10/37.602877=0.00265937$ decimal volatility, or **0.265937 percentage points**. That agrees closely with the exact inversion above. For one 100-share contract, both the price half-spread and vega multiply by 100; their ratio is unchanged.

Low vega makes inversion unstable. With only 0.1 years left, a £100-strike call has vega about £12.54 per unit volatility. A far-out-of-the-money £140 call has vega about **£0.000016**. Its theoretical premium is almost zero. Adding just one penny raises its recovered IV from 20% to about **37.23%**. The local linear approximation is unreliable for such a large relative price move.

The next graph adds the same penny to each call premium. The upward bend is poor quote resolution in the wing, not evidence that a penny contains precise information about a large volatility change. If subtracting a penny creates a negative bid, that side cannot be inverted as a valid price.

```python:line-numbers
short_t = .1
short_f, short_d = S0*np.exp(r*short_t),np.exp(-r*short_t)
conditioning_strikes = np.array([100.,110.,120.,130.,140.])
conditioning_rows = []
for strike in conditioning_strikes:
    premium = black_price(short_f,strike,short_t,short_d,.2)
    vega = black_vega(short_f,strike,short_t,short_d,.2)
    ask_iv = implied_vol(premium+.01,short_f,strike,short_t,short_d)
    conditioning_rows.append([strike,premium,vega,100*ask_iv,"Admissible" if premium>=.01 else "Bid would be negative"])
conditioning = pd.DataFrame(conditioning_rows,columns=["Strike","Premium GBP","Vega GBP/unit vol","One-penny higher IV %","Mid minus penny"])
print(conditioning.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
base_vega = black_vega(F0,K0,T0,D0,.2)
print(f"Baseline half-spread resolution: {100*.10/base_vega:.9f} volatility points")
publish(line_chart("ivConditioning","The Same Penny Gives Very Different Volatility Readings",conditioning_strikes,
    {"Original IV":np.full(5,20.),"After adding GBP 0.01":conditioning["One-penny higher IV %"].to_numpy()},
    "Strike (GBP/share)","Annual implied volatility (%)"))
```
<Editor id="iv-conditioning" />

**Experiment:** halve the penny bump. **Answer:** near the money the IV change is approximately halved; in the far wing the nonlinear inversion can depart substantially from that rule. Report quote quality and price residuals rather than treating all IV decimals as equally reliable.

## 4. A Wrong Forward Can Manufacture a Smile

Hold a set of call premiums fixed. They were generated with forward £105 and flat 20% volatility. Now invert them using £103 or £107 instead. The solver adjusts volatility to compensate for the changed forward, and the adjustment differs by strike.

This follows from the local total price change at fixed strike, time, and discount factor:

$$0\approx D N(d_1)\,\Delta F+\nu\,\Delta\sigma,
\qquad \Delta\sigma\approx-\frac{D N(d_1)}{\nu}\Delta F.$$

For the baseline £100 call, raising the assumed forward by £1 lowers inferred volatility locally by about **1.6072 percentage points**. Nothing happened to the premium in this experiment. The graph shows the false strike-dependent pattern created by a carry-input change.

```python:line-numbers
carry_strikes = np.linspace(90.,130.,17)
fixed_flat_prices = black_price(F0,carry_strikes,T0,D0,.2)
forward_scenarios = {f"Assumed forward {forward:.0f}":100*np.array([
    implied_vol(p,forward,k,T0,D0) for p,k in zip(fixed_flat_prices,carry_strikes)]) for forward in (103.,105.,107.)}
baseline_d1 = (np.log(F0/K0)+.5*.2**2)/.2
iv_forward_slope = -D0*norm.cdf(baseline_d1)/base_vega
print(f"Local IV change per GBP 1 forward bump: {100*iv_forward_slope:.9f} volatility points")
print(pd.DataFrame({"Strike":carry_strikes,**forward_scenarios}).to_string(index=False,float_format=lambda x:f"{x:.6f}"))
publish(line_chart("ivForwardError","Keep the Premiums Fixed and Change Only the Forward",carry_strikes,
    forward_scenarios,"Strike (GBP/share)","Recovered annual IV (%)"))
```
<Editor id="iv-forward" />

**Check:** do extra option quotes separately identify unrestricted financing and dividends? No. Parity can identify an option-implied forward and discount factor under matching conventions, but the forward alone still cannot split financing from dividends. Independent anchors from the basis lesson remain necessary.

## 5. Build a Small, Explicit Quote Snapshot

A **smile** plots IV across strikes at one expiry; a **skew** describes its asymmetry. A **term structure** compares expiries at a stated strike or moneyness. A **surface** combines both directions.

Use log-forward-moneyness $k=\log(K/F)$. It is zero at the forward strike, negative below the forward, and positive above. At $F=105$, $k=0.1$ means $K=105e^{0.1}\approx£116.04$, not £105.10. Comparing the same $k$ across expiries compares the same strike-to-forward ratio.

### Strike, Moneyness, and Delta Are Different Screen Coordinates

A **fixed strike** identifies the same contractual exercise price. A **fixed moneyness** identifies the same ratio to the forward, so its strike changes when the forward changes. “At the money” must also name its convention: today's spot is £100, while our one-year forward is £105.

Some screens label options by delta. For a flat 20% one-year illustration, define undiscounted forward-call delta as $\partial(C/D)/\partial F=N(d_1)$. A 25-delta call then has:

$$K=F\exp\{-\sigma\sqrt T N^{-1}(0.25)+\tfrac12\sigma^2T\}\approx£122.59.$$

The corresponding discounted forward delta is $D N(d_1)$, and FX screens can also use premium-adjusted conventions. A delta label therefore requires a definition. On a smile, volatility itself depends on the strike being solved for. Fixed-strike, fixed-moneyness, and fixed-delta comparisons can select different contracts; none specifies how the market will move. “Sticky strike” or “sticky delta” is an assumed rule for how a surface moves, not an implication of today's fitted quotes.

### Generate the Snapshot

We create a small synthetic quote snapshot, **A at 09:30 on an invented trading day**. No external market data are being used. It has three expiries, 0.25, 0.5, and 1 year, and five moneyness points per expiry. For this teaching surface, annual variance is:

$$\sigma^2(k,T)=a+bk+ck^2+d(T-1),$$
$$a=0.04,\quad b=-0.03,\quad c=0.08,\quad d=0.006.$$

At $k=0,T=1$, this gives $\sigma=\sqrt{0.04}=20\%$. At $k=-0.2,T=1$, it gives $\sqrt{0.04+0.006+0.0032}\approx22.18\%$. Lower strikes are more expensive in volatility terms. These coefficients are a **bounded teaching parameterization**, not a universal surface or an instruction to extrapolate a quadratic into the tails.

Convert these volatilities to call prices and add a small deterministic mid-price disturbance. Start with half-widths of £0.04 at the forward and £0.12 at the outer strikes, but cap each synthetic half-width at 40% of its model time value above the lower bound. This keeps the invented short-dated wing bids admissible. It is a data-generation choice, not permission to repair invalid observed prices. The disturbance is at most one-quarter of a half-width, so the generating prices remain inside the quotes. Each quote retains its timestamp, forward, discount factor, maturity, and strike.

We also reserve four quotes at **0.75 years and previously unused moneyness points** before fitting anything. They will be checked later without tuning the model to their errors. The first graph shows the one-year bid/mid/ask smile; the second compares mid-IV slices. Different widths reflect both price spreads and vega.

Before inversion, reject nonfinite inputs, crossed bid/ask quotes, and mixed snapshot labels. A timestamp label alone does not prove real quotes were synchronized: a market-data application must also check freshness, source clocks, exercise style, and settlement compatibility.

```python:line-numbers
truth = np.array([.04,-.03,.08,.006])
def surface_vol(params,k,t):
    a,b,c,d = params
    variance = a+b*np.asarray(k)+c*np.asarray(k)**2+d*(np.asarray(t)-1)
    if np.any(variance<=0):
        raise ValueError("Surface variance must be positive in the evaluated domain")
    return np.sqrt(variance)

def make_quotes(times, log_moneyness, phase, timestamp):
    times,log_moneyness = np.asarray(times),np.asarray(log_moneyness)
    forward,discount = S0*np.exp(r*times),np.exp(-r*times)
    strikes = forward*np.exp(log_moneyness)
    generating = black_price(forward,strikes,times,discount,surface_vol(truth,log_moneyness,times))
    time_value = generating-discount*np.maximum(forward-strikes,0.)
    half_width = np.minimum(.04+.4*np.abs(log_moneyness),.4*time_value)
    mid = generating+.25*half_width*np.sin(np.arange(len(times))*1.7+phase)
    frame = pd.DataFrame({"As of":timestamp,"T":times,"k":log_moneyness,"F":forward,"D":discount,
                          "K":strikes,"Half-width":half_width,"Bid":mid-half_width,"Mid":mid,"Ask":mid+half_width})
    return quote_ivs(frame)

snapshot = make_quotes(np.repeat([.25,.5,1.],5),np.tile([-.2,-.1,0.,.1,.2],3),0.,"A 09:30")
held_out = make_quotes(np.full(4,.75),[-.15,-.05,.05,.15],.7,"A 09:30 held out")
delta_coordinate_strike = F0*np.exp(-.2*norm.ppf(.25)+.5*.2**2)
print(f"Flat-20% undiscounted forward 25-delta call strike: {delta_coordinate_strike:.6f} GBP")
print(snapshot[["As of","T","K","Bid","Mid","Ask","Bid IV","Mid IV","Ask IV"]].to_string(index=False,float_format=lambda x:f"{x:.6f}"))
one_year = snapshot[snapshot["T"]==1.]
snapshot_charts = line_chart("ivSmile","One Expiry Has a Range of Quote-Consistent Volatilities",one_year["k"],
    {side+" IV":100*one_year[side+" IV"] for side in ("Bid","Mid","Ask")},"Log strike/forward","Annual IV (%)")
snapshot_charts.update(line_chart("ivSlices","Compare Strikes and Expiries in the Same Coordinate",one_year["k"],
    {f"{t:g} years":100*snapshot.loc[snapshot["T"]==t,"Mid IV"].to_numpy() for t in (.25,.5,1.)},
    "Log strike/forward","Mid annual IV (%)"))
publish(snapshot_charts)
```
<Editor id="iv-snapshot" />

**Check:** is a higher put-wing IV automatically a forecast of a crash probability? No. It describes relative option prices conditional on the inputs. Extracting a pricing distribution requires strike-price information and additional care; forecasting physical outcomes adds another layer. Those subjects follow the strategy and distribution lessons.

## 6. Total Variance Keeps the Time Horizon Visible

Annualized volatility divides the uncertainty scale by the square root of time. To put time back in, define **Black total variance**:

$$w(k,T)=\sigma(k,T)^2T.$$

At the forward strike, our generating surface gives:

| Years left | Annual IV | Total variance |
| ---: | ---: | ---: |
| 0.25 | 18.8414% | 0.008875 |
| 0.50 | 19.2354% | 0.018500 |
| 1.00 | 20.0000% | 0.040000 |

The difference from half a year to one year is $0.0400-0.0185=0.0215$. Dividing by the additional half-year gives 0.043; its square root is **20.7364%**. In a deterministic time-varying Black volatility model, that calculation is the volatility over the intervening interval.

With a smile, **ATM Black total variance is not generally the fair expected integrated variance of the underlying**. This difference is an ATM total-variance slope or a model-dependent forward-variance proxy. It is not automatically the strike of an executable forward variance swap. Such a trade requires its own payoff, replication, quotes, and funding.

The graph plots total variance, with its own units; the table reports annual IV alongside it. Annual volatility can fall while total variance rises. For example, 24% at 0.5 years gives 0.0288; 20% at one year gives 0.0400. Comparing 24% with 20% alone would miss the longer horizon.

```python:line-numbers
term_times = np.linspace(.25,1.,31)
term_vols = surface_vol(truth,0.,term_times)
term_variance = term_times*term_vols**2
variance_slope = (.04-.0185)/.5
print(pd.DataFrame({"Years":[.25,.5,1.],"ATM IV %":100*surface_vol(truth,0.,np.array([.25,.5,1.])),
                    "Total variance":[.008875,.0185,.04]}).to_string(index=False))
print(f"ATM total-variance slope: {variance_slope:.9f}; square-root proxy: {100*np.sqrt(variance_slope):.9f}%")
publish(line_chart("ivTotalVariance","Total Variance Includes the Length of the Horizon",term_times,
    {"ATM total variance":term_variance},"Years to expiry","Black total variance (decimal squared times years)"))
```
<Editor id="iv-variance" />

## 7. Understand the Fitting Objective Before Calling a Solver

Fitting means choosing a few parameters so model prices explain the quote set. Start with a one-parameter hand calculation. Suppose two options have local vegas of £0.40 and £0.30 **per volatility point**. Their observed mids exceed the current model by £0.04 and −£0.02. Their half-spreads are £0.04 and £0.06.

Let $x$ be a common change in volatility **percentage points**. A quote-width-scaled least-squares objective is:

$$L(x)=\left(\frac{0.40x-0.04}{0.04}\right)^2+
\left(\frac{0.30x+0.02}{0.06}\right)^2.$$

Differentiating this quadratic and setting its slope to zero gives:

$$x=\frac{\sum_i v_i e_i/h_i^2}{\sum_i v_i^2/h_i^2}=0.066667\text{ volatility points}.$$

Thus a starting 20% becomes about 20.066667%, not 26.6667%. The model misses the two mids by approximately −£0.013333 and +£0.040000, both inside their half-spreads. The graph's minimum is a compromise, not an exact fit to both observations.

Why divide by quote width? A five-penny miss is economically different when the half-spread is one penny versus twenty pence. Width scaling is a chosen calibration convention, not a claim that the half-spread is a measurement standard deviation.

```python:line-numbers
local_vegas = np.array([.40,.30])
mid_discrepancies = np.array([.04,-.02])
local_widths = np.array([.04,.06])
hand_shift = np.sum(local_vegas*mid_discrepancies/local_widths**2)/np.sum(local_vegas**2/local_widths**2)
hand_errors = local_vegas*hand_shift-mid_discrepancies
shifts = np.linspace(-.2,.2,161)
objectives = np.sum(((shifts[:,None]*local_vegas-mid_discrepancies)/local_widths)**2,axis=1)
print(f"Best local shift: {hand_shift:.9f} volatility points; errors: {hand_errors} GBP")
publish(line_chart("ivLeastSquares","A Shared Volatility Shift Compromises Between Two Mids",shifts,
    {"Scaled squared error":objectives},"Volatility change (percentage points)","Sum of squared quote-width errors"))
```
<Editor id="iv-least-squares" />

**Check:** if a model price is anywhere between bid and ask, must it be moved to the mid? No. The quote interval admits several prices. We compare that interpretation next.

## 8. Fit a Bounded Surface and Reprice Every Quote

Our **staged baseline** fixes forward and discount inputs first, inverts quotes, and then fits the four surface coefficients. The pricing objective is evaluated in **GBP**, scaled by half-spreads, so low-vega IV noise does not receive an unexplained large weight.

We use three fits, with the same data and parameter bounds:

1. **Weighted mid:** minimize $\sum_i[(C_i(\theta)-m_i)/h_i]^2$.
2. **Interval distance:** replace $m_i$ by the closest point in $[\text{bid}_i,\text{ask}_i]$. A model price inside the interval contributes zero.
3. **Interval plus prior:** add $\lambda\sum_j[(\theta_j-\theta_{j,\mathrm{prior}})/s_j]^2$, where $s_j$ are stated parameter scales and $\lambda=0.01$.

The prior is an explicit preference for coefficients near $(0.04,-0.02,0.06,0.004)$. It does not create new market information. The interval objective can have many zero-error solutions; the prior selects among nearby solutions and may accept small quote misses in exchange for a lower penalty. We report **market error and prior penalty separately**.

For a simple numerical floor, use at least £0.01 when dividing by quote width. All supplied widths exceed that floor. The initial coefficients, scales, and bounds are visible below. The calibration and cross-sectional audit domain is $-0.25\le k\le0.25$ and $0.25\le T\le1$ years; the later temporal example explicitly rolls maturities by five minutes. The parameter bounds keep this example's variance positive in the audit domain; price consistency still needs separate checks.

The first graph compares the fitted one-year smiles. Several different curves can be compatible with the same bid/ask data. The second shows price residuals divided by half-width; a value between −1 and +1 is inside the corresponding quote. A smooth line on the first graph does not replace the second check.

```python:line-numbers
initial = np.array([.04,0.,.04,.003])
parameter_scales = np.array([.04,.04,.10,.01])
parameter_bounds = ([.025,-.05,0.,0.],[.09,.05,.20,.015])
prior = np.array([.04,-.02,.06,.004])
prior_weight = .01
widths = np.maximum(snapshot["Half-width"].to_numpy(),.01)

def surface_prices(params,frame):
    return black_price(frame["F"].to_numpy(),frame["K"].to_numpy(),frame["T"].to_numpy(),frame["D"].to_numpy(),
                       surface_vol(params,frame["k"].to_numpy(),frame["T"].to_numpy()))

def mid_residual(params):
    return (surface_prices(params,snapshot)-snapshot["Mid"].to_numpy())/widths

def interval_residual(params):
    prices = surface_prices(params,snapshot)
    return (prices-np.clip(prices,snapshot["Bid"],snapshot["Ask"]))/widths

def regularized_residual(params):
    return np.r_[interval_residual(params),np.sqrt(prior_weight)*(params-prior)/parameter_scales]

fits = {name:least_squares(residual,initial,bounds=parameter_bounds,x_scale=parameter_scales,
                         ftol=1e-10,xtol=1e-10,gtol=1e-10)
        for name,residual in (("Weighted mid",mid_residual),("Interval",interval_residual),("Interval + prior",regularized_residual))}
fit_parameters = pd.DataFrame({name:fit.x for name,fit in fits.items()},index=["a","b","c","d"]).T
fit_report = pd.DataFrame([
    [name,fit.success,np.sum(mid_residual(fit.x)**2),np.sum(interval_residual(fit.x)**2),
     prior_weight*np.sum(((fit.x-prior)/parameter_scales)**2) if name=="Interval + prior" else 0.,
     np.max(np.abs(mid_residual(fit.x)))] for name,fit in fits.items()],
    columns=["Fit","Converged","Mid error squared","Interval error squared","Prior penalty","Max mid error / half-width"])
print(fit_parameters.to_string(float_format=lambda x:f"{x:.9f}"))
print(fit_report.to_string(index=False,float_format=lambda x:f"{x:.9g}"))
fit_k = np.linspace(-.2,.2,81)
fit_charts = line_chart("ivFittedSmile","Different Fits Can Describe the Same Quote Intervals",fit_k,
    {name:100*surface_vol(fit.x,fit_k,1.) for name,fit in fits.items()},"Log strike/forward","One-year fitted IV (%)")
fit_charts.update(line_chart("ivPriceResiduals","Check the Fit Back in Price Space",np.arange(len(snapshot)),
    {**{name:mid_residual(fit.x) for name,fit in fits.items()},"Ask boundary":np.ones(len(snapshot)),"Bid boundary":-np.ones(len(snapshot))},
    "Quote index in the printed snapshot","Price error divided by half-spread"))
publish(fit_charts)
```
<Editor id="iv-fit" />

The weighted-mid fit has a largest miss of about **0.29 half-spreads**. The interval-only fit reaches zero interval error with noticeably different skew and curvature. The prior fit has a small nonzero interval miss: its penalty is a soft preference, not a hard quote-feasibility constraint. These alternative parameter readings are not statistical confidence bounds.

**Experiment:** increase only the prior weight. **Answer:** the fit is pulled more strongly toward the chosen prior, potentially worsening market fit. That is a changed calibration preference, not evidence that the market changed.

## 9. Joint Calibration Needs Independent Anchors

The staged fit held $F$ and $D$ fixed. Now allow the one-year forward, discount factor, and three smile coefficients $(a,b,c)$ to move together. We have five one-year option quotes, plus independent quote-like anchors **$F=105\pm0.05$** and **$D=1/1.05\pm0.0002$**. These synthetic anchors represent matching forward and discount observations; they are not the trader's private financing cost.

The joint residual vector contains five option-price errors divided by their half-widths, then $(F-105)/0.05$ and $(D-1/1.05)/0.0002$. Changing $F$ also changes $k=\log(K/F)$ for each fixed contract strike. It would be inconsistent to move the forward while keeping the old moneyness values in the pricing function.

To see identification, first return to **one option with two unknowns**, forward and volatility. Its sensitivity row has two columns, $[\partial C/\partial F,\partial C/\partial\sigma]$, but only one equation. It has rank one: several combinations reproduce the same premium. The earlier forward experiment showed that family directly.

For the joint fit, the **sensitivity matrix** records how each normalized residual changes with each scaled parameter. Singular values measure how strongly combinations of parameters affect those residuals. A tiny singular value indicates a weakly observed direction; a large ratio of largest to smallest indicates sensitivity to quote noise. Scaling matters, so the scales are printed in code rather than comparing pounds with raw variance coefficients.

The graph compares option errors under a staged one-year fit and the anchored joint fit. The printed diagnostics compare option-only sensitivity with sensitivity after adding the two anchor rows. A numerical full rank under a restrictive smile formula is not proof that unrestricted financing, dividends, and volatility have all been identified.

```python:line-numbers
joint_strikes = one_year["K"].to_numpy()
joint_mids = one_year["Mid"].to_numpy()
joint_widths = one_year["Half-width"].to_numpy()
joint_scales = np.array([1.,.01,.04,.04,.10])
joint_initial = np.array([105.,D0,.04,0.,.04])
joint_bounds = ([103.,.94,.025,-.05,0.],[107.,.97,.09,.05,.20])

def joint_prices(params):
    forward,discount,a,b,c = params
    k = np.log(joint_strikes/forward)
    return black_price(forward,joint_strikes,1.,discount,np.sqrt(a+b*k+c*k*k))

def joint_residual(params):
    return np.r_[(joint_prices(params)-joint_mids)/joint_widths,(params[0]-105)/.05,(params[1]-D0)/.0002]

joint_fit = least_squares(joint_residual,joint_initial,bounds=joint_bounds,x_scale=joint_scales,
                          ftol=1e-12,xtol=1e-12,gtol=1e-12)
staged_slice = least_squares(lambda abc:(joint_prices(np.r_[105.,D0,abc])-joint_mids)/joint_widths,
                            [.04,0.,.04],bounds=(joint_bounds[0][2:],joint_bounds[1][2:]),x_scale=joint_scales[2:])
scaled_jacobian = joint_fit.jac*joint_scales
quote_singular_values = np.linalg.svd(scaled_jacobian[:5],compute_uv=False)
anchored_singular_values = np.linalg.svd(scaled_jacobian,compute_uv=False)
single_quote_sensitivity = np.array([[D0*norm.cdf(baseline_d1),base_vega*.01]])
print(f"Joint convergence: {joint_fit.success}; [F,D,a,b,c]: {joint_fit.x}")
print(f"Option-only singular values: {quote_singular_values}")
print(f"Anchored singular values: {anchored_singular_values}")
print(f"Condition ratios: quotes {quote_singular_values[0]/quote_singular_values[-1]:.3f}; anchored {anchored_singular_values[0]/anchored_singular_values[-1]:.3f}")
print(f"One-option/two-input rank: {np.linalg.matrix_rank(single_quote_sensitivity)}")
print(f"Joint option error squared: {np.sum(joint_residual(joint_fit.x)[:5]**2):.9g}; anchor error squared: {np.sum(joint_residual(joint_fit.x)[5:]**2):.9g}")
publish(line_chart("ivJointFit","Independent Anchors Stabilize a Joint Price Fit",joint_strikes,
    {"Staged slice":(joint_prices(np.r_[105.,D0,staged_slice.x])-joint_mids)/joint_widths,
     "Anchored joint":joint_residual(joint_fit.x)[:5]},"Fixed contract strike (GBP/share)","Price error divided by half-spread"))
```
<Editor id="iv-joint" />

**Check:** may we call these fitted forward and discount inputs equity repo and dividend forecasts? No. The decomposition still needs independent economic inputs. Regularization or a narrow parametric smile can stabilize a calculation without supplying that missing information.

## 10. Check Quotes That Were Not Used to Choose the Fit

The four reserved quotes have an unseen maturity, 0.75 years, and unseen moneyness points. Apply the already chosen weighted-mid surface to them. For every held-out contract, print bid, model, ask, and price error in half-spreads.

This is a **cross-sectional interpolation check**. It does not demonstrate forecasting ability, tail accuracy, or performance outside the stated domain. The graph compares held-out price errors against the ±1 quote boundaries. We do not alter the model or penalty after looking at these errors.

```python:line-numbers
chosen_params = fits["Weighted mid"].x.copy()
held_model = surface_prices(chosen_params,held_out)
held_errors = (held_model-held_out["Mid"].to_numpy())/held_out["Half-width"].to_numpy()
held_report = held_out[["T","K","Bid","Ask"]].copy()
held_report["Model GBP"] = held_model
held_report["Error / half-width"] = held_errors
print(held_report.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
publish(line_chart("ivHeldOut","Evaluate an Unused Maturity and Unused Moneyness Points",held_out["k"],
    {"Held-out errors":held_errors,"Ask boundary":np.ones(4),"Bid boundary":-np.ones(4)},
    "Held-out log strike/forward","Price error divided by half-spread"))
```
<Editor id="iv-held-out" />

## 11. Check Strike Prices, Not Just the Appearance of the Smile

For a fixed expiry, increasing a call's strike makes its purchase right less favorable, so call prices must not increase. A £1 strike increase can reduce the terminal call payment by at most £1; discounting gives a strike slope between **$-D$ and zero**. Call prices must also be **convex in strike**: successive price slopes cannot become more negative.

For equally spaced strikes £90, £100, and £110, convexity requires:

$$C(90)-2C(100)+C(110)\ge0.$$

The corresponding basket buys the two outside calls and sells two middle calls. Its terminal payoff is nonnegative: zero outside the strike interval and £10 at £100. Paying a negative entry cost for that basket would produce a credit for a nonnegative future payment under our matched, frictionless contracts. The next strategy chapter will develop this butterfly construction fully.

For unequal spacing, compare slopes or use interpolation weights; the $1,-2,1$ rule is specific to equal spacing. We check the fitted surface on a denser grid of expiries and strikes, including price bounds, vertical-spread slopes, and convexity. A sampled check is evidence on that grid, not a proof for all strikes, times, interpolation rules, and tails.

The second part deliberately corrupts a three-strike mid-price. If the middle mid is £0.02 above the average of the outside mids, the midpoint butterfly costs −£0.04. With £0.05 half-spreads on all legs, buying the outside asks and selling the middle bid costs **+£0.16**. That midpoint flag alone is not an executable credit. Raising the middle mid £0.30 above the average instead gives an executable **−£0.40** cost before fees, under the stated synchronized settlement assumptions.

```python:line-numbers
audit_k = np.linspace(-.25,.25,101)
audit_times = np.linspace(.25,1.,31)
strike_checks = []
for t in audit_times:
    f,d = S0*np.exp(r*t),np.exp(-r*t)
    strikes = f*np.exp(audit_k)
    prices = black_price(f,strikes,t,d,surface_vol(chosen_params,audit_k,t))
    slopes = np.diff(prices)/np.diff(strikes)
    strike_checks.append([t,np.min(prices-d*np.maximum(f-strikes,0)),np.min(d*f-prices),
                          np.min(slopes+d),np.min(-slopes),np.min(np.diff(slopes))])
strike_check_table = pd.DataFrame(strike_checks,columns=["T","Above lower bound","Below upper bound","Slope above -D","Slope below zero","Convex slope increment"])
print(strike_check_table.min(numeric_only=True).to_string())
butterfly_strikes = np.array([90.,100.,110.])
clean_calls = black_price(F0,butterfly_strikes,1.,D0,surface_vol(chosen_params,np.log(butterfly_strikes/F0),1.))
small_fault,large_fault = clean_calls.copy(),clean_calls.copy()
small_fault[1] = (clean_calls[0]+clean_calls[2])/2+.02
large_fault[1] = (clean_calls[0]+clean_calls[2])/2+.30
butterfly_weights = np.array([1.,-2.,1.])
butterfly_half_spread = .05
butterfly_report = pd.DataFrame([
    [name,weights_cost,weights_cost+4*butterfly_half_spread]
    for name,weights_cost in [("Small mid fault",butterfly_weights@small_fault),("Large mid fault",butterfly_weights@large_fault)]
],columns=["Scenario","Mid basket cost GBP","Executable basket cost GBP"])
print(butterfly_report.to_string(index=False))
publish(line_chart("ivStrikeChecks","A Smooth Volatility Story Must Still Respect Call-Price Convexity",butterfly_strikes,
    {"Fitted prices":clean_calls,"Small middle-mid fault":small_fault,"Large middle-mid fault":large_fault},
    "Strike (GBP/share)","One-year call premium (GBP/share)"))
```
<Editor id="iv-strike-checks" />

**Check:** does passing these tests mean the fitted surface is a complete arbitrage-free institutional model? No. We tested a finite domain and grid. Tail limits, continuous interpolation, all dates, contract conventions, and quote feasibility require their own validation.

## 12. Compare Expiries in a Carry-Consistent Coordinate

A raw call-price comparison can mix maturity with changes in forwards and discounting. Under our **deterministic, no-dividend carry model**, normalize by prepaid-forward value:

$$c(k,T)=\frac{C(K,T)}{D(T)F(T)},\qquad K=F(T)e^k.$$

Then $c=E[(X_T-e^k)^+]$, where $X_T=S_T/F(T)$ is a normalized martingale starting at one. A convex payoff on that martingale has nondecreasing expectation with maturity. Thus normalized call prices should not fall with maturity at **fixed $k$**. Since normalized Black prices increase with total variance, nondecreasing $w(k,T)$ is the corresponding calendar condition for these coordinates.

This is a model-specific consistency check. It is not a universal rule to buy one raw call and sell another at the same strike, and it does not silently apply to arbitrary cash dividends or different settlement terms.

For a counterexample, take forward-ATM IV of 24% at 0.5 years and 16% at one year. Total variance falls from 0.0288 to 0.0256, so normalized ATM call value falls. The graph contrasts that inconsistent pair with the fitted surface at $k=0$. The code also checks fixed-moneyness total variance across the entire audit grid.

```python:line-numbers
variance_grid = np.array([t*surface_vol(chosen_params,audit_k,t)**2 for t in audit_times])
calendar_increments = np.diff(variance_grid,axis=0)
normalized_grid = np.array([black_price(1.,np.exp(audit_k),t,1.,surface_vol(chosen_params,audit_k,t)) for t in audit_times])
print(f"Smallest total-variance calendar increment: {calendar_increments.min():.9f}")
print(f"Smallest normalized-call calendar increment: {np.diff(normalized_grid,axis=0).min():.9f}")
calendar_times = np.array([.5,1.])
bad_calendar_vols = np.array([.24,.16])
bad_calendar_prices = black_price(1.,1.,calendar_times,1.,bad_calendar_vols)
good_calendar_prices = black_price(1.,1.,calendar_times,1.,surface_vol(chosen_params,0.,calendar_times))
print(pd.DataFrame({"T":calendar_times,"Bad total variance":calendar_times*bad_calendar_vols**2,
                    "Bad normalized call":bad_calendar_prices,"Fitted normalized call":good_calendar_prices}).to_string(index=False))
publish(line_chart("ivCalendar","Use Normalized Prices at Fixed Forward Moneyness",calendar_times,
    {"Fitted ATM slice":good_calendar_prices,"Inconsistent pair":bad_calendar_prices},
    "Years to expiry","Call premium divided by prepaid forward"))
```
<Editor id="iv-calendar" />

## 13. Experiment: Separate an Input Change from a Quote Change

The independent widget fixes a one-year **£105-strike call** with discount factor $1/1.05$. Its baseline premium is £7.965567, corresponding to a £105 forward and 20% IV.

The **assumed forward** control changes an input used to interpret the quote. The **premium change** control changes the observed price itself by up to fifty pence. For each selected premium, the curve shows all forward/IV pairs that reproduce it. The orange diamond marks the selected assumption. The printed repricing error checks that the interpretation still returns the selected premium.

Changing only the assumed forward is not option trading P&L. Changing the actual premium changes the option's marked value; a hedge's profit additionally includes its own positions and cash flows.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_implied_volatility_echart,
    assumed_forward=widgets.FloatSlider(value=105.,min=103.,max=107.,step=.25,description="Forward (£)",continuous_update=False),
    premium_change=widgets.FloatSlider(value=0.,min=-.5,max=.5,step=.1,description="Premium change (£)",continuous_update=False),
)
widget_instance
```
<Editor id="iv-input-widget" />

**Try it:** first raise only the forward, then restore it and raise only the premium. **Answer:** the first change lowers recovered IV; the second raises it. The numerical root does not tell you which economic input actually moved in a market snapshot.

## 14. A Later Snapshot Is a New Observation, Not a Forecast We Have Proved

Create synthetic snapshot **B at 09:35 on the same invented day**. Five minutes have elapsed under a 365-day year. Spot rises from £100 to £101, and the generating annual-variance level $a$ rises from 0.040 to 0.042. Keep the other generating coefficients unchanged and retain the original **fixed contract strikes and expiry dates**.

Roll the previously fitted parameters forward using the new observed spot, forwards, discount factors, and shorter remaining lives. Compare that unchanged shape with new quote mids. This is a small temporal diagnostic: it reveals how an earlier surface fails when the market's pricing state changes. It is not an out-of-sample trading strategy or an estimate of expected profit.

The table reports each input explicitly and inverts the new premium. The graph shows old-fit price errors against the new half-spreads. We did not use snapshot B to select the original fit or penalty.

```python:line-numbers
elapsed_minutes = 5/(365*24*60)
snapshot_b = snapshot.copy()
snapshot_b["As of"] = "B 09:35"
snapshot_b["T"] = snapshot["T"]-elapsed_minutes
snapshot_b["F"] = 101.*np.exp(r*snapshot_b["T"])
snapshot_b["D"] = np.exp(-r*snapshot_b["T"])
snapshot_b["k"] = np.log(snapshot_b["K"]/snapshot_b["F"])
new_truth = truth+np.array([.002,0.,0.,0.])
new_generating_prices = surface_prices(new_truth,snapshot_b)
snapshot_b["Mid"] = new_generating_prices+.20*snapshot_b["Half-width"]*np.cos(np.arange(len(snapshot_b))*1.3)
snapshot_b["Bid"] = snapshot_b["Mid"]-snapshot_b["Half-width"]
snapshot_b["Ask"] = snapshot_b["Mid"]+snapshot_b["Half-width"]
snapshot_b = quote_ivs(snapshot_b)
rolled_prices = surface_prices(chosen_params,snapshot_b)
later_errors = (rolled_prices-snapshot_b["Mid"])/snapshot_b["Half-width"]
print(snapshot_b.loc[[2,7,12],["As of","T","K","F","D","Bid","Mid","Ask","Mid IV"]].to_string(index=False,float_format=lambda x:f"{x:.9f}"))
publish(line_chart("ivLaterSnapshot","An Earlier Fitted Shape Need Not Explain Later Quotes",np.arange(len(snapshot_b)),
    {"Rolled old-fit errors":later_errors.to_numpy(),"Ask boundary":np.ones(15),"Bid boundary":-np.ones(15)},
    "Fixed contract index","New-price error divided by half-spread"))
```
<Editor id="iv-later-snapshot" />

**Check:** can the old model's underpricing be labeled a realized loss? No. It is a price residual against a selected model. Trading P&L needs the actual signed holdings, entry and exit prices, hedges, funding, and costs.

## 15. Worked Exercise: Read and Reprice One Quote

A European **£110-strike call**, one year left, has forward **£105**, discount factor **$1/1.05$**, and bid/mid/ask premiums **£5.893112 / £5.993112 / £6.093112 per share**. Use the full-precision mid generated at 20% below.

1. Recover all three implied volatilities and reprice them.
2. Estimate the half-spread in volatility points using vega.
3. Reinterpret the unchanged mid with a £106 forward. Which reading changes, and what remains observed?
4. For a 100-share contract, what is the bid/ask half-spread in GBP? Does that multiplier change IV?

**Work it through.** The mid-IV is 20%. Vega is approximately **£0.395450 per volatility point per share**, so ten pence corresponds locally to $0.10/0.395450\approx0.252876$ volatility points. The contract half-spread is **£10** and contract vega approximately **£39.545039 per point**; their ratio is the same. A higher assumed forward requires lower IV to reproduce the unchanged premium.

The graph shows the baseline bid/mid/ask readings. The table prints the exact inversion, the repricing error, and the alternative-forward result. That is the smallest useful market-implied report: contract, price range, conditioning inputs, inferred range, and a repricing check.

```python:line-numbers
exercise_mid = black_price(105.,110.,1.,D0,.2)
exercise_quotes = exercise_mid+np.array([-.10,0.,.10])
exercise_ivs = np.array([implied_vol(p,105.,110.,1.,D0) for p in exercise_quotes])
exercise_repricing = black_price(105.,110.,1.,D0,exercise_ivs)-exercise_quotes
exercise_vega_point = .01*black_vega(105.,110.,1.,D0,.2)
exercise_forward_iv = implied_vol(exercise_mid,106.,110.,1.,D0)
print(pd.DataFrame({"Side":["Bid","Mid","Ask"],"GBP/share":exercise_quotes,"IV %":100*exercise_ivs,
                    "Repricing error GBP":exercise_repricing}).to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(f"Vega per point/share: {exercise_vega_point:.9f}; local half-spread: {.10/exercise_vega_point:.9f} vol points")
print(f"Unchanged mid, forward 106: {100*exercise_forward_iv:.9f}% IV")
print(f"100-share half-spread: {100*.10:.2f} GBP; vega: {100*exercise_vega_point:.9f} GBP per point")
publish(line_chart("ivExercise","Reprice Every Side of the Quote",100*exercise_ivs,
    {"Observed premium":exercise_quotes},"Recovered annual IV (%)","Call premium (GBP/share)"))
```
<Editor id="iv-exercise" />

**Completed answer:** bid/mid/ask IVs are approximately **19.747052% / 20.000000% / 20.252807%**, with repricing errors near numerical zero. The unchanged mid interpreted with forward £106 gives **18.915415% IV**. The observed premium stays £5.993112 per share; the interpretation changes. Multiplying both price and vega by 100 leaves the implied volatility and quote-resolution ratio unchanged.

## Chapter Summary

- Implied volatility is a price coordinate conditional on contract, forward, discounting, maturity, and model conventions.
- Invert bid, mid, and ask separately; reject invalid or expired quotes and reprice every recovered value.
- Vega measures quote resolution. Low-vega wings can turn tiny price differences into large, unreliable IV changes.
- A smile describes strikes, a term structure describes maturities, and total variance keeps the horizon explicit. A wrong carry input can distort all three.
- Fit a stated, bounded model with visible weights, parameter scales, and prior choices. Several quote-consistent fits can coexist.
- Independent anchors improve identification. A solver, a restrictive shape, and a prior do not independently identify financing and dividends.
- Check bounds, vertical spreads, convexity, and carry-consistent calendar behavior in price space. Finite grid checks do not certify all tails or all interpolated points.
- Held-out quotes and later snapshots test different things. An implied reading is neither a physical forecast nor executable profit.

Next: [Straddles, Strangles, Butterflies, and Condors](./d.0-overview.md#option-volatility-strategies). We will build the multi-leg positions behind views on movement size and payoff location before extracting pricing-distribution information.
