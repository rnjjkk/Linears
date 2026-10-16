# วิเคราะห์พอร์ตตัวอย่างทั้งหมดและสรุปผลเปรียบเทียบ
"""สำรวจทุกพอร์ตที่กำหนดไว้ด้วยฟังก์ชันเดิม ไม่ปรับสูตรเพื่อให้ผลชนะ."""
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path

from longtripletun.price_data import load_price_returns
from longtripletun.candidate_analysis import screen_candidates
from longtripletun.rebalance import try_rebalancing
from longtripletun.holdout import evaluate_costs
from longtripletun.report_charts import calculate_drawdown
from longtripletun.risk_levels import evaluate_risk_levels, save_comparison
from longtripletun.recommendation import build_recommendation, concentration_summary, save_recommendation


from longtripletun.project_paths import PROJECT_ROOT, EXAMPLES_DIR, REPORTS_DIR, default_price_path


def main():
    # วิเคราะห์พอร์ตตัวอย่างแต่ละชุดและบันทึกผลเปรียบเทียบ
    base = PROJECT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices', type=Path, default=default_price_path())
    args = parser.parse_args()
    from longtripletun.report_store import begin_report, publish_report
    output = begin_report(REPORTS_DIR / 'comparisons')
    files = [EXAMPLES_DIR / 'portfolio.csv', *sorted((EXAMPLES_DIR / 'portfolios').glob('*.csv'))]
    summary, contexts = [], []
    for path in files:
        print('Analyzing:', path.name, flush=True)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            holdings = list(csv.DictReader(stream))
        names = [row['ticker'].strip().upper() for row in holdings]
        weights = [float(row['weight_percent']) / 100 for row in holdings]
        days, _, audit = load_price_returns(args.prices, names)
        train = [day for day in days if day <= audit['train_boundary_80pct']]
        test = [day for day in days if day > audit['train_boundary_80pct']]
        screening = screen_candidates(args.prices, train, names, weights, pca_target=0.95)
        proposal = try_rebalancing(screening)
        levels = evaluate_risk_levels(args.prices, train[-1], test, screening, proposal)
        save_comparison(levels, output / path.stem)
        decision = build_recommendation(args.prices, train, names, weights)
        concentration = concentration_summary(screening['tickers'], screening['weights'], screening['covariance'])
        save_recommendation(decision, concentration, args.prices, train[-1], test, output / path.stem)
        print('Decision:', decision['reason'], flush=True)
        costs = evaluate_costs(args.prices, train[-1], test, screening['tickers'],
                               screening['weights'], proposal['weights'], fee_rate=0.001)
        original = next(row for row in costs['summary'] if row['strategy'] == 'original')
        for row in costs['summary']:
            result = {'portfolio': path.stem, **row, 'max_drawdown_percent': None,
                      'return_change_pp': None, 'sd_reduction_percent': None}
            if row['status'] == 'ok':
                nav = [day['net_nav'] for day in costs['daily'] if day['strategy'] == row['strategy']]
                result['max_drawdown_percent'] = calculate_drawdown(nav)[1]
                if original['status'] == 'ok':
                    result['return_change_pp'] = row['net_total_return_percent'] - original['net_total_return_percent']
                    sd = original['net_daily_volatility_percent']
                    result['sd_reduction_percent'] = (1 - row['net_daily_volatility_percent'] / sd) * 100 if sd else None
            summary.append(result)
        contexts.append({'portfolio': path.stem, 'input': holdings, 'price_source': str(args.prices.resolve()),
                         'train_start': train[0], 'train_end': train[-1], 'train_days': len(train),
                         'test_start': test[0], 'test_end': test[-1], 'test_days': len(test),
                         'pca_target': 0.95, 'fee_rate': 0.001, 'best': proposal['best'],
                         'new_weights': proposal['weight_changes'], 'assumptions': costs['assumptions']})
    with (output / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    (output / 'contexts.json').write_text(json.dumps(contexts, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# ผลสำรวจพอร์ตตัวอย่าง', '',
             'ใช้ CSV ราคาเดิมและวิธีเดิมทุกพอร์ต เป็นการสำรวจย้อนหลัง ไม่ใช่การทดสอบกลยุทธ์ใหม่แบบไม่เคยเห็นข้อมูล ดูข้อจำกัดใน README.md', '',
             '| Portfolio | Strategy | Status | Net return % | Daily SD % | Max drawdown % |',
             '|---|---|---|---:|---:|---:|']
    for row in summary:
        fmt = lambda value: '-' if value is None else f'{value:.4f}'
        lines.append(f"| {row['portfolio']} | {row['strategy']} | {row['status']} | {fmt(row['net_total_return_percent'])} | {fmt(row['net_daily_volatility_percent'])} | {fmt(row['max_drawdown_percent'])} |")
    (output / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    output, cleanup_warnings = publish_report(output)
    print('Saved:', output)
    for warning in cleanup_warnings:
        print('Kept old files:', warning)


if __name__ == '__main__':
    main()
