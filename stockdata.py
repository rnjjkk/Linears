
import pandas as pd
import yfinance as yf
import time

# 1. ดึงรายชื่อหุ้นจาก Slickcharts; ราคาย้อนหลังยังมาจาก yfinance
from longtripletun.stock_symbols import SOURCE_URL, fetch_sp500_tickers

tickers = fetch_sp500_tickers()
print("แหล่งรายชื่อ:", SOURCE_URL)

print("จำนวนหุ้นทั้งหมด:", len(tickers))
# 2. แบ่งหุ้นเป็นกลุ่ม กลุ่มละ 50 ตัว
all_data = []

for start in range(0, len(tickers), 50):
    batch = tickers[start:start + 50]

    print("กำลังดาวน์โหลด:", batch[0],
          "ถึง", batch[-1])

    try:
        data = yf.download(
            batch,
            period="5y",
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False
        )

        # 3. แยกข้อมูลของหุ้นแต่ละตัว
        for ticker in batch:
            try:
                df = data[ticker].copy()

                if df.empty or "Close" not in df.columns:
                    print("ไม่มีข้อมูล:", ticker)
                    continue

                df = df.reset_index()
                df["Ticker"] = ticker

                columns = [
                    "Date", "Ticker", "Open",
                    "High", "Low", "Close", "Volume"
                ]

                df = df[columns]
                all_data.append(df)

            except (KeyError, TypeError):
                print("ข้ามหุ้น:", ticker)

    except Exception as e:
        print("ดาวน์โหลดกลุ่มนี้ไม่สำเร็จ:", e)

    time.sleep(1)

# 4. รวมข้อมูลและบันทึกเป็น CSV
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)

    final_df.to_csv(
        "sp500_daily_5years.csv",
        index=False
    )

    print("ดาวน์โหลดเสร็จแล้ว!")
    print("จำนวนแถว:", len(final_df))
    print("จำนวนหุ้นที่มีข้อมูล:",
          final_df["Ticker"].nunique())
else:
    print("ไม่พบข้อมูล กรุณาตรวจสอบอินเทอร์เน็ต")
