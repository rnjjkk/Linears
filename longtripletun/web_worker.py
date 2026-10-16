# รันการวิเคราะห์เดิมในกระบวนการแยก แล้วจัดผลสำหรับหน้าเว็บ
import argparse
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
from unittest.mock import patch


def read_csv(path):
    # อ่านตารางผลลัพธ์ที่มีอยู่ โดยไม่คำนวณสูตรใหม่
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def clean_json(value):
    # เปลี่ยนค่าที่ไม่มีนิยามเป็น null เพื่อให้เบราว์เซอร์อ่าน JSON ได้
    import math
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def run_request(request_path, destination):
    # เรียก main.py ด้วยข้อมูลที่ตรวจแล้ว และเผยแพร่ผลเมื่อทำครบทุกส่วน
    from . import settings, project_paths
    from .report_store import begin_report, publish_report
    request_path = Path(request_path)
    request = json.loads(request_path.read_text(encoding='utf-8'))
    policy = settings.validate_policy(request['config'])
    price = Path(request['price_path'])
    workspace = request_path.parent
    private_reports = workspace / 'report'
    # ใช้ค่าของคำขอนี้ในกระบวนการแยก ไม่แก้ config บนดิสก์หรือกระทบ TUI
    settings.load_policy = lambda path=None: dict(policy)
    project_paths.REPORTS_DIR = private_reports
    os.environ['MPLBACKEND'] = 'Agg'
    os.environ['MPLCONFIGDIR'] = str(workspace / 'mpl')
    stream = sys.stdout

    def progress(message):
        # ส่งสถานะตามขั้นที่ทำจริงให้หน้าเว็บ
        print(json.dumps({'event': 'progress', 'message': message}, ensure_ascii=False), file=stream, flush=True)

    class Capture(io.StringIO):
        # เก็บคำอธิบายสูตรจาก Terminal พร้อมส่งชื่อขั้นตอนที่กำลังทำ
        def write(self, text):
            if '---' in text:
                label = text.strip().strip('-').strip()
                if label:
                    progress(label[:180])
            return super().write(text)

    log = Capture()
    progress('ตรวจข้อมูลและเตรียมผลตอบแทน')
    answers = [request['portfolio_path'], '1', str(price)]
    with patch('builtins.input', side_effect=answers), contextlib.redirect_stdout(log):
        namespace = runpy.run_path(str(project_paths.PROJECT_ROOT / 'main.py'), run_name='__main__')
    if not (private_reports / 'report.md').is_file():
        messages = log.getvalue().strip().splitlines()
        raise ValueError('\n'.join(messages[-4:]) or 'การวิเคราะห์ไม่สำเร็จ')

    from .holdout import evaluate_costs
    from .report_charts import calculate_drawdown
    decision = namespace['recommendation']
    context = dict(namespace['report_context'])
    context['portfolio_source'] = request['portfolio_label']
    context['portfolio_holdings'] = request['holdings']
    context['price_label'] = request['price_label']
    # แสดงชื่อไฟล์ที่ผู้ใช้เลือกแทนพาธไฟล์ชั่วคราว
    context_path = private_reports / 'details' / 'run_context.json'
    saved_context = json.loads(context_path.read_text(encoding='utf-8'))
    saved_context.update(context)
    context_path.write_text(json.dumps(clean_json(saved_context), ensure_ascii=False, indent=2), encoding='utf-8')
    root_report = private_reports / 'report.md'
    root_report.write_text(root_report.read_text(encoding='utf-8').replace(request['portfolio_path'], request['portfolio_label']), encoding='utf-8')

    def chart_series(rows, strategy, key, label, metric):
        # จัดเส้นกราฟจากผล Buy and Hold เดิม พร้อมตัวเลขสุทธิ
        data = [row for row in rows if row['strategy'] == strategy]
        if metric['status'] != 'ok' or not data:
            return {'key': key, 'label': label, 'status': metric['status'], 'metrics': metric, 'points': []}
        nav = [float(row['net_nav']) for row in data]
        drawdown, maximum = calculate_drawdown(nav)
        return {'key': key, 'label': label, 'status': 'ok',
                'metrics': {**metric, 'max_drawdown_percent': maximum},
                'points': [{'date': row['date'], 'nav': value, 'drawdown': float(dd)}
                           for row, value, dd in zip(data, nav, drawdown)]}

    costs = namespace['cost_result']
    original_metric = next(row for row in costs['summary'] if row['strategy'] == 'original')
    series = [chart_series(costs['daily'], 'original', 'original', 'พอร์ตเดิม', original_metric)]
    approved = []
    progress('จัดผลของทางเลือกที่ผ่านเกณฑ์และสร้างกราฟสำหรับเว็บ')
    for option in decision['approved_levels']:
        fitted = decision['screening']
        evaluated = evaluate_costs(price, namespace['train_days'][-1], namespace['test_days'],
                                   fitted['tickers'], fitted['weights'], option['weights'], fee_rate=policy['fee_rate'])
        metric = next(row for row in evaluated['summary'] if row['strategy'] == 'proposed')
        key = f"level_{option['level']}"
        trial = option['trial']
        approved.append({'key': key, 'level': option['level'], 'label': option['label'],
                         'ticker': trial['ticker'], 'addition': trial['new_stock_weight_percent'],
                         'holdings': [{'ticker': ticker, 'weight_percent': float(weight * 100)}
                                      for ticker, weight in zip(fitted['tickers'], option['weights']) if weight > 0]})
        series.append(chart_series(evaluated['daily'], 'proposed', key,
                                   f"เพิ่ม {trial['ticker']} {trial['new_stock_weight_percent']:g}%", metric))
    result = clean_json({'context': saved_context, 'status': decision['status'], 'reason': decision['reason'],
                         'holdings': request['holdings'], 'approved': approved, 'series': series,
                         'checks': decision['checks'], 'concentration': namespace['concentration'],
                         'audit': namespace['price_audit'], 'config': policy})
    (private_reports / 'web_result.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (private_reports / 'details' / 'calculations.txt').write_text(
        log.getvalue().replace(request['portfolio_path'], request['portfolio_label']).replace(str(private_reports), str(destination)),
        encoding='utf-8')
    progress('บันทึกรายงานชุดปัจจุบัน')
    draft = begin_report(Path(destination))
    for source in private_reports.iterdir():
        if source.name in ('.report_files.json', '_working') or source.name.startswith('.'):
            continue
        if source.is_dir():
            shutil.copytree(source, draft / source.name)
        else:
            shutil.copy2(source, draft / source.name)
    saved, warnings = publish_report(draft)
    print(json.dumps({'event': 'complete', 'warnings': warnings}, ensure_ascii=False), file=stream, flush=True)


def main():
    # รับคำขอจากเซิร์ฟเวอร์ในเครื่องและแจ้งข้อผิดพลาดเป็นภาษาไทย
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--reports', required=True)
    args = parser.parse_args()
    try:
        run_request(args.request, args.reports)
    except Exception as error:
        print(json.dumps({'event': 'error', 'message': str(error)}, ensure_ascii=False), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
