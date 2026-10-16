# ตรวจว่ารูปในรายงานหลักและรายงานรายละเอียดเปิดได้หลังย้ายเอกสาร
import re
import tempfile
import unittest
from pathlib import Path
from longtripletun.user_summary import write_user_summary


class UserSummaryLinksTests(unittest.TestCase):
    def test_images_resolve_from_both_report_locations(self):
        # รายงานที่ย้ายลง details ต้องยังชี้ถึงรูปที่รากรายงาน
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            images = ['equity.png', 'drawdown.png', 'comparison.png']
            for image in images: (root/image).write_bytes(b'image fixture')
            (root/'report.md').write_text('\n'.join(f'![figure]({image})' for image in images), encoding='utf-8')
            row = dict(strategy='original', label='พอร์ตเดิม', net_total_return_percent=0,
                       net_daily_volatility_percent=1, max_drawdown_percent=-5,
                       profit_money=0, profit_difference_money=0, final_money=100000)
            decision = {'checks': [], 'approved_levels': []}
            concentration = {'holdings': 1, 'largest_ticker': 'A',
                             'largest_weight_percent': 100, 'top_three_weight_percent': 100}
            levels = {'rows': [row], 'capital': 100000}
            context = {'test_start': '2020-01-01', 'test_end': '2020-01-03', 'fee_rate': 0.001}
            write_user_summary(root, decision, concentration, levels, context)
            for report in [root/'report.md', root/'details/report.md']:
                links = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', report.read_text(encoding='utf-8'))
                self.assertEqual(len(links), 3)
                for target in links: self.assertTrue((report.parent/target).is_file(), target)
