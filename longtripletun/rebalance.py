"""ทดลองเพิ่มหุ้นใหม่ครั้งละหนึ่งตัว โดยใช้ covariance จาก Train เท่านั้น"""

import math
import numpy as np


def try_rebalancing(screening, additions=(0.05, 0.10, 0.15, 0.20)):
    names = screening['tickers']
    old_weights = np.asarray(screening['weights'], dtype=float)
    covariance = np.asarray(screening['covariance'], dtype=float)
    if (old_weights.shape != (len(names),) or covariance.shape != (len(names), len(names))
            or len(set(names)) != len(names)):
        raise ValueError("ขนาดเมทริกซ์และลำดับชื่อหุ้นไม่ถูกต้อง")
    if (not np.isfinite(old_weights).all() or not np.isfinite(covariance).all()
            or (old_weights < 0).any() or not np.isclose(old_weights.sum(), 1)):
        raise ValueError("น้ำหนักต้องไม่ติดลบ รวมเป็น 1 และ covariance ต้องเป็นตัวเลขจำกัด")
    if not additions or any(not math.isfinite(a) or not 0 < a < 1 for a in additions):
        raise ValueError("สัดส่วนหุ้นใหม่ต้องมากกว่า 0 และน้อยกว่า 1")
    if len(set(screening['shortlist'])) != len(screening['shortlist']):
        raise ValueError("รายชื่อผู้สมัครซ้ำ")

    def risk(w):
        value = float(w @ covariance @ w)
        if value < -1e-12:
            raise ValueError("ความแปรปรวนติดลบผิดปกติ")
        return max(value, 0.0)

    old_variance = risk(old_weights)
    old_volatility = math.sqrt(old_variance)
    trials = []
    for ticker in screening['shortlist']:
        if ticker not in names:
            raise ValueError(f"ไม่มี covariance ของหุ้นผู้สมัคร {ticker}")
        position = names.index(ticker)
        if old_weights[position] != 0:
            raise ValueError(f"หุ้น {ticker} เป็นหุ้นเดิม ไม่ใช่ผู้สมัครนอกพอร์ต")
        for addition in additions:
            # เงินก้อนเดิม: ลดหุ้นเดิมตามสัดส่วน และจัดสรรให้หุ้นใหม่
            new_weights = old_weights * (1 - addition)
            new_weights[position] = addition
            new_variance = risk(new_weights)
            new_volatility = math.sqrt(new_variance)
            trials.append({
                'ticker': ticker,
                'new_stock_weight_percent': addition * 100,
                'train_variance': new_variance,
                'train_daily_volatility_percent': new_volatility * 100,
                'volatility_reduction_percentage_points': (old_volatility - new_volatility) * 100,
                'relative_volatility_reduction_percent': (
                    (old_volatility - new_volatility) / old_volatility * 100 if old_volatility > 0 else None),
            })
    trials.sort(key=lambda row: (row['train_variance'], row['ticker'], row['new_stock_weight_percent']))

    # พอร์ตเดิมเป็นทางเลือกเสมอ ไม่ฝืนเพิ่มหุ้นถ้าผลไม่ดีขึ้นเกินเศษการคำนวณ
    best = None
    new_weights = old_weights.copy()
    if trials and trials[0]['train_variance'] < old_variance - max(1e-16, old_variance * 1e-10):
        best = trials[0]
        addition = best['new_stock_weight_percent'] / 100
        new_weights = old_weights * (1 - addition)
        new_weights[names.index(best['ticker'])] = addition

    weight_changes = [
        {'ticker': ticker, 'old_weight_percent': float(old * 100),
         'new_weight_percent': float(new * 100), 'change_percentage_points': float((new-old) * 100)}
        for ticker, old, new in zip(names, old_weights, new_weights) if old > 0 or new > 0
    ]
    return {
        'trials': trials, 'best': best, 'weights': new_weights,
        'weight_changes': weight_changes, 'old_variance': old_variance,
        'old_daily_volatility': old_volatility, 'new_daily_volatility': math.sqrt(risk(new_weights)),
    }
