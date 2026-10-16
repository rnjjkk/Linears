# โครงสร้างโปรเจกต์

| ตำแหน่ง | หน้าที่ |
|---|---|
| `main.py` | รับ CSV และแสดงขั้นคำนวณจนสร้างรายงาน |
| `longtripletun/settings.py` | อ่าน ตรวจ และส่งค่าตั้งร่วมให้ทุกขั้น |
| `longtripletun/price_data.py` | อ่านราคา ตรวจข้อมูล และคำนวณผลตอบแทน |
| `longtripletun/candidate_analysis.py` | สร้าง covariance/PCA และ shortlist |
| `longtripletun/rebalance.py` | ทดลองน้ำหนักหุ้นใหม่ |
| `longtripletun/recommendation.py` | ความกระจุกตัวและด่าน Fit/Validation |
| `longtripletun/holdout.py` | Buy and Hold และต้นทุนเริ่มต้น |
| `longtripletun/risk_levels.py` | เลือกระดับและเปรียบเทียบผล |
| `longtripletun/report_charts.py`, `user_summary.py` | กราฟและสรุปผลภาษาไทย |
| `longtripletun/report_store.py` | เขียนทับผลชุดเดิมและคืนไฟล์เมื่อบันทึกล้มเหลว |
| `longtripletun/project_paths.py` | ค้นหาพาธจากรากโปรเจกต์ |
| `longtripletun/stock_symbols.py` | รายชื่อหุ้นสำหรับเครื่องมือดาวน์โหลด |
| `config/` | JSON ค่าตั้งและคำอธิบายหน่วย |
| `examples/portfolios/` | ตัวอย่างมาตรฐาน 01–10 |
| `examples/learning/` | ผลตอบแทนสมมติสำหรับโหมด 2 |
| `examples/portfolio.csv` | พอร์ตเริ่มต้นเมื่อกด Enter |
| `data/raw/sp500_daily_5years.csv` | CSV ราคาที่ผู้ใช้ใส่หรือเปลี่ยนเอง |
| `scripts/compare_example_portfolios.py` | เปรียบเทียบพอร์ตตัวอย่าง 01–10 |
| `scripts/pulldata.py` | เครื่องมือดาวน์โหลดเพิ่มเติมเมื่อจำเป็น |
| `tests/` | ชุดทดสอบสูตร พฤติกรรม ค่าตั้ง และรายงาน |
| `reports/` | สรุป กราฟ และรายละเอียดของพอร์ตที่รันล่าสุด |
| `reports/comparisons/` | ผลเปรียบเทียบตัวอย่างทั้ง 10 |

ดูผลปัจจุบันจาก [รายงานหลัก](../reports/report.md) หรือ [รายงานเปรียบเทียบ](../reports/comparisons/comparison.md) ตรวจช่วงข้อมูลและ config ใน metadata ของแต่ละรายงาน ไม่ถือว่าผลสองชุดใช้ข้อมูลเดียวกันเสมอ

ดู [วิธีใช้แบบสั้น](../README.md) และ [สูตรกับขั้นตอนละเอียด](LongTripleTun_workflow_guide.md) หลักฐานการส่งงานและการทดลองกับผู้ร่วมชั้นต้องจัดเตรียมแยกจากการรันโปรแกรมอัตโนมัติ
