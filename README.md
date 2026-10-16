# LongTripleTun

วิเคราะห์พอร์ตหุ้นด้วยเวกเตอร์ เมทริกซ์ และ PCA เพื่อค้นหาทางเลือกกระจายความเสี่ยง

## 1. ติดตั้ง

เปิด Terminal ในโฟลเดอร์ที่มี `main.py` แล้วรัน:

```bat
py -m pip install -r requirements.txt
```

## 2. เตรียมข้อมูล

วาง CSV ราคาที่ต้องการใช้ใน `data/raw/sp500_daily_5years.csv` คอลัมน์ขั้นต่ำ `Date,Ticker,Close` วันที่ใช้ `YYYY-MM-DD` ผู้ใช้เปลี่ยนไฟล์ราคาเองได้

เลือกพอร์ตตัวอย่าง **01–10** ใน `examples/portfolios/` หรือสร้าง CSV ของตัวเอง:

```csv
ticker,weight_percent
AAPL,60
MSFT,30
GOOGL,10
```

น้ำหนักต้องเป็นบวกและรวม 100% ตั้งค่าการแบ่งข้อมูล, PCA, shortlist, น้ำหนักทดลอง, fee และเกณฑ์ผ่านได้ใน [config/recommendation_policy.json](config/recommendation_policy.json) ดูหน่วยใน [คู่มือ config](config/README_TH.md)

## 3. รัน

**หน้าเว็บ:** ดับเบิลคลิก `OpenWeb.cmd` โปรแกรมจะเริ่ม Python ในเครื่องและเปิดหน้าจอให้อัตโนมัติ เลือกตัวอย่าง กรอกตาราง หรืออัปโหลดพอร์ต CSV แล้วกดวิเคราะห์ ปรับค่าด้วยแถบเลื่อนหรือพิมพ์ตัวเลขได้ มีธีมสว่าง/มืดและแผงรายละเอียด

ติดตั้งตามข้อ 1 ครั้งแรกให้เรียบร้อย 
หน้าเว็บรวม HTML/CSS/JavaScript ใน `web/index.html` 
กด “ปิดโปรแกรม” บนหน้าเว็บเมื่อเลิกใช้งาน

**Terminal (วิธีเดิม):**

```bat
py main.py
```

กรอกพอร์ต เช่น `examples/portfolios/01_popular_large_cap.csv` → เลือก **1** → กด Enter เพื่อใช้ไฟล์ราคาเริ่มต้น

เปรียบเทียบตัวอย่างครบ 10 พอร์ตด้วย config เดียวกัน:

```bat
py scripts/compare_example_portfolios.py
```

## 4. อ่านผล

- [รายงานพอร์ตที่เลือก](reports/report.md) — อ่านหัวข้อ **ทางเลือกที่ผ่านเกณฑ์**
- [ผลเปรียบเทียบ 10 พอร์ต](reports/comparisons/comparison.md)
- [เหตุผลผ่าน/ไม่ผ่าน](reports/details/recommendation.md) และไฟล์น้ำหนักใน `reports/details/recommended_weights.csv`

รันใหม่สำเร็จจะเขียนทับรายงานชุดเดิม แต่ละทางเลือกเป็นคนละพอร์ต ไม่ใช่ซื้อทุกตัวพร้อมกัน

## 5. ข้อจำกัด

ผลย้อนหลังไม่รับประกันกำไร หากไม่มีทางเลือกผ่านเกณฑ์จะคงพอร์ตเดิม ค่าธรรมเนียมเป็นแบบจำลอง ไม่รวมภาษีหรืออัตราแลกเปลี่ยน ใช้ข้อมูลราคาและ config ชุดเดียวกันเมื่อเปรียบเทียบพอร์ต

[สูตรและขั้นตอนละเอียด](docs/WORKFLOW.md) · [โครงสร้างโปรเจกต์](docs/PROJECT_STRUCTURE_TH.md)
