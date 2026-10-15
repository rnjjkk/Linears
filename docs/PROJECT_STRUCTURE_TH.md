# โครงสร้างและสถานะฉบับเพื่อน — ตรวจ 16 ต.ค. 2569

## หน้าที่โมดูล

| ไฟล์ใน longtripletun/ | หน้าที่ |
|---|---|
| price_data.py | อ่านราคา ตรวจ missing/ซ้ำ และคำนวณผลตอบแทน |
| candidate_analysis.py | covariance/PCA ร่วมของหุ้นเดิมและผู้สมัคร, cosine shortlist |
| rebalance.py | ทดลองสัดส่วน 5/10/15/20% และเทียบ wᵀΣw |
| holdout.py | buy and hold และต้นทุนเริ่มต้น |
| risk_levels.py | ทางเลือก 0–3 ระดับตาม SD ที่ประมาณก่อนทดสอบ |
| recommendation.py | Fit/Validation gate, HHI และความสัมพันธ์พอร์ต |
| report_charts.py | NAV, Drawdown, กราฟและตาราง |
| user_summary.py | สรุปภาษาไทยสำหรับผู้ใช้ |
| report_store.py | เผยแพร่ latest หลังสำเร็จ ป้องกันลบไฟล์ที่ไม่รู้จัก |
| project_paths.py | พาธ input/config/data/reports อ้างจากรากโปรเจกต์ |
| stock_symbols.py | อ่านรายชื่อ Slickcharts สำหรับเครื่องมือดาวน์โหลด |

main.py เป็นจุดเริ่มต้น, scripts/ เป็นเครื่องมือดาวน์โหลดและสำรวจหลายพอร์ต, config/ เก็บ policy, tests/ เก็บชุดทดสอบ, examples/ เก็บ input, reports/ เก็บผลรัน, docs/ เก็บคู่มือ

## สูตรที่ใช้จริง

- R แถวเป็นวัน คอลัมน์เป็นหุ้น; R @ w ใช้ในบทเรียน/สถิติแบบน้ำหนักคงที่
- X = R - mean(R); sample covariance Σ = X.T @ X / (n-1)
- Portfolio variance = w.T @ Σ @ w; SD คือรากที่สอง
- PCA: ΣV = VΛ; stock loadings L = V_k sqrt(Λ_k); portfolio loading = w @ L; ใช้ cosine เพื่อ shortlist
- เพิ่มหุ้น C น้ำหนัก a โดยหุ้นเดิมคูณ (1-a) และ C ใช้ a ไม่มีเงินใหม่หรือ short
- HHI = sum(w²), effective holdings = 1/HHI; correlation คู่หุ้นวัดจาก covariance
- Test เป็น buy and hold น้ำหนักลอยตามราคา ต่างจาก R @ w แบบคงน้ำหนัก
- ค่า fee 0.001 คูณสัดส่วนซื้อ/ขายรวม หักตอนเริ่ม ไม่ใช่ปรับพอร์ตรายวัน
- คำแนะนำผ่าน Fit/Validation ก่อน Test; ผล Train เต็มยังเก็บเป็นทางเลือกเปรียบเทียบ

## Snapshot ที่ตรวจพบ

CSV ราคาเดิม 630,762 แถว, 503 ticker, 1,254 วันราคา, 1,253 เวกเตอร์ผลตอบแทน Train 1,002 วัน (2021-10-15–2025-10-13), Test 251 วัน (2025-10-14–2026-10-13)

พอร์ตล่าสุดคือ 02_multi_sector จำนวน 8 หุ้น ไม่ใช่พอร์ตเริ่มต้น AAPL/MSFT/GOOGL มีหุ้นผ่าน Train 491 ตัว PCA ร่วมใช้ 235 แกน อธิบาย variance 95.0454%

ตัวเปรียบเทียบจาก Train เลือก GIS 20% แต่ **คำแนะนำสุดท้ายคือคงพอร์ตเดิม** ไม่มีทางเลือกผ่าน Validation อย่าอ่าน proposed_weights.csv แทน recommended_weights.csv

Test พอร์ตเดิม: net return 22.8835%, daily SD 0.6686%, MDD -5.4877% ทางเลือก Train ระดับต่ำ: net return 12.3951%, SD 0.6342%, MDD -9.1152% ลด SD ได้แต่เสียผลตอบแทนและ Drawdown แย่ลง

Audit ของพอร์ต 8 หุ้นนี้ไม่มีช่องราคาขาด/ผิดเกณฑ์หรือวันผลตอบแทนที่ตัดออก ไม่ได้หมายความว่าหุ้นทั้ง 503 ตัวสมบูรณ์ทั้งหมด

## สิ่งที่ยังขาดในชุดไฟล์ที่ได้รับ

- ไฟล์ราคาต้นฉบับ sp500_daily_5years.csv ไม่อยู่ในโปรเจกต์หรือสองโฟลเดอร์แม่ที่เคยค้น ต้องนำ CSV เดิมมาใส่ data/raw ก่อนทำซ้ำผลตลาดจริง การดาวน์โหลดใหม่คืออีก snapshot
- มี 8 พอร์ตใน examples/portfolios รวม examples/portfolio.csv เป็น 9 ตัวอย่าง ยังขาด 1 ตัวอย่างให้ครบ Demo 10
- ผลสำรวจที่เพื่อนแนบมามีเพียงพอร์ตเริ่มต้นและ 01–03 ยังไม่ใช่ผลครบ 9 input
- ยังไม่พบหลักฐาน peer test, รายงาน PDF, PPTX หรือเอกสาร assignment เดิมในเวอร์ชันนี้

ผลคำนวณเก่าทั้งหมดและ CSV ตัวอย่างคงเนื้อหาเดิม การจัดโฟลเดอร์เปลี่ยนตำแหน่ง imports พาธ และเอกสารนำทาง ไม่ปรับสูตรหรือเกณฑ์ความคุ้มค่า
