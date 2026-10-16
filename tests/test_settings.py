# ตรวจว่าค่าตั้งร่วมส่งผลจริงและปฏิเสธค่าที่ไม่ถูกต้อง
import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
import numpy as np
from longtripletun.settings import load_policy, validate_policy, split_days
from longtripletun.price_data import load_price_returns
from longtripletun.rebalance import try_rebalancing
from longtripletun.recommendation import build_recommendation
from longtripletun.holdout import evaluate_costs


class SettingsTests(unittest.TestCase):
    def test_invalid_settings_rejected(self):
        # ป้องกันค่าผิดชนิดและค่าที่ทำให้สูตรหรือการแบ่งข้อมูลใช้ไม่ได้
        base = load_policy()
        bad = [('train_fraction', 0), ('train_fraction', 1), ('train_fraction', True),
               ('pca_target', 0), ('pca_target', 1.1), ('fee_rate', -1), ('fee_rate', 0.02),
               ('shortlist_size', 0), ('shortlist_size', 1.5), ('minimum_train_days', 149),
               ('minimum_test_days', 1), ('candidate_weights', []), ('candidate_weights', [0]),
               ('candidate_weights', [1]), ('candidate_weights', [True]),
               ('candidate_weights', [0.1, 0.1]), ('candidate_weights', [float('nan')])]
        for key, value in bad:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_policy({**base, key: value})
        with self.assertRaises(ValueError):
            validate_policy({**base, 'shortlist_typo': 3})
        with self.assertRaises(ValueError):
            validate_policy({key: value for key, value in base.items() if key != 'fee_rate'})

    def test_configured_split_uses_calendar_before_missing_filter(self):
        # เปลี่ยนสัดส่วนแล้วเส้นแบ่งต้องถูกต้องแม้ Test มีราคาขาด
        policy = validate_policy({**load_policy(), 'train_fraction': 0.6})
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp)/'prices.csv'
            calendar = [(date(2020, 1, 1)+timedelta(days=i)).isoformat() for i in range(401)]
            with path.open('w', newline='') as f:
                out = csv.writer(f); out.writerow(['Date', 'Ticker', 'Close'])
                for i, day in enumerate(calendar):
                    out.writerow([day, 'A', '' if i == 350 else 100+i])
            days, _, audit = load_price_returns(path, ['A'], policy=policy)
            self.assertEqual(audit['train_boundary'], calendar[240])
            train, test = split_days(days, audit['train_boundary'], policy)
            self.assertEqual(len(train), 240)
            self.assertEqual(len(test), 158)
            self.assertEqual(audit['config'], policy)
            with self.assertRaises(ValueError):
                split_days(days, audit['train_boundary'], {**policy, 'minimum_test_days': 200})

    def test_candidate_weights_control_actual_trials(self):
        # สัดส่วนทดลองจาก config ต้องเปลี่ยนทั้งจำนวนทางเลือกและน้ำหนักที่เลือก
        policy = validate_policy({**load_policy(), 'candidate_weights': [0.12, 0.25]})
        screen = {'tickers': ['A', 'C'], 'weights': np.array([1., 0.]),
                  'covariance': np.array([[1., -0.5], [-0.5, 1.]]), 'shortlist': ['C']}
        result = try_rebalancing(screen, policy=policy)
        self.assertEqual({r['new_stock_weight_percent'] for r in result['trials']}, {12., 25.})
        np.testing.assert_allclose(result['weights'], [0.75, 0.25])

    def test_recommendation_propagates_shared_policy_to_fit_and_validation(self):
        # ทุกขั้นของด่านคำแนะนำต้องใช้ค่าชุดเดียวกับโปรแกรมหลัก
        policy = validate_policy({**load_policy(), 'fit_fraction_of_train': 0.7,
                                  'pca_target': 0.7, 'shortlist_size': 2,
                                  'candidate_weights': [0.12, 0.25], 'fee_rate': 0.005})
        days = [(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(300)]
        metric = {'status': 'ok', 'net_daily_volatility_percent': 1.,
                  'net_total_return_percent': 10., 'max_drawdown_percent': -10.}
        evaluated = {'rows': [{'strategy': 'original', **metric},
                             {'strategy': 'level_1', **metric, 'net_daily_volatility_percent': 0.8}]}
        option = {'level': 1, 'label': 'ต่ำ', 'trial': {}, 'weights': np.array([1.])}
        with patch('longtripletun.recommendation.screen_candidates', return_value={}) as screening, \
             patch('longtripletun.recommendation.try_rebalancing', return_value={}) as rebalance, \
             patch('longtripletun.recommendation.select_risk_levels', return_value=[option]), \
             patch('longtripletun.recommendation.evaluate_risk_levels', return_value=evaluated) as evaluate:
            result = build_recommendation('unused', days, ['A'], [1.], policy=policy)
        self.assertEqual(screening.call_args.args[1], days[:210])
        self.assertEqual(screening.call_args.kwargs['pca_target'], 0.7)
        self.assertEqual(screening.call_args.kwargs['shortlist_size'], 2)
        self.assertEqual(rebalance.call_args.kwargs['policy']['candidate_weights'], [0.12, 0.25])
        self.assertEqual(evaluate.call_args.args[2], days[210:])
        self.assertEqual(evaluate.call_args.kwargs['fee_rate'], 0.005)
        self.assertEqual(result['policy'], policy)
        self.assertEqual(result['status'], 'alternatives_available')

    def test_default_fee_comes_from_config(self):
        # ใช้ราคาคงที่เพื่อแยกผลค่าธรรมเนียมออกจากกำไรตลาด
        policy = validate_policy({**load_policy(), 'fee_rate': 0.005})
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp)/'prices.csv'
            days = ['2020-01-01', '2020-01-02', '2020-01-03', '2020-01-04']
            with path.open('w', newline='') as f:
                out = csv.writer(f); out.writerow(['Date', 'Ticker', 'Close'])
                for day in days:
                    for ticker in ['A', 'B']: out.writerow([day, ticker, 100])
            with patch('longtripletun.holdout.load_policy', return_value=policy):
                result = evaluate_costs(path, days[0], days[1:], ['A','B'], [1.,0.], [0.5,0.5])
            proposed = next(row for row in result['summary'] if row['strategy']=='proposed')
            self.assertAlmostEqual(proposed['initial_fee_percent_of_portfolio'], 0.5)
            self.assertAlmostEqual(proposed['net_final_nav'], 99.5)
