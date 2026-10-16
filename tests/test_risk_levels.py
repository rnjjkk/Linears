import unittest
from unittest.mock import patch
import numpy as np

from longtripletun.risk_levels import (select_risk_levels, compare_metrics, describe_return_change,
                         evaluate_risk_levels, render_comparison)
from longtripletun.rebalance import try_rebalancing


class RiskLevelsTests(unittest.TestCase):
    def setUp(self):
        self.screen = {'tickers': ['A', 'B'], 'weights': np.array([1., 0.]),
                       'covariance': np.diag([0.0004, 0.0001]), 'shortlist': ['B']}

    def test_train_order_and_valid_weights(self):
        result = try_rebalancing(self.screen)
        levels = select_risk_levels(self.screen, result)
        self.assertEqual(len(levels), 3)
        risks = [item['weights'] @ self.screen['covariance'] @ item['weights'] for item in levels]
        self.assertEqual(risks, sorted(risks))
        for option, variance in zip(levels, risks):
            self.assertAlmostEqual(option['weights'].sum(), 1)
            self.assertTrue((option['weights'] >= 0).all())
            self.assertAlmostEqual(variance, option['trial']['train_variance'])
            self.assertLess(variance, result['old_variance'])
        np.testing.assert_array_equal(self.screen['weights'], [1, 0])
        np.testing.assert_array_equal(levels[0]['weights'], result['weights'])

    def test_fewer_choices_and_no_improvement(self):
        for additions in [(0.1,), (0.05, 0.1)]:
            levels = select_risk_levels(self.screen, try_rebalancing(self.screen, additions))
            self.assertEqual(len(levels), len(additions))
        same = {**self.screen, 'covariance': np.full((2, 2), 0.0004)}
        self.assertEqual(select_risk_levels(same, try_rebalancing(same)), [])

    def test_ties_collapsed(self):
        result = try_rebalancing(self.screen)
        for row in result['trials']:
            row['train_variance'] = 0.0003
            row['train_daily_volatility_percent'] = np.sqrt(0.0003) * 100
        self.assertEqual(len(select_risk_levels(self.screen, result)), 1)

    def test_real_example_percent_and_money(self):
        old = dict(status='ok', net_total_return_percent=29.4888, net_daily_volatility_percent=1.2175)
        new = dict(status='ok', net_total_return_percent=17.6773, net_daily_volatility_percent=1.0709)
        diff = compare_metrics(old, new)
        self.assertAlmostEqual(diff['return_change_pp'], -11.8115)
        self.assertAlmostEqual(diff['profit_difference_money'], -11811.5)
        self.assertAlmostEqual(diff['sd_money_at_initial_capital'], 1070.9)
        self.assertAlmostEqual(diff['sd_reduction_percent'], 12.04106776, places=6)
        self.assertIn('กำไรสะสมลดลง', diff['explanation'])

    def test_loss_zero_and_crossing(self):
        self.assertIn('ขาดทุนสะสมลดลง', describe_return_change(-20, -10))
        self.assertIn('ขาดทุนสะสมเพิ่มขึ้น', describe_return_change(-10, -20))
        self.assertIn('เป็นกำไร', describe_return_change(-10, 5))
        self.assertIn('เป็นขาดทุน', describe_return_change(10, -5))
        self.assertIn('ไม่คำนวณ', describe_return_change(0, 5))
        zero = dict(status='ok', net_total_return_percent=0, net_daily_volatility_percent=0)
        self.assertIsNone(compare_metrics(zero, zero)['sd_reduction_percent'])
        self.assertIsNone(compare_metrics(zero, zero)['profit_change_percent'])

    def test_missing_test_keeps_train_selection(self):
        result = try_rebalancing(self.screen)
        original = dict(strategy='original', status='ok', net_total_return_percent=0,
                        net_daily_volatility_percent=0)
        missing = dict(strategy='proposed', status='unavailable: missing price',
                       net_total_return_percent=None, net_daily_volatility_percent=None)
        equal = {**original, 'strategy': 'equal_weight'}
        cost = {'summary': [original, missing, equal],
                'daily': [{'strategy': strategy, 'net_nav': 100} for strategy in ['original', 'equal_weight']]}
        with patch('longtripletun.risk_levels.evaluate_costs', return_value=cost):
            evaluated = evaluate_risk_levels('unused', '2020-01-01', ['2020-01-02', '2020-01-03'], self.screen, result)
        self.assertEqual(len(evaluated['levels']), 3)
        self.assertEqual(len(evaluated['rows']), 5)
        self.assertIn('ประเมินไม่ได้', render_comparison(evaluated))


if __name__ == '__main__':
    unittest.main()
