---
title: "Straddles, Strangles, Butterflies, and Condors"
permalink: /option-movement-range
description: "Compare movement and finishing-range strategies through worked premiums, financed break-even points, payoff charts, and an independent butterfly-to-condor experiment."
---

# Straddles, Strangles, Butterflies, and Condors

**Question:** you have a view about how far a share might move, or where it might finish, rather than whether it will rise. Which option payments express that view, and how much movement or precision does their premium require?

A straddle buys payments in either direction. A strangle moves those payments farther away to reduce the entry price. A butterfly concentrates its payment around one finishing price; a condor spreads the maximum payment across an interval. We will compare these four shapes using one set of market inputs.

## 1. Reuse the Pricing and Cash-Flow Tools

[Spreads and Basic Option Combinations](./option-combinations.md) supplies signed legs, financed profit, and execution accounting. [The Greeks and Hedging](./greeks-hedging.md) supplies local sensitivities. [Reading the Options Market: Implied Volatility and Surfaces](./implied-volatility-surfaces.md) explains the volatility input and its quote conventions.

Keep the same **£100 share, no dividends, European options, one year, 20% annual volatility, and 5% effective annual cash rate**. Premiums and payoffs are GBP per one-share strategy. A matched set of 100-share contracts multiplies the results by 100. These are synthetic model prices, with cash-equivalent settlement, no default, and equal borrowing/lending rates.

Recall the one line of accounting we need: **financed profit = expiry payoff − entry debit × 1.05**. A £2 debit that pays £10 therefore earns £7.90 at expiry. Run the cells in order; the interactive strike experiment also runs independently. The compact functions below implement the pricing and signed-leg rules already used in the prerequisite.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

S0, T, r, sigma = 100., 1., np.log1p(.05), .20
growth = np.exp(r*T)
terminal = np.linspace(50.,150.,401)

def option_price(strike,kind="call",spot=S0,remaining=T,vol=sigma):
    if kind not in ("call","put") or not np.isfinite([strike,spot,remaining,vol]).all():
        raise ValueError("Use finite inputs and call or put")
    if strike<=0 or spot<0 or remaining<0 or vol<0:
        raise ValueError("Use positive strike and nonnegative spot, time, volatility")
    discount = np.exp(-r*remaining)
    if spot==0 or remaining==0 or vol==0:
        return max(spot-strike*discount,0.) if kind=="call" else max(strike*discount-spot,0.)
    scale = vol*np.sqrt(remaining)
    d1 = (np.log(spot/strike)+(r+.5*vol**2)*remaining)/scale
    if kind=="call":
        return spot*norm.cdf(d1)-strike*discount*norm.cdf(d1-scale)
    return strike*discount*norm.cdf(scale-d1)-spot*norm.cdf(-d1)

def value(legs,**inputs):
    return sum(n*option_price(k,kind,**inputs) for n,kind,k in legs)

def payoff(legs,final=terminal):
    final = np.asarray(final,dtype=float)
    return sum(n*np.maximum(final-k if kind=="call" else k-final,0.) for n,kind,k in legs)

def leg_table(legs):
    return pd.DataFrame([[n,kind,k,option_price(k,kind),n*option_price(k,kind)] for n,kind,k in legs],
        columns=["Quantity","Option","Strike GBP","Unit premium GBP","Signed cost GBP"])

def chart(name,title,series,x=terminal,xname="Final share price (GBP/share)",yname="GBP per one-share strategy"):
    print("<ECHARTS_DATA>"+json.dumps({name:{"type":"line","title":title,
        "xAxis":{"type":"value","name":xname,"min":float(min(x)),"max":float(max(x))},"yAxisName":yname,
        "series":{label:np.column_stack([x,y]).tolist() for label,y in series.items()},
        "seriesOptions":{"Zero":{"lineStyle":{"type":"dashed"}}}}},allow_nan=False))

straddle = [(1,"call",100.),(1,"put",100.)]
strangle = [(1,"put",90.),(1,"call",110.)]
butterfly = [(1,"call",90.),(-2,"call",100.),(1,"call",110.)]
condor = [(1,"call",85.),(-1,"call",95.),(-1,"call",105.),(1,"call",115.)]
strategies = {"Straddle":straddle,"Strangle":strangle,"Butterfly":butterfly,"Condor":condor}
costs = {name:value(legs) for name,legs in strategies.items()}
print(pd.DataFrame({"Entry debit GBP":costs,"Financed debit GBP":{name:c*growth for name,c in costs.items()}}).to_string())
```
<Editor id="movement-setup" />

## 2. Straddle: Buy Movement in Either Direction

Buy one **£100 call** and one **£100 put** with the same expiry. Below £100 the put pays; above £100 the call pays. Exactly at £100 both expire worthless.

| Leg | Quantity | Premium paid |
| --- | ---: | ---: |
| £100 call | +1 | £10.386279 |
| £100 put | +1 | £5.624375 |
| Total | | **£16.010654** |

The terminal payment is the distance from the strike: $W_T=|S_T-100|$. Financing the debit costs $16.010654(1.05)=£16.811187$. The two break-even prices are therefore **£83.188813 and £116.811187**. At £110, a £10 move produces £10 of payoff but a **£6.811187 loss**. At £125, the £25 payoff leaves **£8.188813 profit**.

The maximum financed loss is £16.811187 at the strike. Upside profit is unbounded in this model; downside profit is bounded because the share cannot fall below zero. The graph separates the V-shaped payment from the same shape shifted down by the financed debit. Its horizontal axis lists possible expiry outcomes, not their probabilities.

```python:line-numbers
straddle_funded = costs["Straddle"]*growth
straddle_breaks = np.array([100-straddle_funded,100+straddle_funded])
print(leg_table(straddle).to_string(index=False))
print(f"Financed break-even prices: {straddle_breaks}")
print(f"Profit at 110: {payoff(straddle,110)-straddle_funded:.6f}; at 125: {payoff(straddle,125)-straddle_funded:.6f}")
chart("movementStraddle","A Move Must Pay for Both Options",{
    "Expiry payoff":payoff(straddle),"Financed profit":payoff(straddle)-straddle_funded,"Zero":np.zeros_like(terminal)})
```
<Editor id="movement-straddle" />

**Try it:** calculate the profit if the share finishes at £85. **Answer:** $15-16.811187=-£1.811187$. Direction was irrelevant to that payment, but distance from the strike was not enough. Selling the straddle reverses the displayed profit under the same frictionless prices; it creates unbounded upside loss and requires margin funding in practice. Buying both directions does not itself make the initial delta zero, as the comparison below will show.

## 3. Strangle: Pay Less, Require a Larger Move

Buy the **£90 put** for £2.336029 and the **£110 call** for £5.993112. The debit is **£8.329141**, financing to **£8.745599**. The two options both expire worthless throughout £90–£110.

Below £90, the payoff is $90-S_T$; between £90 and £110 it is zero; above £110 it is $S_T-110$. Thus the financed break-even prices are **£81.254401 and £118.745599**. This lower-premium position needs a larger move to break even than our straddle.

At £125 the strangle pays £15, leaving **£6.254401**, versus £8.188813 for the straddle. At £100 the strangle loses £8.745599, versus £16.811187. The graph compares **profit with profit**: the strangle reduces the loss in the central region but pays less in the distant wings. The cheaper debit is a different payment promise, not a bargain established by price alone.

```python:line-numbers
strangle_funded = costs["Strangle"]*growth
strangle_breaks = np.array([90-strangle_funded,110+strangle_funded])
print(leg_table(strangle).to_string(index=False))
print(f"Financed break-even prices: {strangle_breaks}; profit at 125: {payoff(strangle,125)-strangle_funded:.6f}")
chart("movementStrangle","A Lower Premium Leaves a Wider No-Payment Region",{
    "Straddle profit":payoff(straddle)-straddle_funded,"Strangle profit":payoff(strangle)-strangle_funded,"Zero":np.zeros_like(terminal)})
```
<Editor id="movement-strangle" />

**Experiment:** change the strangle to a £85 put and £115 call, then recompute its debit and break-even prices. **Answer:** its debit falls because each purchased option has a less favorable strike. The put starts paying later on the downside and the call later on the upside. Both financed break-even points move outward in this example. Repricing the new legs is essential; keeping the old debit would describe a different trade.

## 4. Butterfly: Concentrate Payment Around One Price

Buy one **£90 call**, sell **two £100 calls**, and buy one **£110 call**. This is also a long £90/£100 call spread plus a short £100/£110 call spread, using the constructions from [Spreads and Basic Option Combinations](./option-combinations.md).

Buying the outside calls costs £22.614856 in total. Selling two middle calls receives £20.772559. Subtracting the proceeds leaves a **£1.842297 debit**, financing to **£1.934412**. Work through each region before reading the triangle:

| Final share price | Signed option payment | Total payoff |
| --- | --- | --- |
| At or below £90 | All calls out of the money | £0 |
| £90 to £100 | Only the £90 call pays | $S_T-90$ |
| £100 to £110 | £90 call less two £100 calls | $110-S_T$ |
| At or above £110 | All call payments cancel | £0 |

At £100 the peak payment is **£10**, giving maximum profit **£8.065588**. Outside the wings the maximum loss is the financed debit, £1.934412. On the rising side, $S_T-90=1.934412$ gives the first break-even; the falling side gives the second. The results are **£91.934412 and £108.065588**.

The graph overlays payment and profit. A positive payment near a wing may still be smaller than the financed cost. The equal £10 strike spacing is what makes the $+1,-2,+1$ call basket a nonnegative triangle; unequal spacing needs adjusted quantities to obtain that construction.

```python:line-numbers
butterfly_funded = costs["Butterfly"]*growth
butterfly_breaks = np.array([90+butterfly_funded,110-butterfly_funded])
print(leg_table(butterfly).to_string(index=False))
print(f"Financed break-even prices: {butterfly_breaks}; maximum profit: {10-butterfly_funded:.6f}")
chart("movementButterfly","The Largest Payment Requires a Precise Finish",{
    "Expiry payoff":payoff(butterfly),"Financed profit":payoff(butterfly)-butterfly_funded,"Zero":np.zeros_like(terminal)})
```
<Editor id="movement-butterfly" />

**Check:** compare finishes at £95 and £105. **Answer:** both pay £5 and earn £3.065588. The peak is narrow, but a profitable finish does not require landing exactly at £100. The [IV chapter's convexity check](./implied-volatility-surfaces.md#_11-check-strike-prices-not-just-the-appearance-of-the-smile) used this same nonnegative payment to test prices; here the question is what a buyer pays to obtain it.

## 5. Condor: Broaden the Maximum-Payment Region

Buy a **£85 call**, sell a **£95 call**, sell a **£105 call**, and buy a **£115 call**. The two outside ramp widths remain £10, but the maximum-payment region now runs from £95 to £105.

Buying the outside calls costs £24.816020 in total. Selling the inside calls receives £21.240194. Subtracting the proceeds leaves a **£3.575826 debit**, financing to **£3.754617**. The payoff is zero below £85, rises as $S_T-85$ to £95, stays at £10 through £105, falls as $115-S_T$ to £115, and is zero above £115.

The maximum financed profit is **£6.245383**, the maximum loss **£3.754617**, and the break-even prices **£88.754617 and £111.245383**. Compared with our butterfly, the peak payoff stays £10, but the broader payment costs more and leaves less profit at the peak. At £95 the condor earns £6.245383, while the butterfly earns £3.065588.

The graph compares the two financed profits. This is a **long all-call condor**. An iron condor uses both puts and calls and has different legs and entry cash flows, so always read the basket rather than relying on the word “condor.”

```python:line-numbers
condor_funded = costs["Condor"]*growth
condor_breaks = np.array([85+condor_funded,115-condor_funded])
print(leg_table(condor).to_string(index=False))
print(f"Financed break-even prices: {condor_breaks}; maximum profit: {10-condor_funded:.6f}")
chart("movementCondor","A Broader Peak Costs More to Buy",{
    "Butterfly profit":payoff(butterfly)-butterfly_funded,"Condor profit":payoff(condor)-condor_funded,"Zero":np.zeros_like(terminal)})
```
<Editor id="movement-condor" />

**Check:** why is the condor's debit larger? Its terminal payoff is at least the butterfly's at every nonnegative share price and strictly greater in some regions. Under our common pricing assumptions, buying that additional payment costs money. This compares these particular strike sets, not every strategy called a condor or butterfly.

## 6. Compare Today's Exposure with the Expiry Story

Use the signed Greek sums from [The Greeks and Hedging](./greeks-hedging.md). At today's inputs, the straddle has delta **+0.269117 shares** and vega **+£0.752058 per volatility point**, per one-share strategy. For one matched 100-share call/put pair, that is about **+26.91 shares of delta** and **+£75.21 per volatility point**. An expiry payoff symmetric around £100 is not a promise of zero delta today.

Our butterfly and condor have negative local vega near today's £100 spot, while the straddle and strangle have positive vega. These are **local readings at specified inputs**, not permanent signs: moving the spot into a wing or changing remaining life changes the exposures. The graph reprices the four baskets over flat volatility scenarios with spot, time, and rates fixed. Its vertical axis is the change from each basket's 20%-volatility value, so the lines share a meaningful zero.

There is also a timing distinction. After six months, suppose spot is £110 and the repricing volatility is 10%. The straddle is worth **£12.682507**, while its financed entry debit is $16.010654\sqrt{1.05}=£16.406039$. Selling at that model value produces **−£3.723531** before execution costs. A 10% spot rise does not guarantee a profitable long straddle. A terminal distance, a pre-expiry mark, and a delta-hedged realized-volatility result are different calculations.

```python:line-numbers
def risks(legs):
    total = np.zeros(3)
    for n,kind,k in legs:
        d1 = (np.log(S0/k)+(r+.5*sigma**2)*T)/(sigma*np.sqrt(T))
        total += n*np.array([norm.cdf(d1)-(kind=="put"),
            norm.pdf(d1)/(S0*sigma*np.sqrt(T)),.01*S0*norm.pdf(d1)*np.sqrt(T)])
    return total

risk_table = pd.DataFrame({name:risks(legs) for name,legs in strategies.items()},
    index=["Delta shares","Gamma shares/GBP","Vega GBP/point"]).T
print(risk_table.to_string(float_format=lambda x:f"{x:.6f}"))
vol_grid = np.linspace(.10,.35,51)
vol_changes = {name:np.array([value(legs,vol=v)-costs[name] for v in vol_grid]) for name,legs in strategies.items()}
exit_value = value(straddle,spot=110.,remaining=.5,vol=.10)
exit_funding = costs["Straddle"]*np.exp(r*.5)
print(f"Six-month straddle exit: value {exit_value:.6f}, funding {exit_funding:.6f}, profit {exit_value-exit_funding:.6f} GBP")
chart("movementVega","Compare Repricing under One Shared Volatility Scenario",vol_changes,
    x=100*vol_grid,xname="Annual volatility (%)",yname="Value change from 20% volatility (GBP/strategy)")
```
<Editor id="movement-risk" />

**Experiment:** keep the six-month £110 spot but restore volatility to 20%. **Answer:** the mark rises to £15.648512, yet financed profit is still **−£0.757526**. Both time and the price paid matter. These common flat-volatility shocks are teaching scenarios; an actual smile may move differently at each strike.

## 7. Experiment: Open the Butterfly into a Condor

Keep the center at £100 and both outside ramp widths at £10. Let the **half-plateau** control be $h$. The four call strikes are $90-h$, $100-h$, $100+h$, and $110+h$, with quantities $+1,-1,-1,+1$.

At $h=0$, the two short calls coincide at £100: the basket is our butterfly. At $h=5$, the strikes become £85, £95, £105, and £115: our condor. The plateau's full width is $2h$. The widget reprices the legs each time; the second control selects a final share price. The orange diamond marks financed profit at that outcome, and the printed values give debit, profit bounds, and break-even prices.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_option_range_echart,
    half_plateau=widgets.FloatSlider(value=5.,min=0.,max=10.,step=1.,description="Half-plateau (£)",continuous_update=False),
    final_spot=widgets.FloatSlider(value=100.,min=60.,max=140.,step=5.,description="Final share (£)",continuous_update=False),
)
widget_instance
```
<Editor id="movement-range-widget" />

**Predict, then try:** increase $h$ from 0 to 5 while leaving the final price at £100. **Answer:** payoff stays £10, debit rises from £1.842297 to £3.575826, and profit falls from £8.065588 to £6.245383. At £95, however, the broader shape pays £10 rather than £5. The extra premium purchases a broader set of payments, not a free improvement at every outcome after costs.

## 8. Worked Comparison: Which Basket Pays for This Finish?

Suppose the final share price is **£108**. Calculate financed profit for all four strategies, first per one-share strategy and then for matched 100-share contracts. Use the original model entry prices.

**Work it through:** the straddle pays £8, the strangle £0, the butterfly £2, and the condor £7. Subtract their respective financed debits. The resulting profits per one-share strategy are **−£8.811187, −£8.745599, +£0.065588, and +£3.245383**. The condor does best at this selected finish; that observation alone does not rank expected returns.

Now give every option a synthetic **£0.05 bid/ask half-spread per share**, centered on its model price. Using the execution rule from the combinations chapter, the straddle and strangle each cost an extra £0.10 to enter; the butterfly and condor each cost an extra £0.20 because they contain four absolute option units. Finance these extra debits too. No other fees are included.

For 100-share contracts, the butterfly's small model profit becomes **−£14.441159** after entry spreads, while the condor earns **£303.538312**. The chart compares model and executed profits across final-price scenarios for those two range positions. Each executed curve sits below its model counterpart by £0.21 per one-share strategy.

```python:line-numbers
exercise_final, multiplier, half_spread = 108., 100, .05
exercise_rows = []
executed_costs = {}
for name,legs in strategies.items():
    executed_costs[name] = sum(n*(option_price(k,kind)+np.sign(n)*half_spread) for n,kind,k in legs)
    payment = float(payoff(legs,exercise_final))
    mid_profit = payment-costs[name]*growth
    executed_profit = payment-executed_costs[name]*growth
    exercise_rows.append([name,payment,mid_profit,multiplier*mid_profit,multiplier*executed_profit])
exercise = pd.DataFrame(exercise_rows,columns=["Strategy","Payoff/share","Model profit/share","Model profit/100","Executed profit/100"])
print(exercise.to_string(index=False,float_format=lambda x:f"{x:.6f}"))
comparison = {}
for name in ("Butterfly","Condor"):
    comparison[name+" model"] = payoff(strategies[name])-costs[name]*growth
    comparison[name+" executed"] = payoff(strategies[name])-executed_costs[name]*growth
chart("movementExercise","Small Range Profits Can Be Consumed by Entry Spreads",comparison)
```
<Editor id="movement-exercise" />

**Final check:** does the condor's higher profit at £108 establish the best trade today? No. Choosing a position requires a view about possible outcomes, their probabilities, prices, and acceptable losses. The diagrams specify payments and conditional profits; they do not supply a physical forecast. Short legs also require collateral arrangements even when the matched terminal payoff has a bounded loss.

## Takeaways

- A straddle buys distance from one strike; a strangle reduces the debit by leaving a wider region without payment.
- A butterfly buys a triangular payment; the illustrated condor buys a broader plateau at a higher debit.
- Financed break-even prices differ from strikes. Local Greeks and early-sale values answer different questions from expiry diagrams.
- A strategy comparison needs consistent contract units, inputs, and execution sides. A favorable selected outcome is not evidence of expected profit.

Next: [Butterflies, Implied Distributions, and Tail Pricing](./implied-distributions.md). Use the butterfly payment already built here to read local pricing-distribution information from option prices.
