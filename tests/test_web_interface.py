# ตรวจข้อมูลหน้าเว็บ ขอบเขตไฟล์ และการป้องกันคำขอจากเว็บไซต์อื่น
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from longtripletun import web_app
from longtripletun.web_worker import clean_json


class WebInputTests(unittest.TestCase):
    def test_holdings_normalization_and_validation(self):
        # รับข้อมูลปกติ และไม่ยอมให้หุ้นซ้ำหรือน้ำหนักผิดผ่านเข้าโปรแกรม
        self.assertEqual(web_app.validate_holdings([{'ticker': ' brk.b ', 'weight_percent': 100}]),
                         [{'ticker': 'BRK-B', 'weight_percent': 100.0}])
        for rows in [[], [{'ticker': 'A', 'weight_percent': 20}],
                     [{'ticker': 'A', 'weight_percent': True}],
                     [{'ticker': '<script>', 'weight_percent': 100}],
                     [{'ticker': 'A', 'weight_percent': 50}, {'ticker': 'a', 'weight_percent': 50}],
                     [{'ticker': 'A', 'weight_percent': float('nan')}]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                web_app.validate_holdings(rows)

    def test_report_paths_cannot_escape(self):
        # อ่านได้เฉพาะไฟล์รายงานที่อยู่ในโฟลเดอร์ผลลัพธ์
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            (root / 'details').mkdir()
            (root / 'details' / 'sample.csv').write_text('A,B\n1,2\n')
            with patch.object(web_app, 'REPORTS_DIR', root):
                self.assertEqual(web_app.report_path('details/sample.csv'), root / 'details/sample.csv')
                for name in ['../requirements.txt', str(root.parent / 'outside.csv'), '.private.json', '_working/secret.csv']:
                    with self.subTest(name=name), self.assertRaises((ValueError, FileNotFoundError)):
                        web_app.report_path(name)

    def test_nonfinite_values_become_json_null(self):
        # ค่าไม่มีนิยามต้องไม่ทำให้ JSON ฝั่งเว็บอ่านไม่ได้
        self.assertEqual(clean_json({'sd': float('nan'), 'nested': [float('inf'), 2]}),
                         {'sd': None, 'nested': [None, 2]})

    def test_local_api_requires_token_and_local_origin(self):
        # เว็บภายนอกต้องสั่งวิเคราะห์ไม่ได้ และไฟล์ราคาผิดรูปแบบต้องไม่ถูกนำมาใช้
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            with patch.object(web_app, 'PROJECT_ROOT', root):
                state = web_app.AppState()
            server = ThreadingHTTPServer(('127.0.0.1', 0), web_app.Handler)
            state.port = server.server_address[1]
            server.app_state = state
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{state.port}'
            try:
                with urlopen(base + '/api/health') as response:
                    self.assertEqual(json.load(response)['app'], 'LongTripleTun')
                requests = [
                    ({'Content-Type': 'application/json'}, b'{}', '/api/analyze', 403),
                    ({'X-App-Token': state.token, 'Origin': 'https://example.org'}, b'{}', '/api/analyze', 403),
                    ({'X-App-Token': state.token}, b'{}', '/api/analyze', 400),
                    ({'X-App-Token': state.token}, b'ticker,weight_percent\nA,100\n', '/api/prices', 400),
                ]
                for headers, body, route, status in requests:
                    with self.subTest(route=route, status=status):
                        request = Request(base + route, data=body, headers=headers, method='POST')
                        with self.assertRaises(HTTPError) as error:
                            urlopen(request)
                        self.assertEqual(error.exception.code, status)
                self.assertIsNone(state.job)
                self.assertFalse((state.workspace / 'uploaded-prices.csv').exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
