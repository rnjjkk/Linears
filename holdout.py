"""ประเมินพอร์ตที่เลือกจาก Train แล้ว โดยไม่ปรับคำแนะนำจากผล Test"""

import csv
import math
from datetime import date
from pathlib import Path
import numpy as np


def buy_and_hold(prices, weights):
    """แถวแรกคือราคาตั้งต้น; NAV เริ่ม 100, ถือสัดส่วนตั้งต้นแล้วปล่อยน้ำหนักลอย.

ใช้ราคาปรับแล้วเป็นดัชนีการเติบโต จึงไม่อ้างว่าเป็นจำนวนหุ้นจริงหลัง corporate actions
ไม่มีค่าธรรมเนียมในขั้นเรียนนี้
"""
    prices = np.asarray(prices, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if prices.ndim != 2 or len(prices) < 3 or weights.shape != (prices.shape[1],):
        raise ValueError("ต้องมีราคาตั้งต้นและอย่างน้อย 2 วันทดสอบ โดยน้ำหนักตรงกับคอลัมน์หุ้น")
    if (not np.isfinite(prices).all() or (prices <= 0).any()
            or not np.isfinite(weights).all() or (weights < 0).any()
            or not np.isclose(weights.sum(), 1, atol=1e-10, rtol=0)):
        raise ValueError("ราคา/น้ำหนักไม่ถูกต้องสำหรับทดสอบ")
    relative_prices = prices / prices[0]
    holding_values = relative_prices * weights
    nav = holding_values.sum(axis=1) * 100
    daily_returns = nav[1:] / nav[:-1] - 1
    final_weights = holding_values[-1] / holding_values[-1].sum()
    return {
        'nav': nav, 'daily_returns': daily_returns, 'final_weights': final_weights,
        'total_return_percent': float((nav[-1] / nav[0] - 1) * 100),
        'daily_volatility_percent': float(np.std(daily_returns, ddof=1) * 100),
        'final_nav': float(nav[-1]),
    }


def evaluate_holdout(csv_path, anchor_day, test_days, names, original_weights, proposed_weights,
                     include_equal_weight=False):
    if (len(test_days) < 2 or test_days != sorted(set(test_days))
            or anchor_day >= test_days[0]):
        raise ValueError("วันตั้งต้นและวัน Test เรียงไม่ถูกต้อง")
    strategies = {'original': np.array(original_weights, dtype=float, copy=True),
                  'proposed': np.array(proposed_weights, dtype=float, copy=True)}
    if len(set(names)) != len(names):
        raise ValueError("ชื่อหุ้นซ้ำ")
    for weights in strategies.values():
        if (weights.shape != (len(names),) or not np.isfinite(weights).all()
                or (weights < 0).any() or not np.isclose(weights.sum(), 1, atol=1e-10, rtol=0)):
            raise ValueError("น้ำหนักทดสอบไม่ตรงกับหุ้นหรือรวมไม่เป็น 1")
    if include_equal_weight:
        held = strategies['original'] > 0
        strategies['equal_weight'] = held.astype(float) / held.sum()
    needed = {names[i] for weights in strategies.values() for i in np.flatnonzero(weights > 0)}
    price_history = {ticker: {} for ticker in needed}
    calendar = set()
    required_days = [anchor_day, *test_days]
    for_day = set(required_days)
    duplicates = set()
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if not {'Date', 'Ticker', 'Close'}.issubset(reader.fieldnames or []):
            raise ValueError("ไฟล์ราคาต้องมี Date,Ticker,Close")
        for row in reader:
            day = date.fromisoformat((row['Date'] or '').strip()).isoformat()
            if not anchor_day <= day <= test_days[-1]:
                continue
            calendar.add(day)
            ticker = (row['Ticker'] or '').strip().upper()
            if ticker not in needed or day not in for_day:
                continue
            if day in price_history[ticker]:
                duplicates.add((ticker, day))
            try:
                close = float(row['Close'])
            except (TypeError, ValueError):
                close = math.nan
            price_history[ticker][day] = close if math.isfinite(close) and close > 0 else None

    # ห้ามข้ามวันที่ missing แล้วทำเสมือนเป็นผลตอบแทนหนึ่งวัน
    if sorted(calendar) != required_days:
        raise ValueError("ช่วง Test มีวันขาดหายหรือไม่ตรงกับปฏิทิน CSV จึงไม่ข้ามวันเพื่อคำนวณความผันผวน")
    summaries, daily_rows, weight_rows = [], [], []
    for label, weights in strategies.items():
        positions = np.flatnonzero(weights > 0)
        active_names = [names[i] for i in positions]
        bad = [(ticker, day) for ticker in active_names for day in required_days
               if price_history[ticker].get(day) is None or (ticker, day) in duplicates]
        row = {
            'strategy': label, 'status': 'ok', 'test_days': len(test_days),
            'total_return_percent': None, 'daily_volatility_percent': None, 'final_nav': None,
        }
        if bad:
            row['status'] = 'unavailable: missing/invalid/duplicate price ' + ', '.join(
                f'{ticker}@{day}' for ticker, day in bad[:5])
            summaries.append(row)
            continue
        matrix = [[price_history[ticker][day] for ticker in active_names] for day in required_days]
        result = buy_and_hold(matrix, weights[positions])
        for field in ('total_return_percent', 'daily_volatility_percent', 'final_nav'):
            row[field] = result[field]
        summaries.append(row)
        for index, day in enumerate(required_days):
            daily_rows.append({
                'strategy': label, 'date': day, 'nav': float(result['nav'][index]),
                'daily_return_percent': None if index == 0 else float(result['daily_returns'][index-1] * 100),
            })
        for ticker, initial, final in zip(active_names, weights[positions], result['final_weights']):
            weight_rows.append({'strategy': label, 'ticker': ticker,
                                'initial_weight_percent': float(initial * 100),
                                'final_weight_percent': float(final * 100)})
    return {'summary': summaries, 'daily': daily_rows, 'weights': weight_rows,
            'anchor_day': anchor_day, 'test_start': test_days[0], 'test_end': test_days[-1],
            'assumptions': 'Ideal initial allocation at last Train adjusted close; buy and hold; no fees, slippage, tax or FX. Adjusted-price growth, not executable fills.'}


def evaluate_costs(csv_path, anchor_day, test_days, names, original_weights, proposed_weights,
                   fee_rate=0.001):
    """เปรียบเทียบสามพอร์ตด้วยต้นทุนประมาณการครั้งแรกจากน้ำหนักเป้าหมาย

fee_fraction = rate * sum(abs(target_weight - original_weight))
คิดทั้งฝั่งซื้อและขาย ไม่หารสอง หักจากเงินลงทุนก่อนเริ่มถือ ไม่คิดซ้ำรายวัน
เป็นแบบจำลองต้นทุนโดยประมาณ: ไม่แก้ย้อนหาปริมาณเทรดหลังหักค่าธรรมเนียม
"""
    if not math.isfinite(fee_rate) or not 0 <= fee_rate <= 0.01:
        raise ValueError("fee_rate ต้องอยู่ระหว่าง 0 และ 0.01 (0% ถึง 1% ต่อฝั่ง)")
    gross = evaluate_holdout(csv_path, anchor_day, test_days, names, original_weights,
                             proposed_weights, include_equal_weight=True)
    original = np.asarray(original_weights, dtype=float)
    held = original > 0
    target_weights = {'original': original,
                      'proposed': np.asarray(proposed_weights, dtype=float),
                      'equal_weight': held.astype(float) / held.sum()}
    summaries, daily_rows = [], []
    for row in gross['summary']:
        label = row['strategy']
        traded_fraction = float(np.abs(target_weights[label] - original).sum())
        cost_fraction = fee_rate * traded_fraction
        summary = {
            'strategy': label, 'status': row['status'], 'test_days': len(test_days),
            'gross_traded_percent': traded_fraction * 100,
            'initial_fee_percent_of_portfolio': cost_fraction * 100,
            'gross_total_return_percent': row['total_return_percent'],
            'net_total_return_percent': None,
            'gross_daily_volatility_percent': row['daily_volatility_percent'],
            'net_daily_volatility_percent': None, 'net_final_nav': None,
        }
        if row['status'] != 'ok':
            summaries.append(summary)
            continue
        path = [item for item in gross['daily'] if item['strategy'] == label]
        gross_nav = np.array([item['nav'] for item in path])
        net_nav = gross_nav * (1 - cost_fraction)
        # จุดอ้างอิงคือ NAV ก่อนจ่าย fee 100; ผลตอบแทนวันแรกจึงรวมต้นทุนตั้งต้น
        net_nav[0] = 100.0
        net_returns = net_nav[1:] / net_nav[:-1] - 1
        summary['net_total_return_percent'] = float(net_nav[-1] - 100)
        summary['net_daily_volatility_percent'] = float(np.std(net_returns, ddof=1) * 100)
        summary['net_final_nav'] = float(net_nav[-1])
        summaries.append(summary)
        for index, item in enumerate(path):
            daily_rows.append({
                'strategy': label, 'date': item['date'], 'gross_nav': float(gross_nav[index]),
                'net_nav': float(net_nav[index]),
                'net_daily_return_percent': None if index == 0 else float(net_returns[index-1]*100),
            })
    return {'summary': summaries, 'daily': daily_rows, 'weights': gross['weights'],
            'fee_rate': fee_rate,
            'assumptions': gross['assumptions'].replace('no fees, slippage, tax or FX',
                'one initial approximate fee on target gross buys plus sells; no slippage, tax or FX')
                + ' NAV starts at 100 before fees; first Test return includes initial cost. Equal weight uses original holdings only.'}
