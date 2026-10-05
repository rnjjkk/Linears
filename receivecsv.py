from pathlib import Path
import csv
import math


def read_portfolio(file_path):
    tickers = []
    weights = []

    # utf-8-sig รองรับ CSV UTF-8 ที่บันทึกจาก Excel
    with open(file_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        required_columns = {"ticker", "weight_percent"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError(
                "CSV ต้องมีคอลัมน์ ticker และ weight_percent"
            )

        for row_number, row in enumerate(reader, start=2):
            ticker = (row.get("ticker") or "").strip().upper()

            if not ticker:
                raise ValueError(f"แถว {row_number}: ไม่ได้ระบุชื่อหุ้น")

            if ticker in tickers:
                raise ValueError(f"แถว {row_number}: หุ้น {ticker} ซ้ำ")

            try:
                percent = float(row.get("weight_percent") or "")
            except ValueError:
                raise ValueError(
                    f"แถว {row_number}: น้ำหนักต้องเป็นตัวเลข"
                ) from None

            if not math.isfinite(percent) or not 0 < percent <= 100:
                raise ValueError(
                    f"แถว {row_number}: น้ำหนักต้องมากกว่า 0 และไม่เกิน 100"
                )

            tickers.append(ticker)
            weights.append(percent / 100)

    if not tickers:
        raise ValueError("ไฟล์ไม่มีข้อมูลหุ้น")

    if not math.isclose(sum(weights), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError(
            f"น้ำหนักรวมต้องเป็น 100% แต่ได้ {sum(weights) * 100:.4f}%"
        )

    return tickers, weights


try:
    user_input = input("กรุณาระบุพาธไฟล์ CSV: ")

    # ตัดช่องว่างและเครื่องหมายคำพูดที่ติดมาจากการคัดลอกพาธ
    file_path = Path(user_input.strip().strip("\"'")).expanduser()

    if not file_path.is_file():
        raise ValueError("ไม่พบไฟล์ กรุณาตรวจสอบพาธ")

    if file_path.suffix.lower() != ".csv":
        raise ValueError("กรุณาเลือกไฟล์นามสกุล .csv")

    tickers, weights = read_portfolio(file_path)

    print("\nอ่านไฟล์สำเร็จ!")
    print("หุ้นในพอร์ต:", tickers)
    print("เวกเตอร์น้ำหนัก:", weights)

    # ต่อด้วยขั้นตอนวิเคราะห์พอร์ตตรงนี้

except (ValueError, OSError) as error:
    print("เกิดข้อผิดพลาด:", error)