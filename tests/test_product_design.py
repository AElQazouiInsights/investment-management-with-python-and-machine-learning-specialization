"""Capstone checks against payoff integrals, analytic Greeks, and signed ledgers."""
import contextlib
import io
import json
from pathlib import Path
import re
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]


class ProductDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = {}
        cls.cells = re.findall(r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"',
                               (ROOT/'docs/product-design-capstone.md').read_text(),re.S)
        with contextlib.redirect_stdout(out := io.StringIO()):
            for code,name in cls.cells:
                exec(compile(code,name,'exec'),cls.ns)
        cls.charts = {}
        for line in out.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    def test_executed_ledgers_include_both_quote_sides_once(self):
        n = self.ns
        self.assertEqual(len(self.cells),6)
        self.assertEqual(len(self.charts),4)
        for p in n['products'].values():
            cash = 100-1-100/1.05-p['units']*(n['call'](100,100)+.1)+p['units']*(n['call'](100,p['cap'])-.1)
            self.assertAlmostEqual(cash,0,places=10)
            self.assertAlmostEqual(n['value'](100,p)+1+.2*p['units'],100,places=10)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)

    def test_original_payoffs_integrate_to_marks_in_all_stresses(self):
        n = self.ns
        for p in n['products'].values():
            for s,t,r,v in [(100,1,.05,.2),(80,.5,.07,.30),(110,.5,.05,.2),(140,.5,.03,.15)]:
                scale=v*np.sqrt(t)
                forward=s*(1+r)**t
                cuts=[-12]+[(np.log(k/forward)+scale**2/2)/scale for k in (100,p['cap'])]+[12]
                def integrand(z):
                    spot=forward*np.exp(-scale**2/2+scale*z)
                    payoff=100+p['units']*(max(spot-100,0)-max(spot-p['cap'],0))
                    return payoff*norm.pdf(z)
                expected=sum(quad(integrand,a,b,epsabs=1e-9)[0] for a,b in zip(cuts,cuts[1:]))/(1+r)**t
                self.assertAlmostEqual(n['value'](s,p,t,r,v),expected,places=8)

    def test_maturity_regions_objective_crossover_and_cash(self):
        n = self.ns
        a,b = n['products'].values()
        for p in (a,b):
            spots=np.r_[np.linspace(0,200,401),1e4]
            expected=100+p['units']*(np.maximum(spots-100,0)-np.maximum(spots-p['cap'],0))
            np.testing.assert_allclose(n['payment'](spots,p),expected)
            for s in (0,90,110,140):
                self.assertAlmostEqual(n['value'](s,p,0),n['payment'](s,p))
        self.assertGreaterEqual(n['payment'](110,a),108)
        self.assertLess(n['payment'](110,b),108)
        crossover=100+(n['payment'](200,a)-100)/b['units']
        self.assertAlmostEqual(crossover,119.51802516200615)
        self.assertAlmostEqual(n['payment'](crossover,a),n['payment'](crossover,b))
        self.assertAlmostEqual(n['cash_six_months'],100*np.sqrt(1.05))

    def test_numerical_greeks_match_independent_analytic_legs(self):
        n = self.ns
        for p in n['products'].values():
            delta=gamma=vega=0.
            rho=-100/(1.05**2)
            for k,sign in ((100,1),(p['cap'],-1)):
                d1=(np.log(100/k)+np.log1p(.05)+.5*.2**2)/.2
                units=sign*p['units']
                delta+=units*norm.cdf(d1)
                gamma+=units*norm.pdf(d1)/20
                vega+=units*100*norm.pdf(d1)*.01
                rho+=units*k/(1.05**2)*norm.cdf(d1-.2)
            risk=n['risks'](p)
            np.testing.assert_allclose([risk['Delta (shares)'],risk['Gamma (shares/GBP)'],risk['Vega (GBP/vol point)'],risk['Rate (GBP/rate point)']],
                                       [delta,gamma,vega,rho*.01],atol=1e-7,rtol=1e-5)

    def test_hedge_cash_ledger_and_local_remainder(self):
        n = self.ns
        p=n['chosen'];d=n['delta']
        initial=n['value'](100,p)-100*d+n['hedge_cash']
        self.assertAlmostEqual(initial,n['value'](100,p))
        for move,change in zip(n['moves'],n['exact_hedged']):
            final=n['value'](100+move,p)-(100+move)*d+n['hedge_cash']
            self.assertAlmostEqual(final-initial,change,places=10)
        for move in (-.1,.1):
            change=n['value'](100+move,p)-n['value'](100,p)-d*move
            self.assertAlmostEqual(change,.5*n['gamma']*move**2,delta=1e-7)
        self.assertLess(n['gamma'],0)

    def test_cap_experiment_reprices_every_budget_and_fee_boundary(self):
        n = self.ns
        for cap in n['cap_grid']:
            p=n['design'](cap)
            self.assertAlmostEqual(100/1.05+1+p['units']*p['entry'],100)
            self.assertGreaterEqual(n['payment'](110,p),100)
            self.assertLessEqual(n['payment'](110,p),n['payment'](cap,p))
        boundary=n['maximum_fee']
        self.assertAlmostEqual(n['payment'](110,n['design'](110,boundary)),108)
        self.assertLess(n['payment'](110,n['design'](110,boundary+.001)),108)
        self.assertAlmostEqual(n['payment'](110,n['design'](110,2)),106.01307212255826)
        for cap,fee in ((100,1),(110,-1),(110,5),(np.nan,1)):
            with self.assertRaises(ValueError):n['design'](cap,fee)


if __name__=='__main__':
    unittest.main()
