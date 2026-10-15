import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np

from longtripletun.recommendation import (load_policy, concentration_summary, assess_candidate,
                            build_recommendation, save_recommendation)


def metric(ret=10., sd=1., mdd=-10., status='ok'):
    return dict(net_total_return_percent=ret, net_daily_volatility_percent=sd,
                max_drawdown_percent=mdd, status=status)


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_gate_requires_all_three(self):
        old = metric()
        self.assertTrue(assess_candidate(old, metric(8, .95, -10), self.policy)['passed'])
        for new in [metric(7.9, .8, -9), metric(11, .96, -9), metric(11, .8, -10.1)]:
            self.assertFalse(assess_candidate(old, new, self.policy)['passed'])

    def test_loss_zero_missing(self):
        self.assertTrue(assess_candidate(metric(-20), metric(-10, .9, -9), self.policy)['passed'])
        self.assertFalse(assess_candidate(metric(sd=0), metric(sd=0), self.policy)['passed'])
        self.assertFalse(assess_candidate(metric(), metric(status='unavailable'), self.policy)['passed'])
        self.assertFalse(assess_candidate(metric(), metric(ret=float('nan')), self.policy)['passed'])

    def test_concentration_known_values(self):
        result = concentration_summary(['A', 'B', 'C'], [.6, .3, .1], np.eye(3))
        self.assertAlmostEqual(result['hhi'], .46)
        self.assertAlmostEqual(result['effective_equal_weight_holdings'], 1/.46)
        self.assertEqual(result['largest_weight_percent'], 60)
        self.assertEqual(result['weighted_pair_correlation'], 0)
        equal = concentration_summary(['A','B'], [.5,.5], np.ones((2,2)))
        self.assertEqual(equal['weighted_pair_correlation'], 1)
        one = concentration_summary(['A'], [1], [[0]])
        self.assertIsNone(one['weighted_pair_correlation'])

    def test_policy_rejects_bad_values(self):
        import json
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder)/'bad.json'
            for key, value in [('minimum_fit_days', 2), ('maximum_return_loss_pp', -1),
                               ('fit_fraction_of_train', 1), ('minimum_sd_reduction_percent', True)]:
                path.write_text(json.dumps({**self.policy, key: value}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_policy(path)

    def test_small_sample_abstains(self):
        days = [(date(2020, 1, 1)+timedelta(days=i)).isoformat() for i in range(150)]
        result = build_recommendation('unused', days, ['A'], [1])
        self.assertEqual(result['status'], 'keep_original')
        self.assertIn('ไม่พอ', result['reason'])

    def test_fit_and_validation_separate_and_test_cannot_change_decision(self):
        days = [(date(2020, 1, 1)+timedelta(days=i)).isoformat() for i in range(240)]
        screening = {'tickers': ['A','B'], 'weights': np.array([1.,0.])}
        option = dict(level=1, label='ระดับเดียว', trial={}, weights=np.array([.9,.1]))
        evaluated = {'rows': [{**metric(), 'strategy': 'original'},
                              {**metric(10, .9, -9), 'strategy': 'level_1'}]}
        with patch('longtripletun.recommendation.screen_candidates', return_value=screening) as fit_call, \
             patch('longtripletun.recommendation.try_rebalancing', return_value={}), \
             patch('longtripletun.recommendation.select_risk_levels', return_value=[option]), \
             patch('longtripletun.recommendation.evaluate_risk_levels', return_value=evaluated) as validation_call:
            result = build_recommendation('unused', days, ['A'], [1])
        self.assertEqual(fit_call.call_args.args[1], days[:180])
        self.assertEqual(validation_call.call_args.args[1], days[179])
        self.assertEqual(validation_call.call_args.args[2], days[180:])
        self.assertEqual(result['status'], 'alternatives_available')
        diagnostic = concentration_summary(['A'], [1], [[1]])
        # การแสดง Test ที่แย่มากต้องไม่ย้อนแก้การตัดสินใจ Validation
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, \
             patch('longtripletun.recommendation.evaluate_risk_levels', return_value={'test_result': 'bad'}) as test_call, \
             patch('longtripletun.recommendation.save_comparison'):
            save_recommendation(result, diagnostic, 'unused', days[-1], ['2021-01-01','2021-01-02'], folder)
            self.assertEqual(result['status'], 'alternatives_available')
            self.assertEqual(len(test_call.call_args.kwargs['levels']), 1)
            self.assertIn('A', (Path(folder)/'recommended_weights.csv').read_text(encoding='utf-8-sig'))

    def test_rejected_weights_not_exported_and_no_test_for_rejected(self):
        days = [(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(150)]
        decision = build_recommendation('unused', days, ['A'], [1])
        diagnostic = concentration_summary(['A'], [1], [[1]])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, patch('longtripletun.recommendation.evaluate_risk_levels') as call:
            text = save_recommendation(decision, diagnostic, 'unused', days[-1], ['2021-01-01','2021-01-02'], folder)
            call.assert_not_called()
            self.assertIn('คงพอร์ตเดิม', text)
            self.assertEqual(len((Path(folder)/'recommended_weights.csv').read_text(encoding='utf-8-sig').splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
