# สร้างสรุปภาษาไทยและแยกรายละเอียดคำนวณออกจากหน้ารายงาน
from pathlib import Path
from datetime import datetime


def portfolio_header(context):
    # จัดข้อความชื่อพอร์ต วันที่ และสัดส่วนหุ้นสำหรับหัวรายงาน
    timestamp = context.get('generated_at')
    when = datetime.fromisoformat(timestamp).strftime('%d/%m/%Y %H:%M:%S') if timestamp else 'ไม่ทราบเวลา (รายงานเก่า)'
    source = context.get('portfolio_source', 'ไม่ทราบชื่อไฟล์ (รายงานเก่า)')
    rows = context.get('portfolio_holdings', [])
    lines = [f'**สร้างรายงาน:** {when} (เวลาไทย UTC+7)', '', f'**ไฟล์พอร์ตที่ใช้:** `{source}`', '',
             '## พอร์ตตั้งต้นของคุณ', '', '| หุ้น | สัดส่วนลงทุน (%) |', '|---|---:|']
    for row in rows:
        lines.append(f"| {row['ticker']} | {float(row['weight_percent']):.2f} |")
    if rows:
        lines.append(f"| **รวม** | **{sum(float(row['weight_percent']) for row in rows):.2f}** |")
    else:
        lines.append('| ไม่พบข้อมูลพอร์ตตั้งต้น | — |')
    lines += ['', 'เป็นสัดส่วนที่กรอกก่อนปรับพอร์ต ไม่ใช่น้ำหนักที่เปลี่ยนตามราคาตอนสิ้นสุดการทดสอบ', '']
    return '\n'.join(lines)


def write_user_summary(folder, decision, concentration, levels, context):
    # สร้างหน้าสรุปผลภาษาไทยพร้อมลิงก์รายละเอียดและกราฟ
    folder = Path(folder)
    details = folder / 'details'
    details.mkdir(exist_ok=True)
    # ย้ายเอกสารรายละเอียดที่เพิ่งสร้างในรอบนี้ ไม่กระทบไฟล์นำเข้าหรือซอร์สโค้ด
    for item in list(folder.iterdir()):
        if item.is_file() and item.suffix in ('.csv', '.json', '.md'):
            if item.suffix == '.md':
                # รายงานย้ายลง details แต่รูปยังอยู่ที่รากรายงาน
                text = item.read_text(encoding='utf-8')
                for image in ('equity.png', 'drawdown.png', 'comparison.png'):
                    text = text.replace(f'({image})', f'(../{image})')
                item.write_text(text, encoding='utf-8')
            item.rename(details / item.name)
        elif item.name == 'approved_test' and item.is_dir():
            item.rename(details / item.name)
    fmt = lambda value, digits=2: 'ข้อมูลไม่ครบ' if value is None else f'{value:,.{digits}f}'
    old = next(row for row in levels['rows'] if row['strategy'] == 'original')
    keep_reason = ('ยังไม่พบทางเลือกที่ลดการแกว่งได้เพียงพอ โดยรักษาผลตอบแทนและการลดลงจากยอดให้อยู่ในเกณฑ์ที่กำหนด'
                   if decision['checks'] else 'ข้อมูลหรือทางเลือกที่ประเมินได้ยังไม่เพียงพอ จึงยังแนะนำให้เปลี่ยนพอร์ตไม่ได้')
    lines = ['# LongTripleTun — สรุปพอร์ตของคุณ', '', portfolio_header(context), '',
             '**' + ('คงพอร์ตเดิม' if not decision['approved_levels'] else 'มีทางเลือกปรับพอร์ตที่ผ่านเกณฑ์') + '**', '',
             (keep_reason
              if not decision['approved_levels'] else 'ทางเลือกด้านล่างผ่านเกณฑ์จากข้อมูลช่วงก่อนทดสอบ คุณสามารถพิจารณาปรับหรือคงพอร์ตเดิมได้'), '',
             f"ช่วงที่เปรียบเทียบผล: **{context['test_start']} ถึง {context['test_end']}**", '',
             '## ภาพรวมพอร์ต', '',
             f"ถือหุ้น {concentration['holdings']} ตัว โดย {concentration['largest_ticker']} มีสัดส่วนมากที่สุด **{concentration['largest_weight_percent']:.0f}%** และสามอันดับแรกรวม **{concentration['top_three_weight_percent']:.0f}%** ของพอร์ต", '',
             '## ทางเลือกที่ผ่านเกณฑ์', '']
    if not decision['approved_levels']:
        lines += ['**ไม่มี — คงสัดส่วนเดิมและไม่เสียค่าปรับพอร์ตเพิ่มในแบบจำลองนี้**', '']
    else:
        for option in decision['approved_levels']:
            holdings = [f'{ticker} {weight*100:.1f}%' for ticker, weight in zip(decision['screening']['tickers'], option['weights']) if weight > 0]
            lines.append(f"- ระดับ {option['level']} ({option['label']}): " + ', '.join(holdings))
        # ผลของตัวเลือกที่ผ่านด่านจริง ไม่ใช้ตัวเลือกวิเคราะห์เดิมมาแทน
        import csv
        metrics = details / 'approved_test' / 'risk_levels.csv'
        with metrics.open(encoding='utf-8-sig', newline='') as stream:
            accepted = list(csv.DictReader(stream))
        lines += ['', '| พอร์ต | ผลตอบแทนสุทธิ % | ความผันผวนรายวัน % | Max Drawdown % |', '|---|---:|---:|---:|']
        for row in accepted:
            vals = [fmt(float(row[k])) if row[k] else 'ข้อมูลไม่ครบ' for k in ('net_total_return_percent', 'net_daily_volatility_percent','max_drawdown_percent')]
            lines.append(f"| {row['label']} | " + ' | '.join(vals) + ' |')
        lines += ['']
    lines += ['## เปรียบเทียบทางเลือกเดิมเพื่อให้เห็นสิ่งที่ต้องแลก', '',
              '**ตารางและกราฟส่วนนี้เป็นการเปรียบเทียบ ไม่ใช่คำแนะนำให้ซื้อ** ระดับต่ำ–สูงเรียงตามการแกว่งที่ประมาณก่อนทดสอบ และเป็นคนละชุดกับทางเลือกที่ผ่านเกณฑ์ด้านบน', '',
              '| พอร์ต | ผลตอบแทนสุทธิ ก่อน → หลัง % | ความผันผวนรายวัน ก่อน → หลัง % | Max Drawdown % |',
              '|---|---:|---:|---:|']
    for row in levels['rows']:
        lines.append(f"| {row['label']} | {fmt(old['net_total_return_percent'])} → {fmt(row['net_total_return_percent'])} | {fmt(old['net_daily_volatility_percent'],4)} → {fmt(row['net_daily_volatility_percent'],4)} | {fmt(row['max_drawdown_percent'])} |")
    lines += ['']
    for row in levels['rows']:
        if row['strategy'].startswith('level_'):
            lines.append(f"- **{row['label']}:** {row['explanation']}")
    lines += ['', f"## ถ้าเริ่มด้วยเงิน {levels['capital']:,.0f} หน่วย", '',
              '| พอร์ต | กำไร/ขาดทุน | ต่างจากพอร์ตเดิม | เงินปลายช่วง |', '|---|---:|---:|---:|']
    for row in levels['rows']:
        lines.append(f"| {row['label']} | {fmt(row['profit_money'])} | {fmt(row['profit_difference_money'])} | {fmt(row['final_money'])} |")
    lines += ['', '## กราฟเปรียบเทียบ', '',
              'Original = พอร์ตเดิม · Proposed = ทางเลือกเดิมที่ประมาณการแกว่งต่ำสุด (เพื่อเปรียบเทียบ) · Equal weight = แบ่งเงินเท่ากันในหุ้นเดิม', '',
              '### มูลค่าพอร์ต เริ่มต้นที่ 100', '', '![มูลค่าพอร์ต](equity.png)', '',
              '### การลดลงจากจุดสูงสุด', '', '![การลดลงจากจุดสูงสุด](drawdown.png)', '',
              '### ผลตอบแทนและความเสี่ยง', '', '![เปรียบเทียบผล](comparison.png)', '',
              '## อ่านตัวเลขอย่างไร', '',
              '- ผลตอบแทนสุทธิ: กำไรหรือขาดทุนตลอดช่วงที่ระบุ หลังค่าธรรมเนียมสมมติ ไม่ใช่ผลตอบแทนต่อปี',
              '- ความผันผวนรายวัน: ขนาดการแกว่งของผลตอบแทน ค่าน้อยไม่ได้แปลว่ากำไรมากหรือขาดทุนน้อยเสมอ',
              '- Max Drawdown: เคยลดจากยอดก่อนหน้าหนักที่สุดเท่าไร เช่น −20% คือจากยอด 100 เหลือ 80 ไม่ใช่โอกาสขาดทุน 20%',
              f"- ค่าธรรมเนียมสมมติ {context['fee_rate']*100:.2f}% ต่อมูลค่าซื้อหรือขาย ไม่รวมภาษีและอัตราแลกเปลี่ยน",
              '- ข้อมูลไม่ครบหมายถึงประเมินไม่ได้ ไม่ใช่ผลเป็นศูนย์ ผลย้อนหลังไม่รับประกันผลในอนาคต', '']
    text = '\n'.join(lines)
    (folder / 'report.md').write_text(text, encoding='utf-8')
    return text
