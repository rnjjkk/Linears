"""ขั้น 38–40: Drawdown, กราฟ PNG และรายงาน Markdown จากผล Test หลังต้นทุน"""

import csv
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from .project_paths import PROJECT_ROOT
import numpy as np


def calculate_drawdown(nav):
    """เทียบแต่ละวันกับ NAV สูงที่สุดที่เคยเกิดขึ้นถึงวันนั้น รวมจุดตั้งต้นก่อน fee"""
    nav = np.asarray(nav, dtype=float)
    if nav.ndim != 1 or len(nav) == 0 or not np.isfinite(nav).all() or (nav <= 0).any():
        raise ValueError("NAV สำหรับ Drawdown ต้องเป็นรายการตัวเลขบวกที่ไม่ว่าง")
    running_peak = np.maximum.accumulate(nav)
    drawdown = (nav / running_peak - 1) * 100
    return drawdown, float(drawdown.min())


def save_report(cost_result, rebalancing, screening, context, output_root):
    context['generated_at'] = datetime.now(timezone(timedelta(hours=7))).isoformat(timespec='seconds')
    # กราฟใช้ข้อความอังกฤษเพื่อไม่ขึ้นกับฟอนต์ไทยที่ติดตั้งในแต่ละเครื่อง
    os.environ.setdefault('MPLCONFIGDIR', str(PROJECT_ROOT / '.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    from .report_store import begin_report
    output = begin_report(output_root)
    labels = {'original': 'Original', 'proposed': 'Proposed', 'equal_weight': 'Equal weight'}
    colors = {'original': '#2563eb', 'proposed': '#ea580c', 'equal_weight': '#15803d'}
    metrics, series, daily = [], {}, []
    for summary in cost_result['summary']:
        row = dict(summary)
        row['max_drawdown_percent'] = None
        if row['status'] == 'ok':
            path = [item for item in cost_result['daily'] if item['strategy'] == row['strategy']]
            nav = [item['net_nav'] for item in path]
            drawdown, worst = calculate_drawdown(nav)
            row['max_drawdown_percent'] = worst
            dates = [datetime.fromisoformat(item['date']) for item in path]
            series[row['strategy']] = (dates, nav, drawdown)
            for item, dd in zip(path, drawdown):
                daily.append({**item, 'drawdown_percent': float(dd)})
        metrics.append(row)

    # บันทึกข้อมูลรอบนี้ไว้คู่กับกราฟ ไม่ต้องอาศัย CSV latest ซึ่งอาจถูกเขียนทับภายหลัง
    for filename, rows, fields in [
        ('metrics.csv', metrics, list(metrics[0])),
        ('daily.csv', daily, ['strategy', 'date', 'gross_nav', 'net_nav', 'net_daily_return_percent', 'drawdown_percent']),
        ('proposed_weights.csv', rebalancing['weight_changes'],
         ['ticker', 'old_weight_percent', 'new_weight_percent', 'change_percentage_points']),
    ]:
        with (output / filename).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (output / 'run_context.json').write_text(json.dumps({
        **context, 'assumptions': cost_result['assumptions'],
        'pca_components': screening['components'], 'pca_explained_variance': screening['explained_variance'],
        'eligible_stocks': len(screening['tickers']), 'shortlist': screening['shortlist'],
        'chosen_on_train': rebalancing['best'],
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    for filename, title, y_label, position in [
        ('equity.png', 'Test: buy-and-hold portfolio value after initial fees', 'NAV (initial = 100)', 1),
        ('drawdown.png', 'Test: decline from each portfolio\'s running peak', 'Drawdown (%)', 2),
    ]:
        fig, ax = plt.subplots(figsize=(10, 5))
        for label, values in series.items():
            ax.plot(values[0], values[position], label=labels[label], color=colors[label], linewidth=1.6)
        if series:
            ax.legend()
        else:
            ax.text(.5, .5, 'No valid holdout data', transform=ax.transAxes, ha='center')
        ax.set(title=title, ylabel=y_label, xlabel='Date')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=150)
        plt.close(fig)

    valid = [row for row in metrics if row['status'] == 'ok']
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, field, title in zip(axes,
        ['net_total_return_percent', 'net_daily_volatility_percent', 'max_drawdown_percent'],
        ['Total return after fees (%)', 'Daily volatility after fees (%)', 'Maximum drawdown (%)']):
        x = np.arange(len(valid))
        heights = [row[field] for row in valid]
        bars = ax.bar(x, heights, color=[colors[row['strategy']] for row in valid])
        ax.set_xticks(x, [labels[row['strategy']] for row in valid], rotation=15)
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color='gray', linewidth=.7)
        ax.bar_label(bars, fmt='%.2f', padding=3)
        ax.margins(y=.2)
    fig.suptitle('Same Test period; fixed initial choice, then buy and hold', fontsize=12)
    fig.tight_layout()
    fig.savefig(output / 'comparison.png', dpi=150)
    plt.close(fig)

    table = ['| พอร์ต | ผลตอบแทนสุทธิ (%) | ความผันผวนรายวัน (%) | Maximum Drawdown (%) |',
             '|---|---:|---:|---:|']
    for row in metrics:
        if row['status'] == 'ok':
            table.append(f"| {labels[row['strategy']]} | {row['net_total_return_percent']:.4f} | "
                         f"{row['net_daily_volatility_percent']:.4f} | {row['max_drawdown_percent']:.4f} |")
        else:
            table.append(f"| {labels[row['strategy']]} | N/A | N/A | N/A |")
    by_label = {row['strategy']: row for row in valid}
    conclusion = 'ข้อมูล Test ไม่ครบสำหรับเปรียบเทียบพอร์ตเดิมกับพอร์ตที่เสนอ'
    if 'original' in by_label and 'proposed' in by_label:
        old, new = by_label['original'], by_label['proposed']
        delta_vol = new['net_daily_volatility_percent'] - old['net_daily_volatility_percent']
        delta_return = new['net_total_return_percent'] - old['net_total_return_percent']
        conclusion = (f"พอร์ตที่เสนอมีความผันผวนรายวันสุทธิต่างจากพอร์ตเดิม {delta_vol:+.4f} จุดเปอร์เซ็นต์ "
                      f"และผลตอบแทนสุทธิต่างกัน {delta_return:+.4f} จุดเปอร์เซ็นต์ "
                      "(ค่าบวกหมายถึงมากกว่าพอร์ตเดิม ค่าลบหมายถึงน้อยกว่า)")
    weights_table = ['| หุ้น | เดิม (%) | เสนอ (%) |', '|---|---:|---:|']
    for row in rebalancing['weight_changes']:
        weights_table.append(f"| {row['ticker']} | {row['old_weight_percent']:.2f} | {row['new_weight_percent']:.2f} |")
    report = f'''# LongTripleTun — สรุปผลการทดสอบพอร์ต

แหล่งราคา: `{context['source']}`

Train: {context['train_start']} ถึง {context['train_end']} ({context['train_days']} วัน)

Test: {context['test_start']} ถึง {context['test_end']} ({context['test_days']} วัน)

## วิธีเลือกพอร์ต

ใช้ Train เท่านั้นคำนวณ Covariance และ PCA ของหุ้นที่ผ่าน {len(screening['tickers'])} ตัว
PCA ใช้ {screening['components']} แกน อธิบายความแปรปรวน {screening['explained_variance']:.2%}
คัดผู้สมัคร {len(screening['shortlist'])} ตัว แล้วทดลอง {len(rebalancing['trials'])} ทางเลือก
เลือกความผันผวน Train ต่ำที่สุดในชุดที่ทดลอง ถ้าไม่ดีขึ้นคงพอร์ตเดิม
ล็อกหุ้นและน้ำหนักก่อนประเมิน Test ไม่เลือกใหม่จากผล Test

{chr(10).join(weights_table)}

## ผล Test หลังต้นทุน

{chr(10).join(table)}

{conclusion}

Equal weight แบ่งเงินเท่ากันเฉพาะหุ้นเดิม ไม่เพิ่มหุ้นผู้สมัคร
ผลตอบแทนรวมเป็นของช่วง Test ไม่ใช่ค่าเฉลี่ยรายวันหรือผลตอบแทนต่อปี
ความผันผวนเป็นส่วนเบี่ยงเบนมาตรฐานรายวัน ไม่ใช่ขาดทุนสูงสุด

![มูลค่าพอร์ต](equity.png)

## Drawdown อ่านอย่างไร

Drawdown = (มูลค่าปัจจุบัน / มูลค่าสูงสุดที่เคยมีถึงวันนั้น - 1) × 100
เช่น จากจุดสูงสุด 120 ลดเหลือ 108 เท่ากับ -10%
Maximum Drawdown คือค่าที่ติดลบมากที่สุดในช่วงนี้ (ไม่ใช่เพดานขาดทุนในอนาคต)
ใช้ NAV หลังต้นทุนและรวมจุดเริ่มต้น 100 ก่อนเสียค่าธรรมเนียม

![การลดลงจากจุดสูงสุด](drawdown.png)

![เปรียบเทียบตัวชี้วัด](comparison.png)

## สมมติฐานและข้อจำกัด

- ใช้ราคาปิดปรับแล้ว จำลองจัดพอร์ตที่ราคาปิดวันสุดท้าย Train จากนั้นถือจนจบ Test
- น้ำหนักลอยตามราคา ไม่ปรับกลับทุกวัน ต่างจากสูตรประมาณความเสี่ยง Train ที่ใช้น้ำหนักคงที่
- ค่าธรรมเนียมสมมติ {context['fee_rate']*100:.3f}% ต่อมูลค่าซื้อหรือขาย คิดประมาณการครั้งแรก ไม่มีค่าขายปิดพอร์ตตอนจบ
- หักต้นทุนจากเงินลงทุน ผลตอบแทน Test วันแรกรวมต้นทุนนี้ ไม่คิดซ้ำทุกวัน
- ยังไม่จำลองการส่งคำสั่งที่ซื้อขายได้จริง ไม่รวม slippage ภาษีและอัตราแลกเปลี่ยน
- ปฏิทินอิง CSV และชุดหุ้นอาจมี survivorship bias จากรายชื่อสมาชิกดัชนีปัจจุบัน
- N/A หมายถึงข้อมูลไม่พอประเมิน ไม่ใช่ผลตอบแทนเป็นศูนย์
- การทดสอบหนึ่งช่วงไม่รับประกันผลอนาคต และพอร์ตผันผวนต่ำอาจได้ผลตอบแทนต่ำกว่า
- รายงานนี้เป็นผลรันโปรแกรม ยังไม่ใช่รายงาน PDF ฉบับส่งวิชา

รายละเอียดสถานะข้อมูล: {json.dumps([{ 'strategy': row['strategy'], 'status': row['status']} for row in metrics], ensure_ascii=False)}

ไฟล์ประกอบในโฟลเดอร์นี้: metrics.csv, daily.csv, proposed_weights.csv และ run_context.json
'''
    (output / 'report.md').write_text(report, encoding='utf-8')
    return output, metrics
