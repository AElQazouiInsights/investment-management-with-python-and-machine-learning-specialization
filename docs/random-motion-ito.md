---
title: "Random Motion and Itô's Lemma"
permalink: /random-motion-ito
description: "Build Itô's formula from slopes, curvature, Brownian increments, and quadratic variation, then derive the drift of a log price with worked Python experiments."
---

# Random Motion and Itô's Lemma

**Question:** if random changes average to zero, why can a curved transformation of those changes have a nonzero average change?

Imagine measuring the area of a square. Increasing its side length adds a slightly larger area than an equal decrease removes. The average side length can stay the same while the average area rises. This small curvature effect is the starting point for **Itô's lemma**: a rule for finding how a function changes when its input follows continuous random motion.

In [Options and Replication](./d.3-options.md), an asset had only two possible future values. We now build a model with many small random changes. We will explain the calculus beside the arithmetic, distinguish a simulated path from a forecast, and derive the correction needed when transforming a price into a log price.

All paths and parameters below are invented teaching inputs. Time is measured in **years**. The early examples use a dimensionless numerical input; the final application uses **GBP per unit**. Run cells in order. The grid-refinement experiment also runs independently.

```python:line-numbers
import json
import numpy as np
import pandas as pd
```
<Editor id="ito-setup" />

## 1. Start with a Curve, Not a Stochastic Formula

Let $f(x)=x^2$: take a number and square it. Our input is $x=2$, so the output is 4. Give the input an equally likely increase or decrease of 0.1:

| Input | Change in input | Squared output | Change from 4 |
| ---: | ---: | ---: | ---: |
| 1.9 | −0.1 | 3.61 | −0.39 |
| 2.1 | +0.1 | 4.41 | +0.41 |

The average input is still 2. The average output is $(3.61+4.41)/2=4.01$, rather than 4. Squaring bends upward, so the positive change wins by a little. Neither row describes a financial return yet; both input and output are dimensionless.

### Slope Measures the First Effect

A **derivative** measures the local slope: how much the output changes per small unit change in the input. Write $h$ for an input change. Expanding the square gives:

$$f(x+h)-f(x)=(x+h)^2-x^2=2xh+h^2.$$

Divide by $h\ne0$: the average slope over that move is $2x+h$. As $h$ approaches zero, this approaches $2x$. We write the derivative as $f'(x)=2x$. At $x=2$, the slope is 4. A **first-order approximation** therefore predicts a change of $4h$: +0.40 or −0.40 in our example.

The **second derivative** measures how the slope itself changes. Since $f'(x)=2x$, we have $f''(x)=2$. The curvature term is $\tfrac12 f''(x)h^2=h^2$. It adds **+0.01 in either direction**. Thus the exact changes are $+0.40+0.01=+0.41$ and $-0.40+0.01=-0.39$.

For a sufficiently smooth general function, a second-order **Taylor expansion** writes:

$$f(x+h)-f(x)\approx f'(x)h+\tfrac12 f''(x)h^2.$$

For a square this is exact; for other functions, higher-order terms remain. “First order” refers to a term proportional to $h$, and “second order” to one proportional to $h^2$.

The graph shows the square curve and its tangent line at 2. The tangent is $4+4(x-2)$. It meets the curve at 2 but lies below it on both sides. The outlined diamonds mark the two outcomes in the table.

```python:line-numbers
centre = 2.0
changes = np.array([-0.1, 0.1])
inputs = centre + changes
exact_changes = inputs ** 2 - centre ** 2
linear_changes = 2 * centre * changes
curvature_changes = changes ** 2
curvature_table = pd.DataFrame({
    "Input": inputs, "Squared output": inputs ** 2,
    "Exact change": exact_changes, "Slope term": linear_changes,
    "Curvature term": curvature_changes,
})
print(curvature_table.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
print(f"Average input: {inputs.mean():.4f}; average squared output: {(inputs ** 2).mean():.4f}")
curve_x = np.linspace(1.5, 2.5, 101)
print("\n<ECHARTS_DATA>" + json.dumps({"itoCurvature": {
    "type": "line", "title": "Equal Input Moves Do Not Cancel After Squaring",
    "xAxis": {"type": "value", "name": "Input x (dimensionless)", "min": 1.5, "max": 2.5},
    "yAxisName": "Squared output (dimensionless)",
    "series": {"Square": np.column_stack([curve_x, curve_x ** 2]).tolist(),
               "Tangent at 2": np.column_stack([curve_x, 4 + 4 * (curve_x - 2)]).tolist(),
               "Two outcomes": np.column_stack([inputs, inputs ** 2]).tolist()},
    "seriesOptions": {
        "Tangent at 2": {"lineStyle": {"type": "dashed"}},
        "Two outcomes": {"type": "scatter", "symbol": "diamond", "symbolSize": 18,
                         "itemStyle": {"color": "#ea580c", "borderColor": "#ffffff", "borderWidth": 2, "opacity": 1}},
    },
}}, allow_nan=False))
```
<Editor id="ito-curvature" />

**Experiment:** replace the two changes with `[-0.2, 0.2]`. Predict the average output before rerunning: the curvature addition becomes $0.2^2=0.04$, giving 4.04. Doubling the shock multiplies this addition by four. Restore `[-0.1, 0.1]` afterwards.

**Check:** for the straight-line function $f(x)=3x+1$, does the average output rise under the same symmetric moves? No. Its slope is 3 and its second derivative is zero. The outputs at 1.9 and 2.1 are 6.7 and 7.3; their average is 7, exactly the output at 2.

## 2. Random Changes Scale with the Square Root of Time

A **Brownian motion**, written $W_t$, is a mathematical model of continuous random motion. It starts at $W_0=0$. Its changes over non-overlapping time intervals are independent, and over an interval of length $\Delta t$:

$$\Delta W=\sqrt{\Delta t}\,Z,\qquad Z\sim N(0,1).$$

$\Delta$ means a finite change. $N(0,1)$ is the standard normal, or bell-shaped, distribution with mean zero and variance one. Each interval uses a fresh independent draw of $Z$. **Expectation**, denoted $\mathbb E$, is the probability-weighted average over possible outcomes. **Variance** measures the average squared deviation from the mean; standard deviation is its square root. Therefore:

$$\mathbb E[\Delta W]=0,\qquad \mathbb E[(\Delta W)^2]=\Delta t,
\qquad \operatorname{SD}(\Delta W)=\sqrt{\Delta t}.$$

With time in years, Brownian motion has units of **square-root years**. Over one year its standard deviation is 1; over a quarter year it is 0.5. Over $1/256$ of a year it is $1/16=0.0625$. A standardized draw $Z=-1.2$ in that last interval gives $\Delta W=-1.2/16=-0.075$ square-root years.

Why not multiply the noise by $\Delta t$? Independent variances add. Four quarter-year increments have total variance $4\times0.25=1$, matching the one-year variance. If we used $\Delta t Z$, their total variance would be $4\times0.25^2=0.25$, and would shrink toward zero as we added more intervals. That would erase the intended uncertainty.

### Simulate Grid Observations of Four Paths

The code uses a fixed random seed so you can reproduce the illustration. Each column is a separate path; rows are time increments. `np.cumsum` accumulates changes, and an initial zero row records the starting point.

The chart's horizontal axis is now **elapsed time**, unlike an option payoff graph. A line joins the simulated observations for readability. Those straight segments are drawing choices, not the true Brownian path between observations. Brownian paths are continuous but almost surely have no ordinary time derivative.

```python:line-numbers
path_steps = 256
path_dt = 1 / path_steps
path_rng = np.random.default_rng(20261101)
path_increments = np.sqrt(path_dt) * path_rng.standard_normal((path_steps, 4))
brownian_paths = np.vstack([np.zeros(4), np.cumsum(path_increments, axis=0)])
path_times = np.linspace(0., 1., path_steps + 1)
print(f"Time interval: {path_dt:.8f} years; increment SD: {np.sqrt(path_dt):.4f} sqrt(years)")
print(f"A standardized shock of -1.2 gives: {-1.2 * np.sqrt(path_dt):.4f} sqrt(years)")
print("\n<ECHARTS_DATA>" + json.dumps({"itoBrownianPaths": {
    "type": "line", "title": "Four Simulated Brownian Paths, All Starting at Zero",
    "xAxis": {"type": "value", "name": "Elapsed time (years)"},
    "yAxisName": "Brownian value W (square-root years)",
    "series": {f"Path {i + 1}": np.column_stack([path_times, brownian_paths[:, i]]).tolist() for i in range(4)},
}}, allow_nan=False))
```
<Editor id="ito-brownian" />

None of these paths is expected to sit at zero throughout the year. Zero is the mean over all possible paths at each date, not a restriction on an individual realization. Brownian motion itself is not an asset price: it can be negative and has different units.

**Experiment:** change `path_steps` to 64. The interval becomes four times longer, so the increment standard deviation doubles to 0.125. The theoretical one-year variance remains 1. Reseeding and changing the array shape generates a different path sample; it is not a refinement of the same four paths. Restore 256 before continuing.

**Check:** if the interval becomes four times shorter, what happens to a deterministic change proportional to time and to the noise standard deviation? The deterministic change is divided by four; the noise standard deviation is divided by two. The squared noise remains of the same order as elapsed time.

## 3. Add Squared Changes: Quadratic Variation

Ordinary changes can cancel. Squared changes cannot. For observations at dates $0=t_0<t_1<\cdots<t_n=T$, define the finite-grid sum:

$$Q_n=\sum_{i=0}^{n-1}(W_{t_{i+1}}-W_{t_i})^2.$$

This has units of years. The **quadratic variation** is the limiting accumulated squared change as the largest interval shrinks. Brownian motion's quadratic variation over $[0,T]$ is $T$.

First check a hand-built four-step illustration. Increments $[+0.5,-0.5,+0.5,+0.5]$ sum to 1, but their squared sum is $4\times0.25=1$. Another sign sequence could finish at zero and still have squared sum 1. These fixed-size teaching steps are not Gaussian draws; they illustrate why cancellation of changes and accumulation of squared changes are different operations.

For actual independent Gaussian increments on $n$ equal intervals, $\mathbb E[Q_n]=T$. The sampling variance is $2T^2/n$, so:

$$\operatorname{SD}(Q_n)=T\sqrt{2/n}.$$

For one year and 16 intervals, this is about 0.353553 years; for 4,096 intervals, about 0.022097 years. The normal fourth-moment identity $\mathbb E[Z^4]=3$ gives $\operatorname{Var}((\Delta W)^2)=3(\Delta t)^2-(\Delta t)^2=2(\Delta t)^2$. Adding these independent variances gives the result above. Thus $Q_n$ approaches $T$ in mean square; the variance of its error goes to zero. This is a limiting statement, not a claim that every finite-grid squared increment equals its interval length.

### Observe One Path on Nested Grids

Generate 4,096 fine increments once. To obtain 16 coarse increments, sum consecutive groups of 256 fine increments. To obtain 64, sum groups of 64. Every grid ends at the same $W_T$; only the observation frequency changes.

The graph compares the sampled squared sum with the one-year target. For comparison with a smooth path, normalize Brownian values by the square root of one year and time by one year. Both plotted squared sums are then dimensionless; over this one-year horizon, the Brownian numbers are unchanged. The normalized smooth path $x(t)=t/(1\text{ year})$ has squared-increment sum $n(1/n)^2=1/n$, which tends to zero. The horizontal labels are interval counts, not dates, and their spacing is categorical.

```python:line-numbers
fine_steps = 4096
fine_rng = np.random.default_rng(20261101)
fine_increments = fine_rng.standard_normal(fine_steps) / np.sqrt(fine_steps)
grid_counts = np.array([16, 64, 256, 1024, 4096])
qv_rows = []
for count in grid_counts:
    increments = fine_increments.reshape(count, -1).sum(axis=1)
    qv_rows.append([count, increments.sum(), np.sum(increments ** 2), np.sqrt(2 / count), 1 / count])
qv_table = pd.DataFrame(qv_rows, columns=[
    "Intervals", "Endpoint W", "Squared sum (years)", "Theoretical SD (years)", "Smooth squared sum",
])
print(qv_table.to_string(index=False, float_format=lambda value: f"{value:.6f}"))
print("\n<ECHARTS_DATA>" + json.dumps({"itoQuadraticVariation": {
    "type": "line", "title": "Random Squared Changes Accumulate as the Grid Gets Finer",
    "xAxis": {"type": "category", "name": "Number of intervals", "data": [str(n) for n in grid_counts]},
    "yAxisName": "Normalized squared-increment sum (dimensionless)",
    "series": {"Brownian squared sum": qv_table["Squared sum (years)"].tolist(),
               "Brownian target": [1.] * len(grid_counts),
               "Smooth path t": qv_table["Smooth squared sum"].tolist()},
    "seriesOptions": {"Brownian target": {"lineStyle": {"type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="ito-quadratic-variation" />

The sampled Brownian sum can move above or below 1 and need not improve at every refinement. A single path is an illustration of the theorem, not its proof. The variance calculation explains why the error shrinks in a probabilistic sense.

**Experiment:** replace the seed with `20261102`. The endpoint and finite-grid errors change, but the target and theoretical standard deviations do not. Restore `20261101` and rerun before continuing.

**Check:** at 64 one-year intervals, the squared-sum standard deviation is $\sqrt{2/64}=0.176777$. Is a sampled value of 1.05 inconsistent with a target of 1? No. The difference is much smaller than one such standard deviation. The target describes a limit and an expectation, not an exact finite-sample restriction.

## 4. See Why the Ordinary Chain Rule Misses a Term

For a differentiable path, you may know the rule “change in the square equals twice the current value times its change.” For Brownian motion, discarding every squared change loses an amount that survives accumulation.

At each grid interval, ordinary algebra still gives the exact identity:

$$W_{i+1}^2-W_i^2=2W_i\Delta W_i+(\Delta W_i)^2.$$

Add the intervals. Intermediate squared values cancel, leaving:

$$W_T^2-W_0^2=2\sum_i W_i\Delta W_i+Q_n.$$

For our four hand-built increments, the values at the **start** of the intervals are $[0,0.5,0,0.5]$. The first-order sum is $2[0(0.5)+0.5(-0.5)+0(0.5)+0.5(0.5)]=0$. The final square is 1. The missing amount is exactly the squared sum, 1.

For a Brownian path, $Q_n$ approaches $T$, not zero. This gives the Itô identity:

$$W_T^2=2\int_0^T W_t\,dW_t+T,\qquad W_0=0.$$

The **Itô integral** here is the limit of the sums using each interval's starting value. That timing matters: $W_i$ is known before the next random increment. It does not look ahead. Under the usual square-integrability conditions, these sums converge in mean square. For example, over one year this identity implies $\int_0^1 W_t\,dW_t=(W_1^2-1)/2$; if $W_1=0$, the integral is −0.5, not zero.

The next graph uses the 256-interval version of our fixed path. Compare the exact square, the first-order sum, and the first-order sum **plus elapsed time**. The last is the finite-grid Itô approximation. Adding the **actual cumulative squared increments** instead would reproduce the exact square at every grid point, up to rounding.

```python:line-numbers
square_steps = 256
square_increments = fine_increments.reshape(square_steps, -1).sum(axis=1)
square_times = np.linspace(0., 1., square_steps + 1)
square_path = np.r_[0., np.cumsum(square_increments)]
square_exact = square_path ** 2
square_first_order = np.r_[0., np.cumsum(2 * square_path[:-1] * square_increments)]
square_qv = np.r_[0., np.cumsum(square_increments ** 2)]
square_ito = square_first_order + square_times
square_discrete = square_first_order + square_qv
print(f"Exact endpoint square: {square_exact[-1]:.6f} years")
print(f"First-order sum: {square_first_order[-1]:.6f} years")
print(f"Squared-increment sum: {square_qv[-1]:.6f} years")
print(f"Itô approximation endpoint error: {square_ito[-1] - square_exact[-1]:.6f} years")
print(f"Maximum exact discrete-identity error: {np.max(np.abs(square_discrete - square_exact)):.2e}")
print("\n<ECHARTS_DATA>" + json.dumps({"itoSquareIdentity": {
    "type": "line", "title": "The Squared-Increment Term Cannot Be Dropped",
    "xAxis": {"type": "value", "name": "Elapsed time (years)"},
    "yAxisName": "Squared Brownian value or accumulated terms (years)",
    "series": {"Exact square": np.column_stack([square_times, square_exact]).tolist(),
               "First order only": np.column_stack([square_times, square_first_order]).tolist(),
               "First order + time": np.column_stack([square_times, square_ito]).tolist()},
    "seriesOptions": {"First order only": {"lineStyle": {"type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="ito-square-identity" />

The exact square is always nonnegative, but the first-order sum need not be. The time-corrected finite-grid approximation can also fall slightly below zero; it does not enforce positivity. Its signed endpoint error is $T-Q_n$: if the sampled squared sum is 1.05 over one year, the approximation is 0.05 below the exact square.

**Experiment:** set `square_steps = 1024` and rerun this cell. You observe the same underlying fine sample at more dates. Check that the endpoint of the exact square is unchanged, the exact discrete identity still holds, and the approximation error equals $1-Q_n$. Restore 256 afterwards.

**Check:** why not use the average of the interval's starting and ending values? Algebra gives $2\sum_i[(W_i+W_{i+1})/2]\Delta W_i=W_T^2$ exactly. That is a different sampling rule, using the endpoint as well. Its stochastic limit is associated with the Stratonovich convention. It is not the left-endpoint Itô integral defined above; changing the timing changes the correction.

## 5. Derive Itô's Formula for a General Diffusion

A **diffusion** combines a predictable local trend with Brownian noise. Write:

$$dX_t=a(t,X_t)\,dt+b(t,X_t)\,dW_t.$$

The coefficient $a$ is the **drift**, the conditional mean-change rate. The coefficient $b$ is the **diffusion coefficient**, the local random-change scale. Their values depend only on information available at the current time. If $X$ is dimensionless, $a$ has units per year and $b$ per square-root year. For locally constant values $a=0.1$ and $b=0.3$, an interval of 0.01 years gives a mean change of 0.001 and noise standard deviation $0.3\sqrt{0.01}=0.03$.

The differential notation describes a limiting model. A short-step numerical approximation is $\Delta X\approx a\Delta t+b\Delta W$. If $a$ and $b$ are constant, this is also the exact increment distribution of an arithmetic Brownian diffusion.

Let $F(t,x)$ be a function of both time and the state. Its **partial derivative** $F_t$ changes time while holding the state fixed. $F_x$ changes the state while holding time fixed; $F_{xx}$ is its second state derivative. A local expansion gives:

$$\Delta F\approx F_t\Delta t+F_x\Delta X+\tfrac12F_{xx}(\Delta X)^2.$$

Substitute the state increment. Its square is:

$$ (\Delta X)^2\approx a^2(\Delta t)^2+2ab\Delta t\Delta W+b^2(\Delta W)^2.$$

As the grid is refined, the accumulated time-squared and time-times-noise terms vanish under the usual regularity conditions. The accumulated squared-noise term survives. For example, over one year, $n(1/n)^2=1/n$ vanishes, while $\sum(\Delta W)^2$ approaches 1. Brownian quadratic variation supplies the extra drift term.

For a diffusion with well-defined dynamics and a function with one continuous time derivative and two continuous state derivatives, Itô's formula is:

$$\boxed{dF(t,X_t)=\left(F_t+aF_x+\tfrac12b^2F_{xx}\right)dt+bF_x\,dW_t.}$$

All coefficients and derivatives are evaluated at the current $(t,X_t)$. The displayed expansion explains the terms; the rigorous stochastic result justifies the limiting passage. The shorthand rules $(dW)^2=dt$, $dt\,dW=0$, and $(dt)^2=0$ summarize these limits. **They do not say that a realized finite increment satisfies $(\Delta W)^2=\Delta t$.** A draw $Z=2$ gives $(\Delta W)^2=4\Delta t$; only the accumulated fluctuation around time vanishes in the appropriate limit.

### Work Every Term in a Small Example

Use the dimensionless state $X=2$, drift $a=0.1$ per year, and diffusion coefficient $b=0.3$ per square-root year. Set $F(t,x)=x^2+ct$ with $c=0.02$ per year, so the output remains dimensionless. At this state:

- $F_t=c=0.02$ per year: the explicit effect of time.
- $F_x=2x=4$: the local slope.
- $F_{xx}=2$: the curvature.
- The transformed drift is $0.02+0.1(4)+\tfrac12(0.3)^2(2)=0.51$ per year.
- The transformed noise coefficient is $0.3(4)=1.2$ per square-root year.

For $\Delta t=0.01$ and illustrative shocks $\Delta W=\pm0.1$, the Itô approximation predicts changes $0.0051\pm0.12$, or **+0.1251 and −0.1149**. Direct substitution uses $X_{t+\Delta t}=2+0.001\pm0.03$, giving changes **+0.125161 and −0.114959**. Finite-step errors remain even though the limiting formula is exact.

The bars compare direct substitution, slope-and-time only, and the Itô approximation for those two diagnostic shocks. They are not the whole Gaussian outcome distribution. Their average happens to match the exact Gaussian expectation here because a quadratic depends only on the first two moments.

```python:line-numbers
state, drift, diffusion, time_coefficient = 2., 0.1, 0.3, 0.02
small_dt = 0.01
diagnostic_dw = np.array([-1., 1.]) * np.sqrt(small_dt)
state_change = drift * small_dt + diffusion * diagnostic_dw
transformed_exact = (state + state_change) ** 2 + time_coefficient * small_dt - state ** 2
transformed_linear = time_coefficient * small_dt + 2 * state * state_change
transformed_drift = time_coefficient + 2 * state * drift + diffusion ** 2
transformed_noise = 2 * state * diffusion
transformed_ito = transformed_drift * small_dt + transformed_noise * diagnostic_dw
exact_expected_change = transformed_drift * small_dt + drift ** 2 * small_dt ** 2
print(pd.DataFrame({"Brownian change": diagnostic_dw, "Direct change": transformed_exact,
                    "Slope + time": transformed_linear, "Itô approximation": transformed_ito}).to_string(index=False))
print(f"Transformed drift: {transformed_drift:.6f} per year; noise coefficient: {transformed_noise:.6f} per sqrt(year)")
print(f"Exact conditional expected change: {exact_expected_change:.6f}; Itô leading term: {transformed_drift * small_dt:.6f}")
print("\n<ECHARTS_DATA>" + json.dumps({"itoLocalTransformation": {
    "type": "bar", "title": "Account for Time, Slope, and Curvature",
    "xAxis": {"type": "category", "name": "Illustrative standardized shock", "data": ["Z = -1", "Z = +1"]},
    "yAxisName": "Change in F (dimensionless)",
    "series": {"Direct substitution": transformed_exact.tolist(), "Slope + time": transformed_linear.tolist(),
               "Itô approximation": transformed_ito.tolist()},
}}, allow_nan=False))
```
<Editor id="ito-general-formula" />

**Experiment:** set `diffusion = 0.0`. The curvature drift disappears, and both diagnostic outcomes become the same deterministic change. The small residual $a^2(\Delta t)^2=0.000001$ is an ordinary finite-step Taylor error. Restore 0.3 afterwards.

**Check:** if diffusion doubles to 0.6, does its curvature contribution double? No: $b^2$ rises from 0.09 to 0.36, so the contribution quadruples. The noise coefficient doubles from 1.2 to 2.4, while the full transformed drift becomes $0.02+0.4+0.36=0.78$ per year.

## 6. Experiment: Refine the Grid on the Same Random Path

The slider chooses the grid power $k$, with **$n=2^k$ intervals**. For example, $k=4$ gives 16 intervals and $k=8$ gives 256. The helper reconstructs the same 4,096 fine increments with seed `20261101` and groups them exactly as in the visible calculations above.

The first graph compares the exact square, the first-order sum, and the time-corrected approximation. The second compares accumulated squared increments with elapsed time. Their endpoint differences are linked: the first graph's corrected error is $1-Q_n$, the negative of the second graph's squared-sum error.

Blue shows the exact or sampled quantity; orange shows the time-based comparison; grey dashes show the first-order-only calculation. Refining the grid reveals more of the same sample. It changes neither the final Brownian value nor the exact final square.

```python:line-numbers
import ipywidgets as widgets
import PortfolioOptimizationKit as pok

widget_instance = widgets.interactive(
    pok.show_ito_refinement_echart,
    grid_power=widgets.IntSlider(value=8, min=4, max=12, step=1,
                                 description="Grid power", continuous_update=False),
)
widget_instance
```
<Editor id="ito-refinement-widget" />

**Try it:** compare powers 4, 8, 10, and 12. Predict which outputs stay fixed before moving the control. The exact discrete identity should stay near machine precision; the time-corrected approximation generally improves at finer scales, but its error need not decrease at every step.

**Check:** if the final squared sum is 0.98, is the corrected square too high or too low? It is too high by $1-0.98=0.02$ years. The uncorrected first-order sum is too low by 0.98 years. More observations alone do not repair an approximation that omits the entire curvature term.

## 7. Prepare the Price Application: Log Returns and Continuous Rates

We now return to money. A price rising from £100 to £110 has a **simple return** of $110/100-1=0.10$, or 10%. Its **log return** is $\log(110/100)=0.095310$, or 9.5310% when displayed as a percentage. Here $\log$ means the natural logarithm, the inverse of the exponential function $e^x$: $e^{\log x}=x$ for $x>0$.

Taking the logarithm of a **ratio** keeps its argument dimensionless. Log returns add across adjacent periods: a move from £100 to £110 and then £121 has total log return $\log(1.1)+\log(1.1)=\log(1.21)$. Simple returns compound: $1.1\times1.1-1=21\%$, rather than 20%.

Our earlier financing examples used an effective annual rate $R=5\%$. The equivalent continuously compounded rate $r$ solves $e^r=1+R$, giving $r=\log(1.05)=0.048790$ per year. For any horizon $T$ in years, $(1.05)^T=e^{rT}$. Continuous and effective rates are two descriptions of the same growth when converted correctly; they are not numerically identical.

The graph compares simple and log returns for final prices between £60 and £140 from an initial £100. Both are zero at £100. The log curve lies below the simple-return line because logarithms are concave. We exclude zero and negative prices from this calculation because their real logarithms are not defined.

```python:line-numbers
return_prices = np.linspace(60., 140., 81)
simple_returns = return_prices / 100 - 1
log_returns = np.log(return_prices / 100)
effective_rate = 0.05
continuous_rate = np.log1p(effective_rate)
print(f"100 to 110: simple return {100 * (110 / 100 - 1):.4f}%; log return {100 * np.log(110 / 100):.4f}%")
print(f"Equivalent continuous rate: {continuous_rate:.8f} per year")
print(f"Half-year growth: {(1 + effective_rate) ** 0.5:.8f}; exponential form: {np.exp(continuous_rate * 0.5):.8f}")
print("\n<ECHARTS_DATA>" + json.dumps({"itoLogReturns": {
    "type": "line", "title": "Simple and Log Returns Measure the Same Move Differently",
    "xAxis": {"type": "value", "name": "Final asset price (GBP/unit)", "min": 60, "max": 140},
    "yAxisName": "Return from an initial 100 GBP (%)",
    "series": {"Simple return": np.column_stack([return_prices, 100 * simple_returns]).tolist(),
               "Log return": np.column_stack([return_prices, 100 * log_returns]).tolist()},
}}, allow_nan=False))
```
<Editor id="ito-log-returns" />

**Experiment:** calculate a fall from £100 to £90. Its simple return is −10%; its log return is approximately −10.5361%. Equal-sized simple gains and losses are not offsetting log returns.

**Check:** a 10% rise followed by a 10% fall finishes at £99. The total simple return is −1%; the total log return is $\log(1.1)+\log(0.9)=\log(0.99)\approx-0.0100503$. Both calculations describe the same loss.

## 8. Apply Itô to a Positive Asset Price

Assume a non-income-paying asset follows **geometric Brownian motion**:

$$dS_t=\mu S_t\,dt+\sigma S_t\,dW_t.$$

$S_t$ is its positive price in GBP per unit. The parameter $\mu$ is the instantaneous expected proportional growth rate, in inverse years. The volatility $\sigma$ is in inverse square-root years. These are model assumptions, not estimates from the simulated path. We use $S_0=£100$, $\mu=0.08$, and $\sigma=0.20$.

At a price of £100, the local price drift is $0.08(100)=£8$ per unit per year, and its noise coefficient is $0.20(100)=£20$ per unit per square-root year. Over 0.01 years, the leading mean price change is £0.08 and noise standard deviation is £2. The small-step description does not mean the price will actually rise by £8 every year.

### Calculate the Derivatives of the Logarithm

For $F(S)=\log(S/S_0)$, elementary differentiation gives $F_S=1/S$ and $F_{SS}=-1/S^2$. The negative second derivative means the logarithm bends downward. At £100, these derivatives are 0.01 and −0.0001 in the corresponding inverse-price units. There is no explicit time term in this function, so $F_t=0$.

Substitute $a=\mu S$, $b=\sigma S$ into Itô's formula:

$$d\log(S_t/S_0)
=\left(\frac{\mu S_t}{S_t}+\frac12\sigma^2S_t^2\frac{-1}{S_t^2}\right)dt
+\frac{\sigma S_t}{S_t}\,dW_t
=\left(\mu-\frac12\sigma^2\right)dt+\sigma\,dW_t.$$

Numerically, the log drift is $0.08-\tfrac12(0.20)^2=0.08-0.02=0.06$ per year. At the £100 state, the curvature calculation is also $\tfrac12(20)^2(-0.0001)=-0.02$ per year. The stochastic coefficient is $20(0.01)=0.20$ per square-root year.

Because the coefficients are constant, accumulating over time gives:

$$\log(S_T/S_0)=\left(\mu-\tfrac12\sigma^2\right)T+\sigma W_T,$$
$$S_T=S_0\exp\left[\left(\mu-\tfrac12\sigma^2\right)T+\sigma W_T\right].$$

For a one-year Brownian outcome $W_T=0.5$ square-root years, log return is $0.06+0.20(0.5)=0.16$, and the price is $100e^{0.16}=£117.351087$. With zero volatility, the formula reduces to deterministic growth $100e^{0.08T}$.

### Separate the Mean Price from the Median Price

Under this model, the mean price at time $T$ is $S_0e^{\mu T}$ and the median is $S_0e^{(\mu-\sigma^2/2)T}$. The median divides the distribution into equally probable upper and lower halves. At one year they are **£108.328707** and **£106.183655**, respectively. Neither is a guaranteed outcome.

The median corresponds to the median Brownian value, zero. The mean uses the normal exponential-average identity $\mathbb E[e^{\sigma W_T}]=e^{\sigma^2T/2}$: the factor $e^{0.02}$ exactly offsets the $e^{-0.02}$ curvature correction when taking the mean. Thus an 0.08 instantaneous drift corresponds to an expected one-year simple return of $e^{0.08}-1\approx8.3287\%$, not exactly 8%. Expected log return is 6%, not $\log$ of the expected price ratio.

The graph uses our fixed 256-interval Brownian sample. It compares the exact model price with the deliberately incorrect expression $S_0e^{\mu t+\sigma W_t}$, which omits the correction. The latter is too large by a factor $e^{\sigma^2t/2}$ on the same path: about **1.020201 at one year**. Its model drift would be $\mu+\sigma^2/2$, rather than the intended $\mu$. The vertical axis zooms in on the price range rather than starting at zero, so this relatively small difference is visible.

```python:line-numbers
initial_price, mu, sigma = 100., 0.08, 0.20
price_times = square_times
price_brownian = square_path
log_drift = mu - 0.5 * sigma ** 2
gbm_prices = initial_price * np.exp(log_drift * price_times + sigma * price_brownian)
uncorrected_prices = initial_price * np.exp(mu * price_times + sigma * price_brownian)
mean_prices = initial_price * np.exp(mu * price_times)
median_prices = initial_price * np.exp(log_drift * price_times)
print(f"Price drift: {mu:.4f} per year; log drift: {log_drift:.4f} per year")
print(f"One-year mean: {mean_prices[-1]:.6f} GBP; median: {median_prices[-1]:.6f} GBP")
print(f"One-year expected simple return: {100 * np.expm1(mu):.6f}%")
print(f"For W(1) = 0.5: {initial_price * np.exp(log_drift + sigma * 0.5):.6f} GBP")
print(f"Omitting correction multiplies the final price by: {uncorrected_prices[-1] / gbm_prices[-1]:.6f}")
print("\n<ECHARTS_DATA>" + json.dumps({"itoLogPrice": {
    "type": "line", "title": "The Log-Drift Correction Preserves the Intended Price Model",
    "xAxis": {"type": "value", "name": "Elapsed time (years)"},
    "yAxisName": "Asset price (GBP/unit)",
    "yAxis": {"type": "value", "name": "Asset price (GBP/unit)", "scale": True},
    "series": {"Exact GBM path": np.column_stack([price_times, gbm_prices]).tolist(),
               "Correction omitted": np.column_stack([price_times, uncorrected_prices]).tolist(),
               "Model mean": np.column_stack([price_times, mean_prices]).tolist(),
               "Model median": np.column_stack([price_times, median_prices]).tolist()},
    "seriesOptions": {"Correction omitted": {"lineStyle": {"type": "dashed"}},
                      "Model mean": {"lineStyle": {"type": "dotted"}},
                      "Model median": {"lineStyle": {"type": "dashed"}}},
}}, allow_nan=False))
```
<Editor id="ito-log-price" />

**Experiment:** double `sigma` to 0.40 while holding `mu` fixed. The log drift becomes $0.08-0.08=0$, the one-year median becomes £100, and the mean stays £108.328707. The distribution becomes wider. Set `sigma = 0.0` to check that the random path, mean, median, and uncorrected curve all coincide; then restore 0.20.

**Check:** does the 0.02 correction represent a fee or cash taken from an account? No. It comes from transforming a random price with a concave function. It reconciles price growth and log-price growth under the same model.

The $\mu$ used here describes an assumed real-world price process. It is not automatically the financing rate. In [Deriving and Using Black–Scholes](./black-scholes.md), replication and a self-financing hedge explain the pricing equation and why a pricing distribution uses a different drift. Itô's formula alone does not establish an option price. A call payoff's kink also fails the smoothness requirement at its strike; applying this twice-differentiable formula directly there is not justified.

## 9. Worked Exercise: Half a Year with a Different Volatility

Take a price of **£80**, instantaneous price drift $\mu=0.06$ per year, volatility $\sigma=0.30$ per square-root year, and horizon $T=0.5$ years.

1. Calculate the log drift and expected log return over the half-year.
2. If $W_T=0.2$ square-root years, calculate the realized log return and final price.
3. Calculate the model mean and median final prices. Is the realized price required to equal either?
4. With 64 equal intervals over this half-year, find the expected squared-increment sum and its standard deviation. If the sample sum is 0.54 years, what is the endpoint error when approximating $W_T^2$ by the first-order sum plus time?

::: details Hint
Subtract half of the **squared** volatility from the price drift, and multiply that log drift by elapsed years. The Brownian outcome already includes its time scaling: multiply it by volatility, without multiplying by another square root of time. For quadratic variation, keep the horizon $T=0.5$ in both the target and the standard-deviation formula.
:::

::: details Worked answer
The log drift is $0.06-0.5(0.30)^2=0.015$ per year. Expected half-year log return is $0.015(0.5)=0.0075$, or 0.75%.

The realized log return is $0.0075+0.30(0.2)=0.0675$. The final price is $80e^{0.0675}\approx£85.586421$.

The mean is $80e^{0.06(0.5)}\approx£82.436363$, and the median is $80e^{0.0075}\approx£80.602256$. The particular realization need equal neither.

The expected squared sum is 0.5 years and its standard deviation is $0.5\sqrt{2/64}\approx0.088388$ years. A sample squared sum of 0.54 gives a corrected-square error $0.5-0.54=-0.04$ years: the approximation is too low. The exact square for the stated Brownian endpoint is $0.2^2=0.04$ years; its first-order sum would be $0.04-0.54=-0.50$, and adding 0.5 would give zero.
:::

```python:line-numbers
exercise_initial, exercise_mu, exercise_sigma = 80., 0.06, 0.30
exercise_time, exercise_w, exercise_count = 0.5, 0.2, 64
exercise_log_drift = exercise_mu - 0.5 * exercise_sigma ** 2
exercise_expected_log = exercise_log_drift * exercise_time
exercise_realized_log = exercise_expected_log + exercise_sigma * exercise_w
exercise_price = exercise_initial * np.exp(exercise_realized_log)
exercise_mean = exercise_initial * np.exp(exercise_mu * exercise_time)
exercise_median = exercise_initial * np.exp(exercise_expected_log)
exercise_qv_sd = exercise_time * np.sqrt(2 / exercise_count)
print(f"Log drift: {exercise_log_drift:.6f} per year; expected log return: {exercise_expected_log:.6f}")
print(f"Realized log return: {exercise_realized_log:.6f}; final price: {exercise_price:.6f} GBP")
print(f"Mean: {exercise_mean:.6f} GBP; median: {exercise_median:.6f} GBP")
print(f"Expected squared sum: {exercise_time:.6f} years; SD: {exercise_qv_sd:.6f} years")
print(f"Corrected-square error if squared sum is 0.54: {exercise_time - 0.54:.6f} years")
```
<Editor id="ito-exercise" />

## Chapter Summary

- A curved function can turn zero-mean input changes into a nonzero average output change. The second derivative measures this effect locally.
- Brownian increments have standard deviation proportional to the square root of elapsed time. Their accumulated squares approach elapsed time rather than zero.
- Itô integrals use information at the start of each interval. Sampling conventions matter.
- Itô's formula combines explicit time change, the ordinary slope effect, and a curvature term equal to half the local variance rate times the second derivative.
- For geometric Brownian motion, log drift is price drift minus half the squared volatility. Mean price, median price, expected log return, and realized price answer different questions.

Continue with [Deriving and Using Black–Scholes](./black-scholes.md). Use these derivatives inside a fully accounted-for hedge, then derive and calculate European option prices.
