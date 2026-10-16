# จัดระดับทางเลือกพอร์ตและเปรียบเทียบผลตอบแทนกับความเสี่ยง
"""ทางเลือกความผันผวน 1–3 ระดับ เลือกด้วย Train และอธิบายผล Test เทียบพอร์ตเดิม."""
import csv
import math
from pathlib import Path

import numpy as np

from .holdout import evaluate_costs
from .report_charts import calculate_drawdown


def select_risk_levels(screening, rebalancing):
    # เลือกทางเลือกความผันผวนต่ำ กลาง และสูงจากช่วงฝึก
    """เลือกดีที่สุดต่อสัดส่วนก่อน แล้วเก็บ SD ต่ำสุด ใกล้กึ่งกลาง และสูงสุด.

    เก็บเฉพาะทางเลือกที่ลด variance Train ได้จริง ไม่จัดอันดับใหม่ด้วย Test.
    หาก SD ซ้ำกันเก็บเพียงหนึ่งตัว จึงอาจได้ 0–3 ระดับ.
    """
    original = np.asarray(screening['weights'], dtype=float)
    old_variance = rebalancing['old_variance']
    tolerance = max(1e-16, old_variance * 1e-10)
    by_allocation = {}
    for trial in sorted(rebalancing['trials'], key=lambda r: (r['train_variance'], r['ticker'])):
        if trial['train_variance'] < old_variance - tolerance:
            by_allocation.setdefault(trial['new_stock_weight_percent'], trial)
    distinct = []
    for trial in sorted(by_allocation.values(), key=lambda r: (r['train_variance'], r['ticker'])):
        if not distinct or trial['train_variance'] - distinct[-1]['train_variance'] > tolerance:
            distinct.append(trial)
    if len(distinct) > 3:
        midpoint = (distinct[0]['train_daily_volatility_percent'] + distinct[-1]['train_daily_volatility_percent']) / 2
        middle = min(distinct[1:-1], key=lambda r: abs(r['train_daily_volatility_percent'] - midpoint))
        distinct = [distinct[0], middle, distinct[-1]]
    labels = {0: [], 1: ['ระดับเดียว'], 2: ['ต่ำ', 'สูง'], 3: ['ต่ำ', 'กลาง', 'สูง']}[len(distinct)]
    levels = []
    for index, (trial, label) in enumerate(zip(distinct, labels), 1):
        weight = trial['new_stock_weight_percent'] / 100
        target = original * (1 - weight)
        target[screening['tickers'].index(trial['ticker'])] = weight
        levels.append({'level': index, 'label': label, 'trial': dict(trial), 'weights': target})
    return levels


def describe_return_change(old, new):
    # อธิบายว่าผลตอบแทนเพิ่มหรือลดลงเมื่อเทียบพอร์ตเดิม
    """ผลตอบแทนเป็นหน่วย %; ไม่เรียกผลขาดทุนว่าเป็นกำไร และไม่หารศูนย์."""
    if abs(new - old) < 1e-10:
        return 'ผลตอบแทนสะสมเท่าเดิม'
    if abs(old) < 1e-10:
        return f'เดิมผลตอบแทนใกล้ศูนย์ → ใหม่ {new:+.2f}%; ไม่คำนวณการเปลี่ยนแปลงสัมพัทธ์'
    if old > 0 and new >= 0:
        direction = 'เพิ่มขึ้น' if new > old else 'ลดลง'
        return f'กำไรสะสม{direction}ประมาณ {abs(new-old)/old*100:.2f}% เมื่อเทียบกับกำไรเดิม'
    if old < 0 and new <= 0:
        direction = 'ลดลง' if new > old else 'เพิ่มขึ้น'
        return f'ขาดทุนสะสม{direction}ประมาณ {abs(new-old)/abs(old)*100:.2f}% เมื่อเทียบกับขาดทุนเดิม'
    return f'จาก{"กำไร" if old > 0 else "ขาดทุน"} {abs(old):.2f}% เป็น{"กำไร" if new > 0 else "ขาดทุน"} {abs(new):.2f}%'


def compare_metrics(original, new, capital=100000.0):
    # เปรียบเทียบผลตอบแทน ความผันผวน และมูลค่าเงินของสองพอร์ต
    if not math.isfinite(capital) or capital <= 0:
        raise ValueError('เงินตัวอย่างต้องเป็นจำนวนบวกที่มีค่าจำกัด')
    if original['status'] != 'ok' or new['status'] != 'ok':
        return {'return_change_pp': None, 'profit_change_percent': None,
                'sd_change_pp': None, 'sd_reduction_percent': None,
                'profit_money': None, 'profit_difference_money': None,
                'final_money': None, 'sd_money_at_initial_capital': None,
                'explanation': 'ข้อมูล Test ไม่ครบ จึงไม่สรุปผลต่างหรือเลือกพอร์ตอื่นมาแทน'}
    old_return, new_return = original['net_total_return_percent'], new['net_total_return_percent']
    old_sd, new_sd = original['net_daily_volatility_percent'], new['net_daily_volatility_percent']
    reduction = (old_sd - new_sd) / old_sd * 100 if old_sd > 1e-12 else None
    if reduction is None:
        sd_text = f'SD เดิมใกล้ศูนย์ → ใหม่ {new_sd:.4f}%; ไม่คำนวณการเปลี่ยนแปลงสัมพัทธ์'
    elif abs(reduction) < 1e-8:
        sd_text = 'การแกว่งรายวันเท่าเดิม'
    else:
        sd_text = f'การแกว่งรายวัน{"ลดลง" if reduction > 0 else "เพิ่มขึ้น"}ประมาณ {abs(reduction):.2f}%'
    return {'return_change_pp': new_return - old_return,
            'profit_change_percent': (new_return-old_return)/old_return*100 if old_return > 1e-10 and new_return >= 0 else None,
            'sd_change_pp': new_sd - old_sd, 'sd_reduction_percent': reduction,
            'profit_money': capital * new_return / 100,
            'profit_difference_money': capital * (new_return-old_return) / 100,
            'final_money': capital * (1 + new_return / 100),
            'sd_money_at_initial_capital': capital * new_sd / 100,
            'explanation': sd_text + '; ' + describe_return_change(old_return, new_return)}


def evaluate_risk_levels(price_path, anchor_day, test_days, screening, rebalancing,
                         fee_rate=0.001, capital=100000.0, *, levels=None):
    # ประเมินแต่ละระดับพอร์ตในช่วงทดสอบด้วยวิธีเดียวกัน
    levels = select_risk_levels(screening, rebalancing) if levels is None else levels
    rows, weights = [], []
    # แม้ไม่มีระดับที่ผ่านเกณฑ์ ยังแสดงพอร์ตเดิมและ Equal Weight
    for index, option in enumerate(levels or [None]):
        target = option['weights'] if option else screening['weights']
        costs = evaluate_costs(price_path, anchor_day, test_days, screening['tickers'],
                               screening['weights'], target, fee_rate=fee_rate)
        original = next(row for row in costs['summary'] if row['strategy'] == 'original')
        for summary in costs['summary']:
            strategy = summary['strategy']
            if strategy == 'proposed' and option is None:
                continue
            if strategy != 'proposed' and index > 0:
                continue
            key = f"level_{option['level']}" if strategy == 'proposed' else strategy
            label = f"ระดับ {option['level']} ({option['label']})" if strategy == 'proposed' else {'original': 'พอร์ตเดิม', 'equal_weight': 'แบ่งเท่ากัน'}[strategy]
            mdd = None
            if summary['status'] == 'ok':
                nav = [day['net_nav'] for day in costs['daily'] if day['strategy'] == strategy]
                mdd = calculate_drawdown(nav)[1]
            train_sd = option['trial']['train_daily_volatility_percent'] if strategy == 'proposed' else None
            if strategy == 'original':
                train_sd = rebalancing['old_daily_volatility'] * 100
            rows.append({**summary, 'strategy': key, 'label': label,
                         'train_daily_sd_percent': train_sd, 'max_drawdown_percent': mdd,
                         **compare_metrics(original, summary, capital)})
        if option:
            for ticker, old, new in zip(screening['tickers'], screening['weights'], target):
                if old > 0 or new > 0:
                    weights.append({'level': option['level'], 'ticker': ticker,
                                    'old_weight_percent': float(old*100), 'new_weight_percent': float(new*100)})
    rows.sort(key=lambda row: (0 if row['strategy'] == 'original' else 2 if row['strategy'] == 'equal_weight' else 1, row['strategy']))
    return {'rows': rows, 'weights': weights, 'levels': levels, 'capital': capital,
            'anchor_day': anchor_day, 'test_start': test_days[0], 'test_end': test_days[-1],
            'fee_rate': fee_rate}


def render_comparison(result):
    # จัดผลเปรียบเทียบพอร์ตเป็นข้อความและตาราง Markdown
    fmt = lambda v, digits=2: 'N/A' if v is None else f'{v:,.{digits}f}'
    original = next(row for row in result['rows'] if row['strategy'] == 'original')
    lines = ['## ทางเลือกความผันผวนและสิ่งที่ต้องแลก', '',
             f"Test: {result['test_start']} ถึง {result['test_end']} | ค่าธรรมเนียมสมมติ {result['fee_rate']*100:.3f}% ต่อฝั่ง", '',
             'ระดับเรียงตาม SD ของ Train จากต่ำไปสูง เฉพาะชุดที่ทดลอง ไม่ใช่ระดับความเสี่ยงมาตรฐาน และลำดับ SD ใน Test อาจต่างออกไป',
             'เลือกทางเลือก variance ต่ำสุดของแต่ละสัดส่วนเพิ่มหุ้นก่อน แล้วเลือก SD ต่ำสุด ใกล้กึ่งกลางช่วง และสูงสุด เก็บเฉพาะที่ลด variance Train ได้และไม่ซ้ำระดับ ไม่มีการใช้ Test เลือกระดับ', '',
             '| พอร์ต | SD Train % | ผลตอบแทนสุทธิ ก่อน → หลัง % | SD Test รายวัน ก่อน → หลัง % | ผลตอบแทนต่าง (จุดเปอร์เซ็นต์) | SD ลดลงสัมพัทธ์ % | Max Drawdown % |',
             '|---|---:|---|---|---:|---:|---:|']
    for row in result['rows']:
        lines.append(f"| {row['label']} | {fmt(row['train_daily_sd_percent'],4)} | {fmt(original['net_total_return_percent'])} → {fmt(row['net_total_return_percent'])} | {fmt(original['net_daily_volatility_percent'],4)} → {fmt(row['net_daily_volatility_percent'],4)} | {fmt(row['return_change_pp'])} | {fmt(row['sd_reduction_percent'])} | {fmt(row['max_drawdown_percent'])} |")
    lines += ['', 'SD ลดลงสัมพัทธ์ติดลบ = ผันผวนเพิ่มขึ้น; ผลตอบแทนต่าง = ใหม่ − เดิม ไม่ใช่เปอร์เซ็นต์การเปลี่ยนแปลงของกำไร', '']
    if not result['levels']:
        lines += ['ไม่พบทางเลือกที่ลดความแปรปรวน Train ได้ จึงคงพอร์ตเดิม ไม่มีการบังคับสร้างสามระดับ', '']
    for row in result['rows']:
        if row['strategy'] != 'original':
            lines.append(f"- {row['label']}: {row['explanation']}")
        if row['status'] != 'ok':
            lines.append(f"- {row['label']} ประเมินไม่ได้: {row['status']}")
    lines += ['', f"### ถ้าเริ่มด้วยเงิน {result['capital']:,.0f} หน่วยเงิน", '',
              '| พอร์ต | กำไร/ขาดทุนสะสม | ต่างจากพอร์ตเดิม | เงินปลายช่วง | ขนาด 1 SD รายวันบนเงินเริ่มต้น |',
              '|---|---:|---:|---:|---:|']
    for row in result['rows']:
        lines.append(f"| {row['label']} | {fmt(row['profit_money'])} | {fmt(row['profit_difference_money'])} | {fmt(row['final_money'])} | {fmt(row['sd_money_at_initial_capital'])} |")
    lines += ['', 'เงินตัวอย่างใช้หน่วยเดียวกันและไม่คิด FX; 1 SD เป็นขนาดการแกว่งรอบค่าเฉลี่ยบนฐานเงินเริ่มต้น ไม่ใช่ขาดทุนรายวันหรือเพดานขาดทุน และนำไปคูณจำนวนวันเป็นเงินที่ประหยัดไม่ได้', '',
              '### น้ำหนักพอร์ตแต่ละระดับ', '']
    for option in result['levels']:
        holdings = [f"{row['ticker']} {row['new_weight_percent']:.2f}%" for row in result['weights']
                    if row['level'] == option['level'] and row['new_weight_percent'] > 0]
        lines.append(f"- ระดับ {option['level']} ({option['label']}): " + ', '.join(holdings))
    lines += ['', 'ผลตอบแทนสะสมกับ SD รายวันวัดคนละอย่าง การลด SD ไม่รับประกันกำไรหรือการลด Drawdown ทางเลือกเหล่านี้ยังใช้เกณฑ์ลด variance เดิม ไม่ได้ปรับสูตรให้ชนะ Test', '']
    return '\n'.join(lines)


def save_comparison(result, folder):
    # บันทึกตารางเปรียบเทียบและน้ำหนักพอร์ตลงไฟล์
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for filename, rows, fields in [
        ('risk_levels.csv', result['rows'], list(result['rows'][0])),
        ('risk_level_weights.csv', result['weights'], ['level', 'ticker', 'old_weight_percent', 'new_weight_percent']),
    ]:
        with (folder / filename).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    text = render_comparison(result)
    (folder / 'risk_levels.md').write_text(text, encoding='utf-8')
    return text
