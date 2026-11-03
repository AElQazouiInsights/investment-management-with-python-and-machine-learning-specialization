---
title: "Design, Price, and Explain a Product"
permalink: /product-design-capstone
description: "Choose between two funded products using an explicit brief, executable budgets, maturity payments, fixed-holdings risks, stress scenarios, and a plain-language investor explanation."
---

# Design, Price, and Explain a Product

**Question:** two products cost £100 and promise to return £100 at maturity if the issuer performs. Which one fits a particular investor, and can you justify that choice without relying on its name or participation percentage?

This capstone applies [Building Structured Products](./structured-products.md), [The Greeks and Hedging](./greeks-hedging.md), and [Spreads and Basic Option Combinations](./option-combinations.md). Work through the brief before revealing the worked results. Run the six cells in order in a fresh browser session. The examples are synthetic, and the editable cap experiment needs no additional market data.

## 1. Write the Brief, Then Reconcile the Purchase

Our hypothetical investor can hold for **one year**, wants a **£100 contractual maturity floor**, and asks for **at least £108 if the share finishes at £110**. They accept capped upside and understand that an unsecured issuer promise can fail. This target describes a desired payment in one state; it is not a forecast that the share will reach £110.

Compare two products with the same **£100 investment**, share starting at **£100**, **5% effective annual safe rate**, **20% volatility**, no dividends, and European options. Each deducts a **£1 fee** and buys a default-free bond paying £100. Both buy the £100 call, but **A sells the £110 call**, while **B sells the £130 call**. Each call has a synthetic **£0.10 bid/ask half-spread**. Buy at ask and sell at bid; the bond has no dealing spread. Fractional share-equivalent units describe allocations per note, not exchange contract counts.

The bond costs £95.238095, leaving **£3.761905** for options. A spread unit costs its lower-call ask less its upper-call bid. Thus A buys $3.761905/4.593168=0.819022$ units; B buys $3.761905/8.964956=0.419623$ units. The cheaper, narrower spread buys more participation, but stops paying extra sooner.

| Date | Investor cash flow | Replicating portfolio |
| --- | --- | --- |
| Issue, $t=0$ | Pay £100 | Pay £1 fee; buy the maturity bond and signed option legs |
| Before maturity | None if held | Model value changes; no coupon is scheduled |
| Maturity, $t=1$ | Receive contractual formula if issuer performs | Bond pays £100; calls settle their intrinsic values |

The functions below reuse the previous pricing convention. `design` sets quantities **at issue**; `value` subsequently marks those fixed quantities. Rates affect the no-dividend forward and discount factor consistently. Fees and entry spreads are paid once, rather than deducted again from maturity payments.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

N, S0, rate, vol, fee, half_spread = 100., 100., .05, .20, 1., .10
bond_cost = N/(1+rate)

def call(spot,strike,remaining=1.,cash_rate=rate,sigma=vol):
    if remaining==0 or spot==0:
        return max(spot-strike,0.)
    discount = (1+cash_rate)**(-remaining)
    scale = sigma*np.sqrt(remaining)
    d1 = (np.log(spot/strike)+np.log1p(cash_rate)*remaining)/scale+scale/2
    return spot*norm.cdf(d1)-strike*discount*norm.cdf(d1-scale)

def design(cap,upfront_fee=fee):
    if not np.isfinite([cap,upfront_fee]).all() or cap<=S0 or upfront_fee<0:
        raise ValueError("Use a cap above 100 and a nonnegative fee")
    budget = N-upfront_fee-bond_cost
    if budget<0:
        raise ValueError("The floor and fee exhaust the budget")
    mid_spread = call(S0,S0)-call(S0,cap)
    entry = mid_spread+2*half_spread
    return {"cap":float(cap),"units":budget/entry,"fee":upfront_fee,"entry":entry}

def payment(spot,product):
    return N+product["units"]*np.minimum(np.maximum(np.asarray(spot)-S0,0.),product["cap"]-S0)

def value(spot,product,remaining=1.,cash_rate=rate,sigma=vol):
    return N*(1+cash_rate)**(-remaining)+product["units"]*(
        call(spot,S0,remaining,cash_rate,sigma)-call(spot,product["cap"],remaining,cash_rate,sigma))

def chart(key,title,x,series,xlabel,ylabel,ymin=0.):
    print("<ECHARTS_DATA>"+json.dumps({key:{"type":"line","title":title,
        "xAxis":{"type":"value","name":xlabel,"min":float(min(x)),"max":float(max(x))},
        "yAxisName":ylabel,"yAxis":{"type":"value","min":ymin},
        "series":{name:np.column_stack([x,y]).tolist() for name,y in series.items()}}},allow_nan=False))

products = {"A: cap 110":design(110.),"B: cap 130":design(130.)}
budget_rows = []
for name,p in products.items():
    purchase = p["units"]*(call(S0,S0)+half_spread)
    proceeds = p["units"]*(call(S0,p["cap"])-half_spread)
    mid = value(S0,p)
    slippage = 2*half_spread*p["units"]
    budget_rows.append([name,bond_cost,purchase,-proceeds,p["fee"],
                        bond_cost+purchase-proceeds+p["fee"],mid,slippage])
print(pd.DataFrame(budget_rows,columns=["Design","Bond","Long call ask","Short call proceeds",
    "Fee","Total paid","Model mid-value","Entry slippage"]).to_string(index=False))
```
<Editor id="product-design-setup" />

**Budget check:** A's model mid-value is **£98.836196**. Add its £1 fee and **£0.163804** entry slippage to recover £100. B's corresponding figures are **£98.916075**, £1, and **£0.083925**. Neither model mid-value is an executable exit quote or a valuation including issuer credit.

## 2. Choose Using the Payment Rule

Before running this cell, write each rule as **£100 plus option units times the share gain above £100, limited by the cap strike**. At £110, A pays **£108.190219**, while B pays **£104.196233**. Only A meets the brief. At £140, B pays **£112.588700**, above A's £108.190219 maximum. The ranking depends on the objective and the outcome.

The graph's horizontal axis is the final share price. Its vertical axis is the maturity payment per £100 invested. The **£105 safe-cash alternative** is the same for both products. Returning £100 means zero nominal profit but a £5 shortfall against cash. A meets its £108 target without promising an 8% unconditional return.

```python:line-numbers
final_spots = np.array([0.,60.,100.,110.,120.,140.])
payoff_rows = []
for name,p in products.items():
    for spot in final_spots:
        paid = payment(spot,p)
        payoff_rows.append([name,spot,paid,paid-N,paid-N*(1+rate)])
print(pd.DataFrame(payoff_rows,columns=["Design","Final share","Payment","Nominal profit","Against cash"]).to_string(index=False))
grid = np.linspace(0.,160.,321)
chart("designPayments","Choose Against the Brief, Not the Largest Headline Return",grid,
      {**{name:payment(grid,p) for name,p in products.items()},"Safe cash":np.full_like(grid,105.)},
      "Final share price (GBP/share)","Maturity payment per GBP 100",90.)
```
<Editor id="product-design-payments" />

**Check:** where does B overtake A? Above **£119.518025**: its option leg must earn £8.190219 to match A's maximum, so divide that amount by B's 0.419623 units and add the £100 strike. This crossover is a payment comparison, not a probability or a trading recommendation.

## 3. Report Risks in Investor Units

The contractual floor is not a current-price floor. Calculate sensitivities of the **investor's long replicating portfolio**, with its original units held fixed. Recall the definitions in [The Greeks and Hedging](./greeks-hedging.md): delta is shares per note, gamma is change in delta per £1 share move, and vega here is GBP per **one volatility percentage point**. Rate sensitivity is GBP per **one percentage-point change in the effective annual safe rate**, changing both bond and option inputs. The one-day carry entry is an exact revaluation after $1/365$ year with other inputs fixed.

At issue, A has delta about **0.153406 shares**, gamma **−0.000795**, and vega **−£0.015907 per point**. B has delta **0.196385**, gamma **+0.002650**, and vega **+£0.052993 per point**. A positive maturity floor does not make gamma or vega positive. The sold upper call changes the basket's risks.

```python:line-numbers
def risks(product):
    h, bump = .01, .0001
    base = value(S0,product)
    delta = (value(S0+h,product)-value(S0-h,product))/(2*h)
    gamma = (value(S0+h,product)-2*base+value(S0-h,product))/h**2
    vega = (value(S0,product,sigma=vol+bump)-value(S0,product,sigma=vol-bump))/(2*bump)*.01
    rho = (value(S0,product,cash_rate=rate+bump)-value(S0,product,cash_rate=rate-bump))/(2*bump)*.01
    day = value(S0,product,remaining=1-1/365)-base
    return {"Delta (shares)":delta,"Gamma (shares/GBP)":gamma,
            "Vega (GBP/vol point)":vega,"Rate (GBP/rate point)":rho,"One-day carry (GBP)":day}

risk_table = pd.DataFrame({name:risks(p) for name,p in products.items()}).T
print(risk_table.to_string(float_format=lambda x:f"{x:.9f}"))
```
<Editor id="product-design-risks" />

**Check:** an issuer owing the payment has the opposite liability sensitivities before hedging. Do not label an investor's positive delta as the issuer's net risk without including the liability and hedge positions.

## 4. Stress the Original Holdings, Then State the Exit Assumptions

At six months, reprice the original quantities under three joint scenarios. These are tests, with **no probabilities assigned**. Assume a hypothetical repurchase deduction of **£0.50 per note** from the default-free model mark, with no other exit costs. It is a stated scenario convention, not an observed quote or a credit adjustment.

| Scenario | Share | Effective safe rate | Volatility |
| --- | ---: | ---: | ---: |
| Down | £80 | 7% | 30% |
| Moderate rise | £110 | 5% | 20% |
| Strong rise | £140 | 3% | 15% |

In the down scenario, A's mark is **£97.559625** and its hypothetical proceeds are **£97.059625**. Against the original £100, that realizes **−£2.940375**. Against cash grown for only six months, **£102.469508**, it is **£5.409883 behind**. Deducting a full year's £105 here would mix dates.

The graph varies the current share price under the down scenario's rate and volatility. It shows hypothetical six-month exit proceeds, not maturity payments. The £100 line identifies where selling now loses nominal principal.

```python:line-numbers
scenarios = [("Down",80.,.07,.30),("Moderate rise",110.,.05,.20),("Strong rise",140.,.03,.15)]
exit_deduction = .50
cash_six_months = N*(1+rate)**.5
stress_rows = []
for name,p in products.items():
    for label,spot,r,v in scenarios:
        mark = value(spot,p,.5,r,v)
        proceeds = mark-exit_deduction
        stress_rows.append([name,label,mark,proceeds,proceeds-N,proceeds-cash_six_months])
print(pd.DataFrame(stress_rows,columns=["Design","Scenario","Model mark","Exit proceeds","Nominal P&L","Against cash"]).to_string(index=False))
current = np.linspace(40.,160.,121)
chart("designExit","An Early Sale Can Realize a Loss Below the Maturity Floor",current,
      {**{name:np.array([value(s,p,.5,.07,.30)-exit_deduction for s in current]) for name,p in products.items()},
       "Original investment":np.full_like(current,N)},
      "Share price after six months (GBP/share)","Exit proceeds per GBP 100",90.)
```
<Editor id="product-design-stress" />

**Issuer check:** under the preceding chapter's explicit **40%-of-contractual-payment recovery stress at maturity**, A pays only **£40** when the share finishes at £80. That is separate from the default-free early-sale calculation. Combining credit, rates, and equity scenarios requires additional assumptions; a floor on paper does not remove issuer exposure.

## 5. Explain What a Delta Hedge Does and Does Not Do

Take A's long replicating portfolio and short **0.153406 shares per note** to offset its initial delta. Invest the short-sale proceeds in cash. At issue the stock and cash legs cancel in value. This is a hypothetical hedge of the long asset, not extra protection automatically included in the investor's note.

For an instantaneous spot shock, no time elapses. The exact hedged change is the portfolio's new model value less its old value, minus delta times the share-price move. Its second-order estimate is **one-half gamma times the squared move**. A negative gamma means either direction can leave a local loss after the delta hedge. The graph compares these two changes; divergence on larger moves is the approximation remainder, not an execution profit. No fee is charged again in this model-to-model risk comparison.

```python:line-numbers
chosen = products["A: cap 110"]
chosen_risk = risks(chosen)
delta = chosen_risk["Delta (shares)"]
gamma = chosen_risk["Gamma (shares/GBP)"]
hedge_cash = delta*S0
print(f"Long model asset {value(S0,chosen):.9f}; stock {-delta*S0:.9f}; cash {hedge_cash:.9f}")
moves = np.linspace(-10.,10.,81)
exact_hedged = np.array([value(S0+move,chosen)-value(S0,chosen)-delta*move for move in moves])
second_order = .5*gamma*moves**2
for move in (-1.,1.,5.):
    exact = value(S0+move,chosen)-value(S0,chosen)-delta*move
    print(f"Spot move {move:+.0f}: exact hedged change {exact:.9f}; gamma estimate {.5*gamma*move**2:.9f}")
chart("designHedge","Delta Neutral Is Only a Local Statement",moves,
      {"Exact hedged change":exact_hedged,"Gamma estimate":second_order},
      "Instantaneous share move (GBP/share)","Model change per note (GBP)",float(min(exact_hedged.min(),second_order.min()))*1.15)
```
<Editor id="product-design-hedge" />

**Check:** this calculation does not simulate rebalancing, stock borrowing charges, or trading spreads. The costed hedge experiments in [The Greeks and Hedging](./greeks-hedging.md) cover those effects. A static local hedge does not lock the terminal return.

## 6. Experiment, Decide, and Write the Investor Explanation

Change `candidate_cap` below, predict whether the £108 payment target at £110 still holds, then run the cell. Every cap designs a **new issue**, using the same £100 floor, fee, and executable entry prices. The graph compares the payment in the target state with the maximum contractual payment. A larger possible maximum can come with a lower payment in the state the investor actually specified.

**Cost exercise:** the distributor raises the fee to £2. Can A still meet the brief? Its new units are **0.601307** and payment at £110 is **£106.013072**, so no. To deliver at least £108 using the £110 cap requires at least **0.8 spread units**. The maximum fee is the investment less the bond cost and the executable cost of those units. Compute it before changing the terms.

```python:line-numbers
candidate_cap = 110.  # Try 105, 115, 120, or 130; rerun this cell.
candidate = design(candidate_cap)
print(f"Candidate cap {candidate_cap:.2f}: participation {100*candidate['units']:.6f}%")
print(f"Payment at 110: {payment(110.,candidate):.9f}; meets target: {payment(110.,candidate)>=108.}")
cap_grid = np.arange(105.,140.1,1.)
target_payments = np.array([payment(110.,design(cap)) for cap in cap_grid])
maximum_payments = np.array([payment(cap,design(cap)) for cap in cap_grid])
maximum_fee = N-bond_cost-.8*chosen["entry"]
print(f"Maximum fee with cap 110 and target payment 108: {maximum_fee:.9f}")
print(f"GBP 2 fee: units {design(110.,2.)['units']:.9f}; payment at 110 {payment(110.,design(110.,2.)):.9f}")
chart("designChoice","The Target State and the Best Possible Outcome Are Different",cap_grid,
      {"Payment if share finishes at 110":target_payments,"Maximum payment":maximum_payments,
       "Required payment":np.full_like(cap_grid,108.)},
      "New-issue cap strike (GBP/share)","Maturity payment per GBP 100",100.)
```
<Editor id="product-design-experiment" />

### Your Submission

Provide a short investor brief, signed bond/option quantities, dated cash flows, the reconciled entry budget, a payment table and graph, a Greek table with units, one early-sale stress, and a plain-language explanation. Include the cash benchmark and state what issuer default changes. If you choose a different objective, explain why it changes your ranking. A pricing model alone does not establish expected physical performance.

### Worked Investor Explanation

> I choose A for the stated brief. You pay £100 today, including a £1 fee. The one-year payment returns £100 if the issuer performs and adds about 81.90% of any positive share return, but only up to a 10% share gain. The maximum payment is £108.19. At a final share price of £110 it meets your £108 target; B pays only £104.20 there, although B has greater distant upside. Below the starting share price, A returns £100, which is £5 less than the safe-cash alternative. Selling early can realize a loss, and issuer failure can reduce the contractual payment. Its £98.84 default-free model value at issue is not a repurchase promise. The chosen target is a preference, not a forecast or a guaranteed return.

**Worked cost answer:** the maximum fee is **£1.087371**. A £2 fee cannot fund the original target with these ingredients and quotes. Revise the fee, target, or contract explicitly; do not quietly reduce the floor or treat issuer borrowing spreads as safe income.

## Completing the Derivatives Track

You have connected contract terms, executable costs, model values, local sensitivities, and investor outcomes. Keep them separate in every product explanation. Revisit the [derivatives overview](./d.0-overview.md) for the full reading route. The next development topic is [Robust Estimation of Factor Models](./3.0-overview.md#_3-2-—-robust-estimation-of-factor-models), returning to the machine-learning sequence after this capstone.
