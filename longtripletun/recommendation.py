# ตรวจความกระจุกตัวและคัดคำแนะนำที่ผ่านเกณฑ์ Validation
"""ด่านความคุ้มค่าจาก Validation ก่อน Test; ค่าเริ่มต้นเป็นนโยบายทดลองของโครงงาน."""
import csv
import json
import math
from pathlib import Path
from .settings import load_policy, validate_policy

import numpy as np

from .candidate_analysis import screen_candidates
from .rebalance import try_rebalancing
from .risk_levels import evaluate_risk_levels, select_risk_levels, save_comparison


def concentration_summary(names, weights, covariance):
    # สรุปความกระจุกตัวของน้ำหนักและความสัมพันธ์ระหว่างหุ้น
    """HHI วัดน้ำหนักเท่านั้น; pair correlation ใช้ผลตอบแทนก่อน Test."""
    w, c = np.asarray(weights, float), np.asarray(covariance, float)
    if (w.shape != (len(names),) or c.shape != (len(names), len(names))
            or not np.isfinite(w).all() or not np.isfinite(c).all()
            or (w < 0).any() or not np.isclose(w.sum(), 1)):
        raise ValueError('ข้อมูลน้ำหนัก/covariance สำหรับสรุปพอร์ตไม่ถูกต้อง')
    active = np.flatnonzero(w > 0)
    ranking = sorted(active, key=lambda i: -w[i])
    hhi = float(w @ w)
    pairs, numerator, denominator = [], 0., 0.
    for offset, i in enumerate(active):
        for j in active[offset+1:]:
            sd_product = math.sqrt(max(0., float(c[i, i])) * max(0., float(c[j, j])))
            correlation = float(np.clip(c[i, j] / sd_product, -1, 1)) if sd_product > 1e-15 else None
            pairs.append({'first': names[i], 'second': names[j], 'correlation': correlation})
            if correlation is not None:
                numerator += w[i] * w[j] * correlation
                denominator += w[i] * w[j]
    return {'holdings': len(active), 'largest_ticker': names[ranking[0]],
            'largest_weight_percent': float(w[ranking[0]] * 100),
            'top_three_weight_percent': float(w[ranking[:3]].sum()*100),
            'hhi': hhi, 'effective_equal_weight_holdings': 1/hhi,
            'weighted_pair_correlation': float(numerator/denominator) if denominator > 0 else None,
            'undefined_pairs': sum(p['correlation'] is None for p in pairs),
            'strongest_pairs': sorted([p for p in pairs if p['correlation'] is not None],
                                      key=lambda p: -p['correlation'])[:5]}


def assess_candidate(original, candidate, policy):
    # ตรวจว่าทางเลือกผ่านเกณฑ์ความเสี่ยงและผลตอบแทนหรือไม่
    required = ('net_total_return_percent', 'net_daily_volatility_percent', 'max_drawdown_percent')
    if (original.get('status') != 'ok' or candidate.get('status') != 'ok'
            or any(not isinstance(row.get(key), (float, int)) or not math.isfinite(row[key])
                   for row in (original, candidate) for key in required)):
        return {'passed': False, 'reasons': ['ข้อมูล Validation ไม่ครบหรือไม่เป็นตัวเลข จึงยังแนะนำไม่ได้'],
                'sd_reduction_percent': None, 'return_change_pp': None, 'drawdown_change_pp': None}
    old_sd = original['net_daily_volatility_percent']
    reduction = (1-candidate['net_daily_volatility_percent']/old_sd)*100 if old_sd > 1e-12 else None
    return_delta = candidate['net_total_return_percent'] - original['net_total_return_percent']
    # Drawdown ใช้ค่าติดลบ: -9 - (-17) = +8 คือดีขึ้น
    drawdown_delta = candidate['max_drawdown_percent'] - original['max_drawdown_percent']
    reasons = []
    if reduction is None:
        reasons.append('SD พอร์ตเดิมใกล้ศูนย์ จึงยืนยันเปอร์เซ็นต์การลดไม่ได้')
    elif reduction + 1e-9 < policy['minimum_sd_reduction_percent']:
        reasons.append(f"SD ลด {reduction:.2f}% ไม่ถึงเกณฑ์ {policy['minimum_sd_reduction_percent']:.2f}%")
    if return_delta < -policy['maximum_return_loss_pp'] - 1e-9:
        reasons.append(f"ผลตอบแทนสุทธิลด {-return_delta:.2f} จุดเปอร์เซ็นต์ เกินที่ยอมรับ {policy['maximum_return_loss_pp']:.2f}")
    if drawdown_delta < -policy['maximum_drawdown_worsening_pp'] - 1e-9:
        reasons.append(f"Drawdown แย่ลง {-drawdown_delta:.2f} จุดเปอร์เซ็นต์ เกินที่ยอมรับ {policy['maximum_drawdown_worsening_pp']:.2f}")
    return {'passed': not reasons, 'reasons': reasons or ['ผ่านทุกเกณฑ์บน Validation หลังค่าธรรมเนียม'],
            'sd_reduction_percent': reduction, 'return_change_pp': return_delta,
            'drawdown_change_pp': drawdown_delta}


def build_recommendation(price_path, train_days, names, weights, *, pca_target=None,
                         fee_rate=None, policy=None):
    # เลือกพอร์ตจาก Fit แล้วตรวจ Validation ก่อนให้คำแนะนำ
    """ไม่มี argument Test; shortlist, PCA และระดับสร้างจาก Fit ก่อน Validation เท่านั้น."""
    policy = load_policy() if policy is None else validate_policy(policy)
    policy = validate_policy({**policy,
                              'pca_target': policy['pca_target'] if pca_target is None else pca_target,
                              'fee_rate': policy['fee_rate'] if fee_rate is None else fee_rate})
    pca_target, fee_rate = policy['pca_target'], policy['fee_rate']
    if train_days != sorted(set(train_days)):
        raise ValueError('Train ต้องเรียงวันและไม่ซ้ำ')
    split = int(len(train_days)*policy['fit_fraction_of_train'])
    fit, validation = train_days[:split], train_days[split:]
    decision = {'policy': policy, 'status': 'keep_original', 'approved_levels': [],
                'checks': [], 'fit_days': fit, 'validation_days': validation,
                'fee_rate': fee_rate, 'pca_target': pca_target,
                'reason': 'ไม่มีทางเลือกผ่านเกณฑ์ความคุ้มค่าบน Validation จึงคงพอร์ตเดิม'}
    if len(fit) < policy['minimum_fit_days'] or len(validation) < policy['minimum_validation_days']:
        decision['reason'] = 'ข้อมูล Fit/Validation ไม่พอ จึงคงพอร์ตเดิมและยังยืนยันความคุ้มค่าไม่ได้'
        return decision
    try:
        screening = screen_candidates(price_path, fit, names, weights, pca_target=pca_target,
                                      shortlist_size=policy['shortlist_size'], policy=policy)
        rebalance = try_rebalancing(screening, policy=policy)
        candidates = select_risk_levels(screening, rebalance)
        evaluated = evaluate_risk_levels(price_path, fit[-1], validation, screening, rebalance,
                                         fee_rate=fee_rate, levels=candidates)
    except (ValueError, OSError) as error:
        decision['reason'] = f'ประเมิน Validation ไม่ได้ จึงคงพอร์ตเดิม: {error}'
        return decision
    original = next(row for row in evaluated['rows'] if row['strategy'] == 'original')
    for option in candidates:
        row = next(row for row in evaluated['rows'] if row['strategy'] == f"level_{option['level']}")
        check = {'level': option['level'], 'label': option['label'], 'trial': option['trial'],
                 'original': original, 'candidate': row, **assess_candidate(original, row, policy)}
        decision['checks'].append(check)
        if check['passed']:
            decision['approved_levels'].append(option)
    decision.update(screening=screening, rebalancing=rebalance)
    if decision['approved_levels']:
        decision['status'] = 'alternatives_available'
        decision['reason'] = f"มี {len(decision['approved_levels'])} ทางเลือกผ่านเกณฑ์ Validation; ผู้ใช้เลือกได้หรือคงพอร์ตเดิม"
    return decision


def save_recommendation(decision, concentration, price_path, anchor_day, test_days, folder):
    # บันทึกเหตุผลคำแนะนำและน้ำหนักพอร์ตที่ผ่านเกณฑ์
    """ผล Test แสดงหลังล็อก decision แล้ว ไม่มีการกลับไปเปลี่ยนสถานะผ่านเกณฑ์."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    policy = decision['policy']
    fmt = lambda value: 'N/A' if value is None else f'{value:.4f}'
    lines = ['# สรุปการตัดสินใจปรับพอร์ต', '', '**' + decision['reason'] + '**', '',
             '## พอร์ตกระจุกตัวแค่ไหน', '',
             f"- ถือ {concentration['holdings']} หุ้น; หุ้นใหญ่สุด {concentration['largest_ticker']} {concentration['largest_weight_percent']:.2f}%",
             f"- สามอันดับแรกคิดเป็น {concentration['top_three_weight_percent']:.2f}% ของพอร์ต",
             f"- HHI = ผลรวมกำลังสองน้ำหนัก = {concentration['hhi']:.4f}; เทียบเท่าถือเท่ากันประมาณ {concentration['effective_equal_weight_holdings']:.2f} ตัวในแง่น้ำหนักเท่านั้น",
             f"- Correlation เฉลี่ยถ่วงด้วยน้ำหนักคู่หุ้น (ไม่รวมแนวทแยง) = {fmt(concentration['weighted_pair_correlation'])}",
             f"- คู่ที่ correlation ไม่มีนิยาม {concentration['undefined_pairs']} คู่ (ไม่นับเป็นศูนย์)",
             '- Correlation ใกล้ +1 หมายถึงเคลื่อนไหวทิศเดียวกันมาก ใกล้ -1 หมายถึงสวนกัน และใกล้ 0 หมายถึงสัมพันธ์เชิงเส้นน้อย ไม่ได้รับประกันว่าจะสวนกันตอนตลาดตก',
             '- ค่าความสัมพันธ์ใช้ Train ก่อน Test; HHI ไม่วัดความซ้ำซ้อนของธุรกิจ และ correlation ไม่ใช่เหตุและผล', '']
    for pair in concentration['strongest_pairs']:
        lines.append(f"- {pair['first']} / {pair['second']}: correlation {pair['correlation']:.4f}")
    lines += ['', '## เกณฑ์ความคุ้มค่า', '',
              f"- SD บน Validation ลดอย่างน้อย {policy['minimum_sd_reduction_percent']:.2f}% เทียบพอร์ตเดิม",
              f"- ผลตอบแทนสุทธิลดไม่เกิน {policy['maximum_return_loss_pp']:.2f} จุดเปอร์เซ็นต์",
              f"- Maximum Drawdown แย่ลงไม่เกิน {policy['maximum_drawdown_worsening_pp']:.2f} จุดเปอร์เซ็นต์",
              f"- ประเมินหลังค่าธรรมเนียมสมมติ {decision['fee_rate']*100:.3f}% ต่อมูลค่าซื้อ/ขาย",
              '- ค่าเหล่านี้เป็นนโยบายทดลองที่แก้ได้ใน recommendation_policy.json ไม่ใช่มาตรฐานรับรองความคุ้มค่าหรือผลอนาคต', '']
    if decision['fit_days'] and decision['validation_days']:
        lines += [f"Fit: {decision['fit_days'][0]} ถึง {decision['fit_days'][-1]} ({len(decision['fit_days'])} วัน)",
                  f"Validation: {decision['validation_days'][0]} ถึง {decision['validation_days'][-1]} ({len(decision['validation_days'])} วัน)",
                  f'Test: {test_days[0]} ถึง {test_days[-1]}', '']
    lines += ['สร้าง PCA/shortlist/น้ำหนักใหม่จาก Fit เท่านั้น ตรวจเกณฑ์ด้วย Validation แล้วล็อกน้ำหนักโดยไม่ fit ใหม่ก่อนประเมิน Test',
              'ตารางวิเคราะห์เดิมที่ใช้ Train ทั้งช่วงยังเก็บไว้เพื่อเรียนและเปรียบเทียบ แต่ไม่ใช่คำแนะนำสุดท้าย', '',
              '## หลักฐานจาก Validation (รวมทางเลือกที่ไม่แนะนำ)', '',
              '| ระดับ | ผลตอบแทนเดิม → ใหม่ % | SD เดิม → ใหม่ % | MDD เดิม → ใหม่ % | ผลตรวจ | เหตุผล |',
              '|---|---|---|---|---|---|']
    for check in decision['checks']:
        old, new = check['original'], check['candidate']
        fields = ['net_total_return_percent', 'net_daily_volatility_percent', 'max_drawdown_percent']
        pairs = [f"{fmt(old[key])} → {fmt(new[key])}" for key in fields]
        lines.append(f"| {check['level']} ({check['label']}) | " + ' | '.join(pairs)
                     + f" | {'ผ่าน' if check['passed'] else 'ไม่แนะนำ'} | {'; '.join(check['reasons'])} |")
    lines += ['', '## ทางเลือกที่แนะนำให้พิจารณา', '']
    weight_rows = []
    for option in decision['approved_levels']:
        holdings = []
        for name, weight in zip(decision['screening']['tickers'], option['weights']):
            if weight > 0:
                weight_rows.append({'level': option['level'], 'ticker': name, 'weight_percent': float(weight*100)})
                holdings.append(f'{name} {weight*100:.2f}%')
        lines.append(f"- ระดับ {option['level']} ({option['label']}): " + ', '.join(holdings))
    if not weight_rows:
        lines += ['คงพอร์ตเดิม — ไม่มีคำแนะนำซื้อขายเพิ่มจากด่านนี้ จึงไม่มีค่าปรับพอร์ตเพิ่มในแบบจำลอง',
                  'การคงพอร์ตเดิมไม่ได้ยืนยันว่าพอร์ตเดิมปลอดภัยที่สุด แต่ยังไม่มีหลักฐานพอให้เปลี่ยนตามเกณฑ์นี้']
    if decision['approved_levels']:
        evaluated = evaluate_risk_levels(price_path, anchor_day, test_days, decision['screening'],
                                         decision['rebalancing'], fee_rate=decision['fee_rate'],
                                         levels=decision['approved_levels'])
        save_comparison(evaluated, folder / 'approved_test')
        lines += ['', 'ผล Test ของทางเลือกที่ผ่าน: [เปิดตาราง](approved_test/risk_levels.md)',
                  'หาก Test ไม่ครบจะแสดงประเมินไม่ได้ ไม่สลับไปเลือกหุ้นอื่น หาก Test แย่ลงยังรายงานตามจริงโดยไม่เปลี่ยนผลตรวจ Validation']
    lines += ['', 'เกณฑ์นี้เพิ่มหลังเคยเห็น Test ชุดเดิมแล้ว ผลรอบนี้จึงเป็นการสำรวจย้อนหลัง ยังต้องประเมินช่วงใหม่ที่ไม่เคยใช้พัฒนาวิธี ก่อนอ้างประสิทธิภาพนอกตัวอย่าง', '']
    text = '\n'.join(lines)
    (folder / 'recommendation.md').write_text(text, encoding='utf-8')
    with (folder / 'recommended_weights.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['level', 'ticker', 'weight_percent'])
        writer.writeheader()
        writer.writerows(weight_rows)
    payload = {key: value for key, value in decision.items() if key not in ('screening', 'rebalancing', 'approved_levels')}
    payload.update(concentration=concentration, price_source=str(Path(price_path).resolve()),
                   test_start=test_days[0], test_end=test_days[-1],
                   approved_levels=[option['level'] for option in decision['approved_levels']],
                   recommended_weights=weight_rows)
    (folder / 'recommendation.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return text
