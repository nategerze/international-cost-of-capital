"""Run: python -m unittest test_calculations.py"""
import unittest
from calculations import compute

class CostOfCapitalTests(unittest.TestCase):
    def test_colombia_class_example(self):
        a=compute(.8,.3,.35,.065,.04,.12,.015)
        self.assertAlmostEqual(a['Levered beta'],1.022857142857,places=9)
        self.assertAlmostEqual(a['Cost of equity'][0],.1064857142857,places=9)
        self.assertAlmostEqual(a['Cost of equity'][1],.1916,places=9)
        self.assertAlmostEqual(a['Pretax cost of debt'][1],.1361538461538,places=9)
        self.assertAlmostEqual(a['WACC'][0],.085265,places=8)
        self.assertAlmostEqual(a['WACC'][1],.16067,places=8)
    def test_equal_yields(self):
        a=compute(1.2,.3,.25,.065,.04,.04,.0111)
        for k in ['Cost of equity','Pretax cost of debt','After-tax cost of debt','WACC']:
            self.assertAlmostEqual(*a[k],places=12)
    def test_zero_debt(self):
        a=compute(1.2,0,.25,.065,.04,.08,.0111)
        for i in [0,1]:self.assertAlmostEqual(a['WACC'][i],a['Cost of equity'][i],places=12)
    def test_override_does_not_change_usd(self):
        a=compute(.9,.3,.25,.065,.04,.08,.0111)
        b=compute(.9,.3,.25,.065,.04,.08,.0111,.04)
        for k in ['Cost of equity','Pretax cost of debt','After-tax cost of debt','WACC']:
            self.assertAlmostEqual(a[k][0],b[k][0],places=12)
        self.assertNotEqual(a['WACC'][1],b['WACC'][1])
if __name__=='__main__':unittest.main()
