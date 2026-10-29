---
layout: home

title: "Investment Management with Python"
titleTemplate: "Portfolio Construction and Analysis"
description: "Study returns, risk, portfolio optimization, factor exposures, covariance estimation, Black–Litterman, and risk budgeting with worked Python examples."

hero:
  name: "Investment Management with Python"
  text: "Understand Risk. Build and Evaluate Portfolios."
  tagline: "Work through financial reasoning, Python calculations, and interactive experiments—from measuring returns to allocating risk."
  image:
    src: "/cppi.jpg"
    alt: "Financial Models and Strategies"
    class: "hero-image"
  actions:
    - theme: brand
      text: "Start with the Fundamentals"
      link: "/1.0-overview"
    - theme: alt
      text: "Explore Advanced Portfolio Analysis"
      link: "/2.0-overview"

features:
  - icon:
      src: "/math-integral.svg"
    title: "Portfolio Management Fundamentals"
    details: "Measure compounded returns and downside risk, construct efficient portfolios, and examine diversification and dynamic allocation."
    link: "/1.0-overview"
    linkText: "View the fundamental lessons"
  - icon:
      src: "/bell-shaped-graph.svg"
    title: "Advanced Portfolio Analysis"
    details: "Interpret factor exposures, estimate covariance, combine reference portfolios with views, and construct risk-budget allocations."
    link: "/2.0-overview"
    linkText: "View the advanced lessons"
  - icon:
      src: "/cosine-graph.svg"
    title: "Asset-Liability Management"
    details: "Value liabilities, measure bond sensitivity, and compare investment policies against funding goals."
    link: "/1.4-alm"
    linkText: "Study asset-liability management"
---

<style>
:root {
  --vp-home-hero-name-color: transparent;
  --vp-home-hero-name-background: linear-gradient(120deg, #bd34fe 30%, #41d1ff);
  --vp-home-hero-image-background-image: linear-gradient(-45deg, #bd34fe 50%, #47caff 50%);
  --vp-home-hero-image-filter: blur(44px);
}

@media (min-width: 640px) {
  :root {
    --vp-home-hero-image-filter: blur(56px);
  }
}

@media (min-width: 960px) {
  :root {
    --vp-home-hero-image-filter: blur(68px);
  }
}

.hero-image {
  width: 200%;
  height: auto;
  max-width: 1000px;
  display: block;
  margin: 0 auto;
}
</style>

## Choose Your Starting Point

Start with [Portfolio Management Fundamentals](./1.0-overview.md) if you are learning how returns, covariance, portfolio constraints, and liabilities enter an investment decision. Continue with [Advanced Portfolio Construction and Analysis](./2.0-overview.md) to examine the estimates and assumptions behind those decisions.

The advanced sequence ends with [Comparing Portfolio Decisions: A Capstone](./2.5-capstone.md), where you bring covariance estimation, Black–Litterman, risk attribution, and implementation costs into one comparison.

**Prepare for the next courses:** the [Machine Learning](./3.0-overview.md) and [Alternative Data](./4.0-overview.md) overviews introduce prerequisites, planned topics, and preparation exercises. Their executable chapters are under development.

## Learn by Calculating and Explaining

Each lesson connects a financial question to equations, worked examples, and editable Python cells. Run the cells in order, compare the output with the explanation, then change one assumption and explain what happens. Python executes in your browser; the interactive charts display the results of those calculations.

The emphasis is on interpreting evidence: distinguish model assumptions from historical observations, estimated risk from realized outcomes, and portfolio objectives from performance rankings.

## About This Resource

After completing EDHEC Business School's **Investment Management with Python and Machine Learning** specialization ([credential WUTZABL42PW8](https://www.coursera.org/account/accomplishments/specialization/WUTZABL42PW8)), I developed this collection of Python tools and teaching notes. The published lessons focus on portfolio construction and analysis: returns and risk, optimization, asset-liability management, factor models, covariance estimation, Black–Litterman, and risk budgeting.
