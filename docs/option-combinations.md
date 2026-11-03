---
title: "Spreads and Basic Option Combinations"
permalink: /option-combinations
description: "Build bull and bear spreads, covered calls, protective puts, collars, and boxes from signed legs; reconcile premiums, financed profits, break-even points, and aggregate Greeks."
---

# Spreads and Basic Option Combinations

**Question:** you want some benefit from a rising share price, but you have a limited premium budget. What changes if you buy one call and sell another? What if you already own the share and want protection instead?

Think of a combination as a shopping basket with both purchases and sales. Each item has a price today and a payment later. A strategy name is shorthand for that basket, not a substitute for checking its contents. Start by listing the legs, with a plus sign for what you own and a minus sign for what you owe.

[Options and Replication](./d.3-options.md) introduced option payoffs and put–call parity. [Deriving and Using Black–Scholes](./black-scholes.md) supplied a pricing model. [The Greeks and Hedging](./greeks-hedging.md) explained local risk. Here we combine those ingredients without changing their units or cash-account conventions.

## 1. Keep One Contract Convention and One Cash Account

Our synthetic share costs **£100**, pays no dividends, and cannot have a negative price. All options are **European**, on this same share, with **one year** to expiry. Each displayed option covers **one share**. A matched set of 100-share option contracts multiplies every option payment by 100 and requires 100 shares for a fully covered stock leg.

Use 20% annual Black–Scholes volatility and a **5% effective annual cash rate**. The equivalent continuous rate is $r=\log(1.05)$, so the one-year growth factor is $G=e^{rT}=1.05$. Prices are model teaching values, not observed executable quotes. We assume cash-equivalent settlement, no default, and a common borrowing/lending rate. We add bid/ask costs later. Real American exercise, dividends, delivery obligations, and separate margin funding need their own cash flows.

For signed option quantities $n_i$ and $h$ shares, the entry value and terminal wealth are:

$$V_0=hS_0+\sum_i n_i O_{i,0},\qquad W_T=hS_T+\sum_i n_i O_{i,T}.$$

A **debit** means $V_0>0$: you pay to enter. A **credit** means $V_0<0$: you receive money. In either case, put the opposite amount, $-V_0$, in the cash account. The total initial net value is zero, and terminal **financed profit** is:

$$\Pi_T=W_T-V_0G.$$

For example, a £4 debit that later pays £10 earns $10-4(1.05)=£5.80$. A £4 credit followed by a £10 payment earns $-10+4(1.05)=-£5.80$. The sign of the initial premium does not decide whether the trade is profitable.

The code below reuses the Black–Scholes formula visibly. `value` sums today's signed legs; `payoff` sums their expiry cash equivalents. These functions do not choose a strategy or optimize it. Run cells in order; the strike experiment later also runs independently.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

S0, T, r, sigma = 100., 1., np.log1p(.05), .20
growth = np.exp(r*T)
terminal = np.linspace(0.,160.,321)
checks = np.array([0.,80.,90.,100.,105.,110.,120.,160.])

def option_price(spot, strike, remaining=T, rate=r, vol=sigma, kind="call"):
    if kind not in ("call","put") or not np.isfinite([spot,strike,remaining,rate,vol]).all():
        raise ValueError("Use finite inputs and call or put")
    if spot < 0 or strike <= 0 or remaining < 0 or vol < 0:
        raise ValueError("Use nonnegative spot, time, volatility and positive strike")
    discount = np.exp(-rate*remaining)
    if remaining == 0 or vol == 0 or spot == 0:
        return max(spot-strike*discount,0.) if kind == "call" else max(strike*discount-spot,0.)
    scale = vol*np.sqrt(remaining)
    d1 = (np.log(spot/strike)+(rate+vol**2/2)*remaining)/scale
    d2 = d1-scale
    if kind == "call":
        return spot*norm.cdf(d1)-strike*discount*norm.cdf(d2)
    return strike*discount*norm.cdf(-d2)-spot*norm.cdf(-d1)

def value(legs, stock=0., spot=S0, remaining=T, rate=r, vol=sigma):
    return stock*spot+sum(n*option_price(spot,k,remaining,rate,vol,kind) for n,kind,k in legs)

def payoff(legs, stock=0., final=terminal):
    final = np.asarray(final,dtype=float)
    total = stock*final
    for n,kind,k in legs:
        total = total+n*np.maximum(final-k if kind == "call" else k-final,0.)
    return total

def leg_table(legs, stock=0.):
    rows = [[kind,n,k,option_price(S0,k,kind=kind),n*option_price(S0,k,kind=kind)] for n,kind,k in legs]
    if stock:
        rows.insert(0,["Share",stock,np.nan,S0,stock*S0])
    return pd.DataFrame(rows,columns=["Instrument","Quantity","Strike GBP","Unit price GBP","Signed cost GBP"])

def chart(name, title, series, x=terminal, xname="Final share price (GBP/share)", yname="GBP per one-share strategy", publish=True):
    styles = {label:{"lineStyle":{"type":"dashed"}} for label in series if label in ("Financed profit","Stock only","Zero")}
    payload = {name:{"type":"line","title":title,"xAxis":{"type":"value","name":xname},
                    "yAxisName":yname,"series":{label:np.column_stack([x,y]).tolist() for label,y in series.items()},
                    "seriesOptions":styles}}
    if not publish:
        return payload
    print("<ECHARTS_DATA>"+json.dumps(payload,allow_nan=False))

quotes = pd.DataFrame({"Strike GBP":[90.,100.,110.],
                       "Call GBP":[option_price(S0,k) for k in (90.,100.,110.)],
                       "Put GBP":[option_price(S0,k,kind="put") for k in (90.,100.,110.)]})
print(quotes.to_string(index=False,float_format=lambda x:f"{x:.6f}"))
```
<Editor id="combinations-setup" />

| Strike | Call premium | Put premium |
| ---: | ---: | ---: |
| £90 | £16.621744 | £2.336029 |
| £100 | £10.386279 | £5.624375 |
| £110 | £5.993112 | £10.755017 |

Keep full precision in calculations. The displayed rounding is for reading. Graphs of expiry outcomes are **scenarios**, not price forecasts or probability distributions.

## 2. Bull Call Spread: Buy Upside, Sell the Distant Upside

A **bull call spread** buys a lower-strike call and sells a higher-strike call, with the same expiry and quantity. “Bull” means the terminal payoff increases as the share rises through the strike interval. “Spread” refers here to the difference between two options, not the bid/ask spread.

Buy the £100 call for £10.386279 and sell the £110 call for £5.993112. The net debit is:

$$D=C(100)-C(110)=10.386279-5.993112=£4.393168.$$

Selling the second call reduces entry cost, but gives away gains above £110. At a final share price of £120, the bought call pays £20 and the sold call costs £10. The basket pays £10, not £20.

| Final price region | Long £100 call | Short £110 call | Combined payoff |
| --- | --- | --- | --- |
| $S_T\le100$ | 0 | 0 | 0 |
| $100<S_T<110$ | $S_T-100$ | 0 | $S_T-100$ |
| $S_T\ge110$ | $S_T-100$ | $-(S_T-110)$ | 10 |

The premium's maturity cost is $DG=4.393168(1.05)=£4.612826$. Subtract it in every region:

- **Maximum loss:** £4.612826, when $S_T\le100$.
- **Maximum gain:** $10-4.612826=£5.387174$, when $S_T\ge110$.
- **Financed break-even:** $100+4.612826=£104.612826$.

These are one-share amounts. One long and one short 100-share contract cost £439.32 today and have a maximum financed loss of £461.28 under these assumptions. The loss exceeds the entry debit because we include funding to expiry.

The first graph adds the two signed payoffs. The second separates the combined payoff from profit. At £105, a positive £5 payment produces only **£0.387174 profit**. The bend at £110 shows exactly what was sold to reduce the premium.

```python:line-numbers
bull_call = [(1.,"call",100.),(-1.,"call",110.)]
bull_debit = value(bull_call)
bull_payoff = payoff(bull_call)
bull_profit = bull_payoff-bull_debit*growth
bull_break_even = 100+bull_debit*growth
print(leg_table(bull_call).to_string(index=False))
print(f"Debit: {bull_debit:.9f}; financed cost: {bull_debit*growth:.9f} GBP")
print(f"Break-even: {bull_break_even:.9f}; max gain: {10-bull_debit*growth:.9f}; max loss: {bull_debit*growth:.9f} GBP")
print(pd.DataFrame({"Final share":checks,"Payoff":payoff(bull_call,final=checks),
                    "Financed profit":payoff(bull_call,final=checks)-bull_debit*growth}).to_string(index=False))
bull_charts = chart("spreadLegs","Add Bought and Sold Call Payments",{
    "Long 100 call":np.maximum(terminal-100,0),"Short 110 call":-np.maximum(terminal-110,0),"Combined":bull_payoff},publish=False)
bull_charts.update(chart("spreadProfit","A Smaller Debit Comes with an Upside Cap",{
    "Payoff":bull_payoff,"Financed profit":bull_profit,"Zero":np.zeros_like(terminal)},publish=False))
print("<ECHARTS_DATA>"+json.dumps(bull_charts,allow_nan=False))
```
<Editor id="combinations-bull-call" />

**Experiment:** evaluate final prices £103 and £108. **Answer:** payoffs are £3 and £8; financed profits are approximately **−£1.612826** and **£3.387174**. Being above the lower strike is not enough to break even.

## 3. Bull Put Spread: The Credit Version of the Same View

Buy the £100 put and sell the £110 put. The short higher-strike put receives more premium than the lower-strike protection costs:

$$V_0=P(100)-P(110)=5.624375-10.755017=-£5.130642.$$

This is a **£5.130642 credit**, not a £5.130642 profit. At £80, the long put pays £20 but the short put owes £30. The net payment is −£10. At or above £110, both puts expire worthless and the basket pays zero.

The payoff is −£10 below £100, $S_T-110$ between the strikes, and zero above £110. The credit grows to **£5.387174**, giving the same financed profit as the bull call spread: maximum loss £4.612826, maximum gain £5.387174, and break-even £104.612826.

Why the same profit? Put–call parity gives:

$$C(100)-C(110)=P(100)-P(110)+10e^{-rT}.$$

The bull call spread is the bull put spread **plus a bond paying £10 at expiry**. Numerically, $4.393168=-5.130642+9.523810$. Their payoffs differ by £10, their entry costs differ by its present value, and financing cancels that difference in profit. This equivalence assumes the same funding and frictionless European contracts. Actual collateral and execution costs can differ.

The graph's payoff line never rises above zero, but its financed-profit line can be positive because we include the invested entry credit.

```python:line-numbers
bull_put = [(1.,"put",100.),(-1.,"put",110.)]
bull_put_cost = value(bull_put)
bull_put_profit = payoff(bull_put)-bull_put_cost*growth
print(leg_table(bull_put).to_string(index=False))
print(f"Entry credit: {-bull_put_cost:.9f}; credit at expiry: {-bull_put_cost*growth:.9f} GBP")
print(f"Maximum bull-call/bull-put profit difference: {np.max(np.abs(bull_profit-bull_put_profit)):.2e} GBP")
chart("bullPut","A Credit Funds a Possible Future Payment",{
    "Payoff":payoff(bull_put),"Financed profit":bull_put_profit,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-bull-put" />

**Check:** can you calculate a meaningful unlevered percentage return by dividing profit by a negative entry value? No. Report GBP profit and a separately defined capital or collateral requirement. The credit is not a measure of capital at risk.

## 4. Bear Spreads: Reverse the Direction, Keep the Accounting

A **bear put spread** buys the £110 put and sells the £100 put. It is the opposite of the bull put basket. Its debit is £5.130642 and its financed cost is £5.387174.

Its payoff is £10 below £100, $110-S_T$ between the strikes, and zero above £110. Therefore:

$$\text{maximum gain}=10-5.387174=£4.612826,$$
$$\text{maximum loss}=£5.387174,\qquad \text{break-even}=110-5.387174=£104.612826.$$

A **bear call spread** sells the £100 call and buys the £110 call. It receives a £4.393168 credit and has the same financed profit as the bear put spread. The credit does not prevent a loss when spot finishes above both strikes.

| Direction | Debit construction | Credit construction |
| --- | --- | --- |
| Bullish | Buy lower call, sell higher call | Buy lower put, sell higher put |
| Bearish | Buy higher put, sell lower put | Buy higher call, sell lower call |

Both calls and puts can express either direction. Read the signed legs rather than assuming “call = bullish” or “put = bearish.” The graph falls across the strike interval because this purchased put spread benefits from lower terminal prices.

```python:line-numbers
bear_put = [(-n,kind,k) for n,kind,k in bull_put]
bear_call = [(-n,kind,k) for n,kind,k in bull_call]
bear_debit = value(bear_put)
bear_profit = payoff(bear_put)-bear_debit*growth
verticals = {"Bull call":bull_call,"Bull put":bull_put,"Bear put":bear_put,"Bear call":bear_call}
vertical_table = pd.DataFrame([
    [name,value(legs),float(payoff(legs,final=80)-value(legs)*growth),
     float(payoff(legs,final=105)-value(legs)*growth),float(payoff(legs,final=120)-value(legs)*growth)]
    for name,legs in verticals.items()],columns=["Spread","Signed entry GBP","Profit at 80","Profit at 105","Profit at 120"])
print(vertical_table.to_string(index=False,float_format=lambda x:f"{x:.6f}"))
chart("bearSpread","A Bear Put Spread Pays More When the Share Finishes Lower",{
    "Payoff":payoff(bear_put),"Financed profit":bear_profit,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-bear" />

**Experiment:** at £105, compare the bull call spread with the bear put spread. **Answer:** approximately **+£0.387174** and **−£0.387174**. Their combined payoff is a fixed £10; later we will price that basket as a box.

## 5. Covered Call: Own the Share, Sell Its Upside Above a Strike

A **covered call** owns one share and sells one call on that share. “Covered” means the stock quantity matches the delivery obligation. It does not mean the stock is protected against falling.

Buy the share for £100 and sell the £110 call for £5.993112. The net entry cost is **£94.006888**. Terminal wealth is:

$$W_T=S_T-\max(S_T-110,0)=\min(S_T,110).$$

At £80, the share is worth £80 and the call expires worthless. At £120, the share is worth £120 but the call obligation is £10, leaving £110. The financed entry cost is **£98.707232**. Consequently, maximum profit is $110-98.707232=£11.292768$; break-even is £98.707232; and a collapse to zero loses **£98.707232**.

If you already own the share, the option trade generates a premium receipt, but the full position still includes the share's current economic value. Excluding it from the risk calculation would hide the main downside exposure. A “premium yield” is not the strategy's total return.

The graph compares financed profit with owning the stock alone, whose profit is $S_T-100(1.05)$. Below the strike, the invested premium improves the covered call's result by £6.292768. Above the strike, its profit stops rising.

```python:line-numbers
covered = [(-1.,"call",110.)]
covered_cost = value(covered,stock=1.)
covered_wealth = payoff(covered,stock=1.)
stock_profit = terminal-S0*growth
print(leg_table(covered,stock=1.).to_string(index=False,na_rep="n/a"))
print(f"Cost: {covered_cost:.9f}; break-even: {covered_cost*growth:.9f}; maximum profit: {110-covered_cost*growth:.9f} GBP")
print(f"Loss if the share reaches zero: {covered_cost*growth:.9f} GBP")
chart("coveredCall","The Premium Cushion Does Not Put a Floor Under the Share",{
    "Covered call":covered_wealth-covered_cost*growth,"Stock only":stock_profit,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-covered" />

**Check:** does selling two 100-share calls against 100 shares remain fully covered? No. One extra call contract is uncovered. Above the strike, that excess short call creates additional upside loss exposure.

## 6. Protective Put: Pay for a Floor, Keep the Upside

A **protective put** owns one share and buys one put on it. Buy the £90 put for £2.336029 alongside the £100 share. Entry cost is **£102.336029** and terminal wealth is:

$$W_T=S_T+\max(90-S_T,0)=\max(S_T,90).$$

At £60, the share is worth £60 and the put pays £30: total £90. At £120, the put pays zero and you retain the £120 share. Unlike the covered call, the position has a floor and no upside cap.

The financed entry cost is **£107.452831**, so the worst financed profit is $90-107.452831=-£17.452831$. The break-even is £107.452831. Protection at £90 does not guarantee recovery of the original £100 share purchase, let alone the premium and funding cost.

The graph flattens below £90 and remains rising above it. Relative to stock alone, protection reduces profit in strong markets by the financed premium, **£2.452831**. That is the price of the floor under these assumptions.

```python:line-numbers
protective = [(1.,"put",90.)]
protective_cost = value(protective,stock=1.)
protective_wealth = payoff(protective,stock=1.)
print(f"Cost: {protective_cost:.9f}; terminal floor: 90; minimum profit: {90-protective_cost*growth:.9f} GBP")
print(f"Break-even: {protective_cost*growth:.9f} GBP/share")
chart("protectivePut","A Purchased Put Creates a Terminal Wealth Floor",{
    "Protective put":protective_wealth-protective_cost*growth,"Stock only":stock_profit,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-protective" />

**Experiment:** lower the put strike to £80 and reprice the put. **Answer:** the premium falls, but so does the terminal wealth floor, from £90 to £80. A cheaper hedge is buying less protection, not improving the same guarantee for free.

## 7. Collar: Exchange Some Upside for Downside Protection

A **collar** combines the preceding two overlays: own the share, buy the £90 put, and sell the £110 call. The put adds a floor; the call pays for some or all of that put by selling upside.

$$V_0=100+P(90)-C(110)=100+2.336029-5.993112=£96.342918.$$

The option overlay alone receives **£3.657082**. Its cost is negative, but the whole stock-plus-options position still costs £96.342918.

| Final share price | Share value | Long put payment | Short call payment | Total wealth |
| ---: | ---: | ---: | ---: | ---: |
| £60 | £60 | £30 | £0 | £90 |
| £100 | £100 | £0 | £0 | £100 |
| £140 | £140 | £0 | −£30 | £110 |

The general payoff is $W_T=\min(\max(S_T,90),110)$. Financed entry cost is **£101.160063**, giving minimum profit **−£11.160063**, maximum profit **£8.839937**, and break-even **£101.160063**. A terminal wealth floor and a nonnegative profit floor are different promises.

In the graph, the flat left section is purchased protection; the flat right section is sold upside. The middle retains one-for-one participation in the share price.

```python:line-numbers
collar = [(1.,"put",90.),(-1.,"call",110.)]
collar_cost = value(collar,stock=1.)
collar_wealth = payoff(collar,stock=1.)
collar_profit = collar_wealth-collar_cost*growth
print(leg_table(collar,stock=1.).to_string(index=False,na_rep="n/a"))
print(f"Overlay credit: {S0-collar_cost:.9f}; whole-position cost: {collar_cost:.9f} GBP")
print(f"Minimum profit: {90-collar_cost*growth:.9f}; maximum profit: {110-collar_cost*growth:.9f}; break-even: {collar_cost*growth:.9f}")
chart("collar","A Collar Trades an Upside Cap for a Downside Floor",{
    "Collar":collar_profit,"Stock only":stock_profit,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-collar" />

### What Does “Zero-Cost Collar” Mean?

It usually means the **option premiums approximately offset at entry**. It does not mean the stock is free or that no economic opportunity has been surrendered. With the £90 put fixed, solve $C(K_C)=P(90)$. Our synthetic model gives **$K_C\approx£124.775157$**. Moving the sold call farther away lowers its premium until it matches the put cost.

The resulting basket costs £100, has a £90 terminal floor, and caps wealth at about £124.775157. Its minimum financed profit is $90-100(1.05)=-£15$; break-even is £105. The graph compares it with the £90/£110 collar. Both have the same **wealth** floor, but different premiums and hence different **profit** floors.

```python:line-numbers
zero_collar_strike = brentq(lambda k:option_price(S0,k)-option_price(S0,90.,kind="put"),100.,160.)
zero_collar = [(1.,"put",90.),(-1.,"call",zero_collar_strike)]
zero_collar_cost = value(zero_collar,stock=1.)
zero_collar_wealth = payoff(zero_collar,stock=1.)
print(f"Zero-premium upper strike: {zero_collar_strike:.9f}; overlay value: {zero_collar_cost-S0:.2e} GBP")
print(f"Minimum financed profit: {90-zero_collar_cost*growth:.9f}; maximum: {zero_collar_strike-zero_collar_cost*growth:.9f} GBP")
chart("zeroCollar","Equal Premiums Still Exchange Protection for Upside",{
    "90/110 collar":collar_profit,"Zero-premium collar":zero_collar_wealth-zero_collar_cost*growth,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-zero-collar" />

**Check:** can the solved strike always be traded exactly? No. Available strikes, bid/ask prices, quantities, and fees determine the actual entry cash flow. A theoretical zero-premium root is a useful reference, not an executable quote.

## 8. Parity Shows What Is Inside the Basket

For a non-dividend-paying share and European options, $C(K)-P(K)=S_0-Ke^{-rT}$. Rearranging gives three useful descriptions:

| Position | Same terminal payments under our assumptions |
| --- | --- |
| Share minus call at £110 | Bond paying £110 minus put at £110 |
| Share plus put at £90 | Bond paying £90 plus call at £90 |
| Share plus £90 put minus £110 call | Bond paying £90 plus a £90/£110 bull call spread |

For the covered call, $S_T-(S_T-110)^+=110-(110-S_T)^+$. At £80, the bond pays £110 and the short put owes £30, leaving £80. At £120, the short put pays zero and the bond pays £110. This explains why a covered call still has downside risk.

For the collar, the present value of its floor is $90/1.05=£85.714286$. Its remaining value is the £90/£110 call spread, $16.621744-5.993112=£10.628632$. Together they cost **£96.342918**, exactly the stock-plus-options construction. This bond-plus-option viewpoint will be useful for structured products.

### A Box Is a Fixed Payment Made from Four Options

Buy the £100/£110 bull call spread and the £110/£100 bear put spread. Below both strikes, the put spread pays £10. Between the strikes, their payments add to $(S_T-100)+(110-S_T)=£10$. Above both, the call spread pays £10.

Thus the **long box** pays £10 in every terminal state and has ideal price:

$$B_0=10e^{-rT}=10/1.05=£9.523810.$$

The four option prices give the same answer, $4.393168+5.130642=£9.523810$. Funding that debit costs £10 at expiry, leaving **zero financed profit**. The graph is flat because the payment is fixed, not because an entry debit can be ignored. A short box reverses the four signs and resembles borrowing under the stated assumptions.

```python:line-numbers
box = bull_call+bear_put
box_cost = value(box)
box_payoff = payoff(box)
replication_table = pd.DataFrame([
    ["Covered call",covered_cost,110/growth-option_price(S0,110.,kind="put")],
    ["Protective put",protective_cost,90/growth+option_price(S0,90.)],
    ["Collar",collar_cost,90/growth+option_price(S0,90.)-option_price(S0,110.)],
    ["Long box",box_cost,10/growth],
],columns=["Position","Direct price GBP","Synthetic price GBP"])
replication_table["Difference GBP"] = replication_table["Direct price GBP"]-replication_table["Synthetic price GBP"]
print(replication_table.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
print(f"Box payment range: {box_payoff.min():.9f} to {box_payoff.max():.9f} GBP")
chart("boxPayments","A Fixed Box Payment Is Priced Like a Bond",{
    "Terminal payment":box_payoff,"Financed profit":box_payoff-box_cost*growth})
```
<Editor id="combinations-parity" />

**Experiment:** suppose the four executable legs cost £9.60 and still deliver £10 in one year. Their implied effective lending return is $10/9.60-1=4.1667\%$. Financing the purchase at 5% loses $10-9.60(1.05)=-£0.08$. A fixed payment alone does not establish a profitable financing trade. Early exercise, settlement timing, and collateral costs can invalidate the simple box cash account for other contracts.

## 9. Add the Greeks with the Same Signs and Quantities

The risk of a basket is the sum of the signed risks of its legs. A stock leg adds delta equal to its share quantity and zero option gamma, vega, and theta. For a common parallel volatility bump:

$$\Delta_{\text{basket}}=h+\sum_i n_i\Delta_i,\qquad
\Gamma_{\text{basket}}=\sum_i n_i\Gamma_i,\qquad
\nu_{\text{basket}}=\sum_i n_i\nu_i.$$

For the £100/£110 bull call spread, initial delta is $0.634558-0.447255=0.187304$ shares. A £1 spot rise contributes about **£0.187304** from initial delta for the one-share strategy, or **£18.730353** for matched 100-share contracts.

Initial gamma is $0.0188014-0.0197725=-0.0009711$ shares per £1 spot move. Initial vega is $0.376029-0.395450=-£0.019422$ per volatility point. This **bullish** spread initially has **negative gamma and negative parallel vega**. Direction, curvature, and volatility exposure are different questions. Their signs can change as spot moves.

The table uses shares for delta, shares per £1/share move for gamma, GBP per volatility point for vega, GBP per calendar day for theta, and GBP per basis point for classical rho. Multiply all by 100 for the matched 100-share construction. The cash account is separate: these are instrument-basket Greeks, not financed profit sensitivities.

The first graph compares deltas of four baskets against **current spot**, with one year still left. The second compares gamma. A protective put has positive curvature; a covered call has negative curvature. A collar or vertical spread combines positive and negative contributions, so a single strategy label cannot specify every risk sign.

```python:line-numbers
def option_risk(spot, strike, remaining=T, rate=r, vol=sigma, kind="call"):
    scale = vol*np.sqrt(remaining)
    d1 = (np.log(spot/strike)+(rate+vol**2/2)*remaining)/scale
    d2 = d1-scale
    discount, density = np.exp(-rate*remaining), norm.pdf(d1)
    delta = norm.cdf(d1) if kind == "call" else norm.cdf(d1)-1
    theta = -spot*density*vol/(2*np.sqrt(remaining))
    theta += -rate*strike*discount*norm.cdf(d2) if kind == "call" else rate*strike*discount*norm.cdf(-d2)
    rho = strike*remaining*discount*(norm.cdf(d2) if kind == "call" else -norm.cdf(-d2))
    return np.array([delta,density/(spot*scale),spot*density*np.sqrt(remaining)*.01,theta/365,rho*.0001])

def basket_risk(legs, stock=0., spot=S0, remaining=T, rate=r, vol=sigma):
    total = np.array([stock,0.,0.,0.,0.])
    for n,kind,k in legs:
        total += n*option_risk(spot,k,remaining,rate,vol,kind)
    return total

strategies = {name:(legs,0.) for name,legs in verticals.items()}
strategies.update({"Covered call":(covered,1.),"Protective put":(protective,1.),"Collar":(collar,1.),"Box":(box,0.)})
risk_table = pd.DataFrame({name:basket_risk(legs,stock) for name,(legs,stock) in strategies.items()},
                         index=["Delta shares","Gamma shares per GBP/share","Vega GBP/point","Theta GBP/day","Rho GBP/bp"]).T
print(risk_table.to_string(float_format=lambda x:f"{x:.9f}"))
risk_spots = np.linspace(40.,160.,121)
selected_risks = {name:np.array([basket_risk(*strategies[name],spot=s) for s in risk_spots])
                  for name in ("Bull call","Covered call","Protective put","Collar")}
risk_charts = chart("combinationDelta","Direction Depends on the Whole Basket",{name:rows[:,0] for name,rows in selected_risks.items()},
      x=risk_spots,xname="Current spot (GBP/share)",yname="Equivalent shares per one-share strategy",publish=False)
risk_charts.update(chart("combinationGamma","A Bullish Position Can Have Negative Gamma",{name:rows[:,1] for name,rows in selected_risks.items()},
      x=risk_spots,xname="Current spot (GBP/share)",yname="Change in delta shares per GBP/share move",publish=False))
print("<ECHARTS_DATA>"+json.dumps(risk_charts,allow_nan=False))
```
<Editor id="combinations-greeks" />

The box has zero spot delta, gamma, and parallel vega, but **positive calendar theta and negative rho**. Its fixed payment gets closer and its present value responds to discount rates. Here theta is approximately **£0.001273 per day** and rho **−£0.000952 per basis point**. Zero directional exposure does not mean zero sensitivity to every input.

The bull call and bull put spreads have the same delta, gamma, and parallel vega, but different theta and rho. Their instrument baskets differ by a bond. Their ideal financed profits agree only after including the corresponding entry cash accounts.

**Check:** does selling the £110 call hedge every volatility change of the £100 call? No. The table bumps both implied volatilities together. A move in just one strike's quote has its own signed vega exposure. The next chapter will introduce the volatility surface explicitly.

## 10. A Terminal Payoff Diagram Is Not an Early Exit Price

At expiry, a £100/£110 bull call spread pays £5 when the share is £105. With six months still left, its value must reflect outcomes on both sides of both strikes. Reprice the two options at the new spot, remaining life, and implied volatility; do not read an early exit price from the expiry line.

If you close after half a year, financed profit is $V_{0.5}-V_0e^{r(0.5)}$. The cash cost accrues for the **elapsed** half-year, while the option pricing uses the **remaining** half-year. Both happen to be 0.5 here, but they answer different questions.

The graph compares the spread's value at one year remaining, three months remaining, and expiry. As maturity approaches, smooth model prices approach the kinked payoff. The printed table holds spot at £105 after six months and compares 20% with 30% implied volatility. A rise in volatility need not help a bullish spread.

At 20%, the exit value is **£5.277790** and the elapsed funding cost is **£4.501657**, leaving **£0.776133 profit**. At 30%, the same spread is worth **£4.920827**, leaving **£0.419170 profit**. We have changed one pricing input while keeping the final-date payoff rules fixed.

```python:line-numbers
exit_spots = np.linspace(60.,140.,161)
exit_values = {f"{remaining:g} years left":np.array([value(bull_call,spot=s,remaining=remaining) for s in exit_spots])
               for remaining in (1.,.25,0.)}
exit_rows = []
elapsed = .5
for exit_vol in (.2,.3):
    exit_value = value(bull_call,spot=105.,remaining=T-elapsed,vol=exit_vol)
    exit_rows.append([105.,T-elapsed,exit_vol,exit_value,bull_debit*np.exp(r*elapsed),exit_value-bull_debit*np.exp(r*elapsed)])
exit_table = pd.DataFrame(exit_rows,columns=["Spot","Years left","Implied vol","Exit value GBP","Funded entry GBP","Profit GBP"])
print(exit_table.to_string(index=False,float_format=lambda x:f"{x:.9f}"))
chart("beforeExpiry","Reprice Both Legs Before Expiry",exit_values,x=exit_spots,
      xname="Current spot (GBP/share)",yname="Spread value before entry funding (GBP)")
```
<Editor id="combinations-exit" />

**Experiment:** set remaining life to zero and spot to £105. **Answer:** value becomes exactly £5, independent of the volatility input. With time left, the model must still price uncertainty. Smooth pre-expiry Greek formulas should not be evaluated at the payoff's strike kinks at expiry.

## 11. From Model Mid-Prices to an Executed Basket

Suppose each option's bid is £0.10 below its model mid and its ask is £0.10 above. Buy at the ask and sell at the bid. Entering a two-leg spread then costs **£0.20 more per one-share strategy**, regardless of whether its mid-price is a debit or a credit.

The bull call spread's actual debit becomes $4.393168+0.20=£4.593168$. Its financed cost becomes £4.822826, break-even rises to £104.822826, and maximum profit falls to £5.177174. The graph's profit line shifts down by **£0.21**, the maturity value of the £0.20 entry cost.

The same rule makes a long box cost $9.523810+4(0.10)=£9.923810$. Its fixed £10 payment then leaves **−£0.42 financed profit**, not zero. Buying a box uses asks on long legs and bids on short legs; selling it uses the opposite sides. Comparing an arbitrary mid-price with a funding rate is not an executable arbitrage test.

```python:line-numbers
half_spread = .10
def executed_cost(legs, stock=0., stock_half_spread=.02, fee_per_option=.0):
    return (value(legs,stock)+abs(stock)*stock_half_spread
            +sum(abs(n)*(half_spread+fee_per_option) for n,kind,k in legs))

filled_bull_cost = executed_cost(bull_call)
filled_box_cost = executed_cost(box)
execution_table = pd.DataFrame([
    [name,value(legs,stock),executed_cost(legs,stock)] for name,(legs,stock) in strategies.items()
],columns=["Strategy","Mid cost GBP","Entry fill cost GBP"])
execution_table["Entry drag at expiry GBP"] = (execution_table["Entry fill cost GBP"]-execution_table["Mid cost GBP"])*growth
print(execution_table.to_string(index=False,float_format=lambda x:f"{x:.6f}"))
print(f"Filled bull break-even: {100+filled_bull_cost*growth:.9f}; filled box profit: {10-filled_box_cost*growth:.9f} GBP")
chart("executionCost","Entry Execution Costs Shift the Whole Profit Curve",{
    "Mid-price profit":bull_profit,"Filled-entry profit":bull_payoff-filled_bull_cost*growth,"Zero":np.zeros_like(terminal)})
```
<Editor id="combinations-execution" />

This calculation includes entry costs and holds to cash-equivalent expiry. Closing early adds exit costs. Collateral is not automatically a loss, but it ties up cash and can require financing; the actual broker's treatment of a matched spread matters. If legs are filled separately, the position between fills can have exposures absent from the completed basket. Contract multipliers, expiry, settlement terms, and filled quantities must match before using the bounded-payoff calculation.

**Check:** why is the cost adjustment positive even for a short option? Its signed entry cost is negative. Selling below mid makes that number less negative, so entering the whole basket costs more or receives less.

## 12. Experiment: Change What You Sell, Then Inspect an Outcome

The independent widget repeats the bull call calculation with a fixed bought strike of £100. The **sold strike** control changes the contract basket and reprices its entry debit at spot £100, one year, 20% volatility, and 5% effective interest. The **final share price** control only selects an expiry outcome. It does not alter today's premiums.

Blue shows payoff; orange shows financed profit. A large blue outlined circle and smaller orange diamond identify the selected outcome. Moving the sold strike farther away generally costs more because you receive less premium, but raises the maximum payoff. The printed break-even and loss show the trade-off rather than declaring one strike best.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_option_spread_echart,
    upper_strike=widgets.FloatSlider(value=110.,min=105.,max=130.,step=5.,description="Sold strike (£)",continuous_update=False),
    final_spot=widgets.FloatSlider(value=120.,min=0.,max=160.,step=5.,description="Final share (£)",continuous_update=False),
)
widget_instance
```
<Editor id="combinations-strike-widget" />

**Try it:** compare sold strikes £110 and £120 at a final share price of £120. **Answer:** the £110 spread earns **£5.387174**; the £120 spread earns about **£12.472012**, but needs a larger entry debit, about **£7.169513**, and has a larger maximum loss. At a final price of £100, both lose their financed entry costs. A larger possible gain is not free improvement.

## 13. Worked Exercise: Cost and Explain a 100-Share Collar

You buy **100 shares**, buy one **100-share £95 put**, and sell one **100-share £115 call**, all with the same one-year expiry. Use the baseline model prices and the entry execution assumptions above: a £0.10 half-spread per option share and £0.02 per stock share. Ignore separate fees and collateral funding for this exercise.

1. What is the filled entry debit?
2. What are terminal wealth at share prices £80, £105, and £130?
3. What are the worst and best financed profits, and the break-even?
4. What initial stock delta remains? Has the collar made the book delta neutral?

**Work it through.** The £95 put costs £3.750817 at mid; the £115 call costs £4.428105. The per-share mid cost is $100+3.750817-4.428105=£99.322712$. Execution adds $0.02+0.10+0.10=£0.22$ per share. Multiply by 100 after adding the signed legs, then grow the whole debit by 1.05.

Terminal wealth is 100 times $\min(\max(S_T,95),115)$. It is **£9,500**, **£10,500**, and **£11,500** in the three scenarios. Subtract the same financed entry cost from each. For delta, add 100 stock shares, the put's signed delta, and the sold call's negative delta. A collar limits terminal outcomes; it does not normally cancel current directional exposure.

The code prints the completed answer and plots total GBP profit for the 100-share position. Compare its units with the earlier one-share charts.

```python:line-numbers
exercise_legs = [(1.,"put",95.),(-1.,"call",115.)]
exercise_multiplier = 100.
exercise_entry = exercise_multiplier*executed_cost(exercise_legs,stock=1.)
exercise_funded = exercise_entry*growth
exercise_prices = np.array([80.,105.,130.])
exercise_wealth = exercise_multiplier*payoff(exercise_legs,stock=1.,final=exercise_prices)
exercise_delta = exercise_multiplier*basket_risk(exercise_legs,stock=1.)[0]
exercise_break_even = exercise_funded/exercise_multiplier
print(f"Filled entry: {exercise_entry:.9f}; financed entry: {exercise_funded:.9f} GBP")
print(pd.DataFrame({"Final share GBP":exercise_prices,"Wealth GBP":exercise_wealth,
                    "Profit GBP":exercise_wealth-exercise_funded}).to_string(index=False))
print(f"Worst profit: {9500-exercise_funded:.9f}; best profit: {11500-exercise_funded:.9f} GBP")
print(f"Break-even: {exercise_break_even:.9f} GBP/share; delta: {exercise_delta:.9f} shares")
chart("collarExercise","A 100-Share Collar with Entry Bid/Ask Costs",{
    "Financed profit":exercise_multiplier*payoff(exercise_legs,stock=1.)-exercise_funded,"Zero":np.zeros_like(terminal)},
    yname="Financed profit for the complete 100-share position (GBP)")
```
<Editor id="combinations-exercise" />

**Completed answer:** filled entry is **£9,954.27** and its maturity cost is **£10,451.98**. The three profits are **−£951.98**, **£48.02**, and **£1,048.02**. The first and third are also the minimum and maximum possible financed profits. Break-even is **£104.519847 per share**. Initial delta is approximately **+36.453826 shares**, so this collar remains directionally exposed.

## Chapter Summary

- List the signed legs before using a strategy name. Match underlying, expiry, settlement, and quantity.
- A vertical spread trades a limited payoff range for a lower debit or an entry credit. Credit is not profit.
- A covered call retains stock downside and caps upside. A protective put buys a terminal floor. A collar combines that floor with an upside cap.
- Compare payoff, entry value, and financed profit on the correct dates. State whether a number is per share, per contract, or for the whole position.
- Put–call parity connects apparently different baskets. A European box is a fixed payment with a financing value, not an automatic profit.
- Add signed Greeks, and reprice every leg for an early exit. Bullish direction does not guarantee positive gamma or vega.
- Execution, collateral funding, and actual contract terms determine how the theoretical basket can be implemented.

Next: [Reading the Options Market: Implied Volatility and Surfaces](./implied-volatility-surfaces.md). Read prices back into volatility, compare strikes and expiries, and check what an inferred surface does and does not tell us.
