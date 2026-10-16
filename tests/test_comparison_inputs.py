# ตรวจว่าการเปรียบเทียบเลือกพอร์ต 01–10 ครบและไม่รวมไฟล์นอกชุด
import tempfile
import unittest
from pathlib import Path
from scripts.compare_example_portfolios import example_portfolio_files


class ComparisonInputTests(unittest.TestCase):
    def test_exact_ten_examples_and_reject_incomplete_or_duplicate_number(self):
        # ไฟล์ 00 และ 11 ต้องไม่ถูกรวม ส่วนเลขที่ซ้ำหรือขาดต้องแจ้งข้อผิดพลาด
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            for number in range(12):
                (root/f'{number:02d}_sample.csv').write_text('ticker,weight_percent\nA,100\n')
            selected = example_portfolio_files(root)
            self.assertEqual([int(p.name[:2]) for p in selected], list(range(1,11)))
            duplicate = root/'01_duplicate.csv'
            duplicate.write_text('ticker,weight_percent\nA,100\n')
            with self.assertRaises(ValueError):
                example_portfolio_files(root)
            duplicate.unlink()
            (root/'10_sample.csv').unlink()
            with self.assertRaises(ValueError):
                example_portfolio_files(root)
