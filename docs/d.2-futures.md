---
title: "Futures and Forwards Compared"
permalink: /d.2-futures
description: "Work through daily futures settlement, initial and maintenance margin, cash calls, funding costs, and the difference between forward and futures prices."
---

# Futures and Forwards Compared

**Question:** two agreements finish with the same £150 gain. Can one still require you to find cash before the gain arrives?

Imagine two ways to keep accounts with a seller. With the first, you settle the agreed difference at the end. With the second, you settle each day's change as you go. The final total may match, but the second arrangement can require money on a day when your account is already under pressure.

In [Forward Contracts](./d.1-forwards.md), we agreed to buy ten units in one year at £105 per unit. We now compare that forward with a hypothetical futures contract on the same income-free investment. We will first add the cash amounts without interest, then put every cash flow on a common date to include funding.

All prices and rules below are invented teaching inputs, not an exchange's contract specification. Run cells in order; the early-drop widget also works independently.

```python:line-numbers
import json
import numpy as np
import pandas as pd
```
<Editor id="futures-setup" />

## 1. What Is a Futures Contract?

A **futures contract** is a standardized agreement whose specification identifies the underlying, quantity or cash multiplier, expiry, and settlement method. Futures are generally traded on an exchange and centrally cleared. A **clearing house** stands between clearing members as the central counterparty; customers ordinarily trade through brokers. Clearing and collateral reduce counterparty exposures but do not remove the possibility of losses or default.

A long position benefits when the quoted futures price rises; a short position benefits when it falls. Both sides have obligations. A position can normally be closed by an offsetting trade in the same contract before expiry, subject to market access and liquidity.

| Question | Forward | Futures |
| --- | --- | --- |
| How are terms agreed? | Often negotiated privately with a dealer or another counterparty | Standardized contract, generally exchange-traded and centrally cleared |
| When are gains and losses paid? | At maturity in our forward example; actual agreements may require collateral and interim transfers | Settlement variation is paid at least daily; intraday settlement can also occur |
| Is an upfront payment the purchase price? | A fair new forward has zero initial value in our example; collateral may still be required | Initial margin is collateral, not a purchase price or option premium |
| What happens at expiry? | Physical delivery or cash settlement, according to the agreement | Physical delivery or final cash settlement, according to the contract |
| Can the contract be exited? | By agreed termination, transfer, or an offsetting agreement, subject to terms | Normally by an opposite trade in the same contract |

The **futures quote** is a price used to calculate settlement. It is not the amount you pay to buy the contract. Immediately after settlement, gains and losses through that settlement price have been paid; the remaining futures position resets to zero value in the ideal model. This does not mean its quote is zero or that previous losses disappear.

### Keep the Units Visible

Our hypothetical contract covers **ten units**, and its quote is in **GBP per unit**. We hold one long contract, so a £1 quote increase produces a £10 gain. The **contract multiplier** converts a quote change into money. Real contracts may quote an index level, a commodity price, or another quantity; read the multiplier before calculating cash.

At the initial £105 quote, the contract's **notional exposure** is $10\times105=£1{,}050$. Notional is a measure of exposure, not the premium or margin deposit.

## 2. Calculate Each Daily Settlement

Keep the forward example's one-year horizon, £100 initial spot, and 5% effective annual financing benchmark, giving an initial quote of £105. We use a **cash-settled futures contract**; any purchase of the underlying investment is a separate transaction. Our invented market has **365 equal daily intervals**, with a settlement every day. This simplifies the calendar; it does not reproduce exchange holidays or business-day rules.

The quote stays at £105 through day 361. We concentrate its movement in the final four days so you can check every nonzero settlement:

| Day | Futures settlement price (GBP/unit) | Change | Long's daily settlement (GBP) |
| ---: | ---: | ---: | ---: |
| 361 | 105 | n/a | 0 |
| 362 | 100 | −5 | −50 |
| 363 | 98 | −2 | −20 |
| 364 | 112 | +14 | +140 |
| 365: expiry | 120 | +8 | +80 |

**Variation margin**, also called **settlement variation**, is the cash gain or loss settled for a price change. Positive means cash credited to the long; negative means cash debited. Let $f_i$ be the settlement quote on day $i$, and $q=10$ the number of underlying units represented by the position. Then:

$$\mathrm{VM}_i=q(f_i-f_{i-1}).$$

For day 362, $10(100-105)=-£50$. The short receives £50. On day 364, the long receives $10(112-98)=£140$; the short pays it.

The bar chart shows the four daily cash amounts. Its horizontal axis is the settlement day, not a possible terminal asset price. The underlying asset is not bought or sold by these daily cash transfers.

```python:line-numbers
quantity = 10
days = np.arange(366)
initial_quote = 105.0
prices_a = np.full(366, initial_quote)
prices_a[-4:] = [100., 98., 112., 120.]
prices_b = np.full(366, initial_quote)
prices_b[-4:] = [110., 115., 118., 120.]
variation_a = np.r_[0., quantity * np.diff(prices_a)]
variation_b = np.r_[0., quantity * np.diff(prices_b)]
last_days = np.arange(361, 366)
settlement_table = pd.DataFrame({
    "Quote (GBP/unit)": prices_a[last_days],
    "Long settlement (GBP)": variation_a[last_days],
    "Short settlement (GBP)": -variation_a[last_days],
}, index=pd.Index(last_days, name="Day"))
print(settlement_table.to_string(float_format=lambda value: f"{value:.2f}"))
print("\n<ECHARTS_DATA>" + json.dumps({
    "futuresDailyCash": {
        "type": "bar", "title": "Settle Each Change, Not the Whole Gain Again",
        "xAxis": {"type": "category", "name": "Settlement day", "data": [str(d) for d in last_days[1:]]},
        "yAxisName": "Daily settlement for ten units (GBP)",
        "series": {"Long": variation_a[-4:].tolist(), "Short": (-variation_a[-4:]).tolist()},
    },
}, allow_nan=False))
```
<Editor id="futures-daily-settlement" />

The last bar is **£80**, not £150. Paying the full £150 again at expiry would double-count earlier settlements. At expiry we assume the final settlement reference equals the underlying spot price of £120 per unit.

## 3. Same Total, Different Payment Dates

Add the four futures settlements:

$$-50-20+140+80=£150.$$

The intermediate quote changes cancel when added:

$$\sum_{i=1}^{365}q(f_i-f_{i-1})=q(f_{365}-f_0)
=10(120-105)=£150.$$

This is an **undiscounted sum of dated payments**, not yet a calculation of their value at one common date. The long position from [Forward Contracts](./d.1-forwards.md) also pays £150 at maturity under cash settlement, but it pays none of that gain beforehand in our uncollateralized example.

The graph compares cumulative contractual settlements. It excludes margin deposits and interest, which we will add separately. Only the last five day labels are shown; all earlier variation payments are zero.

```python:line-numbers
cumulative_variation = np.cumsum(variation_a)
forward_cash = np.zeros(366)
forward_cash[-1] = quantity * (prices_a[-1] - initial_quote)
cumulative_forward = np.cumsum(forward_cash)
print(f"Sum of futures settlements: {variation_a.sum():.2f} GBP")
print(f"Forward's maturity settlement: {forward_cash[-1]:.2f} GBP")
print("\n<ECHARTS_DATA>" + json.dumps({
    "futuresCashTiming": {
        "type": "line", "title": "A Matching Final Total Can Hide an Earlier Cash Outflow",
        "xAxis": {"type": "category", "name": "Day", "data": [str(d) for d in last_days]},
        "yAxisName": "Cumulative settlements, excluding interest (GBP)",
        "series": {"Futures": cumulative_variation[last_days].tolist(),
                   "Forward": cumulative_forward[last_days].tolist()},
        "seriesOptions": {"Futures": {"step": "end"}, "Forward": {"step": "end"}},
    },
}, allow_nan=False))
```
<Editor id="futures-cash-timing" />

By day 363 the long futures position has settled a cumulative **£70 loss**, although its eventual total is a £150 gain. Knowing the ending price would not remove the obligation to fund losses along the way.

**Check:** if the final price were £100 instead of £120, what would the sum of settlements be? $10(100-105)=-£50$. The path determines the timing of those settlements; the endpoints determine their undiscounted sum for a fixed position size.

## 4. Build a Margin Account Ledger

**Initial margin** is collateral deposited to support the position. It is not a down payment on the asset and does not cap the possible loss. **Maintenance margin** is the account threshold used in our example to trigger an additional deposit. The additional deposit is a **margin call**; it is distinct from the day's variation settlement.

Use these explicit teaching rules:

- Deposit **£100 on day 0**. The maintenance level is **£75**.
- Credit or debit each day's variation to the account. It earns **zero interest** in this first ledger.
- Before expiry, if the balance is **below £75**, add enough outside cash to restore **£100**. At exactly £75, make no call.
- Retain gains in the account; make no withdrawals before expiry. Assume every call is met immediately.
- At expiry, settle the last variation and close the account. Return a positive balance to the owner; a negative balance is an amount the owner must pay. Do not first top the account up just to close it.

These are illustrative broker-account rules. Exchanges and brokers can change requirements, call intraday, or handle variation and collateral in separate accounts. If a call cannot be met, the position may be reduced or liquidated; our calculation assumes it remains open.

### Follow the First Two Losses

On day 362, the account starts at £100. The £50 loss leaves **£50**, below the £75 threshold. You add **£50**, restoring £100. Adding only £25 would reach the maintenance level, not the required restoration level.

On day 363, the £20 loss leaves **£80**. That is above £75, so there is no call. Gains then raise the balance to £220 and finally £300. At expiry, the £300 is returned.

You deposited £100 initially and £50 later. Therefore the returned £300 contains **£150 of your deposits plus £150 of net settlement gain**. It is not a £300 profit.

### Reproduce Every Account Movement

The function below follows those rules in order. `before` is the balance after variation but before any deposit or closing transfer. `transfer` is cash returned at closure, negative if money is still owed. **Outside cash flow** is positive when the owner receives money and negative when the owner supplies it.

```python:line-numbers
def margin_ledger(prices, quantity=10, initial_margin=100., maintenance_margin=75.):
    balance = 0.0
    records = []
    for day, price in enumerate(prices):
        variation = 0.0 if day == 0 else quantity * (price - prices[day - 1])
        before = balance + variation
        if day == 0:
            deposit = initial_margin
        elif day < len(prices) - 1 and before < maintenance_margin:
            deposit = initial_margin - before
        else:
            deposit = 0.0
        transfer = before + deposit if day == len(prices) - 1 else 0.0
        balance = before + deposit - transfer
        records.append([price, variation, before, deposit, transfer, balance, transfer - deposit])
    frame = pd.DataFrame(records, columns=[
        "Quote (GBP/unit)", "Variation (GBP)", "Before funding/close (GBP)",
        "Deposit (GBP)", "Close-out transfer (GBP)", "Closing balance (GBP)", "Outside cash flow (GBP)",
    ], index=pd.Index(range(len(prices)), name="Day"))
    frame["Cumulative deposits (GBP)"] = frame["Deposit (GBP)"].cumsum()
    return frame

margin_a = margin_ledger(prices_a)
shown_days = [0, 361, 362, 363, 364, 365]
print(margin_a.loc[shown_days].to_string(float_format=lambda value: f"{value:.2f}"))
print(f"Total deposited: {margin_a['Deposit (GBP)'].sum():.2f} GBP")
print(f"Net outside cash, before interest: {margin_a['Outside cash flow (GBP)'].sum():.2f} GBP")
print("\n<ECHARTS_DATA>" + json.dumps({
    "futuresMarginBalance": {
        "type": "line", "title": "Losses, Top-Ups, and the Return of the Remaining Balance",
        "xAxis": {"type": "category", "name": "Selected day", "data": [str(d) for d in shown_days]},
        "yAxisName": "Margin account balance (GBP)",
        "series": {
            "Before funding/close": margin_a.loc[shown_days, "Before funding/close (GBP)"].tolist(),
            "Closing balance": margin_a.loc[shown_days, "Closing balance (GBP)"].tolist(),
            "Maintenance level": [75.] * 5 + [None],
        },
        "seriesOptions": {"Maintenance level": {"lineStyle": {"type": "dashed"}}},
    },
    "futuresOutsideCash": {
        "type": "bar", "title": "Cash Supplied by or Returned to the Owner",
        "xAxis": {"type": "category", "name": "Selected day", "data": [str(d) for d in shown_days]},
        "yAxisName": "Outside cash flow; positive is received (GBP)",
        "series": {"Owner's cash flow": margin_a.loc[shown_days, "Outside cash flow (GBP)"].tolist()},
    },
}, allow_nan=False))
```
<Editor id="futures-margin-ledger" />

The first graph distinguishes the £50 pre-call balance from the £100 closing balance on day 362. Its final closing balance is zero because the money was **returned**, not lost. The second graph shows the owner's payments of £100 and £50 and the eventual £300 receipt. The horizontal labels omit the unchanged intervening days; their spacing is not elapsed time.

## 5. Compare Two Paths with the Same Ending Price

Path A is the fall-then-recovery sequence above. Path B rises through £110, £115, and £118 before ending at the same £120. Both start at £105, both represent ten units, and both have an undiscounted settlement gain of £150.

Path B never falls below maintenance. It needs only the £100 initial deposit and returns £250 at closure. Path A needs £150 of deposits and returns £300. The difference in returned cash reflects the extra £50 supplied, not a larger gain.

The price chart shows only the last four intervals. The table includes the initial deposit made on day 0, as well as any later calls.

```python:line-numbers
margin_b = margin_ledger(prices_b)
path_ledgers = {"A: fall then recover": margin_a, "B: steady rise": margin_b}
path_comparison = pd.DataFrame({name: {
    "Total deposits (GBP)": ledger["Deposit (GBP)"].sum(),
    "Additional deposits (GBP)": ledger["Deposit (GBP)"].iloc[1:].sum(),
    "Close-out receipt (GBP)": ledger["Close-out transfer (GBP)"].iloc[-1],
    "Net cash before interest (GBP)": ledger["Outside cash flow (GBP)"].sum(),
} for name, ledger in path_ledgers.items()}).T
print(path_comparison.to_string(float_format=lambda value: f"{value:.2f}"))
print("\n<ECHARTS_DATA>" + json.dumps({
    "futuresTwoPaths": {
        "type": "line", "title": "Same Start and Finish, Different Cash Calls",
        "xAxis": {"type": "category", "name": "Day", "data": [str(d) for d in last_days]},
        "yAxisName": "Futures settlement price (GBP/unit)",
        "series": {"A: fall then recover": prices_a[last_days].tolist(), "B: steady rise": prices_b[last_days].tolist()},
    },
}, allow_nan=False))
```
<Editor id="futures-two-paths" />

**Liquidity** here means having cash available when a payment is due. A position can finish profitably and still create a liquidity problem earlier. The £70 cumulative settlement loss is also not the same number as the £50 additional deposit: the account started with collateral and our rule allows its balance to fall to £75 before requiring a top-up.

### Experiment: Make the Early Fall Deeper

The slider changes the fall on day 362. Day 363's quote is set 1.4 times that amount below £105; the final two quotes stay at £112 and £120. For a £5 first fall, the prices are £100 and £98. For a £10 first fall, they are £95 and £91.

Predict which will change: the final settlement total, the amount deposited, or both. The second graph includes the £100 initial deposit from day 0; it plots the total supplied so far, not losses or current account value. The helper repeats the ledger rules above on these explicit paths.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_futures_liquidity_echart,
    dip=widgets.IntSlider(value=5, min=0, max=15, step=1, description="Drop (GBP)", continuous_update=False),
)
widget_instance
```
<Editor id="futures-liquidity-widget" />

**Try it:** compare drops of £0, £5, £10, and £15. Total deposits should be **£100, £150, £240, and £310**, respectively. The settlement gain remains £150. At the £15 setting, a £150 first loss exceeds the £100 initial deposit; the temporary negative balance must still be funded. Collateral is not a maximum-loss guarantee.

## 6. Include the Cost of Supplying Cash

So far we added payments from different dates without interest. Now suppose outside cash can be borrowed or invested at a constant **5% effective annual rate**, while the margin account still earns zero. There are no fees. Retain the same deposit and withdrawal policy; do not add a second, separate financing charge for variation already in this account.

A £100 deposit on day 0 ties up money that could become £105 by day 365. Path A's extra £50 on day 362 has three days left to finance:

$$50(1.05)^{3/365}\approx£50.0201.$$

Its maturity-date net cash is therefore:

$$300-100(1.05)-50(1.05)^{3/365}\approx£144.9799.$$

Path B returns £250 after supplying only £100 at inception: $250-105=£145$. The uncollateralized forward has no interim cash flows in this example and pays £150 at maturity.

More generally, let $c_i$ be the owner's signed outside cash flow on day $i$. Its maturity equivalent is $c_i(1+R)^{(365-i)/365}$. For day 0's negative £100, that is −£105; for day 365's £300 receipt, it is £300. Add those maturity-equivalent amounts to compare the strategies on the same date.

```python:line-numbers
funding_rate = 0.05
to_maturity = (1 + funding_rate) ** ((365 - days) / 365)
funded_gains = {name: float(np.dot(ledger["Outside cash flow (GBP)"], to_maturity))
                for name, ledger in path_ledgers.items()}
funded_gains["Forward"] = float(forward_cash[-1])
funding_comparison = pd.DataFrame({
    "Gross settlement gain (GBP)": [150., 150., 150.],
    "Maturity-equivalent net cash (GBP)": list(funded_gains.values()),
}, index=list(funded_gains))
funding_comparison["Funding/opportunity cost (GBP)"] = (
    funding_comparison["Gross settlement gain (GBP)"] - funding_comparison["Maturity-equivalent net cash (GBP)"])
funding_comparison["Funded purchase cost (GBP)"] = quantity * prices_a[-1] - funding_comparison["Maturity-equivalent net cash (GBP)"]
print(funding_comparison.to_string(float_format=lambda value: f"{value:.4f}"))
print("\n<ECHARTS_DATA>" + json.dumps({
    "futuresFundedComparison": {
        "type": "bar", "title": "Put Deposits and Receipts on the Same Date",
        "xAxis": {"type": "category", "data": list(funded_gains)},
        "yAxisName": "Maturity-equivalent net cash (GBP)",
        "series": {"After funding": list(funded_gains.values()), "Before interest": [150., 150., 150.]},
    },
}, allow_nan=False))
```
<Editor id="futures-funding" />

For the purchase hedge from [Forward Contracts](./d.1-forwards.md), buying ten units at the final £120 spot costs £1,200. Subtracting the nominal £150 derivative gain gives £1,050 for all three constructions **before funding**. Including this account's funding costs gives approximately **£1,055.02 for A**, **£1,055.00 for B**, and **£1,050 for the forward**. The differences describe our specified account rules, not a universal ranking of futures and forwards. Collateral remuneration, withdrawals, borrowing spreads, and a collateralized forward would change the comparison.

The chart's vertical axis begins at zero: the differences are small relative to the £150 gross gain. Read the table for the precise amounts.

## 7. When Are Forward and Futures Quotes Equal?

For the income-free asset in [Forward Contracts](./d.1-forwards.md), a fair new forward quote is $S_0(1+R)^T$. Under the standard frictionless benchmark with **deterministic interest rates**, matching underlying and maturity, and consistent borrowing, investment, and collateral treatment, the futures quote equals that forward quote. Our £100 asset and one-year 5% rate give **£105** for both.

That equality concerns **quotes at entry**, not an assertion that a fixed-size futures position has the same funded cash flows as a forward. The zero-interest margin account in Section 6 is a particular implementation with a funding cost, separate from the frictionless pricing benchmark.

### A Small Replication Check

For this check, switch to an ideal arrangement: settle variation into an outside cash account that earns or pays the known 5% rate. Any collateral is remunerated at its funding rate so its net cost is zero. Allow fractional exposure and costless rebalancing. This is a separate calculation; do not combine its reinvested variation with the retained-margin cash flows in Section 6.

To make a day-$i$ settlement have the same maturity effect as ten units without interest, hold:

$$q_i=\frac{10}{(1.05)^{(365-i)/365}}$$

units during the interval ending on day $i$. These quantities are known in advance because the rate is deterministic. On day 362, $q_{362}\approx9.995991$ rather than ten. For the £5 quote fall, the settlement is approximately −£49.979953; financing it for the remaining three days produces exactly −£50 at maturity.

For every interval, multiplying $q_i(f_i-f_{i-1})$ by its known growth factor gives $10(f_i-f_{i-1})$. Adding them reproduces $10(f_{365}-f_0)$ at maturity. This deterministic adjustment is called **tailing the hedge**. Our one-contract position represents ten units, so these fractional quantities describe an ideal replication, not an executable whole-contract trade for this small account.

```python:line-numbers
settlement_growth = to_maturity[1:]
adjusted_units = quantity / settlement_growth
replication_rows = []
for name, prices in [("A: fall then recover", prices_a), ("B: steady rise", prices_b)]:
    changes = np.diff(prices)
    fixed_terminal_cash = np.sum(quantity * changes * settlement_growth)
    adjusted_terminal_cash = np.sum(adjusted_units * changes * settlement_growth)
    replication_rows.append([name, fixed_terminal_cash, adjusted_terminal_cash])
replication = pd.DataFrame(replication_rows, columns=[
    "Path", "Fixed units: reinvested VM (GBP)", "Adjusted units: reinvested VM (GBP)",
]).set_index("Path")
print(replication.to_string(float_format=lambda value: f"{value:.6f}"))
print(f"Units for the interval ending day 362: {adjusted_units[361]:.6f}")
print(f"Day 362 cash settlement: {adjusted_units[361] * (100 - 105):.6f} GBP")
```
<Editor id="futures-quote-replication" />

The fixed ten-unit positions produce approximately **£149.993313** and **£150.037434** after reinvesting or financing each variation payment. The adjusted positions both produce **£150**, matching the forward. This supplies the replication argument for equal entry quotes under the stated ideal assumptions. At zero interest, the adjustment disappears and all quantities are ten.

With **uncertain interest rates**, the future growth factors are not known in advance. The relationship between price changes and funding or reinvestment rates then matters; matching forward and futures quotes is no longer automatic. A joint model is needed to calculate that difference. Neither quote, by itself, is a prediction of the future spot price.

## 8. Work Through a Different Settlement Path

For a short three-interval exercise, a long ten-unit futures position has quotes **£105 → £102 → £101 → £108**. Use £100 initial margin, £75 maintenance, the same restoration rule, retained gains, and zero interest.

1. Calculate the three variation payments.
2. Find the additional deposit, if any. Restore to £100, not £75.
3. Calculate the final account transfer and the net cash gain. Why are they different?
4. If you buy ten units at the final £108 spot, what is the net purchase cost before funding?

::: details Hint
Start the account at £100. Apply each price change multiplied by ten before testing the maintenance threshold. On the last day, settle and close the account rather than topping it up for a position that has ended.
:::

::: details Worked answer
Variation payments are −£30, −£10, and +£70. The first leaves £70, triggering a £30 deposit to restore £100. The second leaves £90, so there is no call. The last raises the balance to £160, which is returned at closure. Total deposits were £130, so the net cash gain is £30, equal to $10(108-105)$. Buying the units costs £1,080; subtracting the £30 gain gives £1,050 before funding.
:::

```python:line-numbers
exercise_prices = np.array([105., 102., 101., 108.])
exercise_ledger = margin_ledger(exercise_prices)
exercise_gain = exercise_ledger["Outside cash flow (GBP)"].sum()
print(exercise_ledger.to_string(float_format=lambda value: f"{value:.2f}"))
print(f"Net cash gain before interest: {exercise_gain:.2f} GBP")
print(f"Net purchase cost before funding: {10 * exercise_prices[-1] - exercise_gain:.2f} GBP")
```
<Editor id="futures-exercise" />

## Chapter Summary

- A futures quote, contract notional, collateral deposit, and contract value are different quantities.
- Variation margin settles price changes. A margin call supplies additional collateral under the account rules; it is not another trading loss.
- Equal endpoint gains can require different amounts of cash along the way. A final receipt can include the return of your own deposits.
- Compare dated cash flows at a common date before comparing funded outcomes. State how collateral and variation are treated.
- Deterministic-rate replication explains matching forward and futures quotes in the ideal benchmark. Real account costs and uncertain rates require additional analysis.

Continue with [Options and Replication](./d.3-options.md). Replace the obligation to buy with the right to choose, then calculate what that right is worth in a two-outcome example.

## References for Contract Mechanics

- CME Group, [Margin: Know What's Needed](https://www.cmegroup.com/education/courses/introduction-to-futures/margin-know-what-is-needed): initial margin, maintenance margin, and possible responses to a margin call.
- CME Group, [Money Calculations for Futures and Options](https://www.cmegroup.com/education/articles-and-reports/money-calculations-for-futures-and-options): daily cash mark-to-market and settlement variation. Our £100/£75 rules and daily calendar are teaching assumptions, not CME requirements.
