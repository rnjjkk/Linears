# LongTripleTun (beta1)

โปรเจกต์วิเคราะห์พอร์ตหุ้น S&P 500 ด้วย covariance และ PCA พร้อมเปรียบเทียบผลตอบแทน ความผันผวน และ Maximum Drawdown และตรวจความคุ้มค่าด้วย Fit/Validation ก่อนเสนอปรับพอร์ต

## เริ่มใช้งาน

ใช้ Python 3.13 (เวอร์ชันที่ทดสอบบน Windows)

```powershell
python -m pip install -r longtripletun/requirements.txt
cd longtripletun
python main.py
```

กรอกพาธ CSV พอร์ตเมื่อโปรแกรมถาม หรือกด Enter ใช้ portfolio.csv เลือกโหมด 1 เพื่อใช้ข้อมูลราคาจริง หรือโหมด 2 เพื่อเรียนสูตรจากข้อมูลสมมติ

ไฟล์ราคาย้อนหลังจริงที่ใช้บนเครื่องพัฒนาอยู่ภายนอก repo และไม่ได้รวมใน branch นี้ ต้องเตรียม CSV คอลัมน์ Date,Ticker,Open,High,Low,Close,Volume แล้วกรอกพาธในโปรแกรม หรือใช้ตัวดาวน์โหลดจากโฟลเดอร์ราก repo:

```powershell
python -m pip install -r requirements-download.txt
python stockdata.py
```

ตัวดาวน์โหลดดึงรายชื่อจาก Slickcharts และราคาจาก yfinance หากเว็บปฏิเสธการเชื่อมต่อ จะให้กรอกพาธ HTML ที่บันทึกจากเบราว์เซอร์ ผลดาวน์โหลด sp500_daily_5years.csv อยู่ในโฟลเดอร์ที่ Terminal ทำงาน และเขียนทับชื่อเดิมเมื่อดาวน์โหลดสำเร็จ รายชื่อปัจจุบันอาจมีอคติเมื่อนำไปทดสอบย้อนหลัง

## รายงานและตัวอย่าง

- longtripletun/reports/latest/report.md: สรุปผู้ใช้ พร้อมเวลาสร้าง ชื่อไฟล์พอร์ต สัดส่วนหุ้น ตัวชี้วัด และกราฟ
- longtripletun/reports/latest/details/: ข้อมูลคำนวณสำหรับตรวจสอบ
- longtripletun/example_portfolios/: พอร์ตสมมติ 8 ตัวอย่าง
- longtripletun/LongTripleTun_workflow_guide.md: คู่มืออธิบายขั้นตอนและทฤษฎี
- longtripletun/recommendation_policy.json: เกณฑ์ความคุ้มค่าแบบทดลอง

รายงานใน repo เป็นตัวอย่างจากข้อมูลบนเครื่องพัฒนา พาธแหล่งข้อมูลในรายงานจึงต้องปรับเมื่อใช้เครื่องอื่น รายงาน latest จะเปลี่ยนเมื่อรันใหม่สำเร็จ รายงานเก่าที่โปรแกรมรู้จักจะถูกล้าง โดยเก็บไฟล์ที่ไม่รู้จักไว้

## ทดสอบ

```powershell
cd longtripletun
python -m unittest test_report_store.py test_recommendation.py test_risk_levels.py
python compare_example_portfolios.py --prices "พาธไฟล์ราคาของคุณ.csv"
```

ผลย้อนหลังเป็นการทดลอง ไม่รับประกันผลอนาคต การลดความผันผวนไม่ได้รับประกันกำไรหรือ Drawdown ที่ดีขึ้น ไม่มีการส่งคำสั่งซื้อขายจริง
