---
title: "Butterflies, Implied Distributions, and Tail Pricing"
permalink: /implied-distributions
description: "Read pricing probabilities from call spreads and butterflies, recover a discrete distribution, distinguish mass from density, and expose quote-noise and missing-tail uncertainty."
---

# Butterflies, Implied Distributions, and Tail Pricing

**Question:** a screen gives option prices at different strikes. What can those prices tell us about the way the market values future outcomes, and what remains unknown?

[Straddles, Strangles, Butterflies, and Condors](./option-movement-range.md) built the payments. Here we use those payments as measuring instruments. A narrow call spread probes an upper-tail event; a butterfly probes a neighborhood of its middle strike. [Reading the Options Market: Implied Volatility and Surfaces](./implied-volatility-surfaces.md) supplies quote quality, price consistency, and explicit forward/discount inputs.

## 1. Start with Prices We Can Audit

Keep one-year European options on a nonnegative, no-dividend share. Spot is **£100**, the forward **£105**, and deterministic discount factor **$D=1/1.05$**. Premiums are GBP per share. A **pricing probability**, written $Q$, is a weight used with discounting to reproduce prices. It is not automatically the real-world probability, usually written $P$: compensation for bearing risk can make the two differ.

For example, a contract paying £1 on an event with pricing probability 30% costs $D(0.30)=£0.285714$. Dividing its price by the £1 payoff and by $D$ recovers 30%. This is a pricing reading, not an assertion that the event will occur in 30% of future years.

Begin with an explicitly invented seven-state distribution. Its probabilities are **2%, 8%, 20%, 40%, 20%, 8%, 2%** at terminal prices **£45, £65, £85, £105, £125, £145, £165**. They sum to one and their weighted mean is £105. Generate calls using the familiar discounted-payoff rule:

$$C(K)=D\sum_j q_j\max(s_j-K,0).$$

At strike £105, only £125, £145, and £165 contribute. Their weighted payments are £4, £3.20, and £1.20, totaling £8.40. Discounting gives **£8**. The graph plots the resulting call prices against strike. The corners come from discrete terminal states; this first example has probability masses, not a smooth density.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

F, D, T = 105., 1/1.05, 1.
states = np.arange(45.,166.,20.)
source_q = np.array([.02,.08,.20,.40,.20,.08,.02])
strikes = np.arange(25.,186.,20.)
h = 20.

def state_calls(k,locations=states,weights=source_q):
    k = np.asarray(k,dtype=float)
    return D*np.sum(np.maximum(locations-k[...,None],0.)*weights,axis=-1)

def chart(name,title,x,series,xname,yname,styles=None):
    print("<ECHARTS_DATA>"+json.dumps({name:{"type":"line","title":title,
        "xAxis":{"type":"value","name":xname,"min":float(min(x)),"max":float(max(x))},"yAxisName":yname,
        "series":{label:np.column_stack([x,y]).tolist() for label,y in series.items()},
        "seriesOptions":styles or {}}},allow_nan=False))

calls = state_calls(strikes)
print(pd.DataFrame({"Strike GBP":strikes,"Call GBP":calls}).to_string(index=False))
print(f"Source probability: {source_q.sum():.9f}; mean: {states@source_q:.9f} GBP; zero-strike call: {state_calls(0):.9f} GBP")
chart("distributionCalls","Call-Price Corners Encode Discrete Outcomes",strikes,{"Synthetic calls":calls},
    "Strike (GBP/share)","Call premium (GBP/share)")
```
<Editor id="distribution-setup" />

We reveal the generating distribution to make the later recovery checkable. Real quotes do not arrive with these answers attached. Run cells in order; the quote-resolution widget also runs independently.

## 2. A Call Spread Approximates an Event Payment

Buy a £110 call and sell a £120 call. Divide the basket by its £10 strike gap so its maximum payment is £1. It pays zero below £110, rises linearly from zero to £1 between £110 and £120, and pays £1 above £120. This is a ramp approximation to a **digital option**, which pays a fixed amount when a stated event occurs.

The call prices are £6.571429 and £3.714286. The normalized spread costs **£0.285714**, and its undiscounted expected normalized payment is **30%**. Here that equals $Q(S_T>120)$ exactly, because the discrete example has no states inside the ramp or at its boundaries. In general it is a ramp-weighted expectation, bounded by the probabilities above the upper and lower strikes.

For a continuous pricing distribution, narrowing the strike gap gives:

$$-\frac{1}{D}\frac{\partial C(K)}{\partial K}=Q(S_T>K).$$

The graph compares the £110/£120 ramp with a step paying £1 strictly above £115. It explains the approximation in payoff space before we differentiate prices. At a probability mass, left and right derivatives differ: the left gives $Q(S_T\ge K)$ and the right gives $Q(S_T>K)$. In our example at £105 these are **70% and 30%**. A centered difference can mix them; the event convention matters.

```python:line-numbers
digital_cost = (state_calls(110.)-state_calls(120.))/10
digital_reading = digital_cost/D
left_tail_105 = -(state_calls(105.)-state_calls(85.))/(20*D)
right_tail_105 = -(state_calls(125.)-state_calls(105.))/(20*D)
print(f"Ramp price: {digital_cost:.9f} GBP per GBP 1 maximum payment; pricing reading: {digital_reading:.9f}")
print(f"At 105: left tail including the atom {left_tail_105:.6f}; right tail excluding it {right_tail_105:.6f}")
final = np.linspace(90.,140.,501)
chart("distributionDigital","A Narrow Call Spread Buys a Ramp, Not an Exact Step",final,
    {"110/120 ramp":np.clip((final-110)/10,0,1),"Strictly above 115":(final>115).astype(float)},
    "Final share price (GBP/share)","Payment per GBP 1 maximum")
```
<Editor id="distribution-digital" />

**Check:** if pricing probability is 30%, is the digital price £0.30? **Answer:** no. £0.30 is the expected expiry payment under the pricing weights; the price today is £0.285714 after discounting.

## 3. Recover a Complete Discrete Distribution

Recall the equal-spaced butterfly's triangular payment from the previous chapter. With strikes $K-h,K,K+h$, its peak payment is $h$. If all terminal states lie on that same grid, it pays only at its center state. Hence:

$$q(K)=\frac{C(K-h)-2C(K)+C(K+h)}{Dh}.$$

At £105, the three call prices are £21.333333, £8, and £2.285714. The butterfly costs **£7.619048** and pays **£20** only in the £105 state. Dividing by $D\times20$ gives **40%**. Its state price, the price of a £1 payment in that state, is $Dq=£0.380952$.

To make this a complete reconstruction, we explicitly assume **piecewise-linear call prices between the grid strikes**, slope $-D$ below £25, and zero call value beyond £185. These boundary and interpolation choices encode a discrete law with no mass outside the interior states. They reproduce the generating model here; finite market quotes alone do not establish that model uniquely.

Recover all seven masses, then check **nonnegativity, sum equal to one, mean equal to the forward, and repricing of every supplied call**. Each marker on the graph gives the probability of one exact terminal state. There is no probability assigned between these discrete states.

```python:line-numbers
recovered_states = strikes[1:-1]
recovered_q = np.diff(calls,n=2)/(D*h)
repriced = state_calls(strikes,recovered_states,recovered_q)
recovery = pd.DataFrame({"Terminal price GBP":recovered_states,"Recovered probability":recovered_q,
    "Source probability":source_q,"State price GBP":D*recovered_q})
print(recovery.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(f"Mass: {recovered_q.sum():.9f}; mean: {recovered_states@recovered_q:.9f} GBP; maximum repricing error: {max(abs(repriced-calls)):.3e} GBP")
chart("distributionMass","Recover Probability Masses, Then Reprice the Calls",recovered_states,
    {"Recovered mass (%)":100*recovered_q},"Terminal share price (GBP/share)","Pricing probability mass (%)",
    styles={"Recovered mass (%)":{"type":"scatter","symbol":"diamond","symbolSize":14,
        "itemStyle":{"color":"#ea580c","borderColor":"#ffffff","borderWidth":2}}})
```
<Editor id="distribution-recovery" />

**Check:** can we recover probabilities without the discount input? **Answer:** option prices first identify discounted state weights. Turning them into probabilities requires the appropriate discount factor and compatible settlement conventions. The forward is a separate check on their first moment.

## 4. A Smooth Distribution Has Density, Not Mass at Each Strike

Now use a continuous lognormal pricing example with the same £105 forward, discount factor, and one-year maturity, and **20% Black volatility**. Its annual volatility is a pricing-model input. For a smooth call-price curve:

$$f_Q(K)=\frac{1}{D}\frac{\partial^2 C(K)}{\partial K^2}
\approx\frac{C(K-h)-2C(K)+C(K+h)}{Dh^2}.$$

Notice the extra division by $h$ compared with the discrete mass formula. The triangle has area $h^2$, so the normalized butterfly measures a **triangularly averaged density**, not an exact probability for a bin. Density has units **per GBP of share price**; probability is an area under it.

At strike £105, the exact lognormal density is **0.0189025 per GBP**. A small £1-wide interval near that strike has about **1.89%** pricing probability. A butterfly with £5 wing spacing gives **0.0188268 per GBP**; £20 spacing gives **0.0177374**. Wider spacing averages over more of the curve and smooths its peak.

The graph compares the exact density with both approximations on £60–£160. The printed integral covers only that plotted window. It need not equal one, and we do not normalize it to hide omitted tails. For a fitted smile, differentiate the **whole repriced call curve**, including its strike-dependent volatility, rather than treating each strike's volatility as locally constant without justification.

```python:line-numbers
sigma = .20
def smooth_call(k):
    k = np.asarray(k,dtype=float)
    d1 = (np.log(F/k)+.5*sigma**2*T)/(sigma*np.sqrt(T))
    return D*(F*norm.cdf(d1)-k*norm.cdf(d1-sigma*np.sqrt(T)))

def exact_density(k):
    k = np.asarray(k,dtype=float)
    z = (np.log(k/F)+.5*sigma**2*T)/(sigma*np.sqrt(T))
    return norm.pdf(z)/(k*sigma*np.sqrt(T))

def butterfly_density(k,spacing):
    return (smooth_call(k-spacing)-2*smooth_call(k)+smooth_call(k+spacing))/(D*spacing**2)

density_grid = np.linspace(60.,160.,201)
smooth_density = exact_density(density_grid)
window_mass = np.sum(np.diff(density_grid)*(smooth_density[1:]+smooth_density[:-1])/2)
print(f"Exact density at 105: {exact_density(105):.9f}; h=5: {butterfly_density(105,5):.9f}; h=20: {butterfly_density(105,20):.9f}")
print(f"Density integral on the plotted window only: {window_mass:.9f}")
chart("distributionDensity","Narrower Butterflies Resolve a Smooth Density More Locally",density_grid,
    {"Exact lognormal":smooth_density,"Spacing GBP 5":butterfly_density(density_grid,5),
     "Spacing GBP 20":butterfly_density(density_grid,20)},"Terminal share price (GBP/share)","Pricing density (per GBP)")
```
<Editor id="distribution-density" />

**Check:** is 0.0189025 the probability of finishing exactly at £105? **Answer:** no. That exact-point probability is zero in a continuous distribution. Multiply by a sufficiently small interval width for a local probability approximation, or integrate over the interval.

## 5. Narrow Spacing Also Amplifies Quote Noise

Numerical resolution has a cost. If the middle call premium is three pence too high, the butterfly numerator falls by six pence. With £1 spacing, the resulting density reading at £105 changes from **0.0188995 to −0.0441005 per GBP**. With £5 spacing, it changes only to **0.0163068**. The negative value flags inconsistent midpoint curvature; it is not a negative probability to accept or silently clip away.

Suppose each of the three calls has a **£0.05 half-spread**. Allowing each price to vary independently within its quote interval gives a worst-case density half-width:

$$\frac{\epsilon+2\epsilon+\epsilon}{Dh^2}=\frac{4\epsilon}{Dh^2}.$$

For $\epsilon=£0.05$, the half-width is **0.21 per GBP** at £1 spacing and **0.0084** at £5 spacing. These are quote-box bounds, not statistical confidence intervals. Jointly consistent prices must also satisfy neighboring convexity constraints. The [IV chapter](./implied-volatility-surfaces.md#_11-check-strike-prices-not-just-the-appearance-of-the-smile) explains why a midpoint flag alone does not establish an executable arbitrage.

The graph adds £0.03 to just the £105 call on a £1 grid. The central trough and neighboring spikes show how second differences redistribute one quote error across adjacent density readings.

```python:line-numbers
noise_strikes = np.arange(85.,126.)
clean_prices = smooth_call(noise_strikes)
noisy_prices = clean_prices.copy()
noisy_prices[noise_strikes==105.] += .03
clean_readings = np.diff(clean_prices,n=2)/D
noisy_readings = np.diff(noisy_prices,n=2)/D
quote_half_spread = .05
resolution = pd.DataFrame([[gap,butterfly_density(105,gap),
    butterfly_density(105,gap)-.06/(D*gap**2),4*quote_half_spread/(D*gap**2)] for gap in (1.,5.,10.)],
    columns=["Spacing GBP","Clean density","Three-penny mid bump","Quote-box half-width"])
print(resolution.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
chart("distributionNoise","One Noisy Premium Creates a Trough and Two Spikes",noise_strikes[1:-1],
    {"Clean readings":clean_readings,"One bumped mid":noisy_readings},"Central strike (GBP/share)","Inferred density (per GBP)")
```
<Editor id="distribution-noise" />

### Experiment: Choose a Spacing and Perturb One Quote

The independent widget uses nine equally spaced strikes centered on £105. **Spacing** controls the strike gap; **middle quote change** perturbs only the central call. The orange diamond marks the density reading at £105. Its printed quote-box bounds use the same £0.05 half-spread on every quote. The generating prices remain inside these synthetic intervals for every control setting.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_implied_density_echart,
    spacing=widgets.FloatSlider(value=5.,min=1.,max=10.,step=1.,description="Spacing (£)",continuous_update=False),
    quote_change=widgets.FloatSlider(value=.03,min=-.05,max=.05,step=.01,description="Middle quote (£)",continuous_update=False),
)
widget_instance
```
<Editor id="distribution-resolution-widget" />

**Predict, then try:** keep the three-penny bump and reduce spacing from £5 to £1. **Answer:** its density effect grows by a factor of 25 because the denominator contains the square of spacing. Smaller spacing improves locality with exact prices, but can make noisy readings much less reliable. Quote-aware smoothing requires a stated model and a repricing check, as in the surface lesson.

## 6. Missing Tail Strikes Leave More Than One Answer

Return to the discrete example. Imagine that calls are observed only at strikes **£65, £85, £105, and £125**, alongside the forward and discount inputs. The original upper tail has 8% at £145 and 2% at £165. Together these states have 10% probability and conditional mean **£149**.

An alternative tail puts **9% at £129 and 1% at £329**. It has the same 10% mass and £149 conditional mean. Keep all states at or below £125 unchanged. For every observed strike, all modified tail states are above the strike, so only their total mass and first moment enter the call price. **Both complete distributions reproduce every observed call and the £105 forward exactly.**

Yet $Q(S_T>150)$ is **2% in the original and 1% in the alternative**. The £150 call costs **£0.285714 versus £1.704762**: less probability can still support a higher call value when the rare outcome is much larger. The graph shows the unobserved upper-strike call prices diverging after the last observed strike. Their shared price at £125 is £2.285714.

This is a constructive demonstration of missing information, not a fitted forecast. Tail extrapolation assumptions affect probabilities, option prices, and higher moments. More decimals in an optimizer cannot replace absent tail observations.

```python:line-numbers
alternative_states = np.r_[states[:5],129.,329.]
alternative_q = np.r_[source_q[:5],.09,.01]
observed_strikes = np.array([65.,85.,105.,125.])
original_observed = state_calls(observed_strikes)
alternative_observed = state_calls(observed_strikes,alternative_states,alternative_q)
print(pd.DataFrame({"Observed strike":observed_strikes,"Original calls":original_observed,
    "Alternative calls":alternative_observed,"Difference":alternative_observed-original_observed}).to_string(index=False))
tail_rows = [[name,weights.sum(),locations@weights,weights[locations>150].sum(),float(state_calls(150.,locations,weights))]
    for name,locations,weights in (("Original",states,source_q),("Alternative",alternative_states,alternative_q))]
print(pd.DataFrame(tail_rows,columns=["Law","Mass","Mean GBP","Probability above 150","Call 150 GBP"]).to_string(index=False))
tail_strikes = np.linspace(125.,350.,226)
chart("distributionTails","Matching Observed Calls Does Not Fix the Unobserved Tail",tail_strikes,
    {"Original tail":state_calls(tail_strikes),"Alternative tail":state_calls(tail_strikes,alternative_states,alternative_q)},
    "Unobserved strike beyond GBP 125","Call premium (GBP/share)")
```
<Editor id="distribution-tails" />

**Check:** does either law become a physical forecast because it fits the quotes? **Answer:** no. Both are possible pricing laws under the stated observations. A physical forecast requires additional information and assumptions about risk compensation and future outcomes.

## 7. Worked Exercise: Separate Discounting, Mass, and Truncation

Use the original discrete grid to answer three questions:

1. A £1-maximum £110/£120 call spread costs £0.285714. What is its undiscounted pricing reading?
2. The £105/£125/£145 butterfly costs £3.809524 and pays £20 in the £125 state. What probability mass does it imply?
3. You retain only the recovered states £85, £105, and £125. Do they form a complete distribution?

**Work it through.** First divide £0.285714 by $D$, giving **30%**. For the butterfly, divide £3.809524 by $20D$, giving **20%**. The three retained masses are 20%, 40%, and 20%, totaling **80%**. Their unnormalized first moment is £84. Dividing £84 by 0.8 gives £105, but that is a **conditional mean within the retained states**, not proof that no tails are missing. Symmetry happens to preserve the mean here.

The graph keeps the omitted states visible as zeros in the retained series. Hollow blue circles mark the complete distribution; smaller orange diamonds mark retained masses, so overlapping values remain visible. Renormalizing the retained probabilities would inflate the £105 mass from 40% to 50% and change option prices. The code prints that repricing failure for the £105 call.

```python:line-numbers
exercise_butterfly = state_calls(105.)-2*state_calls(125.)+state_calls(145.)
exercise_mass = exercise_butterfly/(20*D)
retained_q = recovered_q*np.isin(recovered_states,[85.,105.,125.])
conditional_q = retained_q/retained_q.sum()
conditional_call = float(state_calls(105.,recovered_states,conditional_q))
print(f"Digital reading: {digital_cost/D:.9f}; butterfly mass: {exercise_mass:.9f}")
print(f"Retained mass: {retained_q.sum():.9f}; first moment: {recovered_states@retained_q:.9f}; conditional mean: {recovered_states@conditional_q:.9f}")
print(f"Original call 105: {state_calls(105):.9f}; renormalized truncated call: {conditional_call:.9f} GBP")
chart("distributionExercise","Keep Missing Probability Visible",recovered_states,
    {"Complete mass (%)":100*recovered_q,"Retained mass (%)":100*retained_q},
    "Terminal share price (GBP/share)","Pricing probability mass (%)",
    styles={"Complete mass (%)":{"type":"scatter","symbol":"circle","symbolSize":24,
        "itemStyle":{"color":"#ffffff","borderColor":"#2563eb","borderWidth":3}},
        "Retained mass (%)":{"type":"scatter","symbol":"diamond","symbolSize":14,
        "itemStyle":{"color":"#ea580c","borderColor":"#ffffff","borderWidth":2}}})
```
<Editor id="distribution-exercise" />

**Completed answer:** the renormalized truncated £105 call is **£4.761905**, versus the observed **£8**. A plausible-looking mean is insufficient: check total mass, the forward, and repricing together.

## Optional Extension: Moments Summarize the Whole Pricing Law

For terminal share price $S_T$, let $\mu=E_Q[S_T]$ and $v=E_Q[(S_T-\mu)^2]$. Standardized **skewness** is $E_Q[(S_T-\mu)^3]/v^{3/2}$; **kurtosis** is $E_Q[(S_T-\mu)^4]/v^2$. Excess kurtosis subtracts three. These definitions concern terminal **price levels**, not log returns; changing the variable changes the moments.

For the original symmetric law, the pairs £60, £40, and £20 away from the mean contribute **144, 256, and 160 GBP²** to variance. For example, the first pair contributes $2(0.02)(60^2)=144$. The total is **560 GBP²**. Standard deviation is **£23.664319**, skewness **0**, and kurtosis **3.163265**. This terminal-price standard deviation is not an annualized Black implied volatility.

The alternative tail keeps the £105 mean and observed call prices but raises variance to **913.6**, skewness to approximately **3.77335**, and kurtosis to **30.83174**. Higher moments give large weight to distant outcomes, so missing tails matter greatly.

A quoted **risk reversal** compares call-wing and put-wing implied volatilities under a stated delta convention. A quoted **smile butterfly** compares wing and central volatility quotes. Neither is literally statistical skewness or kurtosis, and a smile-butterfly quote is not the cash payoff of our equal-strike-spaced call butterfly. Calculating moments requires a complete, coherent distribution and a specified variable.

```python:line-numbers
def moments(locations,weights):
    mean = locations@weights
    centered = locations-mean
    variance = centered**2@weights
    skewness = (centered**3@weights)/variance**1.5
    kurtosis = (centered**4@weights)/variance**2
    return [mean,variance,np.sqrt(variance),skewness,kurtosis,kurtosis-3]

moment_table = pd.DataFrame({"Original":moments(states,source_q),
    "Alternative":moments(alternative_states,alternative_q)},
    index=["Mean GBP","Variance GBP squared","Std deviation GBP","Skewness","Kurtosis","Excess kurtosis"]).T
print(moment_table.to_string(float_format=lambda x:f"{x:.6f}"))
```
<Editor id="distribution-moments" />

## Takeaways

- Call-price slopes measure discounted tail-event weights; curvature measures local pricing-distribution information.
- Discrete mass and continuous density have different normalizations and units. Narrow spreads and butterflies have finite-width averaging effects.
- Check nonnegativity, total probability, the forward mean, and repricing, with boundary and interpolation assumptions visible.
- Narrow spacing amplifies price noise. Quote-box bounds are not confidence intervals, and negative midpoint curvature is a diagnostic.
- Missing tail prices allow different complete pricing laws to fit the same observations. Fitting prices does not identify physical forecasts.

Next: [Building Structured Products](./d.0-overview.md#structured-products). Use bonds and options to allocate a fixed investment budget between a maturity payment and conditional participation.
