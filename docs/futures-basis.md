---
title: "Futures Basis, Dividends, and Implied Financing"
permalink: /futures-basis
description: "Read financing and dividends from derivative prices, fit anchored curves, and reconcile executable carry trades, margin funding, and calendar-spread profit."
---

# Futures Basis, Dividends, and Implied Financing

**Question:** a basket costs 5,000 index points and its three-month future trades at 5,040. Is the extra 40 points expensive, fair, or informative about financing and dividends?

Imagine buying something now with borrowed money instead of agreeing to buy it later. Buying now incurs interest, but it also gives you any income paid before the future purchase date. An equity-index basis calculation follows those two cash flows. A private agreement to buy later is a forward; an exchange future additionally involves clearing, margin, and settlement, as explained in [Futures and Forwards Compared](./d.2-futures.md).

We will also run the calculation backwards. Given the traded price, what financing rate or dividend amount is embedded in it? This is **inverse pricing**. Several inputs can produce the same price, so a reading of the market must identify both its evidence and its assumptions.

The chapter develops one synthetic price-index market. It contains no live quotes or claimed trading returns. All small calculations remain visible in Python. Run cells in order; the identification widget runs independently.

## 1. Define the Contract Before Reading Its Price

Our invented cash basket exactly tracks a **price index**: ordinary dividends leave the index and are paid separately to the owner. One basket corresponding to one futures contract costs **€10 per index point**. Thus a 5,000-point level corresponds to €50,000 of shares, and a one-point futures gain is €10. The index number itself is not a security you can purchase.

For a simple illustration of index construction, 100 index shares at €40 and 50 at €20 have combined market value €5,000. Dividing by a divisor of 1 gives a 5,000-point index. Ten copies of that illustrative basket match our €10-per-point contract. Real indices apply their own eligible shares, free-float adjustments, weights, divisor changes, and corporate-action rules.

Use valuation time zero and a three-month horizon $T=0.25$ years. Except where stated otherwise, rates are **continuously compounded** and deterministic. A 4% continuous rate gives effective annual growth $e^{0.04}-1\approx4.0811\%$. For calendar dates, a model must specify its day count; 90 actual days under ACT/365 is $90/365$, not exactly 0.25.

| Quantity | Definition in this lesson |
| --- | --- |
| $S$ | Current cash-basket level, in index points |
| $F(0,T)$ | Quote for a new forward/future maturing at $T$, in points |
| $M=10$ | Contract multiplier, in EUR per point |
| $B=F-S$ | **Basis**, using futures minus spot |
| $F^{\mathrm{model}}$ | Quote calculated under specified assumptions |
| $\epsilon=F^{\mathrm{market}}-F^{\mathrm{model}}$ | Model residual, in points |
| $P(0,u)$ | Discount factor: today's value of one unit payable at time $u$ |

A positive basis is not automatically a positive residual. Nor is a residual automatically executable profit. Prices, financing, dividends, taxes, and settlement references must describe matching instruments. A **gross-return index** reinvests eligible dividends before withholding; a **net-return index** applies its specified withholding assumptions first. The headline DAX, for example, incorporates dividend reinvestment; applying the price-index dividend subtraction to a performance index without adapting the model would double-count the effect.

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.optimize import brentq, least_squares, lsq_linear
from scipy.stats import norm

spot, maturity, multiplier = 5000., .25, 10.
rate, dividend, market_future = .04, 30., 5040.
print(f"Basket capital: {spot*multiplier:,.2f} EUR")
print(f"Market basis: {market_future-spot:.2f} points")
print(f"4% continuous is {np.expm1(rate):.6%} effective annually")
```
<Editor id="basis-setup" />

## 2. Derive Carry from the Money Owed

First suppose 30 dividend points are **known and paid at expiry**, immediately before the cash basket is sold. Buy one basket using borrowing. The debt per €10 multiplier grows from 5,000 to:

$$5000e^{0.04(0.25)}=5050.250835\text{ points}.$$

The dividend contributes 30 points toward repayment. A forward delivery price that exactly covers the remainder is:

$$F^{\mathrm{model}}=Se^{rT}-D=5020.250835.$$

The fair basis is therefore 20.250835 points. A quote of 5,040 is 19.749165 points above that benchmark, or **€197.491646 per contract before costs and settlement-funding adjustments**. Using full precision avoids turning €197.49 into €197.50 by rounding the points first.

For a terminally settled short forward, the accounting at expiry is explicit: sell the basket for $S_T$, receive forward payment $F_0-S_T$, receive dividend $D$, and repay $Se^{rT}$. Total is $F_0+D-Se^{rT}$. The unknown $S_T$ cancels. This locks a positive difference only if the dividend, financing, execution, and other required conditions are actually secured. A dividend forecast does not provide that certainty. Futures settlement cash flows will be accounted for separately below.

### A Continuous-Yield Approximation

If income is modeled as a continuously reinvestable proportional yield $q$, replication gives $F=Se^{(r-q)T}$. For $S=6000$, $r=0.05$, $q=0.02$, and $T=90/365$, this is **6,044.548126 points**. A continuous yield is an income model; companies do not literally pay a continuous stream of cash dividends. Its $q$ cannot be interchanged with a dated dividend amount in points.

The graph holds the market quote fixed and varies the financing assumption. The crossing is the rate implied **conditional on the 30-point dividend**. The vertical axis is the futures quote, zoomed to its plotted range.

```python:line-numbers
fair_future = spot*np.exp(rate*maturity)-dividend
gross_edge = market_future-fair_future
rate_grid = np.linspace(.02, .08, 121)
print(f"Debt: {spot*np.exp(rate*maturity):.6f}; model future: {fair_future:.6f} points")
print(f"Gross benchmark edge: {gross_edge:.6f} points = {gross_edge*multiplier:.6f} EUR")
print(f"Continuous-yield example: {6000*np.exp((.05-.02)*90/365):.6f} points")
print("<ECHARTS_DATA>" + json.dumps({"basisCarry": {
    "type": "line", "title": "A Positive Basis Can Be the Cost of Carry",
    "xAxis": {"type": "value", "name": "Continuous financing rate (%)"},
    "yAxisName": "Futures quote (points)",
    "yAxis": {"type": "value", "name": "Futures quote (points)", "scale": True},
    "series": {"Model quote": np.column_stack([100*rate_grid, spot*np.exp(rate_grid*maturity)-dividend]).tolist(),
               "Market quote": np.column_stack([100*rate_grid, np.full(len(rate_grid), market_future)]).tolist()},
    "seriesOptions": {"Market quote": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="basis-carry" />

**Experiment:** increase `dividend` from 30 to 40 and rerun. The model quote falls by ten points, increasing the short-forward benchmark edge by ten. Restore 30. **Check:** does this make the trade safer? Not by itself: increasing a forecast is not securing the additional payment.

## 3. Put Dividends and Financing on Their Actual Dates

Let $e_i$ be an ex-dividend date and $p_i$ its cash payment date, in years from today. Buying before the ex-date and retaining the entitlement gives a dividend receivable; buying on the ex-date ordinarily does not. The **record date** determines the issuer's registered holders under the market's settlement rules. Cash becomes available to reduce borrowing only on the payment date. Record announcement time separately: a historical decision cannot use an announcement published later. When expiry and ex-date coincide, the formula below assumes delivery after entitlement detaches; verify the actual contract's event and settlement ordering.

With known amounts $D_i$, a common deterministic financing curve, and retained dividend entitlements, the forward relation is:

$$F(0,T)=\frac{S-\sum_{0<e_i\le T}D_iP(0,p_i)}{P(0,T)}.$$

This formula assumes the initial quoted basket excludes already-detached receivables. The sum includes entitlements earned before delivery even if payment follows delivery. Such a future receivable must be valued or financed at expiry, rather than recorded as cash already received. Our deterministic example assumes it is fully collectible and financeable at the stated curve.

At a flat rate, $P(0,u)=e^{-ru}$ and each dividend reduces the delivery quote by $D_i e^{r(T-p_i)}$. If €10-equivalent dividend points are paid early, they can reduce the debt for longer. If payment is after expiry, the receivable's value at expiry is less than its future amount at positive rates.

For $T=0.25$, use these invented events:

| Ex-date | Payment date | Dividend points | Included in this expiry? |
| ---: | ---: | ---: | --- |
| 0.08 | 0.10 | 10 | Yes |
| 0.20 | 0.30 | 20 | Yes: receivable payable after expiry |
| 0.28 | 0.32 | 15 | No: entitlement arises after delivery |

The expiry-valued deductions are $10e^{.04(.25-.10)}\approx10.060180$ and $20e^{.04(.25-.30)}\approx19.960040$. The third is excluded. The resulting quote is approximately **5,020.230615**. The graph varies the second payment date, keeping its ex-date and amount fixed. Delaying cash makes the forward quote slightly higher.

```python:line-numbers
events = pd.DataFrame({"Ex": [.08, .20, .28], "Pay": [.10, .30, .32], "Points": [10., 20., 15.]})
def dated_forward(s, t, schedule, discount):
    entitled = schedule.loc[(schedule["Ex"] > 0) & (schedule["Ex"] <= t)]
    pv_income = sum(row.Points*discount(row.Pay) for row in entitled.itertuples())
    return (s-pv_income)/discount(t)

flat_discount = lambda u: np.exp(-rate*u)
dated_quote = dated_forward(spot, maturity, events, flat_discount)
payment_dates = np.linspace(.20, .40, 41)
payment_quotes = []
for pay in payment_dates:
    revised = events.copy()
    revised.loc[1, "Pay"] = pay
    payment_quotes.append(dated_forward(spot, maturity, revised, flat_discount))
print(events.to_string(index=False))
print(f"Dated-dividend quote: {dated_quote:.6f} points")
print("<ECHARTS_DATA>" + json.dumps({"basisDividendDates": {
    "type": "line", "title": "Entitlement and Cash Availability Are Different Dates",
    "xAxis": {"type": "value", "name": "Second dividend payment time (years)"},
    "yAxisName": "Model futures quote (points)",
    "yAxis": {"type": "value", "name": "Model futures quote (points)", "scale": True},
    "series": {"Quote": np.column_stack([payment_dates, payment_quotes]).tolist()},
}}, allow_nan=False))
```
<Editor id="basis-dividend-dates" />

**Experiment:** move the second ex-date to 0.26, after expiry. Its dividend deduction disappears even if its payment date stays 0.30. **Check:** should a payment at 0.30 be accrued as cash at 0.25? No. At expiry it is a receivable with a discounted value. Restore the original schedule.

For real contracts, ordinary and special dividends can be treated differently. Withholding, manufactured payments on shorts, index rebalances, and divisor adjustments must match the exact underlying and investor. The simple share-count-times-dividend calculation is only a starting point: convert each eligible contribution to index points using the applicable shares, currency conversion, and divisor at the relevant event.

## 4. Move from a Mid-Price to Executable Carry

A **bid** is what someone will pay you; an **ask** is what you must pay to buy. A published cash-index level may use stale constituent prices and does not guarantee that its basket can be executed at that value. Align timestamps and trading sessions before comparing basket and futures quotes.

Return to the 30-point dividend paid at expiry. Suppose the basket is bid at 4,999.8 and offered at 5,000.2; the future is bid at 5,039.5 and offered at 5,040.5. Borrow cash at 4% continuous, lend at 3.5%, and pay a fixed stock-loan fee of $5000(0.01)(0.25)=12.5$ points at expiry when shorting. That fixed-fee convention is an invented contract assumption, not a universal stock-borrow formula. Let other costs total one point **valued at expiry**.

For a terminal-settled carry benchmark, the upper and lower entry thresholds are:

$$U=S_{\mathrm{ask}}e^{r_bT}-D+\mathrm{cost},$$
$$L=S_{\mathrm{bid}}e^{r_lT}-D-\mathrm{borrow\ fee}-\mathrm{cost}.$$

Cash-and-carry has benchmark net edge $F_{\mathrm{bid}}-U$. Reverse carry has benchmark net edge $L-F_{\mathrm{ask}}$. For the first trade, buy shares at the ask and sell the derivative at the bid. For the second, short shares at the bid, invest the proceeds, pay the manufactured dividend and stock-loan fee, and buy the derivative at the ask. This reverse calculation assumes the short-sale proceeds are available to invest at $r_l$; actual rebates and restrictions can change it.

The thresholds are approximately **5,021.452845** and **5,000.240208** points. The market lies above the upper benchmark. A quote between the thresholds would offer neither direction a positive benchmark edge. We have a **no-trade band**, not one universally executable fair price. Futures margin funding remains to be added, and forecast dividends remain uncertain.

The graph shows the two directional edges as the derivative quote changes. Bid/ask width stays one point. The zero line identifies where an edge changes sign; the lines must not both be positive under these consistent assumptions.

```python:line-numbers
cash_bid, cash_ask = 4999.8, 5000.2
future_bid, future_ask = 5039.5, 5040.5
borrow_rate, lend_rate, terminal_cost = .04, .035, 1.
stock_loan_fee = spot*.01*maturity
upper = cash_ask*np.exp(borrow_rate*maturity)-dividend+terminal_cost
lower = cash_bid*np.exp(lend_rate*maturity)-dividend-stock_loan_fee-terminal_cost
quote_grid = np.linspace(4980., 5060., 81)
print(f"Lower threshold: {lower:.6f}; upper threshold: {upper:.6f} points")
print(f"Carry edge at bid: {future_bid-upper:.6f}; reverse edge at ask: {lower-future_ask:.6f} points")
print("<ECHARTS_DATA>" + json.dumps({"basisExecutableBand": {
    "type": "line", "title": "Different Trading Directions Face Different Costs",
    "xAxis": {"type": "value", "name": "Derivative mid quote (points)"},
    "yAxisName": "Terminal-settled benchmark net edge (points)",
    "series": {"Cash-and-carry": np.column_stack([quote_grid, quote_grid-.5-upper]).tolist(),
               "Reverse carry": np.column_stack([quote_grid, lower-quote_grid-.5]).tolist(),
               "Zero": np.column_stack([quote_grid, np.zeros(len(quote_grid))]).tolist()},
    "seriesOptions": {"Reverse carry": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}},
                      "Zero": {"itemStyle": {"color": "#64748b"}, "lineStyle": {"color": "#64748b", "type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="basis-executable" />

**Experiment:** raise the borrowing rate by 0.01, or 100 basis points. Buying the basket becomes more expensive to finance, moving the upper threshold upward. **Check:** should that financing cost also be subtracted a second time as an additional fee? No. Deduct only costs not already included in the carry calculation.

### Which Rate Pays for Which Account?

An **overnight indexed swap (OIS)** exchanges a fixed rate against compounded overnight rates; a curve built from appropriate rate contracts can value cash flows under matching collateral terms. **Equity repo** is secured financing against shares. A **haircut** limits the cash advanced against collateral: a 10% haircut on a €50,000 basket leaves €5,000 to finance elsewhere. At 4% secured financing on €45,000 and 6% unsecured financing on €5,000, one year of continuous-rate interest costs $45000(e^{.04}-1)+5000(e^{.06}-1)\approx2145.67$ EUR, before fees. Applying 4% to the whole basket would understate this cost.

**Collateral remuneration** is interest credited on posted cash. A **short-sale rebate** is the rate credited on eligible short-sale collateral; it is not necessarily the ordinary cash lending rate. Stock-loan fees pay for access to the borrowed shares. Our next ledger deliberately specifies zero margin remuneration, full basket borrowing, and a single cash rate. Each different actual account term needs its own dated cash flow.

## 5. Reconcile a Futures Trade and Its Margin Funding

Now trade an actual settlement stream in our invented market. Buy one basket at 5,000 and short one future at 5,040, retaining a **fixed** contract count. Contribute 250 points (€2,500) of initial equity to a non-interest-bearing margin account. Borrow the basket purchase price plus a 0.5-point entry fee. The cash account starts at −5,000.5 points. Initial wealth is therefore 249.5 points after the fee.

For each interval, accrue cash at 4% continuous. The short futures variation is $F_{i-1}-F_i$ points and is credited to margin. Before the final date, if margin falls below 200, borrow enough cash to restore it to 250. Retain gains in margin. At expiry, receive the 30-point dividend, sell the basket, release margin, and pay a 0.5-point exit fee. The futures final quote equals the specified cash settlement level. Short-sale borrow is irrelevant to this **long** cash basket.

Two paths share spot endpoints 5,000/5,100 and futures endpoints 5,040/5,100 but reverse their intermediate moves. Settlements occur at $0.25/3$, $2(0.25)/3$, and 0.25 years. These sparse dates are teaching settlement dates, not an exchange calendar. The sum of variation is −60 points for either path. Its timing and the resulting borrowing differ.

On path A the first futures quote rises to 5,250. Margin falls from 250 to 40, triggering a 210-point (€2,100) top-up financed by more borrowing. On path B the first move is a fall to 4,850, generating 190 points of margin gain; its 210-point top-up happens later. Both can finish profitably while requiring additional liquidity along the way.

The first chart displays marked account wealth, including the basket, cash, and margin. The second displays cumulative borrowed top-ups in EUR. Financed profit at expiry is final wealth minus the initial 250 points grown at the same financing benchmark. This measures profit after the cost of the initial capital; it is not a return on the futures contract's zero initial value.

For comparison, the cell also prints a **reverse-carry ledger** on path A. Set basket quantity to −1 and take one long future. Invest the 5,000-point short-sale proceeds less the entry fee at 3.5%, transfer cash from those proceeds when margin requires it, and pay the 30-point manufactured dividend plus the 12.5-point stock-loan fee at expiry. This assumes the proceeds are available, the share loan survives to expiry, and there is no extra stock-loan collateral requirement. It uses the common mid entries to isolate cash accounting; use the bid/ask entries above for an execution decision. In this account a margin transfer reduces invested cash rather than increasing debt.

```python:line-numbers
settlement_times = np.linspace(0., maturity, 4)
def carry_ledger(spots, futures, financing=.04, paid_dividend=30., basket_quantity=1., loan_fee=0.):
    cash, margin, topups = -basket_quantity*spots[0]-.5, 250., 0.
    rows = [[0., spots[0], futures[0], cash, margin, 0., 0., 0., cash+margin+basket_quantity*spots[0]]]
    for i in range(1, len(settlement_times)):
        cash *= np.exp(financing*(settlement_times[i]-settlement_times[i-1]))
        variation = basket_quantity*(futures[i-1]-futures[i])
        margin += variation
        transfer = max(250.-margin, 0.) if margin < 200. and i < len(settlement_times)-1 else 0.
        before = cash+margin
        cash -= transfer
        margin += transfer
        topups += transfer
        budget_error = cash+margin-before
        wealth = cash+margin+basket_quantity*spots[i]
        if i == len(settlement_times)-1:
            cash = wealth+basket_quantity*paid_dividend-loan_fee-.5
            margin, wealth = 0., cash
        rows.append([settlement_times[i], spots[i], futures[i], cash, margin, variation, topups, budget_error, wealth])
    return pd.DataFrame(rows, columns=["Time", "Spot", "Future", "Cash", "Margin", "Variation", "Top-ups", "Transfer error", "Wealth"])

path_a = carry_ledger([5000., 5200., 4800., 5100.], [5040., 5250., 4850., 5100.])
path_b = carry_ledger([5000., 4800., 5200., 5100.], [5040., 4850., 5250., 5100.])
funded_profits = {name: float((ledger.Wealth.iloc[-1]-250*np.exp(rate*maturity))*multiplier)
                  for name, ledger in (("A", path_a), ("B", path_b))}
print(path_a.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
print("Financed profits (EUR):", funded_profits)
reverse_ledger = carry_ledger([5000., 5200., 4800., 5100.], [5040., 5250., 4850., 5100.],
                              financing=.035, basket_quantity=-1., loan_fee=12.5)
reverse_profit = (reverse_ledger.Wealth.iloc[-1]-250*np.exp(.035*maturity))*multiplier
print("Reverse carry (points; top-ups transferred from invested proceeds):")
print(reverse_ledger.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
print(f"Reverse financed profit: {reverse_profit:.6f} EUR")
print("<ECHARTS_DATA>" + json.dumps({
    "basisMarginWealth": {"type": "line", "title": "Include Cash, Basket, and Margin in Account Wealth",
        "xAxis": {"type": "value", "name": "Elapsed time (years)"}, "yAxisName": "Marked account wealth (EUR)",
        "series": {name: np.column_stack([ledger.Time, multiplier*ledger.Wealth]).tolist() for name, ledger in (("Path A", path_a), ("Path B", path_b))},
        "seriesOptions": {"Path B": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}}},
    "basisMarginLiquidity": {"type": "line", "title": "The Same Final Settlement Can Require Funding Earlier",
        "xAxis": {"type": "value", "name": "Elapsed time (years)"}, "yAxisName": "Cumulative borrowed margin top-ups (EUR)",
        "series": {name: np.column_stack([ledger.Time, multiplier*ledger["Top-ups"]]).tolist() for name, ledger in (("Path A", path_a), ("Path B", path_b))},
        "seriesOptions": {"Path A": {"step": "end"}, "Path B": {"step": "end", "itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}}}},
}, allow_nan=False))
```
<Editor id="basis-margin" />

The transfer error should stay near zero: moving borrowed cash to margin changes the account's composition, not its wealth. Funding and fees do change wealth. Earlier borrowing makes path A less profitable. A flat rate and matching initial forward/futures quotes do not make a fixed-quantity futures trade's funded cash flows identical to a terminal-settled forward. [Futures and Forwards Compared](./d.2-futures.md) derives the idealized tailing adjustment under its own account assumptions.

The printed funded profits are **€148.269207** for path A and **€155.304298** for path B. For example, path A ends with 267.339462 points; subtract the initial capital benchmark $250e^{.04(.25)}=252.512542$ and multiply by €10. The €7.035091 path difference is the extra cost of borrowing 210 points one interval earlier.

**Experiment:** rerun both ledger calls with `financing=0`. Their final profits before any financing benchmark should coincide because payment timing no longer earns or costs interest. Then set `paid_dividend=10`: each final account loses 20 points relative to its baseline. **Check:** is the €2,100 margin top-up itself a €2,100 expense? No. It is a transfer financed by borrowing; interest on that borrowing is an expense, and the margin balance is released at close.

## 6. Read Financing Backwards from a Market Quote

With a known dividend paid at expiry, invert $F=Se^{rT}-D$:

$$r_{\mathrm{impl}}=\frac{\log((F+D)/S)}{T}.$$

At 5,040 with a 30-point dividend, this is **5.561162% continuous per year**. The simple-interest approximation $(F+D-S)/(ST)$ gives 5.6%. Compared with a 4% continuous financing quote, the exact continuous difference is **156.1162 basis points**, not 160. One basis point is 0.01 percentage points, or 0.0001 in decimal rate units.

For multiple dated payments the rate appears inside several exponential terms. A **root finder** searches for a rate making model price minus observed price equal zero. A bracket supplies two rates whose pricing errors have opposite signs; bisection-like steps and interpolation locate a zero inside. Inspect the final repricing error and the economically allowed rate range. A missing sign change is a diagnostic, not permission to return the nearest bound as a fitted rate.

The graph shows implied financing versus futures price, with the dividend fixed. Bid and ask define a range of implied rates, not a statistical confidence interval. The numerical root uses the same flat-rate single-dividend example first, allowing an exact independent check.

Then solve the dated-event example from the earlier section. With its own quote 5,020.230615, the root should recover 4%. Using 5,040 instead produces a different rate because the payment dates differ. The helper rejects zero/negative maturity, missing inputs, crossed bid/ask quotes, and a bracket that contains no root. It returns a numerical answer only after checking the price residual.

```python:line-numbers
implied_rate = np.log((market_future+dividend)/spot)/maturity
root_rate = brentq(lambda x: spot*np.exp(x*maturity)-dividend-market_future, -.05, .20, xtol=1e-13)
implied_bid = np.log((future_bid+dividend)/spot)/maturity
implied_ask = np.log((future_ask+dividend)/spot)/maturity
def implied_dated_rate(s, t, schedule, bid, ask, bracket=(-.05, .20)):
    if not np.isfinite([s, t, bid, ask]).all() or s <= 0 or t <= 0 or bid > ask:
        raise ValueError("Use finite positive spot/time and an ordered bid/ask quote")
    target = (bid+ask)/2
    error = lambda r: dated_forward(s, t, schedule, lambda u: np.exp(-r*u))-target
    fitted = brentq(error, *bracket, xtol=1e-13)
    if abs(error(fitted)) > 1e-7:
        raise ValueError("Root failed its quote repricing check")
    return fitted

dated_recovered_rate = implied_dated_rate(spot, maturity, events, dated_quote, dated_quote)
dated_market_rate = implied_dated_rate(spot, maturity, events, future_bid, future_ask)
print(f"Dated-event recovery: {dated_recovered_rate:.9%}; at market mid: {dated_market_rate:.9%}")
for bad_bid, bad_ask in [(5041., 5040.), (np.nan, 5040.), (10000., 10001.)]:
    try:
        implied_dated_rate(spot, maturity, events, bad_bid, bad_ask)
    except ValueError as error:
        print(f"Rejected quote [{bad_bid}, {bad_ask}]: {error}")
print(f"Continuous implied rate: {implied_rate:.9%}; numerical root: {root_rate:.9%}")
print(f"Simple approximation: {(market_future+dividend-spot)/(spot*maturity):.6%}")
print(f"Bid/ask implied range: {implied_bid:.6%} to {implied_ask:.6%}")
print(f"Repricing error: {spot*np.exp(root_rate*maturity)-dividend-market_future:.2e} points")
implied_grid = np.log((quote_grid+dividend)/spot)/maturity
print("<ECHARTS_DATA>" + json.dumps({"basisImpliedRate": {
    "type": "line", "title": "Read a Financing Rate Conditional on the Dividend Input",
    "xAxis": {"type": "value", "name": "Futures quote (points)"}, "yAxisName": "Implied continuous annual rate (%)",
    "series": {"Implied financing": np.column_stack([quote_grid, 100*implied_grid]).tolist()},
}}, allow_nan=False))
```
<Editor id="basis-implied" />

**Experiment:** keep the quote at 5,040 and change the dividend to 20 points in the inversion. The inferred financing falls. **Check:** did the observed repo market change? No. You changed a conditioning assumption, not an observed financing transaction. Restore the dividend to 30.

## 7. Identification: One Price Can Have Several Explanations

**Identification** asks whether different inputs can produce the same observations. Rearrange the same equation as $D=Se^{rT}-F$. For our market quote:

| Assumed continuous financing | Dividend points that reproduce 5,040 |
| ---: | ---: |
| 4% | 10.250835 |
| 5% | 22.892258 |
| 6% | 35.565323 |

Every row fits exactly. A numerical optimizer cannot discover which row is economically correct from that one quote. More futures maturities help only to the extent that they add independent information relative to the number and structure of unknown financing and dividend inputs.

The widget plots compatible dividend amounts against financing rates. The orange diamond marks the selected assumption; the market futures quote stays fixed at 5,040. Here the rate range is restricted to 4–8%, giving positive dividends in every displayed case. No dividend forecast is being generated.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_basis_identification_echart,
    financing_percent=widgets.FloatSlider(value=5., min=4., max=8., step=.25,
                                          description="Rate (%)", continuous_update=False),
)
widget_instance
```
<Editor id="basis-identification-widget" />

**Try it:** select 4%, 5%, and 6%, then reprice each displayed dividend/rate pair. The quote remains 5,040. **Check:** would smoothing the curve create new information? No. A smoothness penalty or prior can select an answer, but that selection reflects an additional assumption.

To disentangle the inputs, use independent evidence: secured financing quotes, announced dividends, point-in-time dividend estimates, and suitably matched dividend derivatives. A listed dividend future settles a defined dividend period and eligibility rule. Its quote does not directly identify every ex-date amount, and its pricing-measure interpretation need not equal an unbiased real-world dividend forecast. Tax and timing mismatches remain exposures.

## 8. Fit a Financing Curve with Dividends Independently Anchored

We now move from one quote to a synthetic maturity panel. **Calibration** means selecting model parameters to reproduce those prices under stated assumptions. We first know the dividend schedule independently. Later we reverse that choice and anchor financing instead.

Use three continuously compounded **forward financing rates**, each applying over a time interval: 4% over years 0–0.25, 4.5% over 0.25–0.5, and 5% after 0.5. For time $u$, write $a_j(u)$ for the length of time spent in interval $j$. The discount factor is:

$$P(0,u)=\exp\left[-\sum_{j=1}^{3} f_j a_j(u)\right].$$

For $u=0.75$, cumulative interest is $0.04(0.25)+0.045(0.25)+0.05(0.25)=0.03375$. Thus $P(0,0.75)=e^{-0.03375}\approx0.966813$. The **zero-equivalent rate** to that date is $0.03375/0.75=4.5\%$, different from the last interval's 5% forward rate. Between dates $u<v$, the continuous forward-equivalent rate is $\log[P(0,u)/P(0,v)]/(v-u)$. For 0.5–0.75 it recovers 5%.

Assume known dividends of 30, 45, and 20 points, with matching ex/payment dates 0.25, 0.5, and 0.75. An equal ex/payment date is a simplifying assumption specific to this panel. Observe five futures maturities: 0.25, 0.5, 0.75, 1, and 1.25 years. Build quotes from the known curve plus explicitly disclosed small perturbations. Fit the first four; reserve the fifth to check interpolation-model extension beyond the fitted maturity range. The last forward rate is held constant beyond 0.5, an explicit extrapolation assumption.

### Explain the Objective Before Calling the Solver

For each fitted quote, divide model-minus-mid error by its quoted half-spread $h_i$. A 0.25-point error on a 0.5-point half-spread is a scaled residual of 0.5. Squaring it contributes 0.25 to the objective. Minimize the sum of these squared residuals with rates bounded between −2% and 12%. Negative rates are allowed; exponential discount factors remain positive.

We also compare a regularized fit. Its extra objective term is $\lambda\sum_j[(f_{j+1}-f_j)/0.01]^2$, with illustrative $\lambda=0.2$ selected in advance. A one-percentage-point jump contributes 0.2. This favors smoother rates but does not add observations. Report the market fit separately from the penalty. Neither fit is a claim about future returns or about the correct degree of smoothing in real data.

The first chart compares zero-equivalent rates from the known generating curve, the fitted curve, and the smoothed fit. The second shows each quote error divided by its half-spread. Values between −1 and +1 are inside the supplied quote interval. The 1.25-year observation was withheld from both fits, rather than used to select the penalty.

```python:line-numbers
def interval_lengths(u):
    return np.array([min(u, .25), min(max(u-.25, 0.), .25), max(u-.5, 0.)])

def curve_discount(u, forwards):
    return np.exp(-np.dot(interval_lengths(u), forwards))

curve_events = pd.DataFrame({"Ex": [.25, .5, .75], "Pay": [.25, .5, .75], "Points": [30., 45., 20.]})
true_forwards = np.array([.04, .045, .05])
tenors = np.array([.25, .5, .75, 1., 1.25])
def curve_quotes(forwards, schedule=curve_events):
    return np.array([dated_forward(spot, t, schedule, lambda u: curve_discount(u, forwards)) for t in tenors])

true_quotes = curve_quotes(true_forwards)
quote_mids = true_quotes+np.array([.12, -.08, .15, -.10, .07])
half_spreads = np.array([.5, .5, .75, .75, 1.])
def fit_residuals(forwards, penalty=0.):
    market_errors = (curve_quotes(forwards)[:4]-quote_mids[:4])/half_spreads[:4]
    return np.r_[market_errors, np.sqrt(penalty)*np.diff(forwards)/.01]

plain_fit = least_squares(fit_residuals, [.03, .03, .03], bounds=(-.02, .12), x_scale=.01,
                          ftol=1e-12, xtol=1e-12, gtol=1e-10)
smooth_fit = least_squares(lambda f: fit_residuals(f, .2), [.03, .03, .03], bounds=(-.02, .12), x_scale=.01,
                           ftol=1e-12, xtol=1e-12, gtol=1e-10)
if not plain_fit.success or not smooth_fit.success:
    raise RuntimeError("Curve fit did not converge")
curve_table = pd.DataFrame({"Years": tenors, "Mid": quote_mids, "Half-spread": half_spreads,
                           "Plain model": curve_quotes(plain_fit.x), "Smoothed model": curve_quotes(smooth_fit.x)})
print(curve_table.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
print("Forward rates: true", true_forwards, "plain", plain_fit.x, "smoothed", smooth_fit.x)
for name, fit, penalty in (("Plain", plain_fit, 0.), ("Smoothed", smooth_fit, .2)):
    market_loss = np.sum(((curve_quotes(fit.x)[:4]-quote_mids[:4])/half_spreads[:4])**2)
    smooth_loss = penalty*np.sum((np.diff(fit.x)/.01)**2)
    print(f"{name}: market loss {market_loss:.6f}; penalty {smooth_loss:.6f}; held-out error {curve_quotes(fit.x)[4]-quote_mids[4]:.6f} points")
singular_values = np.linalg.svd(plain_fit.jac[:4], compute_uv=False)
print("Scaled price-sensitivity singular values:", singular_values)
print(f"Sensitivity condition ratio: {singular_values[0]/singular_values[-1]:.6f}")
print("<ECHARTS_DATA>" + json.dumps({
    "basisCurveFit": {"type": "line", "title": "Fit Financing Only After Anchoring the Dividends",
        "xAxis": {"type": "value", "name": "Maturity (years)"}, "yAxisName": "Zero-equivalent continuous rate (%)",
        "series": {name: [[float(t), float(-100*np.log(curve_discount(t, f))/t)] for t in tenors]
                   for name, f in (("Generating curve", true_forwards), ("Fitted", plain_fit.x), ("Smoothed", smooth_fit.x))},
        "seriesOptions": {"Fitted": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c", "type": "dashed"}},
                          "Smoothed": {"itemStyle": {"color": "#9333ea"}, "lineStyle": {"color": "#9333ea", "type": "dotted"}}}},
    "basisCurveResiduals": {"type": "line", "title": "Reprice Training Quotes and a Withheld Maturity",
        "xAxis": {"type": "category", "name": "Maturity; last observation withheld", "data": [str(t) for t in tenors]},
        "yAxisName": "Model minus mid / quoted half-spread",
        "series": {"Plain fit": ((curve_quotes(plain_fit.x)-quote_mids)/half_spreads).tolist(),
                   "Smoothed fit": ((curve_quotes(smooth_fit.x)-quote_mids)/half_spreads).tolist(),
                   "Ask boundary": [1.]*5, "Bid boundary": [-1.]*5},
        "seriesOptions": {"Smoothed fit": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}},
                          "Ask boundary": {"lineStyle": {"color": "#64748b", "type": "dashed"}},
                          "Bid boundary": {"lineStyle": {"color": "#64748b", "type": "dashed"}}}},
}, allow_nan=False))
```
<Editor id="basis-curve-fit" />

### Diagnose the Fit, Not Just Solver Success

The solver's **Jacobian** records how each scaled quote changes with each rate parameter. Its singular values measure sensitivity along independent combinations of those parameters. A zero singular value means some combination is locally invisible to these observations; a very small one means small quote noise can cause large parameter changes. The ratio of largest to smallest is a conditioning diagnostic, dependent on the stated parameter scaling. It is not a confidence interval or proof of global uniqueness.

For example, one quote with local sensitivities $[1250,-1]$ to rate and dividend has only one observed direction. A rate increase of 0.0008 and a dividend increase of approximately one point offset to first order. The exact compatible curve was shown in the widget. The three-rate anchored panel has independent directions because its maturities span all three rate intervals.

An alternative **interval-distance objective** gives zero error whenever a model price lies between bid and ask, and penalizes only the distance outside. A model at 100.2 inside [100, 100.4] has zero interval error; at 100.6 it is 0.2 outside. Such an objective may admit many fits. Selecting one by smoothness expresses a preference, not additional precision in market knowledge.

**Experiment:** increase the 0.75-year quote perturbation from 0.15 to 3 points and rerun. Inspect fit errors, the fitted curve, and withheld error before interpreting a financing move. Restore the original perturbation. **Check:** does a successful solver guarantee that every quote is inside its spread? No. Convergence describes the optimization; the residual report describes agreement with the observations.

## 9. Read Dividends with Financing Independently Anchored

Now assume the generating financing curve is independently observed and ask what dividends the noisy quotes imply. Do **not** use the previously fitted financing curve and then call the recovered dividends independent evidence: both would be explaining the same prices.

For known entitlement/payment dates, write the quote equations as:

$$y_j=\frac{S}{P(0,T_j)}-F_j=\sum_i A_{ji}D_i,\qquad
A_{ji}=\mathbf 1_{\{e_i\le T_j\}}\frac{P(0,p_i)}{P(0,T_j)}.$$

The symbol $\mathbf 1$ is one when its condition holds and zero otherwise. Each matrix entry is the financing multiplier for one eligible dividend. In the first maturity, only the first dividend is eligible and payment coincides with expiry, so $A_{11}=1$. The quote's +0.12-point perturbation makes its directly implied dividend $30-0.12=29.88$ points.

Fit the first four observations to three nonnegative ordinary-dividend amounts. Divide each equation by its quote half-spread, so uncertain quotes have less influence. The fifth quote is again withheld. With just the first two maturities, the third dividend would have no effect and could not be identified. An annual dividend-contract quote can anchor a sum, but not necessarily its distribution among several ex-dates.

The bars compare known synthetic generating amounts with fitted amounts. This is a recovery experiment with noisy inputs, not evidence that market prices reveal future corporate decisions perfectly.

```python:line-numbers
discounts = np.array([curve_discount(t, true_forwards) for t in tenors])
dividend_matrix = np.array([[float(e <= t)*curve_discount(p, true_forwards)/curve_discount(t, true_forwards)
                            for e, p in zip(curve_events.Ex, curve_events.Pay)] for t in tenors])
dividend_rhs = spot/discounts-quote_mids
dividend_fit = lsq_linear(dividend_matrix[:4]/half_spreads[:4, None], dividend_rhs[:4]/half_spreads[:4], bounds=(0., 200.), tol=1e-12)
if not dividend_fit.success:
    raise RuntimeError("Dividend fit did not converge")
dividend_reprices = spot/discounts-dividend_matrix@dividend_fit.x
print("Generating dividends:", curve_events.Points.to_numpy(), "fitted:", dividend_fit.x)
print("Repricing errors (points):", dividend_reprices-quote_mids)
print("Rank with two maturities:", np.linalg.matrix_rank(dividend_matrix[:2]), "; with four:", np.linalg.matrix_rank(dividend_matrix[:4]))
print("<ECHARTS_DATA>" + json.dumps({"basisDividendFit": {
    "type": "bar", "title": "Infer Dividend Buckets Conditional on an Independent Curve",
    "xAxis": {"type": "category", "name": "Dividend ex/payment time (years)", "data": [str(t) for t in curve_events.Ex]},
    "yAxisName": "Dividend amount (index points)",
    "series": {"Generating amount": curve_events.Points.tolist(), "Fitted amount": dividend_fit.x.tolist()},
    "seriesOptions": {"Fitted amount": {"itemStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="basis-dividend-fit" />

**Experiment:** raise the independent first-interval financing rate by 0.005 and rebuild the discount factors, matrix, and right side. Higher assumed carry generally requires larger implied dividends to explain the same quotes. **Check:** would those larger fitted dividends prove a more generous corporate payout policy? No. They reflect the changed financing anchor. Restore the generating curve.

## 10. Listen to Options Too: Forward and Discounting from Parity

[Options and Replication](./d.3-options.md) and [Deriving and Using Black–Scholes](./black-scholes.md) establish put–call parity. For comparable European options with common expiry and settlement, under deterministic discounting:

$$C(K,T)-P_{\mathrm{put}}(K,T)=P_d(0,T)[F(0,T)-K].$$

$P_d$ is a discount factor, not a put price. Across strikes this is a straight line: slope $-P_d$ and intercept $P_dF$. Given two strikes $K_1<K_2$ and price differences $y_1,y_2$, calculate $P_d=(y_1-y_2)/(K_2-K_1)$, then $F=K_1+y_1/P_d$.

For the earlier 4%/30-point benchmark, synthetic call-minus-put values at strikes 4,900 and 5,100 are **119.054320** and **−78.955647** points. Their difference is 198.009967. Dividing by 200 gives $P_d=0.990049834$; either strike then gives $F=5020.250835$. These observations identify the forward and option discounting in this model. They still do not independently split that forward into dividends and equity financing.

The code generates option quotes using the forward-Black representation, with 20% implied volatility, and fits parity across five strikes. This is a synthetic quotation model, not a claim that fixed cash dividend jumps produce an exactly lognormal stock price. We center strikes at 5,000 to improve numerical scaling. The fitted intercept is then $P_d(F-5000)$ and the second coefficient is $P_d$.

Each call and put has a 0.25-point half-spread, so their difference has a conservative executable interval of ±0.5 points around its mid. Contaminate one put by adding three points and fit again. The chart compares residuals in units of that interval width. More than one quote can appear inconsistent after fitting; a residual flags the need to inspect timestamps/contracts, not automatic proof of which observation is wrong.

```python:line-numbers
strikes = np.array([4800., 4900., 5000., 5100., 5200.])
option_discount = np.exp(-rate*maturity)
option_forward = fair_future
option_volatility = .20
scale = option_volatility*np.sqrt(maturity)
d1 = (np.log(option_forward/strikes)+.5*option_volatility**2*maturity)/scale
d2 = d1-scale
calls = option_discount*(option_forward*norm.cdf(d1)-strikes*norm.cdf(d2))
puts = option_discount*(strikes*norm.cdf(-d2)-option_forward*norm.cdf(-d1))
parity_design = np.column_stack([np.ones(len(strikes)), -(strikes-spot)])
parity_width = .5
def fit_parity(differences):
    coefficients = np.linalg.lstsq(parity_design/parity_width, differences/parity_width, rcond=None)[0]
    discount = coefficients[1]
    if discount <= 0:
        raise ValueError("Parity fit implies a nonpositive discount factor")
    forward = spot+coefficients[0]/discount
    return discount, forward, (parity_design@coefficients-differences)/parity_width

clean_discount, clean_forward, clean_residuals = fit_parity(calls-puts)
stale_puts = puts.copy()
stale_puts[3] += 3.
bad_discount, bad_forward, bad_residuals = fit_parity(calls-stale_puts)
print(pd.DataFrame({"Strike": strikes, "Call": calls, "Put": puts, "Call minus put": calls-puts}).to_string(index=False))
print(f"Clean: discount {clean_discount:.9f}; forward {clean_forward:.9f}")
print(f"Contaminated: discount {bad_discount:.9f}; forward {bad_forward:.9f}")
print("<ECHARTS_DATA>" + json.dumps({"basisParityFit": {
    "type": "line", "title": "Use Comparable Option Quotes to Cross-Check the Forward",
    "xAxis": {"type": "value", "name": "Option strike (points)"},
    "yAxisName": "Parity residual / difference half-spread",
    "series": {"Clean quotes": np.column_stack([strikes, clean_residuals]).tolist(),
               "One stale put": np.column_stack([strikes, bad_residuals]).tolist()},
    "seriesOptions": {"One stale put": {"itemStyle": {"color": "#ea580c"}, "lineStyle": {"color": "#ea580c"}}},
}}, allow_nan=False))
```
<Editor id="basis-option-parity" />

**Experiment:** move the three-point error from the 5,100 put to the 4,800 put. A far-from-center error can influence the fitted slope differently. **Check:** may the inferred option discount rate be called the desk's equity repo rate? Not without additional assumptions. Collateral discounting, secured equity financing, short-sale rebates, and unsecured borrowing are distinct quantities. A parity difference across strikes also creates a fixed-payment option combination; its fuller construction belongs in [Spreads and Basic Option Combinations](./d.0-overview.md#option-spreads).

## 11. A Calendar Residual Is Not the Position's Profit

Suppose near/far futures quotes are 5,050 and 5,080, while model values are 5,048 and 5,070. The market spread $C=F_{\mathrm{far}}-F_{\mathrm{near}}$ is 30 points; the model spread is 22. Its residual $\epsilon=C-C^{\mathrm{model}}$ is +8. Buying near and selling far benefits if the **market spread** narrows.

For one contract of each with multiplier $M$, before funding and execution costs:

$$\Delta\Pi=M(\Delta F_{\mathrm{near}}-\Delta F_{\mathrm{far}})
=-M\Delta C=-M(\Delta C^{\mathrm{model}}+\Delta\epsilon).$$

If the residual falls from 8 to zero while the model spread rises from 22 to 32, the market spread rises from 30 to 32. The position **loses 2 points, or €20**, despite complete residual convergence. If the model spread had stayed at 22, it would instead gain €80. These are quote-change P&Ls over a common interval before the near contract expires; settling and funding the changes at intermediate dates adds the earlier cash-account effects.

One contract against one is also only approximately spot-neutral. With fixed absolute dividend amounts and deterministic carry, $\partial F(0,T)/\partial S=1/P(0,T)$. For equal multipliers and one short far contract, a locally neutral near quantity is $n_{\mathrm{near}}=P(0,T_{\mathrm{near}})/P(0,T_{\mathrm{far}})$. At 4%, maturities 0.25 and 0.5 give $e^{.04(.5-.25)}\approx1.010050$ near contracts. Actual positions require integer contract choices or another hedge; a changed ratio also changes the simple spread-P&L formula.

The bar chart separates model-spread and residual contributions. Its total must equal direct revaluation of both futures legs. This is the bridge from a model discrepancy to an actual position.

For the single-expiry benchmark, financing sensitivity is $\partial F/\partial r=TSe^{rT}=1262.562709$ points per unit annual rate. A one-basis-point increase therefore adds approximately $1262.562709(0.0001)=0.126256$ points to fair value. Exact repricing gives 0.126258 points. Dividend sensitivity for payment at expiry is −1 point of quote per dividend point; for payment at $p_i$, it is $-P(0,p_i)/P(0,T)$. These are benchmark price sensitivities, not additional cash income from changing a model input.

```python:line-numbers
initial_near, initial_far = 5050., 5080.
initial_model_spread, initial_residual = 22., 8.
final_near, final_far = 5060., 5092.
final_model_spread, final_residual = 32., 0.
direct_calendar_pnl = multiplier*((final_near-initial_near)-(final_far-initial_far))
model_contribution = -multiplier*(final_model_spread-initial_model_spread)
residual_contribution = -multiplier*(final_residual-initial_residual)
neutral_near_quantity = np.exp(rate*(.5-.25))
print(f"Direct calendar P&L: {direct_calendar_pnl:.2f} EUR")
print(f"Model-spread effect: {model_contribution:.2f}; residual effect: {residual_contribution:.2f} EUR")
print(f"Locally spot-neutral near quantity per far contract: {neutral_near_quantity:.9f}")
rate_sensitivity = maturity*spot*np.exp(rate*maturity)
one_bp_repricing = spot*np.exp((rate+.0001)*maturity)-dividend-fair_future
print(f"One-bp financing change: linear {rate_sensitivity*.0001:.9f}; exact {one_bp_repricing:.9f} points")
print("<ECHARTS_DATA>" + json.dumps({"basisCalendarAttribution": {
    "type": "bar", "title": "Residual Convergence Can Accompany a Trading Loss",
    "xAxis": {"type": "category", "name": "Position P&L component", "data": ["Model spread", "Residual", "Total"]},
    "yAxisName": "Change in position value before costs (EUR)",
    "series": {"Contribution": [model_contribution, residual_contribution, direct_calendar_pnl]},
}}, allow_nan=False))
```
<Editor id="basis-calendar" />

**Experiment:** set final model spread to 25, final residual to 3, and final far quote to 5,088 while retaining near at 5,060. The market spread is 28, so P&L is +€20; the model contribution is −€30 and residual contribution +€50. **Check:** do the two maturities have to converge to the same price before near expiry? No. They cover different carry/dividend intervals. Define the near-expiry exit or roll explicitly.

## 12. Stress the Account and Read a Market Dashboard

Raise financing from 4% to 6%, cut the paid dividend from 30 to 10, and retain path A's settlement sequence. These shocks reduce the long-cash/short-futures account's final profit. We can reconcile them by changing financing first, then dividends. The graph compares the full baseline and stressed financed profits with the incremental changes. The chosen order defines sequential attribution; with interacting nonlinear changes, another order can assign different contributions. Always retain a remainder or verify that the attributed parts sum to the full repricing.

Also keep peak cash needs separate from profit. Under the specified margin rule, the total 210-point top-up remains, but its financing cost rises. A change in the exchange's margin requirement or a funding limit would require changing that rule, not just the discount rate. Forced liquidation before expiry would change both holdings and realized P&L.

```python:line-numbers
funding_stress_ledger = carry_ledger([5000., 5200., 4800., 5100.], [5040., 5250., 4850., 5100.], financing=.06)
joint_stress_ledger = carry_ledger([5000., 5200., 4800., 5100.], [5040., 5250., 4850., 5100.], financing=.06, paid_dividend=10.)
funding_profit = (funding_stress_ledger.Wealth.iloc[-1]-250*np.exp(.06*maturity))*multiplier
joint_profit = (joint_stress_ledger.Wealth.iloc[-1]-250*np.exp(.06*maturity))*multiplier
stress_components = [funded_profits["A"], funding_profit-funded_profits["A"], joint_profit-funding_profit, joint_profit]
print(pd.Series(stress_components, index=["Baseline", "Funding change", "Dividend change", "Stressed profit"]).to_string())
print(f"Borrowed margin top-ups: {joint_stress_ledger['Top-ups'].max()*multiplier:.2f} EUR")
snapshot_mids = np.array([5040., 5045.])
snapshot_rates = np.log((snapshot_mids+dividend)/spot)/maturity
snapshot_dividends_fixed_rate = spot*np.exp(snapshot_rates[0]*maturity)-snapshot_mids
print("Snapshot implied rates (%):", 100*snapshot_rates)
print("Snapshot dividends if first rate is held fixed:", snapshot_dividends_fixed_rate)
print("<ECHARTS_DATA>" + json.dumps({"basisStress": {
    "type": "bar", "title": "Reconcile Financing and Dividend Shocks to the Account",
    "xAxis": {"type": "category", "name": "Sequential scenario attribution", "data": ["Baseline", "Funding change", "Dividend change", "Stressed profit"]},
    "yAxisName": "Financed profit or incremental change (EUR)", "series": {"Amount": stress_components},
}}, allow_nan=False))
```
<Editor id="basis-stress" />

**Check:** is a risk/capital charge deducted by an optimizer necessarily a cash expense in this ledger? No. It may be a preference or allocation penalty. Report actual funding and execution expenses separately from a capital-adjusted decision score.

### What the Dashboard Should Say

| Reading | Evidence | What must accompany the number |
| --- | --- | --- |
| Implied financing | Futures and anchored dividend inputs | Continuous/effective convention, maturity, quote range, and dividend assumptions |
| Implied dividends | Futures and an independent financing curve | Eligible period, dates, tax/index convention, and parameter-identification limits |
| Option-implied forward/discount | Comparable call/put pairs | Exercise style, settlement, timestamp, spreads, and parity residuals |
| Executable basis | Basket and derivative bid/ask | Quantity, liquidity, fees, borrowing, collateral, and settlement funding |
| Calendar residual | Market and model maturity spreads | Model revisions, hedge quantities, exit date, and direct P&L attribution |

A change between two timestamped snapshots needs the same input definitions. A higher future could reflect higher financing, lower priced dividends, or a temporary quote inconsistency. It is not possible to distinguish these explanations from the futures move alone. The small perturbations in our calibration panel are disclosed synthetic quote noise, not an observed funding time series.

Here is a controlled two-snapshot example. Times are invented UTC observation labels, both with the same modeled 0.25-year tenor; we ignore the one-minute passage of time to isolate inputs. The independently anchored dividend remains 30 and spot remains 5,000.

| Snapshot | Futures bid/ask | Implied continuous financing at mid | Interpretation conditional on the fixed dividend |
| --- | --- | --- | --- |
| 2026-01-05 10:00 UTC | 5,039.5 / 5,040.5 | 5.561162% | First reading |
| 2026-01-05 10:01 UTC | 5,044.5 / 5,045.5 | 5.955445% | Higher carry embedded in the quote |

The second rate is $\log(5075/5000)/.25$. Holding financing at the first reading instead would imply a dividend of 25 points. Both explain the five-point price rise. To call it a financing-market move, seek independent financing evidence. Quote-age rules also need a concrete policy: if this research experiment permits at most one second of mismatch, a futures update at 10:01:00 paired with a basket last updated at 10:00:57 is rejected before inversion. The tolerance is a study assumption, not an exchange rule.

### Intraday and Multi-Day Use Need Different Evidence

For an intraday example, suppose a buy-near/sell-far signal uses near ask 5,050.5 and far bid 5,079.5: the executable spread is 29, rather than the mid spread 30. If only the near leg fills and the far bid then falls to 5,077.5, the achieved entry spread is 27. The lost two points are €20 per matched pair before fees. A screen showing the original 29 does not represent a completed two-leg trade. Exchange spread orders can reduce legging risk, but size, matching rules, and fill availability still matter.

Intraday validation requires quote timestamps, sequence, stale-quote rejection, partial fills, adverse selection, and a stated latency assumption. A backtest using candle closes or simultaneous mid fills cannot validate that execution claim. For days-to-weeks positions, the emphasis shifts to point-in-time dividend revisions, financing renewals, margin paths, roll rules, and held-out evaluation. Neither horizon converts a model residual directly into expected profit.

The fuller volatility sequence will follow [The Greeks and Hedging](./greeks-hedging.md) and [Spreads and Basic Option Combinations](./d.0-overview.md#option-spreads). [Reading the Options Market: Implied Volatility and Surfaces](./d.0-overview.md#volatility-surfaces) will extract single-option implied volatility before fitting level, skew, curvature, and term structure. [Butterflies, Implied Distributions, and Tail Pricing](./d.0-overview.md#implied-distributions) will distinguish local butterfly information from distributional skewness and kurtosis. Carry inputs established here support those readings; a wrong forward can distort the inferred smile.

## 13. Worked Exercise: Read a Price, Then Explain the Trade

Use spot 4,000, maturity 0.5 years, a known 20-point dividend paid at expiry, and a market future of 4,080. The continuous financing benchmark is 4%; the multiplier is €10 per point.

1. Calculate the benchmark future and market-minus-model residual.
2. Extract the continuous implied financing rate and its difference from 4% in basis points.
3. If financing is fixed at 4%, what dividend reproduces the market quote? What would you investigate if it is inconsistent with the contract's ordinary-dividend assumptions?
4. For a long-near/short-far calendar, the residual falls by five points while its model spread rises by seven. Calculate P&L before funding and costs.
5. Name two pieces of independent evidence needed before treating these readings as a trade.

::: details Hint
Use $4000e^{.04(.5)}-20$ for the benchmark quote. For implied financing, take the natural log of $(4080+20)/4000$ and divide by 0.5. For implied dividends, solve the original equation for the amount rather than changing the sign of the residual by guesswork.
:::

::: details Worked answer
The benchmark quote is approximately 4,060.805360, giving a residual of 19.194640 points, or €191.946401 before the missing implementation effects.

The implied continuous rate is $\log(1.025)/0.5\approx4.938523\%$, which is 93.852252 basis points above 4%. At fixed 4% financing, the compatible dividend is $4000e^{.02}-4080\approx0.805360$ points. This is positive but far below the 20-point input; the quote alone cannot establish which input is wrong. More extreme quotes could imply a negative ordinary dividend, indicating incompatible assumptions or observations rather than a negative corporate cash distribution to accept without investigation.

The calendar's market spread increases by $7-5=2$ points. Long near/short far loses €20 before funding and costs, despite a smaller residual.

Independent financing terms and eligible dividend information help interpret carry. Synchronized executable basket/futures quotes and margin/borrow terms determine whether the proposed position can be implemented. A physical dividend forecast, a derivative-implied dividend price, and a locked payment are different kinds of evidence.
:::

```python:line-numbers
exercise_spot, exercise_time, exercise_dividend, exercise_market = 4000., .5, 20., 4080.
exercise_fair = exercise_spot*np.exp(.04*exercise_time)-exercise_dividend
exercise_rate = np.log((exercise_market+exercise_dividend)/exercise_spot)/exercise_time
exercise_implied_dividend = exercise_spot*np.exp(.04*exercise_time)-exercise_market
print(f"Model quote: {exercise_fair:.9f}; residual: {exercise_market-exercise_fair:.9f} points")
print(f"Implied continuous rate: {exercise_rate:.9%}; premium: {(exercise_rate-.04)*10000:.9f} bp")
print(f"Dividend compatible with 4%: {exercise_implied_dividend:.9f} points")
print(f"Calendar P&L: {-multiplier*(7-5):.2f} EUR")
```
<Editor id="basis-exercise" />

## Chapter Summary

- Basis is futures minus spot; a model residual compares the quote with specified carry assumptions. Neither is automatically profit.
- Ex-dividend entitlement and cash payment dates have different jobs. Curve ratios move each cash flow to the appropriate date.
- Executable carry depends on trade direction, spreads, borrowing, stock loan, and funding. Futures variation margin makes dated cash accounting essential.
- Inverse pricing reads implied inputs conditional on independent anchors. Unrestricted financing and dividends cannot both be recovered from the same futures quotes alone.
- Fit quality, parameter identification, quote consistency, and predictive usefulness are different checks. Reprice every inferred input and preserve held-out observations.
- Calendar-residual convergence can accompany losses. Reconcile actual quantities and price changes before discussing an investment signal.

Continue with [The Greeks and Hedging](./greeks-hedging.md) to derive first-, second-, and higher-order sensitivities and reconcile exact repricing with funded hedge behavior. [Advanced Portfolio Construction and Analysis](./2.0-overview.md) supplies the later estimation, covariance, and portfolio-cost connections.

## Sources and Market Context

The worked dataset above is invented. For actual markets, consult the applicable version of exchange specifications and index methodology:

- [CME: Understanding Stock Index Futures](https://www.cmegroup.com/content/dam/cmegroup/education/files/understanding-stock-index-futures.pdf), for cash/futures carry and market mechanics.
- [Eurex: EURO STOXX 50 Index Futures](https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Futures-160088) and [Index Dividend Futures](https://www.eurex.com/ex-en/markets/did/eqt-idx-div-fut/EURO-STOXX-50-Index-Dividend-Futures-946316), for product-specific contracts and dividend periods.
- [STOXX: DAX Equity Index Calculation Guide](https://www.stoxx.com/document/Indices/Common/Indexguide/DAX_Equity_Calculation_Guide.pdf), for performance-index and dividend conventions.
- [Federal Reserve: Decomposing Hedge Funds' U.S. Treasury Exposures](https://www.federalreserve.gov/econres/notes/feds-notes/decomposing-hedge-funds-u-s-treasury-exposures-20260622.html), June 22, 2026. Its approximately $830 billion estimate concerns Treasury cash–futures basis positions in September 2025, not equity-index trading volume or profit. Treasury delivery baskets, conversion factors, and cheapest-to-deliver options require a distinct pricing treatment.
