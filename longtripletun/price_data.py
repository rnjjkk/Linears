"""อ่าน CSV ที่ stockdata.py สร้าง โดยไม่เรียกดาวน์โหลดซ้ำ

รับราคา long format: Date,Ticker,Open,High,Low,Close,Volume
คืน dates และเมทริกซ์ผลตอบแทนทศนิยม โดยเรียงหุ้นตาม tickers ที่รับเข้า
"""

import csv
import math
from datetime import date
from pathlib import Path


def load_price_returns(csv_path, tickers):
    csv_path = Path(csv_path)
    wanted = set(tickers)
    prices = {ticker: {} for ticker in tickers}
    market_days = set()
    all_tickers = set()
    total_rows = 0
    selected_rows = 0
    invalid_prices = 0

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not {"Date", "Ticker", "Close"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV ราคาต้องมีคอลัมน์ Date, Ticker และ Close")
        for row in reader:
            total_rows += 1
            ticker = (row["Ticker"] or "").strip().upper()
            if not ticker:
                raise ValueError(f"CSV ราคาแถวข้อมูลที่ {total_rows}: ไม่มี Ticker")
            try:
                day = date.fromisoformat((row["Date"] or "").strip()).isoformat()
            except ValueError:
                raise ValueError(f"CSV ราคาแถวข้อมูลที่ {total_rows}: วันที่ต้องเป็น YYYY-MM-DD") from None
            market_days.add(day)
            all_tickers.add(ticker)
            if ticker not in wanted:
                continue
            selected_rows += 1
            if day in prices[ticker]:
                raise ValueError(f"พบราคาซ้ำของ {ticker} วันที่ {day}; ต้องแก้ข้อมูลก่อน")
            try:
                close = float(row["Close"])
            except (ValueError, TypeError):
                close = math.nan
            if not math.isfinite(close) or close <= 0:
                invalid_prices += 1
                prices[ticker][day] = None
            else:
                prices[ticker][day] = close

    missing = [ticker for ticker in tickers if ticker not in all_tickers]
    if missing:
        raise ValueError("ไม่พบหุ้นใน CSV ราคา: " + ", ".join(missing))
    ordered_days = sorted(market_days)
    if len(ordered_days) < 2:
        raise ValueError("ต้องมีราคาอย่างน้อย 2 วันเพื่อคำนวณผลตอบแทน")

    days = []
    returns_matrix = []
    skipped_dates = []
    first_example = None
    # คำนวณคู่วันที่ติดกันในชุดข้อมูลก่อนคัด missing เพื่อไม่ข้ามช่วงราคาแล้วเรียกว่ารายวัน
    for previous_day, current_day in zip(ordered_days, ordered_days[1:]):
        if any(prices[ticker].get(previous_day) is None
               or prices[ticker].get(current_day) is None for ticker in tickers):
            skipped_dates.append(current_day)
            continue
        daily_returns = []
        for ticker in tickers:
            previous_price = prices[ticker][previous_day]
            current_price = prices[ticker][current_day]
            stock_return = current_price / previous_price - 1
            if not math.isfinite(stock_return):
                raise ValueError(f"ผลตอบแทนผิดปกติของ {ticker} วันที่ {current_day}")
            daily_returns.append(stock_return)
        days.append(current_day)
        returns_matrix.append(daily_returns)
        if first_example is None:
            ticker = tickers[0]
            first_example = {
                "ticker": ticker, "previous_day": previous_day, "day": current_day,
                "previous_price": prices[ticker][previous_day],
                "price": prices[ticker][current_day], "return": daily_returns[0],
            }

    if len(days) < 150:
        raise ValueError(f"เหลือข้อมูลสมบูรณ์เพียง {len(days)} วัน ต้องมีอย่างน้อย 150 วัน")

    audit = {
        "source": str(csv_path.resolve()), "total_rows": total_rows,
        "total_stocks": len(all_tickers), "selected_rows": selected_rows,
        "price_start": ordered_days[0], "price_end": ordered_days[-1],
        "price_days": len(ordered_days), "potential_return_days": len(ordered_days)-1,
        # กำหนดเส้นแบ่งจากปฏิทินก่อนตัด missing ไม่ให้ missing ใน test เลื่อนขอบเขต train
        "train_boundary_80pct": ordered_days[int((len(ordered_days)-1) * 0.8)],
        "return_days": len(days), "invalid_selected_prices": invalid_prices,
        "missing_selected_price_cells": sum(
            prices[ticker].get(day) is None for ticker in tickers for day in ordered_days),
        "skipped_return_dates": skipped_dates, "first_example": first_example,
        "policy": "No filling or outlier clipping; keep only adjacent observed market-date pairs with complete portfolio prices.",
        "limitation": "Calendar inferred from CSV; dates missing for ALL stocks cannot be detected without an exchange calendar.",
    }
    return days, returns_matrix, audit
