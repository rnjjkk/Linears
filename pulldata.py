import yfinance as yf
import pandas as pd

# รายชื่อจาก Slickcharts; ใช้ตัวอ่านร่วมกับ stockdata.py
from stock_symbols import SOURCE_URL, fetch_sp500_tickers

tickers = fetch_sp500_tickers()
print("แหล่งรายชื่อ:", SOURCE_URL)
print("จำนวนหุ้นทั้งหมด:", len(tickers))

# โหลดข้อมูลย้อนหลัง 5 ปี แบบรายวัน
data = yf.download(
    tickers,
    period="5y",
    interval="1d",
    auto_adjust=True,
    group_by="ticker",
    threads=True
)

all_data = []

for ticker in tickers:
    try:
        df = data[ticker].copy()

        df = df.reset_index()
        df["Ticker"] = ticker

        df = df[
            ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
        ]

        all_data.append(df)

    except:
        pass

# รวมทุกหุ้นไว้ในไฟล์เดียว
final_df = pd.concat(all_data, ignore_index=True)

final_df.to_csv(
    "sp500_daily_5years.csv",
    index=False
)

print("บันทึกไฟล์เรียบร้อย")
