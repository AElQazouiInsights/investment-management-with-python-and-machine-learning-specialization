---
title: "Options and Replication"
permalink: /d.3-options
description: "Understand calls, puts, financed profit, two-state option pricing, and put–call parity with worked cash accounts and interactive payoff graphs."
---

# Options and Replication

**Question:** what should you pay today for the right to buy an investment next year, if you can walk away when buying would be unfavorable?

A forward is like a binding purchase agreement. An option is more like paying for a reservation: you pay for the choice, then decide whether to use it. The reservation payment is not refunded just because you decide not to buy.

In [Forward Contracts](./d.1-forwards.md), the buyer had an obligation. In [Futures and Forwards Compared](./d.2-futures.md), we followed daily settlement and collateral. Here we introduce a **premium**: the price paid to acquire an option. It is different from the collateral supporting a futures position.

Our invented investment costs **£100 per unit today**, pays no income, and has a nonnegative price. Each option covers **one unit**, expires in **one year**, and has a **£100 strike price**. The strike is the fixed price at which the holder can buy or sell. We use **European options**, exercisable only at expiry; “European” describes exercise timing, not geography. An American option permits earlier exercise and needs additional analysis.

We express exercise benefits as cash-equivalent payoffs. With physical settlement, a call holder pays the strike and receives the asset; its net exercise benefit is the asset's value minus the strike. A cash-settled contract instead pays the specified difference. For our cash-flow calculations, assume cash settlement, no fees or default, fractional asset holdings and short selling, and borrowing and lending at the same **5% effective annual rate**. These assumptions make the replication arithmetic transparent.

Run cells in order. The final-price widget also runs independently. All prices are teaching inputs, not market observations.

```python:line-numbers
import json
import numpy as np
import pandas as pd

spot_today = 100.0
strike = 100.0
annual_rate = 0.05
years = 1.0
growth = (1 + annual_rate) ** years
```
<Editor id="options-setup" />

## 1. A Call Buys a Choice; a Put Buys a Different Choice

A **call** gives its holder the right to **buy** at the strike. A **put** gives its holder the right to **sell** at the strike. The buyer is **long** the option. The seller, or **writer**, is **short** and must meet the contractual obligation when exercise occurs. The seller does not share the buyer's choice to walk away.

Let $S_T$ be the asset price at expiry, with $T$ denoting the expiry date, and let $K=£100$ be the strike. The call's maturity payoff is $C_T=\max(S_T-K,0)$; the put's is $P_T=\max(K-S_T,0)$. Here $\max(a,b)$ means choose the larger number. These are pound amounts for one unit, before subtracting the premium.

At a final price of £120, the call lets you buy something worth £120 for £100: $\max(120-100,0)=£20$. The put's right to sell for £100 has no exercise benefit when the asset is worth £120, so its payoff is zero. At £80, the call expires without exercise benefit, while the put pays $100-80=£20$.

| Final asset price | Long call payoff | Long put payoff | Short call payoff | Short put payoff |
| ---: | ---: | ---: | ---: | ---: |
| £80 | £0 | £20 | £0 | −£20 |
| £100 | £0 | £0 | £0 | £0 |
| £120 | £20 | £0 | −£20 | £0 |

An option is **in the money** when immediate exercise would have a positive benefit, **at the money** when spot equals strike, and **out of the money** when exercise would be unfavorable. At expiry, a £120 spot makes this call in the money and this put out of the money. At exactly £100 neither has a positive exercise benefit. Before expiry, a zero immediate exercise benefit does not imply a zero option price: future outcomes can still make the right valuable.

### Read the Kink Before Running the Code

The horizontal axis below is a **possible final asset price**, not elapsed time. The first graph shows the holder's cash payoff. The call is flat until £100, then gains £1 for every £1 rise. The put falls toward zero as the final price approaches £100, then stays at zero. The second graph reflects the same obligations from the writer's side. The point where the slope changes is a **kink**.

`np.maximum` applies the “choose the larger value” calculation at every price in the array. The code computes the table before generating the two graphs.

```python:line-numbers
final_prices = np.arange(0., 201., 1.)
call_payoff = np.maximum(final_prices - strike, 0.)
put_payoff = np.maximum(strike - final_prices, 0.)
check_prices = np.array([80., 100., 120.])
payoff_table = pd.DataFrame({
    "Final asset (GBP)": check_prices,
    "Long call (GBP)": np.maximum(check_prices - strike, 0.),
    "Long put (GBP)": np.maximum(strike - check_prices, 0.),
    "Short call (GBP)": -np.maximum(check_prices - strike, 0.),
    "Short put (GBP)": -np.maximum(strike - check_prices, 0.),
})
print(payoff_table.to_string(index=False))
payoff_charts = {}
for label, sign in [("Holder", 1), ("Writer", -1)]:
    payoff_charts["optionsPayoff" + label] = {
        "type": "line", "title": label + ": Cash at Expiry Before Premium Costs",
        "xAxis": {"type": "value", "name": "Final asset price (GBP/unit)"},
        "yAxisName": "Option payoff for one unit (GBP)",
        "series": {
            "Call": np.column_stack([final_prices, sign * call_payoff]).tolist(),
            "Put": np.column_stack([final_prices, sign * put_payoff]).tolist(),
        },
    }
print("\n<ECHARTS_DATA>" + json.dumps(payoff_charts, allow_nan=False))
```
<Editor id="options-payoffs" />

The writer's negative payoff is a payment to the holder. It is not yet the writer's profit, because the writer received a premium at entry.

**Experiment:** change only `strike` to `110.0` in the setup cell, rerun it and this cell, and predict the payments at £120. The call pays £10; the put pays zero. Then restore `strike = 100.0` and rerun both cells before continuing.

**Check:** at a final price of £90, which right has a positive exercise benefit? The put pays £10, the call zero; the short put pays £10. A negative number inside `maximum` is replaced by zero for the holder, not charged to the holder.

## 2. Payoff Is Not Profit

An option's **premium** is paid today. Its payoff arrives in one year. Compare them on one date, as we did for futures cash flows.

For this example, use a call premium $C_0=£11.904762$ and put premium $P_0=£7.142857$ per unit, rounded here for display. The subscript 0 means today. Sections 3–4 will derive these numbers rather than assume they are market prices. Keep full precision in Python.

At 5%, the call premium's maturity equivalent is $11.904762\times1.05=£12.50$. If the final asset price is £120, the **financed profit** is $20-12.50=£7.50$. If the final price is £110, exercise still pays £10, but financed profit is $10-12.50=-£2.50$. Exercising can be sensible even when the whole investment loses money: the premium has already been paid.

With effective annual rate $R$ and time $T$ in years, define the growth factor $G=(1+R)^T$. Here $G=1.05$. The maturity-date profits are:

$$\Pi_{\text{long call}}=\max(S_T-K,0)-C_0G,$$
$$\Pi_{\text{long put}}=\max(K-S_T,0)-P_0G.$$

For the put at £80, this is $20-7.142857\times1.05=20-7.50=£12.50$. Borrowing the premium produces these cash flows literally; using your own money produces the same opportunity-cost comparison. Ignoring financing gives the different quantity “payoff minus premium,” which would be £8.095238 for the call at £120.

The writer's financed profit is the negative of the holder's under the same ideal funding rate: premium grown to maturity minus the payoff owed. We exclude collateral costs from this option example; actual short-option margin and funding can change the result.

### Find the Break-Even Prices

**Break-even** means zero financed profit, not zero payoff. For the call, solve $S_T-100-12.50=0$, giving **£112.50**. For the put, solve $100-S_T-7.50=0$, giving **£92.50**. These prices are on opposite sides of the common £100 strike.

The following graphs shift the payoff lines by the financed premiums. At £100 both long options lose their respective premium costs. The zero line lets you distinguish a positive payment from a positive profit.

```python:line-numbers
call_premium = 250 / 21
put_premium = 50 / 7
call_cost_at_expiry = call_premium * growth
put_cost_at_expiry = put_premium * growth
call_profit = call_payoff - call_cost_at_expiry
put_profit = put_payoff - put_cost_at_expiry
print(f"Call premium today: {call_premium:.6f} GBP; financed cost: {call_cost_at_expiry:.2f} GBP")
print(f"Put premium today: {put_premium:.6f} GBP; financed cost: {put_cost_at_expiry:.2f} GBP")
print(f"Call break-even: {strike + call_cost_at_expiry:.2f} GBP/unit")
print(f"Put break-even: {strike - put_cost_at_expiry:.2f} GBP/unit")
profit_charts = {}
for label, sign in [("Holder", 1), ("Writer", -1)]:
    profit_charts["optionsProfit" + label] = {
        "type": "line", "title": label + ": Include the Premium and One Year of Funding",
        "xAxis": {"type": "value", "name": "Final asset price (GBP/unit)"},
        "yAxisName": "Financed profit at expiry for one unit (GBP)",
        "series": {
            "Call": np.column_stack([final_prices, sign * call_profit]).tolist(),
            "Put": np.column_stack([final_prices, sign * put_profit]).tolist(),
            "Zero profit": [[0., 0.], [200., 0.]],
        },
        "seriesOptions": {"Zero profit": {"lineStyle": {"type": "dashed"}}},
    }
print("\n<ECHARTS_DATA>" + json.dumps(profit_charts, allow_nan=False))
```
<Editor id="options-profit" />

For a nonnegative asset price, the long call's maximum financed loss is £12.50, while its upside has no finite bound. The long put's maximum financed loss is £7.50 and its maximum financed gain is £92.50, reached if the asset becomes worthless. The short call's maximum gain is £12.50 but its loss has no finite bound. The short put's maximum gain is £7.50 and its maximum loss is £92.50. The graph stops at £200 for readability; it does not cap the asset price or the short call's loss.

**Experiment:** in this cell, temporarily set `call_premium = 14.0`, keeping everything else fixed. The funded cost becomes £14.70 and break-even becomes £114.70. Payoff is unchanged. This is a transaction-cost what-if, not the model price we will derive. Restore `250 / 21` before continuing.

**Check:** if the call finishes at £105, should the holder forgo a £5 payoff because the funded premium was £12.50? No. Taking the £5 leaves a £7.50 loss; forgoing it leaves a £12.50 loss. The premium is a past payment at the exercise decision.

## 3. Reproduce a Call with the Asset and a Loan

We now ask what the right is worth **today**. For pricing only, impose a small model: next year the asset can be **£80 or £120, and no other price**. Both states are possible. These invented states are not a forecast or a claim that real prices take only two values.

The call pays £0 in the down state and £20 in the up state. Can an asset holding plus a cash account make exactly those two payments? Such a portfolio is a **replication**. If it can be traded under our assumptions, a different call price would allow buying the cheaper payment stream and selling the more expensive identical stream.

### Step 1: Match the Difference Between Outcomes

The asset's outcome difference is $120-80=£40$. The call's is $20-0=£20$. Hold **half a unit**: its value also changes by £20 across states.

Let $\Delta$ (delta) be the number of underlying units held per one-unit option. In this one-step model:

$$\Delta_C=\frac{C_u-C_d}{S_u-S_d}=\frac{20-0}{120-80}=0.5.$$

Subscripts $u$ and $d$ mean up and down states. Delta here is a two-state hedge ratio, not yet the continuously rebalanced sensitivity introduced later in the track.

### Step 2: Subtract the Unwanted £40

Half a unit is worth £40 in the down state and £60 in the up state. We need £0 and £20. Subtract £40 from both outcomes by borrowing an amount today that requires **£40 repayment at expiry**.

Let $B_0$ be today's signed cash-account balance: positive means money invested, negative means borrowing. Then:

$$B_0=\frac{C_d-\Delta_C S_d}{G}
=\frac{0-0.5\times80}{1.05}=-£38.095238.$$

The portfolio costs $0.5\times100-38.095238=£11.904762$ today. Its maturity cash is $0.5S_T-40$, which is exactly the call payoff **at £80 and £120**.

| Position | Value today | Down state: £80 | Up state: £120 |
| --- | ---: | ---: | ---: |
| Half a unit of the asset | £50.000000 | £40 | £60 |
| Borrowing account | −£38.095238 | −£40 | −£40 |
| Net replicating portfolio | **£11.904762** | **£0** | **£20** |

The initial asset purchase is a £50 cash outflow, partly funded by £38.095238 of borrowing proceeds. That leaves £11.904762 to supply. Negative cash-account value is a liability, not another asset. No rebalancing is required between the two dates in this one-step model.

The graph below uses two discrete state labels rather than a smooth curve. Compare the net portfolio and option bars within each state; the separate asset and cash bars explain how the match is built.

```python:line-numbers
state_prices = np.array([80., 120.])
call_states = np.maximum(state_prices - strike, 0.)
call_delta = (call_states[1] - call_states[0]) / (state_prices[1] - state_prices[0])
call_cash_today = (call_states[0] - call_delta * state_prices[0]) / growth
replicated_call_price = call_delta * spot_today + call_cash_today
call_replication = call_delta * state_prices + call_cash_today * growth
print(f"Asset units: {call_delta:.6f}; cash account today: {call_cash_today:.6f} GBP")
print(f"Replicated call price today: {replicated_call_price:.6f} GBP")
print(pd.DataFrame({"Asset (GBP)": call_delta * state_prices,
                    "Cash (GBP)": np.full(2, call_cash_today * growth),
                    "Net portfolio (GBP)": call_replication, "Call (GBP)": call_states},
                   index=["Down: 80", "Up: 120"]).to_string())
print("\n<ECHARTS_DATA>" + json.dumps({"optionsCallReplication": {
    "type": "bar", "title": "Half a Unit Minus a 40 GBP Repayment",
    "xAxis": {"type": "category", "name": "Model state", "data": ["Down: 80", "Up: 120"]},
    "yAxisName": "Maturity value for one call (GBP)",
    "series": {"Asset holding": (call_delta * state_prices).tolist(),
               "Cash account": [float(call_cash_today * growth)] * 2,
               "Net portfolio": call_replication.tolist(), "Call payoff": call_states.tolist()},
}}, allow_nan=False))
```
<Editor id="options-call-replication" />

**Experiment:** change the up outcome from £120 to £140 in `state_prices` and rerun this cell. The call pays £40 in that state, so delta becomes $40/(140-80)=2/3$. Borrowing is £50.793651 today, and the call price becomes £15.873016. Restore `[80., 120.]` and rerun before continuing. Altering a possible future state changes the pricing model; moving the eventual realized price along a payoff graph does not reprice the original purchase.

**Check:** suppose this call is offered at £13 while the replication still costs £11.904762. Sell the call and buy the replication. You receive £1.095238 net today, and the portfolio meets the call obligation in either state. Investing that initial surplus gives £1.15 at maturity. The argument assumes both trades, including the short option and borrowing, can be executed at the stated terms.

**Where the model stops:** at a final price of £100, the static portfolio pays $0.5(100)-40=£10$, but the call pays zero. That is not a third state of our pricing model. A static straight line through two outcomes does not reproduce a kink for every possible price. This limitation motivates richer models and dynamic hedging later.

## 4. Reproduce a Put with a Short Holding and Cash

The put pays £20 at £80 and zero at £120. Its state difference is $0-20=-£20$, so:

$$\Delta_P=\frac{0-20}{120-80}=-0.5.$$

A negative holding means **short selling** half a unit: borrow it, sell it today, and later buy it back to return it. This brings in £50 today. Its maturity liability is £40 in the down state or £60 in the up state.

Add a cash account that pays £60 in one year. It costs $60/1.05=£57.142857$ today. The £50 short-sale proceeds fund part of that deposit, leaving $57.142857-50=£7.142857$ to supply. At maturity, £60 minus £40 leaves £20 in the down state; £60 minus £60 leaves zero in the up state.

In the same notation, $B_0=(20-(-0.5)\times80)/1.05=£57.142857$, and $P_0=\Delta_P S_0+B_0=£7.142857$. The chart shows the negative asset liability and positive cash holding separately, followed by their net value and the put payoff.

```python:line-numbers
put_states = np.maximum(strike - state_prices, 0.)
put_delta = (put_states[1] - put_states[0]) / (state_prices[1] - state_prices[0])
put_cash_today = (put_states[0] - put_delta * state_prices[0]) / growth
replicated_put_price = put_delta * spot_today + put_cash_today
put_replication = put_delta * state_prices + put_cash_today * growth
print(f"Asset units: {put_delta:.6f}; cash account today: {put_cash_today:.6f} GBP")
print(f"Replicated put price today: {replicated_put_price:.6f} GBP")
print(pd.DataFrame({"Short asset (GBP)": put_delta * state_prices,
                    "Cash (GBP)": np.full(2, put_cash_today * growth),
                    "Net portfolio (GBP)": put_replication, "Put (GBP)": put_states},
                   index=["Down: 80", "Up: 120"]).to_string())
print("\n<ECHARTS_DATA>" + json.dumps({"optionsPutReplication": {
    "type": "bar", "title": "A 60 GBP Cash Receipt Covers the Short Asset",
    "xAxis": {"type": "category", "name": "Model state", "data": ["Down: 80", "Up: 120"]},
    "yAxisName": "Maturity value for one put (GBP)",
    "series": {"Short asset": (put_delta * state_prices).tolist(),
               "Cash account": [float(put_cash_today * growth)] * 2,
               "Net portfolio": put_replication.tolist(), "Put payoff": put_states.tolist()},
}}, allow_nan=False))
```
<Editor id="options-put-replication" />

**Experiment:** for two identical puts, double each holding: short one unit and invest £114.285714. Initial net cost is £14.285714, and the final net payments are £40 or £0. Doubling quantity doubles cost and payoff; it does not change the per-unit strike. Real option contracts may cover many units, so check the multiplier before applying these amounts.

**Check:** why is the cash deposit £57.142857 rather than the put premium £7.142857? Because the short asset supplies £50 of the deposit. The premium is the **net** portfolio cost, not the value of its cash component.

## 5. Pricing Weights Are Not a Forecast

We have priced both rights without choosing the actual chance of an up move. Replication depends on traded prices and matching payoffs. A different expression packages the same calculation as a discounted weighted average.

Choose a weight $q$ for the up state so that the weighted asset value grows at the funding rate:

$$q(120)+(1-q)(80)=100(1.05)=105.$$

Subtract 80 from both sides: $40q=25$, giving $q=0.625$. The down-state weight is $1-q=0.375$. These are **risk-neutral pricing weights**: they are chosen for a pricing identity, not measured probabilities of what will happen. They do not assert that investors are indifferent to risk.

The call price is $(0.625\times20+0.375\times0)/1.05=£11.904762$. The put price is $(0.625\times0+0.375\times20)/1.05=£7.142857$. Both equal the replication costs. More generally, for up/down option payoffs $V_u,V_d$:

$$q=\frac{S_0G-S_d}{S_u-S_d},\qquad V_0=\frac{qV_u+(1-q)V_d}{G}.$$

We require $S_d<S_0G<S_u$, here $80<105<120$, so both weights are strictly between zero and one. If the bank account outperformed the asset in every possible state, or vice versa, borrowing or short selling would already create an arbitrage in this frictionless model. An invalid weight is a signal to examine the inputs, not a probability to clip into range.

For comparison, suppose your **real-world** up probability is $p=0.5$. The call's expected payoff is £10 and expected financed profit is $10-12.50=-£2.50$. If instead $p=0.8$, these become £16 and £3.50. The replicated price stays £11.904762 when traded prices and states are unchanged. Expected profit is a forecast-dependent quantity; its sign is not an arbitrage because either state can still occur.

The graph varies the assumed real-world probability on its horizontal axis. It shows expected **financed profit**, not option price. It crosses zero at 62.5%, which is the pricing weight for this particular model.

```python:line-numbers
pricing_weight = (spot_today * growth - state_prices[0]) / (state_prices[1] - state_prices[0])
weighted_call_price = (pricing_weight * call_states[1] + (1 - pricing_weight) * call_states[0]) / growth
weighted_put_price = (pricing_weight * put_states[1] + (1 - pricing_weight) * put_states[0]) / growth
real_up_probabilities = np.linspace(0., 1., 101)
expected_call_profit = (real_up_probabilities * call_states[1]
                        + (1 - real_up_probabilities) * call_states[0] - call_cost_at_expiry)
print(f"Pricing up weight: {pricing_weight:.3f}; down weight: {1 - pricing_weight:.3f}")
print(f"Discounted weighted call: {weighted_call_price:.6f} GBP; put: {weighted_put_price:.6f} GBP")
for probability in [0.5, 0.625, 0.8]:
    expected_payoff = probability * call_states[1] + (1 - probability) * call_states[0]
    print(f"Real up probability {probability:.1%}: expected payoff {expected_payoff:.2f} GBP; "
          f"expected financed profit {expected_payoff - call_cost_at_expiry:.2f} GBP")
print("\n<ECHARTS_DATA>" + json.dumps({"optionsForecastProfit": {
    "type": "line", "title": "Your Probability Changes Expected Profit, Not This Replication Cost",
    "xAxis": {"type": "value", "name": "Assumed up probability (%)"},
    "yAxisName": "Expected financed call profit at expiry (GBP)",
    "series": {"Expected profit": np.column_stack([100 * real_up_probabilities, expected_call_profit]).tolist(),
               "Zero profit": [[0., 0.], [100., 0.]]},
    "seriesOptions": {"Zero profit": {"lineStyle": {"type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="options-pricing-weights" />

**Experiment:** replace the printed probability `0.8` with `0.7`. Expected call payoff becomes £14 and expected financed profit £1.50. The pricing weight and option price remain unchanged.

**Check:** at a real-world up probability of 62.5%, does zero expected financed profit mean no risk? No. The actual financed profit is still −£12.50 or +£7.50, depending on the state. Only their weighted average is zero.

## 6. Put–Call Parity: Two Ways to Buy the Same Final Value

Consider two packages with the **same strike, expiry, underlying, and one-unit quantity**:

- **Package A:** one call plus cash invested today to pay £100 at expiry.
- **Package B:** one put plus one unit of the asset.

At £80, A pays $0+100=£100$, while B pays $20+80=£100$. At £120, A pays $20+100=£120$, while B pays $0+120=£120$. At £100, both pay £100. In fact, both pay $\max(S_T,100)$ at **every nonnegative final price**, not just at our two model states.

Equal future payments require equal current prices under the stated trading assumptions. This is **put–call parity** for European options on a non-income-paying asset:

$$C_0+\frac{K}{G}=P_0+S_0.$$

Our numbers give $11.904762+95.238095=7.142857+100=£107.142857$. Rearranging gives $C_0-P_0=S_0-K/G=£4.761905$.

The first graph overlays the two packages; the dashed line lies on the solid line because they are equal. The second compares **long call plus short put** with a forward's signed maturity payment. The identity $\max(S_T-K,0)-\max(K-S_T,0)=S_T-K$ holds for every final price. At £80 it is −£20; at £120 it is +£20.

```python:line-numbers
strike_present_value = strike / growth
package_a = call_payoff + strike
package_b = put_payoff + final_prices
synthetic_forward = call_payoff - put_payoff
print(f"Call plus discounted strike: {call_premium + strike_present_value:.6f} GBP")
print(f"Put plus asset: {put_premium + spot_today:.6f} GBP")
print(f"Call minus put today: {call_premium - put_premium:.6f} GBP")
print(f"Asset minus discounted strike: {spot_today - strike_present_value:.6f} GBP")
print("\n<ECHARTS_DATA>" + json.dumps({
    "optionsParityPackages": {
        "type": "line", "title": "Call Plus Cash and Put Plus Asset Pay the Same Amount",
        "xAxis": {"type": "value", "name": "Final asset price (GBP/unit)"},
        "yAxisName": "Package value at expiry (GBP)",
        "series": {"Call + cash": np.column_stack([final_prices, package_a]).tolist(),
                   "Put + asset": np.column_stack([final_prices, package_b]).tolist()},
        "seriesOptions": {"Put + asset": {"lineStyle": {"type": "dashed"}}},
    },
    "optionsSyntheticForward": {
        "type": "line", "title": "Buying a Call and Selling a Put Restores the Obligation",
        "xAxis": {"type": "value", "name": "Final asset price (GBP/unit)"},
        "yAxisName": "Maturity payoff before entry cost (GBP)",
        "series": {"Call - put": np.column_stack([final_prices, synthetic_forward]).tolist(),
                   "Forward at K = 100": np.column_stack([final_prices, final_prices - strike]).tolist()},
        "seriesOptions": {"Forward at K = 100": {"lineStyle": {"type": "dashed"}}},
    },
}, allow_nan=False))
```
<Editor id="options-parity" />

The synthetic £100-delivery-price forward costs **£4.761905 today**. It is not the zero-cost new forward from [Forward Contracts](./d.1-forwards.md): today's fair one-year forward delivery price is £105. Financing the synthetic position's initial cost gives £5 at maturity, so its financed profit is $S_T-100-5=S_T-105$, matching the payoff of that fair new forward. For example, at £120 both give £15 after this funding adjustment.

**Experiment:** if a market call quote were £13 and the put quote stayed £7.142857, Package A would cost £108.238095 and B £107.142857. Sell A and buy B; the initial surplus is £1.095238, and expiry payments cancel for every final price. This parity comparison does not require the two-state assumption, but it still requires the same contract terms and executable trades.

**Check:** with the call at £11.904762, spot £100, and discounted strike £95.238095, recover the put price: $P_0=C_0+K/G-S_0=£7.142857$. Parity prices one option from the other; it does not determine both prices without further information.

## 7. Check Price Bounds Before Trusting a Quote

Even without specifying two states, some prices cannot be consistent with these European contracts and our assumptions. A call cannot cost more than the asset: owning the asset supplies at least the call's final payoff when prices are nonnegative. A put cannot cost more than cash that will pay the strike, since its payoff never exceeds the strike.

Parity and nonnegative option prices also give lower bounds:

$$\max(0,S_0-K/G)\le C_0\le S_0,$$
$$\max(0,K/G-S_0)\le P_0\le K/G.$$

For this example, the call must lie between **£4.761905 and £100**, and the put between **£0 and £95.238095**. Our derived prices lie within these intervals. The bounds are broad checks, not a substitute for a pricing model. The call's lower bound is not always its immediate exercise benefit: these European rights cannot be exercised early.

```python:line-numbers
bound_table = pd.DataFrame({
    "Lower bound (GBP)": [max(0., spot_today - strike_present_value), max(0., strike_present_value - spot_today)],
    "Model price (GBP)": [replicated_call_price, replicated_put_price],
    "Upper bound (GBP)": [spot_today, strike_present_value],
}, index=["Call", "Put"])
print(bound_table.to_string(float_format=lambda value: f"{value:.6f}"))
print("Both model prices satisfy the bounds:", bool(
    ((bound_table.iloc[:, 0] <= bound_table.iloc[:, 1])
     & (bound_table.iloc[:, 1] <= bound_table.iloc[:, 2])).all()))
```
<Editor id="options-bounds" />

**Experiment:** test a £3 call quote. It is below the £4.761905 lower bound. Sell one asset, buy the call for £3, and invest £95.238095 to have £100 at expiry. You retain £1.761905 today. At expiry, the call plus cash is worth at least the asset you owe, in every state. The lower bound detects the inconsistency without choosing an up probability.

**Check:** a £12 call satisfies the bounds. Does that prove it is the fair price? No. It passes a necessary check, but the specified two-state model gives £11.904762, and real-market valuation requires a suitable model and trading inputs.

## 8. Experiment: Move the Final Price, Keep the Purchased Options Fixed

Keep the £100 strike, one-year horizon, 5% rate, and original premiums fixed. Move only the **final** asset price. This is a payoff/profit scenario experiment, not a change to today's spot price or a new pricing model.

Each graph shows a blue payoff line and a purple financed-profit line for one long option. Large outlined markers show the selected amounts: an orange diamond for payoff and a magenta square for profit. Their vertical separation is the financed premium: £12.50 for the call and £7.50 for the put. The slider includes £92.50 and £112.50 so you can inspect both break-even points exactly.

The helper repeats the visible payoff and funding formulas. Prices between and beyond £80 and £120 illustrate the contracts' payments; they are not additional states in the model used to derive the original premiums.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_option_payoff_echart,
    final_spot=widgets.FloatSlider(value=120., min=0., max=200., step=2.5,
                                   description="Final GBP", continuous_update=False),
)
widget_instance
```
<Editor id="options-payoff-widget" />

**Try it:** predict each row, then move the slider.

| Final price | Call payoff | Call financed profit | Put payoff | Put financed profit |
| ---: | ---: | ---: | ---: | ---: |
| £80 | £0 | −£12.50 | £20 | £12.50 |
| £92.50 | £0 | −£12.50 | £7.50 | £0 |
| £100 | £0 | −£12.50 | £0 | −£7.50 |
| £110 | £10 | −£2.50 | £0 | −£7.50 |
| £112.50 | £12.50 | £0 | £0 | −£7.50 |
| £120 | £20 | £7.50 | £0 | −£7.50 |

**Check:** why are both long-option profits negative at £100? Neither right produces an exercise benefit, but both premiums have been paid and financed. “No exercise” does not mean “no loss.”

## 9. Worked Exercise: Change the Strike to £110

Return to the original two-state pricing model: £100 today, £80 or £120 in one year, and 5% effective annual financing. Change the common option strike to **£110**.

1. Find the call and put payoffs in each state.
2. Find each option's asset holding, signed cash account today, and premium.
3. Verify put–call parity. Does its payoff identity still hold at a hypothetical final price of £100?
4. Calculate both financed break-even prices. Is the call's positive £10 up-state payoff entirely profit?

::: details Hint
For each right, divide the up-minus-down payoff difference by £40. Then use the down-state payoff to solve for the cash account. Discount that cash amount before calculating today's portfolio cost. Retain full precision until displaying results.
:::

::: details Worked answer
The call pays £0 or £10. Hold 0.25 units and borrow £19.047619, which requires £20 repayment. Its price is $25-19.047619=£5.952381$.

The put pays £30 or £0. Short 0.75 units and invest £85.714286 to receive £90. Its price is $-75+85.714286=£10.714286$.

Both parity packages cost £110.714286 today. Call minus put costs −£4.761905, equal to $100-110/1.05$. At a hypothetical £100 final price, the call pays zero and the put £10, so their difference is −£10, equal to the forward payment $100-110$. This all-price identity still holds; the individual static replications are guaranteed only in the two model states.

The financed premiums are £6.25 and £11.25. Call break-even is £116.25, put break-even £98.75. The call's up-state payoff of £10 leaves **£3.75 financed profit**.
:::

```python:line-numbers
exercise_strike = 110.0
exercise_states = np.array([80., 120.])
exercise_growth = 1.05
exercise_rows = []
for name, payments in [("Call", np.maximum(exercise_states - exercise_strike, 0.)),
                       ("Put", np.maximum(exercise_strike - exercise_states, 0.))]:
    units = (payments[1] - payments[0]) / (exercise_states[1] - exercise_states[0])
    cash_today = (payments[0] - units * exercise_states[0]) / exercise_growth
    premium = units * 100 + cash_today
    funded_premium = premium * exercise_growth
    break_even = exercise_strike + funded_premium if name == "Call" else exercise_strike - funded_premium
    exercise_rows.append([name, *payments, units, cash_today, premium, break_even])
exercise_results = pd.DataFrame(exercise_rows, columns=[
    "Option", "Down payoff (GBP)", "Up payoff (GBP)", "Asset units", "Cash today (GBP)",
    "Premium (GBP)", "Break-even (GBP/unit)",
]).set_index("Option")
print(exercise_results.to_string(float_format=lambda value: f"{value:.6f}"))
exercise_call = exercise_results.loc["Call", "Premium (GBP)"]
exercise_put = exercise_results.loc["Put", "Premium (GBP)"]
print(f"Parity difference: {exercise_call - exercise_put:.6f} GBP")
print(f"Asset minus discounted strike: {100 - exercise_strike / exercise_growth:.6f} GBP")
print(f"Call financed profit in up state: {10 - exercise_call * exercise_growth:.2f} GBP")
```
<Editor id="options-exercise" />

## Chapter Summary

- The holder buys a right; the writer accepts the corresponding obligation. Strike, premium, payoff, and financed profit are different quantities.
- Exercise decisions compare the asset with the strike. Profit also includes the premium and its funding or opportunity cost.
- A two-state option can be replicated by an asset holding and a signed cash account. The portfolio's net cost gives its model price.
- Pricing weights reproduce that cost. Real-world probabilities answer a different question: what outcomes and profits you expect.
- European put–call parity is an all-price payoff identity under matched terms. A static two-state replication has a narrower scope.
- Option price bounds detect some inconsistent quotes, but do not determine a unique price.

Continue with [Random Motion and Itô's Lemma](./random-motion-ito.md). Introduce changes, slopes, and curvature with small numerical examples, then build the tools needed to move beyond a two-state model.
