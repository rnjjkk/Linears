# ให้บริการหน้า HTML และ API เฉพาะเครื่องนี้ โดยส่งงานคำนวณให้ Python เดิม
import argparse
import csv
import hmac
import importlib.util
import io
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .project_paths import PROJECT_ROOT, EXAMPLES_DIR, REPORTS_DIR, default_price_path
from .settings import load_policy, validate_policy

MAX_UPLOAD = 200 * 1024 * 1024
MAX_REQUEST = 128 * 1024


def validate_holdings(rows):
    # ตรวจหุ้น น้ำหนักรวม และค่าซ้ำก่อนส่งให้โค้ดวิเคราะห์
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('กรอกหุ้นอย่างน้อย 1 ตัว และไม่เกิน 100 ตัว')
    clean, seen = [], set()
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f'แถว {number}: รูปแบบข้อมูลไม่ถูกต้อง')
        ticker = str(row.get('ticker', '')).strip().upper().replace('.', '-')
        if not re.fullmatch(r'[A-Z][A-Z0-9^\-]{0,14}', ticker):
            raise ValueError(f'แถว {number}: กรุณากรอกชื่อหุ้น เช่น AAPL')
        if ticker in seen:
            raise ValueError(f'หุ้น {ticker} ซ้ำ กรุณารวมเป็นแถวเดียว')
        value = row.get('weight_percent')
        if isinstance(value, bool):
            raise ValueError(f'{ticker}: น้ำหนักต้องเป็นตัวเลข')
        try:
            weight = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'{ticker}: น้ำหนักต้องเป็นตัวเลข') from None
        if not math.isfinite(weight) or not 0 < weight <= 100:
            raise ValueError(f'{ticker}: น้ำหนักต้องมากกว่า 0 และไม่เกิน 100%')
        clean.append({'ticker': ticker, 'weight_percent': weight})
        seen.add(ticker)
    total = sum(row['weight_percent'] for row in clean)
    if not math.isclose(total, 100, rel_tol=0, abs_tol=0.000001):
        raise ValueError(f'น้ำหนักรวม {total:g}% กรุณาปรับให้รวมเป็น 100%')
    return clean


def report_path(relative):
    # อนุญาตให้อ่านเฉพาะไฟล์ผลลัพธ์ภายใน reports โดยไม่ผ่านลิงก์
    raw = Path(relative)
    if raw.is_absolute() or '..' in raw.parts or any(part.startswith('.') or part == '_working' for part in raw.parts):
        raise ValueError('พาธไฟล์ไม่ถูกต้อง')
    path = REPORTS_DIR / raw
    if not path.resolve().is_relative_to(REPORTS_DIR.resolve()):
        raise ValueError('พาธอยู่นอกโฟลเดอร์รายงาน')
    for part in [path, *path.parents]:
        if part == REPORTS_DIR:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError('ไม่อ่านไฟล์ผ่านลิงก์')
    if path.suffix.lower() not in ('.csv', '.json', '.md', '.txt', '.png') or not path.is_file():
        raise FileNotFoundError('ไม่พบไฟล์รายงาน')
    return path


class AppState:
    # เก็บสถานะงานเดียว เพื่อให้การเขียนทับรายงานไม่ชนกัน
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.job = None
        self.process = None
        self.workspace = PROJECT_ROOT / '.web'
        if self.workspace.is_symlink() or self.workspace.is_junction():
            raise ValueError('โฟลเดอร์ชั่วคราวของเว็บต้องไม่เป็นลิงก์')
        self.workspace.mkdir(exist_ok=True)
        self.price_path = default_price_path()
        self.price_label = self.price_path.name
        self.port = 0

    def busy(self):
        # บอกว่างานคำนวณกำลังทำอยู่หรือไม่
        return self.job is not None and self.job['status'] == 'running'

    def bootstrap(self):
        # ส่งค่าเริ่มต้น ตัวอย่าง และรายงานล่าสุดให้หน้าจอ
        examples = []
        for path in sorted((EXAMPLES_DIR / 'portfolios').glob('[0-9][0-9]_*.csv')):
            if not 1 <= int(path.name[:2]) <= 10:
                continue
            with path.open(encoding='utf-8-sig', newline='') as stream:
                holdings = validate_holdings(list(csv.DictReader(stream)))
            examples.append({'name': path.name, 'holdings': holdings})
        result = None
        saved = REPORTS_DIR / 'web_result.json'
        if saved.is_file():
            try:
                result = json.loads(saved.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                pass
        return {'token': self.token, 'config': load_policy(), 'examples': examples,
                'price': {'name': self.price_label, 'exists': self.price_path.is_file(),
                          'size': self.price_path.stat().st_size if self.price_path.is_file() else 0},
                'runtime_ready': all(importlib.util.find_spec(module) for module in ('numpy', 'matplotlib')),
                'job': self.job, 'result': result}

    def start_job(self, payload):
        # บันทึก input ชั่วคราวและเริ่มงานแยก โดยไม่แก้ config ต้นฉบับ
        holdings = validate_holdings(payload.get('holdings'))
        policy = validate_policy(payload.get('config'))
        label = str(payload.get('label', 'พอร์ตที่กรอก'))[:150]
        with self.lock:
            if self.busy():
                raise RuntimeError('กำลังวิเคราะห์อยู่ กรุณารอให้รอบนี้เสร็จก่อน')
            if not self.price_path.is_file():
                raise ValueError('ยังไม่มี CSV ราคา กรุณาเลือกไฟล์ราคาก่อน')
            if not all(importlib.util.find_spec(module) for module in ('numpy', 'matplotlib')):
                raise ValueError('ยังไม่มีไลบรารีคำนวณ กรุณาติดตั้งตาม README ก่อนใช้งานครั้งแรก')
            folder = Path(tempfile.mkdtemp(prefix='job_', dir=self.workspace))
            portfolio = folder / 'portfolio.csv'
            with portfolio.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['ticker', 'weight_percent'])
                writer.writeheader()
                writer.writerows(holdings)
            request = {'holdings': holdings, 'config': policy, 'portfolio_label': label,
                       'portfolio_path': str(portfolio), 'price_path': str(self.price_path),
                       'price_label': self.price_label}
            (folder / 'request.json').write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
            job_id = secrets.token_hex(12)
            self.job = {'id': job_id, 'status': 'running', 'message': 'เตรียมข้อมูล', 'started': time.time()}
            threading.Thread(target=self.run_job, args=(folder, job_id), daemon=True).start()
            return dict(self.job)

    def run_job(self, folder, job_id):
        # ติดตามสถานะจาก worker และส่งข้อผิดพลาดที่อ่านเข้าใจให้หน้าเว็บ
        environment = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        errors = []
        try:
            self.process = subprocess.Popen([sys.executable, '-m', 'longtripletun.web_worker',
                '--request', str(folder / 'request.json'), '--reports', str(REPORTS_DIR)],
                cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', env=environment,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(line.strip())
                    continue
                with self.lock:
                    if event.get('event') == 'progress':
                        self.job['message'] = event['message']
                    elif event.get('event') == 'error':
                        errors.append(event['message'])
            code = self.process.wait()
            with self.lock:
                self.job.update(status='done' if code == 0 else 'error', finished=time.time(),
                                message='วิเคราะห์เสร็จแล้ว' if code == 0 else '\n'.join(errors[-3:]) or 'วิเคราะห์ไม่สำเร็จ')
        except Exception as error:
            with self.lock:
                self.job.update(status='error', message=str(error), finished=time.time())
        finally:
            self.process = None
            # ลบเฉพาะโฟลเดอร์งานที่สร้างภายในพื้นที่ชั่วคราวของโปรแกรม
            if folder.resolve().is_relative_to(self.workspace.resolve()) and folder.name.startswith('job_'):
                shutil.rmtree(folder, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    # ให้บริการไฟล์หน้าจอและ API โดยรับการเขียนจากหน้าเว็บของตัวเองเท่านั้น
    def log_message(self, *_):
        # ไม่พิมพ์คำขอทั่วไปในหน้าต่างผู้ใช้
        pass

    @property
    def state(self):
        # คืนสถานะร่วมของเซิร์ฟเวอร์
        return self.server.app_state

    def send_bytes(self, data, content_type, status=200, filename=None):
        # ส่งข้อมูลพร้อมชนิดไฟล์และปิดการเก็บ cache ของรายงานเก่า
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        if content_type.startswith('text/html'):
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, payload, status=200):
        # ส่ง JSON ที่มีภาษาไทย
        self.send_bytes(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'), 'application/json; charset=utf-8', status)

    def check_request(self, mutation=False):
        # ป้องกันเว็บภายนอกสั่งงานเซิร์ฟเวอร์ในเครื่อง
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.state.port}', f'localhost:{self.state.port}'}
        if host not in allowed:
            raise PermissionError('ไม่อนุญาตให้เข้าถึงจากโฮสต์นี้')
        if mutation:
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://{item}' for item in allowed}:
                raise PermissionError('ไม่อนุญาตคำขอจากเว็บไซต์ภายนอก')
            if not hmac.compare_digest(self.headers.get('X-App-Token', ''), self.state.token):
                raise PermissionError('กรุณาโหลดหน้าเว็บใหม่ก่อนลองอีกครั้ง')

    def do_GET(self):
        # อ่านหน้าเว็บ รายงาน สถานะ และตัวอย่างข้อมูล
        try:
            self.check_request()
            url = urlsplit(self.path)
            if url.path in ('/', '/index.html'):
                return self.send_bytes((PROJECT_ROOT / 'web' / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if url.path == '/favicon.ico':
                return self.send_bytes(b'', 'image/x-icon', 204)
            if url.path == '/api/health':
                return self.send_json({'app': 'LongTripleTun', 'root': str(PROJECT_ROOT), 'port': self.state.port})
            if url.path == '/api/bootstrap':
                return self.send_json(self.state.bootstrap())
            if url.path == '/api/job':
                return self.send_json(self.state.job or {'status': 'idle'})
            if url.path == '/api/result':
                return self.send_bytes(report_path('web_result.json').read_bytes(), 'application/json; charset=utf-8')
            if url.path == '/api/files':
                files = []
                for path in (REPORTS_DIR / 'details').rglob('*'):
                    if path.is_file() and path.suffix in ('.csv', '.json', '.md', '.txt'):
                        files.append({'path': path.relative_to(REPORTS_DIR).as_posix(), 'name': path.name, 'size': path.stat().st_size})
                return self.send_json(sorted(files, key=lambda item: item['path']))
            if url.path == '/api/detail':
                query = parse_qs(url.query)
                path = report_path(query.get('file', [''])[0])
                offset = max(0, min(int(query.get('offset', ['0'])[0]), 100000))
                if path.suffix == '.csv':
                    with path.open(encoding='utf-8-sig', newline='') as stream:
                        reader = csv.reader(stream)
                        header = next(reader, [])
                        rows = []
                        for index, row in enumerate(reader):
                            if index < offset:
                                continue
                            rows.append(row)
                            if len(rows) == 101:
                                break
                    return self.send_json({'kind': 'table', 'header': header, 'rows': rows[:100], 'offset': offset, 'more': len(rows) > 100})
                text = path.read_text(encoding='utf-8-sig')
                return self.send_json({'kind': 'text', 'text': text[:150000], 'truncated': len(text) > 150000})
            if url.path == '/api/export':
                data = io.BytesIO()
                with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
                    names = json.loads((REPORTS_DIR / '.report_files.json').read_text(encoding='utf-8'))
                    for name in names:
                        path = report_path(name)
                        archive.write(path, name)
                return self.send_bytes(data.getvalue(), 'application/zip', filename='LongTripleTun-report.zip')
            if url.path.startswith('/reports/'):
                path = report_path(unquote(url.path[len('/reports/'):]))
                mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                return self.send_bytes(path.read_bytes(), mime, filename=path.name if path.suffix != '.png' else None)
            self.send_json({'error': 'ไม่พบหน้าที่ต้องการ'}, 404)
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except (ValueError, OSError, json.JSONDecodeError) as error:
            self.send_json({'error': str(error)}, 400)

    def do_POST(self):
        # รับการวิเคราะห์ การเลือกไฟล์ราคา และคำสั่งปิดเซิร์ฟเวอร์
        try:
            self.check_request(mutation=True)
            url = urlsplit(self.path)
            size = int(self.headers.get('Content-Length', '0'))
            if url.path == '/api/prices':
                if not 0 < size <= MAX_UPLOAD:
                    raise ValueError('CSV ราคาต้องมีขนาดไม่เกิน 200 MB')
                with self.state.lock:
                    if self.state.busy():
                        raise RuntimeError('กรุณารอการวิเคราะห์ก่อนเปลี่ยนไฟล์ราคา')
                    upload = self.state.workspace / 'uploaded-prices.tmp'
                    remaining = size
                    try:
                        with upload.open('wb') as stream:
                            while remaining:
                                block = self.rfile.read(min(1024 * 1024, remaining))
                                if not block:
                                    raise ValueError('อัปโหลดไฟล์ไม่ครบ กรุณาลองใหม่')
                                stream.write(block)
                                remaining -= len(block)
                        with upload.open(encoding='utf-8-sig', newline='') as stream:
                            columns = next(csv.reader(stream), [])
                        if not {'Date', 'Ticker', 'Close'}.issubset(columns):
                            raise ValueError('CSV ราคาต้องมีคอลัมน์ Date,Ticker,Close')
                        destination = self.state.workspace / 'uploaded-prices.csv'
                        os.replace(upload, destination)
                    finally:
                        upload.unlink(missing_ok=True)
                    self.state.price_path = destination
                    self.state.price_label = unquote(self.headers.get('X-File-Name', 'ราคาที่เลือก.csv'))[:150]
                return self.send_json({'name': self.state.price_label, 'exists': True, 'size': size})
            if not 0 <= size <= MAX_REQUEST:
                raise ValueError('คำขอมีขนาดใหญ่เกินไป')
            raw = self.rfile.read(size)
            payload = json.loads(raw or b'{}')
            if not isinstance(payload, dict):
                raise ValueError('รูปแบบคำขอไม่ถูกต้อง')
            if url.path == '/api/analyze':
                return self.send_json(self.state.start_job(payload), 202)
            if url.path == '/api/prices/default':
                with self.state.lock:
                    if self.state.busy():
                        raise RuntimeError('กรุณารอการวิเคราะห์ก่อนเปลี่ยนไฟล์ราคา')
                    self.state.price_path = default_price_path()
                    self.state.price_label = self.state.price_path.name
                return self.send_json(self.state.bootstrap()['price'])
            if url.path == '/api/shutdown':
                if self.state.busy():
                    raise RuntimeError('กรุณารอการวิเคราะห์ก่อนปิดโปรแกรม')
                self.send_json({'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send_json({'error': 'ไม่พบคำสั่ง'}, 404)
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except RuntimeError as error:
            self.send_json({'error': str(error)}, 409)
        except (ValueError, OSError, UnicodeError, csv.Error) as error:
            self.send_json({'error': str(error)}, 400)


def main():
    # เปิดเซิร์ฟเวอร์เฉพาะ localhost และเปิดเบราว์เซอร์เมื่อเรียกจากตัวเปิดเว็บ
    parser = argparse.ArgumentParser(description='LongTripleTun local web interface')
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    state = AppState()
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
            state.port = port
            break
        except OSError:
            try:
                with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=0.5) as response:
                    health = json.load(response)
                if health.get('app') == 'LongTripleTun' and health.get('root') == str(PROJECT_ROOT):
                    if args.launch:
                        webbrowser.open(f'http://127.0.0.1:{port}/')
                    return
            except (OSError, ValueError):
                pass
    if server is None:
        raise SystemExit('ไม่พบพอร์ตว่างสำหรับเปิดเว็บ')
    server.app_state = state
    if args.launch:
        webbrowser.open(f'http://127.0.0.1:{state.port}/')
    print(f'LongTripleTun: http://127.0.0.1:{state.port}/', flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
