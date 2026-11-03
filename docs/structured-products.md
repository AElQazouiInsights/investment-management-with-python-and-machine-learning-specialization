---
title: "Building Structured Products"
permalink: /structured-products
description: "Allocate a £100 budget between bonds and options, calculate participation and caps, explain downside-funded income, and reconcile fees, early-sale values, and issuer exposure."
---

# Building Structured Products

**Question:** an investor pays £100 today. How can we allocate that money between a maturity payment and an option payoff, and what does the investor give up to obtain each feature?

A **structured product** packages a payment rule into one investment. Its name does not create value: the bond and option ingredients must fit the budget. [Spreads and Basic Option Combinations](./option-combinations.md) supplies the signed legs; [The Greeks and Hedging](./greeks-hedging.md) supplies local risk. We use those tools to design funded investments, with all payments measured per **£100 invested**.

## 1. The Budget Comes Before the Payoff Diagram

Use the same no-dividend share starting at **£100**, European cash-equivalent options, **one year**, **20% annual volatility**, and a **5% effective annual safe cash rate**. Our initial replicating portfolios use a default-free zero-coupon bond and perfectly performing options. Fees, execution costs, and the legal difference between owning that portfolio and holding an issuer's note are introduced explicitly below.

A **zero-coupon bond** pays one fixed amount at maturity and nothing before. A bond paying £100 in one year costs $100/1.05=£95.238095$. Spending the remaining **£4.761905** on options uses the full £100 budget.

The investor pays the £100 from their own capital. Thus **nominal profit** is the final payment less £100. To compare with putting the same money into safe cash, subtract **£105**, its one-year cash alternative. A £100 maturity floor protects nominal principal under our performance assumptions; it does not preserve the forgone interest or purchasing power.

The code keeps forward and option discounting explicit. In this no-dividend teaching model, one safe rate determines both, as well as the bond price. A bank's unsecured borrowing spread is not substituted for a safe return to create extra option budget. Real equity carry and option discounting require compatible market inputs, as discussed in [Futures Basis, Dividends, and Implied Financing](./futures-basis.md).

```python:line-numbers
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

N, S0, T, cash_rate, sigma = 100., 100., 1., .05, .20
D, F = 1/(1+cash_rate), S0*(1+cash_rate)
terminal = np.linspace(0.,180.,361)
cash_payment = N*(1+cash_rate)

def black(forward,strike,remaining,discount,vol,kind="call"):
    if kind not in ("call","put") or not np.isfinite([forward,strike,remaining,discount,vol]).all():
        raise ValueError("Use finite inputs and call or put")
    if forward<0 or strike<=0 or remaining<0 or discount<=0 or vol<0:
        raise ValueError("Invalid forward, strike, time, discount, or volatility")
    if forward==0 or remaining==0 or vol==0:
        return discount*max(forward-strike if kind=="call" else strike-forward,0.)
    scale = vol*np.sqrt(remaining)
    d1 = np.log(forward/strike)/scale+.5*scale
    if kind=="call":
        return discount*(forward*norm.cdf(d1)-strike*norm.cdf(d1-scale))
    return discount*(strike*norm.cdf(scale-d1)-forward*norm.cdf(-d1))

def protected_terms(rate=.05,vol=.20,fee=0.,cap=None):
    if not np.isfinite([rate,vol,fee]).all() or rate<=-1 or vol<=0 or fee<0:
        raise ValueError("Use rate above -100%, positive volatility, and nonnegative fee")
    if cap is not None and (not np.isfinite(cap) or cap<=S0):
        raise ValueError("The cap strike must exceed the initial share price")
    discount = (1+rate)**(-T)
    forward = S0/discount
    bond_cost = N*discount
    option_budget = N-fee-bond_cost
    if option_budget<0:
        raise ValueError("The budget cannot fund this maturity floor and fee")
    option_cost = black(forward,S0,T,discount,vol)
    if cap is not None:
        option_cost -= black(forward,cap,T,discount,vol)
    units = option_budget/option_cost
    return {"Bond cost":bond_cost,"Option budget":option_budget,"Unit option cost":option_cost,
            "Option units":units,"Participation":units*S0/N,"Fee":fee}

def protected_payoff(final,units,cap=None):
    upside = np.maximum(np.asarray(final)-S0,0.)
    if cap is not None:
        upside = np.minimum(upside,cap-S0)
    return N+units*upside

def chart(name,title,series,x=terminal,xname="Final share price (GBP/share)",yname="Payment per GBP 100 invested",y_min=0.):
    print("<ECHARTS_DATA>"+json.dumps({name:{"type":"line","title":title,
        "xAxis":{"type":"value","name":xname,"min":float(min(x)),"max":float(max(x))},"yAxisName":yname,
        "yAxis":{"type":"value","min":y_min},
        "series":{label:np.column_stack([x,y]).tolist() for label,y in series.items()}}},allow_nan=False))

protected = protected_terms()
call_100 = black(F,100.,T,D,sigma)
call_120 = black(F,120.,T,D,sigma)
put_100 = black(F,100.,T,D,sigma,"put")
print(pd.Series(protected).to_string())
print(f"Call 100: {call_100:.9f}; call 120: {call_120:.9f}; put 100: {put_100:.9f} GBP/share")
```
<Editor id="structured-setup" />

Run cells in order. The funding/volatility experiment later also runs independently. All prices are synthetic model values until the executed example specifies bid/ask quotes.

## 2. Bond Plus Call: Buy a Floor and Some Upside

The £100-strike call costs **£10.386279 per share**. Our £4.761905 option budget buys:

$$n=\frac{4.761905}{10.386279}=0.458480\text{ call units}.$$

With initial share price and investment both £100, this is **45.8480% participation** in a positive share return. More generally, participation is $\alpha=nS_0/N$, so the maturity payment is:

$$W_T=N+\alpha N\max(S_T/S_0-1,0).$$

At a final share price of £140, the share return is 40%. The option adds $0.458480(40)=£18.339213$, so the investor receives **£118.339213**. At £80, the call expires worthless and the bond pays **£100**. Fractional option units describe an idealized per-note allocation; an issuer can aggregate many notes, while exchange contract multipliers and hedge rounding require scaling.

| Budget item | Amount today |
| --- | ---: |
| Bond paying £100 | £95.238095 |
| 0.458480 call units | £4.761905 |
| Total investment | **£100.000000** |

The graph compares the note's payment with the **£105 cash alternative**. The note returns principal below the strike but trails cash by £5. It overtakes cash only above **£110.905593**, found by solving $0.458480(S_T-100)=5$.

```python:line-numbers
protected_units = protected["Option units"]
protected_cash_break = S0+(cash_payment-N)/protected_units
print(f"Participation: {100*protected['Participation']:.6f}%; cash break-even share price: {protected_cash_break:.6f}")
print(f"Payment at 80: {protected_payoff(80,protected_units):.6f}; at 140: {protected_payoff(140,protected_units):.6f}")
chart("structuredProtected","Returning Principal Can Still Underperform Cash",{
    "Bond plus call":protected_payoff(terminal,protected_units),"Safe cash alternative":np.full_like(terminal,cash_payment)},y_min=90.)
```
<Editor id="structured-protected" />

**Check:** if the share finishes at £110, is the investment profitable? **Answer:** its £104.584803 payment gives a £4.584803 nominal gain, but it is **£0.415197 behind cash**. State the comparison before calling a result a gain or a loss.

## 3. Cap the Upside to Buy More Initial Participation

Keep the same £100 maturity bond, but buy the £100/£120 call spread instead of an uncapped call. Its price is **£7.169513**: pay £10.386279 for the lower call and receive £3.216767 for selling the upper call. The same £4.761905 budget now buys **0.664188 spread units**, or **66.4188% participation** up to a 20% share gain.

The payment is £100 plus 0.664188 times the share gain above £100, limited to a £20 share gain. Thus the maximum payment is **£113.283761**. At £110 it pays **£106.641881**, more than the uncapped version. At £140 it still pays £113.283761, less than the uncapped £118.339213.

The graph shows exactly where the added participation ends. The investor has exchanged distant upside for a steeper payoff between £100 and £120. The cap applies to the **underlying gain used in the formula**; it is not a 20% maximum return on the investment.

```python:line-numbers
cap_strike = 120.
capped = protected_terms(cap=cap_strike)
capped_units = capped["Option units"]
capped_maximum = N+capped_units*(cap_strike-S0)
capped_cash_break = S0+(cash_payment-N)/capped_units
print(pd.Series(capped).to_string())
print(f"Maximum payment: {capped_maximum:.6f}; cash break-even share price: {capped_cash_break:.6f}")
chart("structuredCapped","Higher Participation Is Purchased by Selling Distant Upside",{
    "Uncapped":protected_payoff(terminal,protected_units),
    "Capped at share price 120":protected_payoff(terminal,capped_units,cap_strike),
    "Safe cash alternative":np.full_like(terminal,cash_payment)},y_min=90.)
```
<Editor id="structured-capped" />

**Experiment:** lower the cap strike to £110 and reprice the spread. **Answer:** the spread costs £4.393168 and participation rises to **108.3934%**, but ends after a 10% share gain. The maximum payment falls to **£110.839343**. Participation can exceed 100% over a limited interval; its percentage alone does not rank two products.

## 4. Enhanced Income: Sell Downside Protection to Fund the Payment

Now sell **one £100 put** for £5.624375 and add that premium to the investor's £100. Invest **£105.624375** in the safe bond. It funds a fixed maturity amount of **£110.905593**, but the sold put creates a deduction when the share finishes below £100:

$$W_T=110.905593-\max(100-S_T,0).$$

This is a simple cash-settled **reverse-convertible-style** construction: extra income is financed by accepting downside exposure. All income is paid at maturity in this example. At £120 the investor receives £110.905593. At £80, the put deduction is £20 and the investor receives **£90.905593**. At zero, the payment is only **£10.905593**. There is no £100 floor.

The **10.9056% maximum one-year return** is conditional on the share finishing at or above £100. It is not an unconditional deposit yield. The nominal break-even share price is **£89.094407**; beating safe cash requires **£94.094407**. The graph makes the downside that funds the extra payment visible.

```python:line-numbers
income_bond_cost = N+put_100
income_face = income_bond_cost/D
def income_payoff(final):
    return income_face-np.maximum(S0-np.asarray(final),0.)

income_nominal_break = S0+N-income_face
income_cash_break = S0+cash_payment-income_face
print(f"Initial budget: bond {income_bond_cost:.6f} minus put proceeds {put_100:.6f} = {income_bond_cost-put_100:.6f}")
print(f"Maximum payment: {income_face:.6f}; nominal break-even: {income_nominal_break:.6f}; cash break-even: {income_cash_break:.6f}")
comparison_spots = np.array([0.,80.,100.,120.,140.])
comparison = pd.DataFrame({"Final share":comparison_spots,
    "Protected":protected_payoff(comparison_spots,protected_units),
    "Capped":protected_payoff(comparison_spots,capped_units,cap_strike),
    "Income":income_payoff(comparison_spots),"Cash":cash_payment})
print(comparison.to_string(index=False,float_format=lambda x:f"{x:.6f}"))
chart("structuredIncome","The Larger Payment Is Funded by Accepting Downside",{
    "Income construction":income_payoff(terminal),"Original investment":np.full_like(terminal,N),
    "Safe cash alternative":np.full_like(terminal,cash_payment)})
```
<Editor id="structured-income" />

**Check:** why do all three portfolios cost £100 despite different payments? They buy different combinations of states. Under the common pricing model, each has discounted expected payment £100, so each has pricing-measure expected maturity payment £105. That equality neither makes their risks identical nor supplies their physical expected returns. [Butterflies, Implied Distributions, and Tail Pricing](./implied-distributions.md) explains that distinction.

## 5. Fees Reduce What the Budget Can Buy

Suppose a **£1 distribution fee** is taken from the £100 payment at issue. The £100 maturity bond still costs £95.238095, leaving **£3.761905** for the uncapped call. Participation falls from **45.8480% to 36.2199%**. A 1% fee on invested capital consumes **21% of the original option budget**, because that budget was only £4.761905.

The graph varies the upfront fee while holding market inputs and the maturity floor fixed. Each pound of fee reduces participation by about **9.6281 percentage points** in this example. A fee above £4.761905 makes this £100-floor design infeasible at the stated issue price. The code reports that constraint rather than converting the negative option budget into an unintended short position.

```python:line-numbers
fee_one = protected_terms(fee=1.)
fees = np.linspace(0.,4.5,46)
fee_participation = np.array([protected_terms(fee=fee)["Participation"] for fee in fees])
print(f"GBP 1 fee: participation {100*fee_one['Participation']:.6f}%; fraction of original option budget {1/protected['Option budget']:.2%}")
try:
    protected_terms(fee=5.)
except ValueError as error:
    print(f"GBP 5 fee: {error}")
chart("structuredFees","A Small Notional Fee Can Consume a Large Option Budget",{
    "Participation":100*fee_participation},x=fees,xname="Upfront fee (GBP per GBP 100 invested)",yname="Upside participation (%)")
```
<Editor id="structured-fees" />

**Check:** are these fees the only reason an issue price can exceed model value? No. Execution costs and issuer/distributor margins also matter. Keep each cost visible in the budget; the final exercise adds bid/ask execution explicitly.

## 6. A Maturity Floor Is Not an Early-Sale Price Floor

Six months later, suppose the share is **£80**, volatility is **25%**, and the safe effective annual rate is **7%**. The original uncapped note still owns **0.458480 call units** and a bond paying £100 at the original expiry. These quantities were fixed at issue; we do not redesign the note using today's budget.

The bond is now worth $100/\sqrt{1.07}=£96.673649$. The call, with half a year remaining, is worth **£1.126685 per unit**, so the whole portfolio is worth **£97.190212**. Selling at that model mid-value realizes **−£2.809788** relative to the original £100, before any exit spread. The original safe cash alternative would now be worth **£102.469508**.

The graph varies today's share price under those same six-month inputs. It compares an **early-sale mark** with the **£100 promised at maturity**. The latter remains a future payment, not a current bid. An issuer's actual repurchase quote can additionally reflect credit, liquidity, and dealing costs.

```python:line-numbers
remaining, new_rate, new_vol = .5, .07, .25
new_discount = (1+new_rate)**(-remaining)
def protected_mark(spot):
    new_forward = spot/new_discount
    return N*new_discount+protected_units*black(new_forward,S0,remaining,new_discount,new_vol)

early_value = protected_mark(80.)
early_cash = N*(1+cash_rate)**(T-remaining)
current_spots = np.linspace(40.,160.,121)
early_marks = np.array([protected_mark(spot) for spot in current_spots])
print(f"Fixed original call units: {protected_units:.9f}; bond mark: {N*new_discount:.9f}")
print(f"Early-sale mark: {early_value:.9f}; nominal P&L: {early_value-N:.9f}; difference from cash: {early_value-early_cash:.9f}")
chart("structuredEarlySale","Reprice the Existing Note, Keeping Its Original Units",{
    "Six-month model mark":early_marks,"Maturity promise":np.full_like(current_spots,N)},
    x=current_spots,xname="Share price after six months (GBP/share)",yname="GBP per original GBP 100 investment",y_min=90.)
```
<Editor id="structured-early-sale" />

**Check:** does the mark below £100 contradict the construction? No. The bond pays £100 at maturity if it performs, but its current discounted value can be lower. Selling early also gives up the remaining option exposure.

## 7. The Issuer's Promise Has Its Own Risk

Owning a default-free bond and options in a separately held portfolio is different from buying an **unsecured issuer note** promising the same formula. The note investor normally has a claim against the issuer, not direct ownership of its hedge assets. The contractual floor depends on the issuer meeting its obligation.

For a transparent stress, assume issuer default occurs at maturity and recovery is **40% of the entire contractual payment**. At a final share price of £80, the protected formula promises £100, but this recovery convention pays **£40**. At £140, the promise is £118.339213 and recovery is **£47.335685**.

The graph compares promised and recovered payments under that explicit convention. This is a loss scenario, not a credit-pricing model: no default probability has been inferred, and no issuer spread has been treated as free funding. Real recovery definitions, seniority, collateral, and investor claims depend on the contract.

```python:line-numbers
recovery_fraction = .40
promised_payments = protected_payoff(terminal,protected_units)
default_payments = recovery_fraction*promised_payments
print(f"At share 80: promise {protected_payoff(80,protected_units):.6f}; recovery {recovery_fraction*protected_payoff(80,protected_units):.6f}")
print(f"At share 140: promise {protected_payoff(140,protected_units):.6f}; recovery {recovery_fraction*protected_payoff(140,protected_units):.6f}")
chart("structuredIssuer","A Contractual Floor Depends on the Promised Payment Being Made",{
    "Issuer performs":promised_payments,"40% recovery stress":default_payments})
```
<Editor id="structured-issuer" />

## 8. Experiment: Change the Terms Available at Issue

The independent widget designs a **new uncapped £100-floor product**, with no fees. Change the safe cash rate or annual volatility. The rate changes the bond discount factor, option discount factor, and no-dividend forward consistently. The curve shows participation across volatility inputs at the selected rate; the orange diamond marks the chosen volatility.

At 5% and 20% volatility, participation is **45.8480%**. At a zero cash rate, the bond consumes all £100 and participation is **zero**. Higher volatility makes the call more expensive and reduces participation for a fixed rate. A higher safe rate also changes the call price, so both sides of the budget are repriced.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_structured_budget_echart,
    cash_rate_percent=widgets.FloatSlider(value=5.,min=0.,max=8.,step=.5,description="Cash rate (%)",continuous_update=False),
    volatility_percent=widgets.FloatSlider(value=20.,min=10.,max=40.,step=2.5,description="Volatility (%)",continuous_update=False),
)
widget_instance
```
<Editor id="structured-budget-widget" />

**Predict, then try:** increase the cash rate from 5% to 8% with volatility at 20%. **Answer:** the bond cost falls to £92.592593 and the call price rises to £11.933041. The larger option budget dominates here, raising participation to **62.0748%**. These are terms for new issuance, not a change to an existing investor's fixed participation.

## 9. Worked Exercise: Price an Executable Capped Product

An investor pays **£100**, including a **£1 upfront fee**, for a one-year £100-floor product capped at share price £120. Keep the original 5% rate and 20% volatility. Give each call a synthetic **£0.10 bid/ask half-spread** around its model price; buy the £100 call at its ask and sell the £120 call at its bid. The bond trades at the stated discount factor without a spread.

1. Calculate the option budget and executable spread cost.
2. Find participation and the maximum maturity payment.
3. Calculate payment, nominal profit, and performance against cash at final share prices £80, £110, and £140.
4. Reconcile the issue price with the portfolio's model mid-value.

**Work it through.** The option budget is **£3.761905**. The lower-call ask is £10.486279 and the upper-call bid £3.116767, so the spread costs **£7.369513**. The budget buys **0.510469 spread units**, giving **51.0469% participation** and maximum payment **£110.209372**.

The graph compares this executed design with the original fee-free, model-mid capped design. Their participation rates differ because their budgets and entry costs differ. The floor remains £100, while the cash alternative remains £105.

```python:line-numbers
exercise_fee, half_spread = 1., .10
exercise_budget = N-exercise_fee-N*D
lower_ask, upper_bid = call_100+half_spread,call_120-half_spread
executable_spread = lower_ask-upper_bid
exercise_units = exercise_budget/executable_spread
exercise_spots = np.array([80.,110.,140.])
exercise_payments = protected_payoff(exercise_spots,exercise_units,cap_strike)
model_mid_value = N*D+exercise_units*(call_100-call_120)
execution_cost = exercise_units*2*half_spread
print(f"Budget: bond {N*D:.9f} + spread purchase {exercise_units*executable_spread:.9f} + fee {exercise_fee:.9f}")
print(f"Participation: {100*exercise_units*S0/N:.9f}%; maximum payment: {N+exercise_units*20:.9f}")
print(pd.DataFrame({"Final share":exercise_spots,"Payment":exercise_payments,
    "Nominal profit":exercise_payments-N,"Difference from cash":exercise_payments-cash_payment}).to_string(index=False))
print(f"Model mid-value: {model_mid_value:.9f}; fee: {exercise_fee:.9f}; execution cost: {execution_cost:.9f}; sum: {model_mid_value+exercise_fee+execution_cost:.9f}")
chart("structuredExercise","Reconcile Fees and Execution with the Participation Offered",{
    "Fee-free model design":protected_payoff(terminal,capped_units,cap_strike),
    "Executed design with fee":protected_payoff(terminal,exercise_units,cap_strike),
    "Safe cash alternative":np.full_like(terminal,cash_payment)},y_min=90.)
```
<Editor id="structured-exercise" />

**Completed answer:** the three payments are **£100, £105.104686, and £110.209372**. Nominal profits are £0, £5.104686, and £10.209372; differences from cash are **−£5, +£0.104686, and +£5.209372**. The portfolio's model mid-value is **£98.897906**. Adding the £1 fee and **£0.102094 execution cost** reconciles the £100 paid. A £100 issue price and a £100 maturity floor do not imply a £100 immediate resale value.

## Takeaways

- Fund the maturity payment first, then calculate exactly how many option units the remaining budget buys.
- Participation, the underlying cap, and the investment's maximum return are different quantities.
- Enhanced income can be paid for by selling downside protection; read the resulting loss region.
- Separate nominal profit from performance against cash, and new issuance terms from an existing note's early-sale value.
- Fees, execution costs, issuer performance, and the legal claim affect what the investor actually receives.

Next: [Design, Price, and Explain a Product](./d.0-overview.md#structured-products-capstone). The final capstone will combine these tools into one fully reconciled product design and investor explanation.
