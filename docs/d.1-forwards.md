---
title: "Forward Contracts: Agreeing Today on a Future Price"
permalink: /d.1-forwards
description: "Define a forward, calculate long and short payoffs, derive its delivery price through financing, value an existing contract, and hedge a future purchase."
---

# Forward Contracts: Agreeing Today on a Future Price

**Question:** an investment costs £100 today, but you need to buy it in one year. Can you agree on the purchase price now?

Think of ordering something for delivery next year and fixing its price today. A **forward contract** is a binding agreement: one party must buy a specified quantity of an underlying asset at an agreed price on a future date, and the other must sell it. It is usually negotiated directly between the parties, often with a dealer, rather than traded as a standardized exchange contract.

Fixing the price removes one uncertainty. It also means you must honor the agreement if the market later offers a better price. A forward is an **obligation**, not the option to walk away.

We will use an invented, tradable investment that pays no income. All money amounts are in pounds sterling, labeled **GBP** in Python and charts. Run the cells in order; the spot-price widget also works independently. The [derivatives overview](./d.0-overview.md) explains the full sequence from forwards to structured products.

```python:line-numbers
import json
import numpy as np
import pandas as pd
```
<Editor id="forward-setup" />

## 1. Read the Agreement Before Calculating

Suppose you agree to buy **10 units for £105 each in one year**. The important terms are:

| Term | Meaning in this example |
| --- | --- |
| Underlying | The investment to be delivered |
| Spot price, $S_t$ | The price of one unit for immediate purchase at time $t$ |
| Delivery price, $K$ | The agreed £105 per unit, fixed for this contract |
| Quantity, $q$ | 10 units |
| Maturity, $T$ | The delivery date, one year from today |
| Long position | Your obligation to buy the 10 units for £1,050 |
| Short position | The other party's obligation to sell those units for £1,050 |

Time zero means today. The subscript $T$ in $S_T$ means the spot price **at maturity**, which we do not know today. A short forward means agreeing to sell later; it does not itself require borrowing and selling the asset today.

### What Happens at Delivery?

If the asset costs £120 at maturity, you pay £105 for each unit. You receive something worth £120, so the agreement gives you a £15 advantage per unit relative to buying at the market price:

$$120-105=15.$$

For ten units, the long's maturity payoff is $10\times15=£150$. If the asset instead costs £80, the agreement is unfavorable: $10(80-105)=-£250$.

In a **physically settled** forward, the long pays £1,050 and receives ten units. The £150 above is the net value of that exchange, not an additional cash payment. In an otherwise equivalent **cash-settled** forward, the parties exchange only the signed difference using the specified settlement price. At £120, the long receives £150; at £80, the long pays £250.

The formulas summarize both sides of that net payment:

$$\text{Long payoff}=q(S_T-K),\qquad
\text{Short payoff}=q(K-S_T).$$

The payoffs sum to zero: one party's contractual gain is the other's loss, before costs or default. The graph below places the **possible maturity spot price** on the horizontal axis, not time. Its vertical axis is the payoff for the **whole ten-unit contract**.

```python:line-numbers
quantity = 10
delivery_price = 105.0
terminal_spots = np.array([80., 100., 105., 120., 140.])
long_payoffs = quantity * (terminal_spots - delivery_price)
short_payoffs = -long_payoffs
payoff_table = pd.DataFrame({
    "Maturity spot (GBP/unit)": terminal_spots,
    "Long payoff (GBP)": long_payoffs,
    "Short payoff (GBP)": short_payoffs,
})
print(payoff_table.to_string(index=False, float_format=lambda value: f"{value:.2f}"))
payoff_grid = np.linspace(60, 150, 91)
print("\n<ECHARTS_DATA>" + json.dumps({
    "forwardPayoffs": {
        "type": "line", "title": "An Obligation to Buy and an Obligation to Sell",
        "xAxis": {"type": "value", "name": "Maturity spot (GBP/unit)", "scale": True},
        "yAxisName": "Ten-unit contract payoff (GBP)",
        "series": {
            "Long": np.column_stack([payoff_grid, quantity * (payoff_grid - delivery_price)]).tolist(),
            "Short": np.column_stack([payoff_grid, quantity * (delivery_price - payoff_grid)]).tolist(),
        },
    },
}, allow_nan=False))
```
<Editor id="forward-payoffs" />

Both lines cross zero at £105. A £1 increase in the maturity spot price adds £10 to the long's payoff and subtracts £10 from the short's. A negative payoff is a payment obligation; it is not cut off at zero as an option payoff would be.

**Check:** if the maturity spot price is £100, does the long break even because that was today's spot price? No. The agreement uses the delivery price of £105: the long loses £5 per unit, or £50 in total.

## 2. Where Does the £105 Delivery Price Come From?

The delivery price should make entering a new forward worth **zero today**, under our pricing assumptions. The parties agree to exchange value later; the long does not pay the £105 delivery price today. Zero initial value does not mean zero future obligation.

For the calculation, assume the asset can be bought, held, and short-sold; it pays no dividends or other income and has no storage costs. Borrowing and lending use the same known rate. Ignore fees, taxes, collateral cash flows, and default. These assumptions let us isolate the financing calculation. Real forward agreements may require collateral, and real financing and short-sale costs can differ.

### Buy Now and Finance the Purchase

The asset costs £100. The effective annual interest rate is 5%, meaning £100 borrowed today requires £105 repayment in one year:

$$100(1+0.05)=105.$$

You could therefore:

1. Borrow £100 today.
2. Buy one unit today and hold it.
3. Repay £105 in one year.

This secures one unit for a future cash outflow of £105. A zero-initial-value forward should offer the same future purchase price. Otherwise, we can combine the cheaper purchase route with the more expensive sale route, as the next section shows.

Let $F_{0,T}$ denote the **fair delivery price for a new forward** agreed at time zero for maturity $T$. With an effective annual rate $R$:

$$\boxed{F_{0,T}=S_0(1+R)^T.}$$

$S_0$ and $F_{0,T}$ are pounds per unit, $R$ is a decimal annual rate, and $T$ is in years. In Python, `0.05` means 5%. For two years, the same flat annual rate gives $100(1.05)^2=£110.25$. Fractional years use the same constant-rate compounding assumption: six months gives $100(1.05)^{0.5}\approx£102.47$.

The next graph varies **time to delivery** while holding today's spot price and the rate fixed. These are quotes for different maturities today, not predictions of the asset's future market prices.

```python:line-numbers
initial_spot = 100.0
annual_rate = 0.05
years_to_delivery = 1.0
fair_delivery = initial_spot * (1 + annual_rate) ** years_to_delivery
financing_table = pd.DataFrame({
    "Cash flow per unit (GBP)": [100., -100., -fair_delivery],
    "When": ["Today", "Today", "In one year"],
    "Action": ["Borrow", "Buy asset", "Repay loan; retain asset"],
})
print(financing_table.to_string(index=False))
print(f"Fair one-year delivery price: {fair_delivery:.2f} GBP/unit")
print(f"Two-year delivery price at the same rate: {initial_spot * (1 + annual_rate) ** 2:.2f} GBP/unit")
maturities = np.linspace(0, 3, 61)
new_forward_quotes = initial_spot * (1 + annual_rate) ** maturities
print("\n<ECHARTS_DATA>" + json.dumps({
    "forwardMaturities": {
        "type": "line", "title": "Financing a Longer Wait at a Positive Rate",
        "xAxis": {"type": "value", "name": "Years to delivery"},
        "yAxisName": "New forward delivery price (GBP/unit)",
        "series": {"Financed purchase": np.column_stack([maturities, new_forward_quotes]).tolist()},
    },
}, allow_nan=False))
```
<Editor id="forward-financing" />

The curve starts at £100 for immediate delivery and reaches £105 after one year. It rises here because the financing rate is positive and the asset pays no income. Income or other holding costs change the comparison; this formula is not a universal commodity-pricing rule.

## 3. Check Both Directions of the Pricing Argument

**Arbitrage** means a combination of trades with no net initial investment and a guaranteed positive gain in this example's idealized market. We must identify the trades and their dates, not just claim that a quote looks too high or too low.

Both new forward quotes below assume **no upfront payment**. A different delivery price can instead be paired with a compensating payment today; the delivery quote alone would then be insufficient to identify an arbitrage.

### If a New Forward Is Quoted at £110

- Today, borrow £100 and buy one unit. The two cash flows cancel.
- Agree to **sell** that unit in one year for £110: take a short forward.
- At maturity, deliver the unit, receive £110, and repay £105.
- The remaining cash is $110-105=£5$, regardless of the maturity spot price.

### If a New Forward Is Quoted at £100

- Today, borrow and sell one unit for £100: this is a **short sale of the asset**. Invest the £100 proceeds.
- Agree to **buy** one unit in one year for £100: take a long forward.
- At maturity, the investment pays £105. Use £100 to acquire the unit and return it to the asset lender.
- The remaining cash is $105-100=£5$, again independent of the maturity spot price.

The second strategy assumes the asset can be borrowed without an additional fee or recall restriction and that the short-sale proceeds can be invested. Both examples ignore trading frictions. The no-arbitrage delivery price of £105 makes the terminal surplus of either construction zero.

The chart shows each construction's maturity cash surplus **per unit** at different quoted delivery prices. A negative value means that construction loses money at that quote; use the positive side to identify the relevant arbitrage direction.

```python:line-numbers
high_quote, low_quote = 110.0, 100.0
arbitrage_cashflows = pd.DataFrame({
    "Sell expensive forward": [100., -100., high_quote, -fair_delivery],
    "Buy cheap forward": [100., -100., -low_quote, fair_delivery],
}, index=["Today: financing or short-sale receipt", "Today: asset purchase or cash investment",
          "Maturity: forward settlement cash", "Maturity: loan repayment or investment proceeds"])
print("Cash flows per unit (GBP); asset delivery/return closes the asset positions:")
print(arbitrage_cashflows.to_string(float_format=lambda value: f"{value:.2f}"))
print("Initial net cash:", arbitrage_cashflows.iloc[:2].sum().to_dict())
print("Maturity net cash:", arbitrage_cashflows.iloc[2:].sum().to_dict())
quoted_prices = np.linspace(90, 120, 61)
print("\n<ECHARTS_DATA>" + json.dumps({
    "forwardArbitrage": {
        "type": "line", "title": "Which Purchase-and-Sale Combination Has a Surplus?",
        "xAxis": {"type": "value", "name": "Quoted delivery price (GBP/unit)", "scale": True},
        "yAxisName": "Maturity cash surplus per unit (GBP)",
        "series": {
            "Buy asset; sell forward": np.column_stack([quoted_prices, quoted_prices - fair_delivery]).tolist(),
            "Sell asset; buy forward": np.column_stack([quoted_prices, fair_delivery - quoted_prices]).tolist(),
        },
    },
}, allow_nan=False))
```
<Editor id="forward-arbitrage" />

At £110 the first line is £5; at £100 the second is £5. Both are zero at £105. This calculation uses financing and matched trades, not a guess about where the investment's price will go.

**Check:** does a £105 forward quote mean the asset is expected to trade at £105 next year? No. The quote is determined here by the £100 spot price and financing. Investors can disagree about the future spot price while facing the same no-arbitrage forward quote.

## 4. Value an Agreement That Already Exists

Six months pass. The original contract still requires you to pay **£105 per unit** in another six months. Suppose the current spot price is **£110**, and the effective annual rate remains 5%.

Keep three quantities separate:

| Quantity | At this six-month review |
| --- | ---: |
| Current spot price, $S_t$ | £110 per unit |
| Existing contract's delivery price, $K$ | £105 per unit, fixed |
| New fair delivery price for the same maturity, $F_{t,T}$ | $110(1.05)^{0.5}\approx£112.72$ per unit |

Your original buying price is now better than the price available on a new forward. But the difference is received at maturity, so discount it before calling it today's value.

### Lock in the Difference, Then Discount It

Keep the old long forward, and imagine entering a new short forward with the same quantity, maturity, underlying, and settlement terms. At maturity you acquire the asset for £105 and deliver it for approximately £112.72. The locked difference is approximately £7.72 per unit.

Let $\tau=T-t$ be the **remaining** time in years. The old long forward's current value per unit is:

$$v_t=\frac{F_{t,T}-K}{(1+R)^\tau}
=S_t-\frac{K}{(1+R)^\tau}.$$

The second form follows by substituting $F_{t,T}=S_t(1+R)^\tau$. Numerically:

$$v_t=110-\frac{105}{\sqrt{1.05}}
\approx110-102.4695=£7.5305.$$

For ten units, $V_t=qv_t\approx£75.30$. The short's value is the negative of this. This is a model value at the review date, not a cash payment that automatically arrives then. Closing or transferring a real forward depends on its terms and the counterparty. Keeping it open leaves its value exposed to subsequent changes.

The next graph varies the **current** spot price at this fixed review date. It is different from the earlier maturity-payoff graph: the £105 future payment is discounted by the remaining six months.

```python:line-numbers
review_spot = 110.0
remaining_years = 0.5
discount_factor = (1 + annual_rate) ** (-remaining_years)
replacement_quote = review_spot / discount_factor
value_per_unit = review_spot - delivery_price * discount_factor
contract_value = quantity * value_per_unit
locked_terminal_difference = quantity * (replacement_quote - delivery_price)
print(f"Existing delivery price: {delivery_price:.2f} GBP/unit")
print(f"New delivery price for the same maturity: {replacement_quote:.4f} GBP/unit")
print(f"Old long's value per unit today: {value_per_unit:.4f} GBP")
print(f"Ten-unit long's value today: {contract_value:.4f} GBP")
print(f"Old long + new short: {locked_terminal_difference:.4f} GBP at maturity")
print(f"Discounted locked difference: {locked_terminal_difference * discount_factor:.4f} GBP")
current_spots = np.linspace(60, 150, 91)
review_values = quantity * (current_spots - delivery_price * discount_factor)
print("\n<ECHARTS_DATA>" + json.dumps({
    "forwardReview": {
        "type": "line", "title": "An Existing Contract Can Have Positive or Negative Value",
        "xAxis": {"type": "value", "name": "Current spot (GBP/unit)", "scale": True},
        "yAxisName": "Ten-unit long forward value today (GBP)",
        "series": {
            "Existing long": np.column_stack([current_spots, review_values]).tolist(),
            "Zero value": [[60, 0], [150, 0]],
        },
        "seriesOptions": {"Zero value": {"lineStyle": {"type": "dashed"}}},
    },
}, allow_nan=False))
```
<Editor id="forward-review" />

The line crosses zero at approximately £102.47, the present value of the £105 delivery payment. At maturity, the remaining time is zero, the discount factor becomes one, and the valuation formula becomes the payoff $q(S_T-K)$. At inception, using $K=F_{0,T}$ makes the value zero. These two endpoints check that pricing and payoff are consistent.

### Experiment: Change the Spot Price, Keep the Agreement Fixed

Before moving the slider, predict what a £5 rise in the current spot price will do to the ten-unit contract's value. The future £105 payment, six-month remaining term, and 5% effective annual rate all stay fixed. The increase should be $10\times£5=£50$.

The line below repeats the preceding calculation; the dot marks your selected spot price. The printed new forward quote is for a **different agreement entered now**. Moving the slider does not rewrite the existing £105 delivery price.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_forward_value_echart,
    spot=widgets.IntSlider(value=110, min=60, max=150, step=5, description="Spot (GBP)", continuous_update=False),
)
widget_instance
```
<Editor id="forward-value-widget" />

**Try it:** move from £110 to £115, then down to £100. The contract values should be approximately £75.30, £125.30, and −£24.70. Explain why today's spot price can equal the original £100 spot while the old contract has a negative value: the remaining financing period is now shorter, but the agreed £105 payment is unchanged.

## 5. Use the Forward to Fix a Future Purchase Cost

Return to the original date. Suppose you really need ten units in one year. A long forward can hedge that purchase: **hedging** means using one position to offset a particular risk in another exposure.

With physical delivery, you pay £1,050 and receive the units. With matching cash settlement, buy the units in the market and use the forward's payment to offset the changing purchase cost:

$$\text{Net purchase cost}
=qS_T-q(S_T-K)=qK=£1{,}050.$$

At a £120 spot price, the market purchase costs £1,200 and the forward pays you £150: net cost £1,050. At £80, the purchase costs £800 but you must pay £250 on the forward: again £1,050. The hedge also gives up the benefit of a cheaper future purchase.

The graph compares the uncertain market cost with the fixed net cost. All values refer to maturity; the calculation does not mix today's money with next year's money.

```python:line-numbers
market_purchase_costs = quantity * terminal_spots
net_purchase_costs = market_purchase_costs - long_payoffs
hedge_table = pd.DataFrame({
    "Maturity spot (GBP/unit)": terminal_spots,
    "Market purchase cost (GBP)": market_purchase_costs,
    "Forward receipt; negative means payment (GBP)": long_payoffs,
    "Net purchase cost (GBP)": net_purchase_costs,
})
print(hedge_table.to_string(index=False, float_format=lambda value: f"{value:.2f}"))
print("\n<ECHARTS_DATA>" + json.dumps({
    "forwardHedge": {
        "type": "line", "title": "A Matching Forward Fixes the Maturity Purchase Cost",
        "xAxis": {"type": "value", "name": "Maturity spot (GBP/unit)", "scale": True},
        "yAxisName": "Cost of acquiring ten units at maturity (GBP)",
        "series": {
            "Market purchase alone": np.column_stack([payoff_grid, quantity * payoff_grid]).tolist(),
            "Purchase plus long forward": np.column_stack([payoff_grid, np.full(len(payoff_grid), quantity * delivery_price)]).tolist(),
        },
    },
}, allow_nan=False))
```
<Editor id="forward-hedge" />

The flat line is a fixed cost, not a guaranteed investment profit. It relies on matching the asset or settlement reference, quantity, and purchase date, and on contractual performance. A forward linked to a different asset or date can leave a mismatch, called **basis risk**. If you do not have an offsetting purchase need, a long forward instead adds exposure to the asset price.

## 6. Work Through a New Agreement

An income-free asset costs **£125**. The effective annual borrowing/lending rate is **4%**. You enter a fair forward to buy **four units in two years**, under the same assumptions.

1. What delivery price per unit makes its initial value zero?
2. After one year, the spot price is £140 and the annual rate remains 4%. What is the value of the existing long contract? Remember that only one year remains.
3. If you keep it until maturity and the final spot price is £120, what is its payoff? Does a positive value at the earlier review guarantee a positive maturity payoff?

::: details Hint
First compound £125 for two years. Keep that delivery price fixed when reviewing the old contract. Discount its payment for the remaining one year, then multiply the value per unit by four. At maturity, use the final spot price and stop discounting.
:::

::: details Worked answer
The delivery price is $125(1.04)^2=£135.20$ per unit. After one year, the value per unit is $140-135.20/1.04=140-130=£10$, so the four-unit contract is worth £40. Its maturity payoff at £120 is $4(120-135.20)=-£60.80$. The earlier positive value was not locked in merely by observing it: a subsequent price fall can produce a negative payoff.
:::

```python:line-numbers
exercise_spot, exercise_rate, exercise_quantity = 125.0, 0.04, 4
exercise_delivery = exercise_spot * (1 + exercise_rate) ** 2
exercise_review_value = exercise_quantity * (140 - exercise_delivery / (1 + exercise_rate))
exercise_payoff = exercise_quantity * (120 - exercise_delivery)
print(f"Delivery price: {exercise_delivery:.2f} GBP/unit")
print(f"Contract value after one year: {exercise_review_value:.2f} GBP")
print(f"Maturity payoff at a 120 GBP spot: {exercise_payoff:.2f} GBP")
```
<Editor id="forward-exercise" />

## Chapter Summary

- A forward obligates the long to buy and the short to sell. Read the quantity, delivery price, underlying, settlement terms, and maturity first.
- A new fair forward has zero initial value in our model; its delivery price includes financing. That quote is not a forecast of the future spot price.
- The existing delivery price stays fixed while the contract's value changes. Value it using the current spot, current financing conditions, and remaining term.
- A matching forward can fix a future purchase cost. It exchanges price uncertainty for a binding obligation and also removes the benefit of a favorable price move.

Continue with [D.2 — Futures and Forwards Compared](./d.2-futures.md). Keep the same purchase question and investigate what changes when gains and losses are settled daily.
