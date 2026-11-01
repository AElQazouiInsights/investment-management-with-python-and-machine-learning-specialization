---
title: "Derivatives, Options, and Structured Products"
permalink: /d.0-overview
description: "Understand forwards, futures, options, Black–Scholes, the Greeks, and structured payoffs through everyday explanations and worked Python examples."
---

# Derivatives, Options, and Structured Products

**Question:** can we agree on a future purchase price, protect against a fall, or design an investment that pays only when a particular movement occurs?

A **derivative** is a contract whose value depends on something else, called its **underlying**. For example, a contract linked to a share price is a derivative; the share is its underlying. The contract specifies who must pay, how much, and when.

Start with a future purchase. An investment costs £100 today, but you want to buy it in one year. One arrangement commits you to a purchase price now. Another gives you the choice to buy later. That difference—an obligation versus a choice—will lead us from forwards to options and then to combinations of contracts.

**Track status:** [Forward Contracts](./d.1-forwards.md), [Futures and Forwards Compared](./d.2-futures.md), [Options and Replication](./d.3-options.md), [Random Motion and Itô's Lemma](./random-motion-ito.md), and [Deriving and Using Black–Scholes](./black-scholes.md) are available. The remaining chapters below are planned and will be developed in order. This additional learning track follows Portfolio Management Fundamentals.

## Where to Begin

You need percentages, averages, basic algebra, and a little Python. We will introduce the calculus needed for Itô's lemma beside the examples, before using it in the Black–Scholes derivation.

Useful foundations from [Portfolio Management Fundamentals](./1.0-overview.md) are:

- **Returns and units:** distinguish a pound amount from a percentage return.
- **Compounding and discounting:** £100 invested at 5% for one year becomes £105; £105 due in one year is worth £100 today at that rate.
- **Asset prices and uncertainty:** [Strategies Beyond Diversification](./1.3-diversification.md) introduces simulated price paths.
- **Dated payments:** [Fundamentals of Asset-Liability Management](./1.4-alm.md) explains bonds, present value, and interest-rate sensitivity.

The recommended sequence continues from this track to [Advanced Portfolio Construction and Analysis](./2.0-overview.md). The latter studies the estimates behind portfolio allocations; this track studies contractual payments and their replication. Both share the same cash-flow and return conventions. The [Black–Scholes convention comparison](./black-scholes.md#_1-connect-the-portfolio-and-pricing-conventions) distinguishes portfolio arithmetic means, GBM drift, quoted rates, and pricing probabilities. The portfolio course can also be studied directly after the foundations.

## The Learning Sequence

### Forward Contracts

**Available:** [start the lesson](./d.1-forwards.md).

Agree today on a price for a purchase next year. Define spot price, delivery price, maturity, and long/short positions. Price a forward by comparing it with buying and financing the asset. Then value an existing contract and use it to hedge a future purchase.

**Experiment:** change today's asset price while keeping the existing delivery price fixed. Explain why a contract that began with zero value can later have a positive or negative value.

### Futures and Forwards Compared {#futures}

**Available:** [study futures and daily settlement](./d.2-futures.md).

Reuse the forward example to introduce futures, exchanges, clearing, initial margin, and daily variation margin. Follow the cash paid or received each day and compare that timing with a forward settled at maturity. Distinguish collateral from an option premium and a quoted futures price from a forecast.

**Experiment:** compare two price paths with the same endpoint. Examine cumulative settlement and the cash required along the way. Explain the assumptions under which forward and futures quotes coincide, and why uncertain interest rates can make them differ.

### Options and Replication {#options}

**Available:** [study options and replication](./d.3-options.md).

Introduce calls and puts as rights rather than obligations. Build payoff tables before plotting them. Separate premium, maturity payoff, and financed profit. Establish put–call parity and solve a two-outcome example using an asset holding and cash.

**Experiment:** change the final asset price and identify which right is exercised. Reconcile the replicated payment in both outcomes before introducing a continuous-time model.

### Random Motion and Itô's Lemma {#ito}

**Available:** [Random Motion and Itô's Lemma](./random-motion-ito.md).

Begin with rates of change and curvature. Show why an unchanged average input can produce a changed average curved output. Introduce Brownian increments and quadratic variation, derive Itô's lemma from a second-order expansion, and apply it to a log price.

**Experiment:** compare transformations of simulated increments with the first-order and curvature-adjusted calculations. Explain what changes as the time step shrinks.

### Deriving and Using Black–Scholes {#black-scholes}

**Available:** [Deriving and Using Black–Scholes](./black-scholes.md).

Match an option's exposure with the underlying asset and a cash account. Explain self-financing rebalancing, derive the pricing equation, and work through the normal integrals leading to European call and put prices. Separate the pricing distribution from a real-world return forecast. Connect put–call parity to a forward payoff and reconcile discrete stock and futures hedge ledgers.

**Experiment:** compare call and put prices under matched assumptions, verify parity, and inspect expiry and low-volatility limits.

### The Greeks and Hedging {#greeks}

**Planned.** Explain delta, gamma, theta, vega, and rho as answers to specific questions about changing inputs. Estimate each with a small numerical change before using its analytical formula. State units, including a one-percentage-point volatility change and the chosen day-count convention for theta. Combine sensitivities across positions and examine discrete delta hedging.

**Experiment:** compare exact repricing with delta and delta–gamma approximations. Follow the cash account during hedging and investigate the effect of rebalancing frequency.

### Spreads and Basic Option Combinations

**Planned.** Construct bull and bear spreads, covered calls, protective puts, and collars one position at a time. Explain bought and sold legs, debit and credit, limited gains and losses, and break-even calculations. Price each component before adding the signed values.

**Experiment:** change a strike and explain the change in entry cost, payoff, and aggregate Greeks.

### Straddles, Strangles, Butterflies, and Condors

**Planned.** Build strategies related to the size and location of price movements. Distinguish expiry payoffs from pre-expiry values and sensitivities. For a call butterfly, buy one lower-strike call, sell two middle-strike calls, and buy one upper-strike call; verify every region of the payoff before using the combined graph.

**Experiment:** vary strike spacing and time remaining. Compare the price of the ingredients, financed profit, and the position's sensitivity to volatility.

### Building Structured Products

**Planned.** Combine bonds and options into a funded investment. Allocate a £100 budget between a maturity payment and upside participation, then add caps or exchange downside exposure for premium income. Explain issuer credit exposure, early-sale value, fees, and which promises apply only at maturity.

**Experiment:** change the funding rate or option cost and calculate the participation rate the budget can actually buy.

### Design, Price, and Explain a Product

**Planned.** Choose an investment objective, identify every bond and option position, reconcile the initial budget, and calculate maturity payments and pre-maturity risks. Explain the result in ordinary language, including what the investor gives up in exchange for each benefit.

**Exercise:** compare two constructions with the same budget. Support the explanation with a payment table, a payoff graph, and a sensitivity calculation.

## How to Study Each Chapter

Follow **everyday explanation → numbers → calculation → explained graph → Python → experiment → worked exercise**. Run cells in order, then predict the effect of one changed assumption before changing it. Python and charts run in your browser.

Keep three questions separate throughout the track:

1. **What does the contract promise to pay?** Read its terms and payment dates.
2. **What is that promise worth today?** State the pricing assumptions and show the replication or discounting calculation.
3. **What does the investor gain or lose?** Include the cost of entering and financing the position, using a common valuation date.

**Check your reasoning:** a contract pays £20 in one year but costs £12 today. Is £20 the profit? No: it is the maturity payoff. At a 5% annual financing rate, the £12 cost grows to £12.60, leaving a maturity-date profit of £7.40 before other costs.

Begin with [Forward Contracts](./d.1-forwards.md).
