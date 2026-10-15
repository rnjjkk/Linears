"""อ่านรายชื่อหุ้นจากตาราง Slickcharts เพื่อส่งต่อให้ yfinance."""

from io import StringIO
from pathlib import Path
import re

import pandas as pd
import requests

SOURCE_URL = "https://www.slickcharts.com/sp500"


def parse_symbols(html):
    tables = pd.read_html(StringIO(html))
    matches = [table for table in tables
               if {"Company", "Symbol", "Weight"}.issubset(table.columns)]
    if len(matches) != 1:
        raise ValueError("ไม่พบตารางรายชื่อหุ้นที่ชัดเจนใน Slickcharts; โครงสร้างเว็บอาจเปลี่ยน")
    symbols = matches[0]["Symbol"]
    if symbols.isna().any():
        raise ValueError("ตาราง Slickcharts มีช่อง Symbol ว่าง")
    tickers = symbols.astype(str).str.strip().str.upper().str.replace(".", "-", regex=False).tolist()
    if any(re.fullmatch(r"[A-Z][A-Z0-9-]*", ticker) is None for ticker in tickers):
        raise ValueError("พบ Symbol รูปแบบไม่ถูกต้องใน Slickcharts")
    if len(set(tickers)) != len(tickers):
        raise ValueError("พบ Symbol ซ้ำใน Slickcharts")
    # ตรวจความสมเหตุสมผล ไม่กำหนดว่าต้องมี 500 หลักทรัพย์พอดี
    if not 450 <= len(tickers) <= 550:
        raise ValueError(f"ได้รายชื่อ {len(tickers)} ตัว ซึ่งผิดจากช่วงที่คาดไว้ กรุณาตรวจหน้าเว็บ")
    return tickers


def fetch_sp500_tickers():
    try:
        response = requests.get(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        print("อ่าน Slickcharts ผ่านเครือข่ายไม่ได้:", error)
        print("เปิด", SOURCE_URL, "ในเบราว์เซอร์ แล้วบันทึกหน้าเว็บเป็น HTML (Ctrl+S)")
        print("ข้อมูลจะอ้างอิงเวลาที่บันทึกไฟล์ HTML; ยังไม่ได้ดาวน์โหลดราคาหรือเขียนทับ CSV")
        html_path = input("พาธไฟล์ HTML ที่บันทึกไว้ [Enter = ยกเลิก]: ").strip().strip('"')
        if not html_path:
            raise RuntimeError("ยกเลิกการดึงรายชื่อ ยังไม่ได้เริ่มดาวน์โหลดราคา") from error
        return parse_symbols(Path(html_path).read_text(encoding="utf-8-sig"))
    return parse_symbols(response.text)


if __name__ == "__main__":
    symbols = fetch_sp500_tickers()
    print("แหล่งรายชื่อ:", SOURCE_URL)
    print("จำนวนหุ้น:", len(symbols))
    print("ตัวอย่าง 10 ตัวแรก:", ", ".join(symbols[:10]))
