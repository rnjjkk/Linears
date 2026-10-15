# LongTripleTun

วิเคราะห์พอร์ตด้วย Vector, Covariance Matrix และ PCA แล้วตรวจความคุ้มค่าก่อนเสนอปรับพอร์ต ผลย้อนหลังไม่รับประกันอนาคต

## เริ่มใช้งาน

รันจากโฟลเดอร์ที่มี main.py:

```powershell
python -m pip install -r requirements.txt
python main.py
```

กด Enter เพื่อใช้ `examples/portfolio.csv` หรือกรอก `examples/portfolios/02_multi_sector.csv` รับชื่อไฟล์สั้นหรือพาธเต็มได้เช่นกัน

```csv
ticker,weight_percent
AAPL,60
MSFT,30
GOOGL,10
```

น้ำหนักต้องเป็นบวกและรวม 100% เวอร์ชันนี้ไม่รับ `ticker,shares` หรือ `ticker,weight` แบบเดิม

- โหมด 1 อ่าน CSV ราคา คอลัมน์ขั้นต่ำ `Date,Ticker,Close` วางที่ `data/raw/sp500_daily_5years.csv` หรือกรอกพาธเอง
- โหมด 2 ใช้ข้อมูลสมมติใน `examples/learning/` เพื่อเรียนสูตร พอร์ตต้องมีหุ้นตรงกับตัวอย่าง โหมดนี้ยังไม่ค้นหุ้นใหม่หรือสร้างรายงานตลาดจริง
- **ไฟล์ราคาต้นฉบับยังไม่อยู่ในโปรเจกต์** เปิดผลรันเดิมได้ แต่ต้องนำ CSV เดิมกลับมาก่อนทำซ้ำผลชุดเดียวกัน

## โครงสร้าง

```text
Linear/
  main.py                       รับ input และอธิบายขั้นคำนวณ
  README.md
  requirements.txt              ไลบรารีวิเคราะห์
  requirements-download.txt     ไลบรารีเพิ่มสำหรับดาวน์โหลด
  longtripletun/                 โมดูลคำนวณและสร้างรายงาน
  config/                       เกณฑ์ Fit/Validation
  examples/
    portfolio.csv               พอร์ตเริ่มต้น
    learning/                   ผลตอบแทนสมมติ
    portfolios/                 พอร์ตตัวอย่าง 8 ชุดและคำอธิบาย
  scripts/                      ดาวน์โหลด / เปรียบเทียบหลายพอร์ต
  tests/                        ชุดทดสอบ
  docs/                         คู่มือสูตรและโครงสร้าง
  data/raw/                     วาง CSV ราคาที่ต้องการวิเคราะห์
  reports/
    report.md                   สรุปผู้ใช้
    equity.png / drawdown.png / comparison.png
    details/                    รายละเอียดคำนวณ CSV/JSON/Markdown
    comparisons/         ผลสำรวจหลายพอร์ต
    _working/                   ไฟล์ชั่วคราวขณะรันโหมด 1
```

## Workflow ปัจจุบัน

1. CSV พอร์ต → ตรวจน้ำหนัก → CSV ราคา → return `Close_t / Close_previous - 1` ไม่เติมราคา missing
2. แบ่ง Train/Test 80/20 ตามปฏิทินก่อนคัด missing ต้องเหลือ Train ≥150 วันและ Test ≥50 วัน
3. Train: `X = R - mean(R)`, `Σ = X.T @ X / (n-1)`, variance `w.T @ Σ @ w`; PCA เก็บ variance ≥95%, cosine ของ loadings ช่วย shortlist หุ้นนอกพอร์ต 10 ตัว
4. ทดลองหุ้นใหม่ทีละตัว 5/10/15/20% ลดหุ้นเดิมตามสัดส่วน เลือกลด variance ด้วย covariance เต็ม
5. **คำแนะนำสุดท้ายใช้ด่านแยก:** Train แบ่ง Fit 75% / Validation 25%; เลือกหุ้นและน้ำหนักบน Fit แล้วตรวจ Validation หลังค่าธรรมเนียม SD ลด ≥5%, ผลตอบแทนสุทธิลดไม่เกิน 2 จุดเปอร์เซ็นต์ และ Drawdown ไม่แย่ลง ไม่ผ่านให้คงพอร์ตเดิม
6. ล็อกทางเลือกก่อน Test: buy and hold น้ำหนักลอยตามราคา คิดค่าธรรมเนียมเริ่มต้น 0.10% ต่อมูลค่าซื้อ/ขาย ไม่รวมภาษี slippage หรือ FX ผล Train เต็มมีไว้เปรียบเทียบแยกจากคำแนะนำสุดท้าย

แก้เกณฑ์ใน `config/recommendation_policy.json` ผลชุดนี้เป็นการสำรวจย้อนหลัง เพราะพัฒนาวิธีหลังเห็น Test เดิมแล้ว

## อ่านผลลัพธ์และคู่มือ

- [สรุปผู้ใช้](reports/report.md)
- [คำแนะนำสุดท้ายและเหตุผล](reports/details/recommendation.md)
- [ผลสำรวจหลายพอร์ตเดิม](reports/comparisons/comparison.md)
- [คู่มือสูตรคำนวณ](docs/LongTripleTun_workflow_guide.md)
- [หน้าที่โมดูลและสถานะล่าสุด](docs/PROJECT_STRUCTURE_TH.md)

รายงานเดิมบันทึกพาธต้นทาง `C:\kmitl\...` ตามจริง ไม่ใช่พาธที่ต้องมีบนเครื่องนี้ รอบใหม่จะแทนที่ reports หลังทำงานสำเร็จ

## รายงานล่าสุดชุดเดียว

ทุกครั้งที่รันโหมดราคาจริงสำเร็จ โปรแกรมเขียนทับ `reports/report.md` กราฟ และไฟล์ใน `reports/details/` ด้วยผลของพอร์ตที่เพิ่งเลือก ล้างไฟล์ผลเก่าที่รอบใหม่ไม่ได้ใช้ ไม่สร้างโฟลเดอร์รายงานตามวันเวลาหรือสะสมรายงานแต่ละพอร์ต

ระหว่างคำนวณใช้ `.building_current` และ `_working` เป็นพื้นที่ชั่วคราวชื่อเดิม ถ้ารอบใหม่ไม่สำเร็จ รายงานล่าสุดที่ทำเสร็จแล้วยังอยู่ ให้รันโปรแกรมทีละรอบ

เครื่องมือเปรียบเทียบหลายพอร์ตใช้ `reports/comparisons` ชุดเดียวแยกจากรายงานหลัก และเขียนทับเมื่อเรียกเครื่องมือนี้ซ้ำ โหมดบทเรียนข้อมูลสมมติแสดงสูตรใน Terminal และไม่เปลี่ยนรายงานตลาดจริง

## ทดสอบและเปรียบเทียบ

```powershell
python -m unittest discover -s tests -v
python scripts/compare_example_portfolios.py --help
python scripts/compare_example_portfolios.py --prices "C:\path\sp500_daily_5years.csv"
```

การเปรียบเทียบหลายพอร์ตใช้สูตรเดิม บันทึก reports/comparisons แยกจากรายงานหลัก

ดาวน์โหลด snapshot ใหม่เมื่อจำเป็น:

```powershell
python -m pip install -r requirements-download.txt
python scripts/pulldata.py
```

บันทึก data/raw/sp500_daily_5years.csv ใช้รายชื่อ Slickcharts และราคา yfinance หากเว็บปฏิเสธ Python โค้ดเดิมให้กรอก HTML ที่บันทึกจากเบราว์เซอร์ การดาวน์โหลดใหม่อาจได้ผลต่างจากรายงานเดิม
