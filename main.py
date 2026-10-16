# ภาพรวม: รับพอร์ตและข้อมูลราคา อธิบายการคำนวณ แล้วสร้างคำแนะนำและรายงานผล
"""แบ่ง Train/Test ตามเวลา และวิเคราะห์พอร์ตจาก Train เท่านั้น"""

import csv
import json
from longtripletun.price_data import load_price_returns
import math
from pathlib import Path
import sys
from longtripletun.project_paths import (PROJECT_ROOT, EXAMPLES_DIR, REPORTS_DIR, default_price_path, resolve_portfolio)

# ทำให้ Terminal บน Windows แสดงภาษาไทยได้
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    # 1. รับชื่อไฟล์หรือพาธจากผู้ใช้
    filename = input("กรอกชื่อไฟล์ CSV [Enter = examples/portfolio.csv]: ").strip().strip('"')
    if filename == "":
        filename = "portfolio.csv"

    # รับพาธเต็ม พาธจากรากโปรเจกต์ หรือชื่อ CSV ใน examples/
    file_path = resolve_portfolio(filename)

    # 2. อ่าน CSV: หัวคอลัมน์เป็นชื่อข้อมูลของแต่ละแถว
    with open(file_path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        rows = list(reader)

    # 3. แสดงข้อมูลที่อ่านได้ ยังไม่คำนวณความเสี่ยง
    print("\nไฟล์ที่อ่าน:", file_path)
    print("ชื่อคอลัมน์:", columns)
    print("จำนวนแถวข้อมูล:", len(rows))

    for number, row in enumerate(rows, start=1):
        print(f"แถวที่ {number}: {row}")

    # 4. ต้องมีทั้งชื่อหุ้นและน้ำหนัก เพื่อจับคู่ข้อมูลให้ถูกต้อง
    if not columns or "ticker" not in columns or "weight_percent" not in columns:
        raise ValueError("ไฟล์ต้องมีคอลัมน์ ticker และ weight_percent")
    if not rows:
        raise ValueError("ไฟล์ไม่มีข้อมูลพอร์ต")

    # 5. แปลงข้อความเป็นตัวเลข แล้วบวกสะสมทีละแถว
    total_weight = 0.0
    tickers = []
    weights = []

    for number, row in enumerate(rows, start=1):
        # ตัดช่องว่างและเปลี่ยนชื่อหุ้นเป็นตัวใหญ่ เช่น aapl -> AAPL
        ticker = (row["ticker"] or "").strip().upper()
        if ticker == "":
            raise ValueError(f"แถวข้อมูลที่ {number}: ชื่อหุ้นต้องไม่ว่าง")
        if ticker in tickers:
            raise ValueError(f"แถวข้อมูลที่ {number}: ชื่อหุ้น {ticker} ซ้ำ")

        weight_text = row["weight_percent"]
        try:
            weight = float(weight_text)
        except (ValueError, TypeError):
            raise ValueError(
                f"แถวข้อมูลที่ {number}: น้ำหนัก {weight_text!r} ไม่ใช่ตัวเลข"
            ) from None

        if not math.isfinite(weight) or not 0 < weight <= 100:
            raise ValueError(f"แถวข้อมูลที่ {number}: น้ำหนักต้องมากกว่า 0 และไม่เกิน 100")

        total_weight = total_weight + weight
        # เก็บคู่กันตามลำดับแถว: หุ้นตำแหน่งแรกใช้น้ำหนักตำแหน่งแรก
        tickers.append(ticker)
        weights.append(weight / 100)

    # 6. ตรวจผลรวม โดยยอมให้คลาดเคลื่อนเล็กน้อยจากทศนิยมของคอมพิวเตอร์
    print(f"\nน้ำหนักรวม: {total_weight:.2f}%")
    if not math.isclose(total_weight, 100.0, rel_tol=0, abs_tol=0.000001):
        raise ValueError("น้ำหนักรวมต้องเป็น 100% กรุณาแก้ข้อมูลใน CSV")
    print("ผ่าน: น้ำหนักรวมเป็น 100%")
#----------------------------------------------------------------------------------------------------------
    # 7. แสดงเวกเตอร์เฉพาะเมื่อข้อมูลทั้งหมดผ่านการตรวจสอบ
    print("\nรายชื่อหุ้น:", tickers)
    print("เวกเตอร์น้ำหนัก:", weights)
    print(f"ผลรวมเวกเตอร์น้ำหนัก: {sum(weights):.6f}")

    for ticker, weight in zip(tickers, weights):
        print(f"{ticker}: {weight * 100:.2f}% -> {weight:.4f}")
#------------------------------------------------------------------------------------------------------------
    # 8–10. เลือกแหล่งข้อมูล: ราคาจริงจาก stockdata หรือบทเรียนข้อมูลสมมติ
    data_mode = input("\nแหล่งข้อมูล: 1 = CSV ราคาจริง, 2 = ตัวอย่างสมมติ [Enter = 1]: ").strip() or "1"
    if data_mode not in ("1", "2"):
        raise ValueError("กรุณาเลือก 1 หรือ 2")

    if data_mode == "1":
        base_path = PROJECT_ROOT
        default_path = default_price_path()
        print("ไฟล์ราคาเริ่มต้น:", default_path)
        price_input = input("พาธ CSV ราคา [Enter = ใช้ไฟล์ข้างบน]: ").strip().strip('"')
        price_path = Path(price_input) if price_input else default_path
        if not price_path.is_absolute():
            price_path = base_path / price_path

        days, returns_matrix, price_audit = load_price_returns(price_path, tickers)
        data_label = "ข้อมูลราคาจริงจาก CSV (ผลตอบแทนย้อนหลัง)"
        print(f"\nCSV มี {price_audit['total_rows']:,} แถว จาก {price_audit['total_stocks']} หุ้น")
        print(f"ช่วงราคา: {price_audit['price_start']} ถึง {price_audit['price_end']}")
        print(f"เลือกเฉพาะหุ้นในพอร์ต {len(tickers)} ตัว; ได้ผลตอบแทน {len(days):,} วัน")
        print(f"ราคาที่ขาดหรือใช้ไม่ได้: {price_audit['missing_selected_price_cells']} ช่อง")
        print(f"คู่วันที่ตัดออกเพราะราคาไม่ครบ: {len(price_audit['skipped_return_dates'])} วัน")
        example = price_audit['first_example']
        print(f"ตัวอย่าง {example['ticker']}: {example['previous_day']} -> {example['day']}")
        print(f"({example['price']:.6f} / {example['previous_price']:.6f}) - 1"
              f" = {example['return']:.8f} หรือ {example['return'] * 100:.4f}%")
        # เก็บ audit ของการรันล่าสุดเพื่อเปิดตรวจวันและข้อมูลที่ถูกตัด
        scratch_path = REPORTS_DIR / "_working"
        scratch_path.mkdir(parents=True, exist_ok=True)
        audit_path = scratch_path / "last_price_audit.json"
        audit_path.write_text(json.dumps(price_audit, ensure_ascii=False, indent=2), encoding="utf-8")
        print("บันทึกรายละเอียดการอ่านราคา:", audit_path)
        print("ขั้นต่อไปจะแบ่ง Train/Test ก่อนคำนวณสถิติ ยังไม่มีคำแนะนำลงทุน")
    else:
        data_label = "ข้อมูลสมมติ ไม่ใช่ข้อมูลตลาดจริง"
        # 8. อ่านผลตอบแทนสมมติ 1 วัน เก็บคู่ชื่อหุ้นเพื่อไม่พึ่งลำดับแถว CSV
        returns_path = EXAMPLES_DIR / "learning" / "daily_returns_example.csv"
        print("\n--- ผลตอบแทนสมมติ 1 วัน สำหรับฝึกคำนวณ ไม่ใช่ข้อมูลตลาดจริง ---")
        print("ไฟล์ผลตอบแทน:", returns_path)
        returns_by_ticker = {}

        with open(returns_path, encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not {"ticker", "return_percent"}.issubset(reader.fieldnames):
                raise ValueError("ไฟล์ผลตอบแทนต้องมีคอลัมน์ ticker และ return_percent")

            for number, row in enumerate(reader, start=1):
                ticker = (row["ticker"] or "").strip().upper()
                if not ticker or ticker in returns_by_ticker:
                    raise ValueError(f"แถวผลตอบแทนที่ {number}: ชื่อหุ้นต้องไม่ว่างและไม่ซ้ำ")
                try:
                    return_percent = float(row["return_percent"])
                except (ValueError, TypeError):
                    raise ValueError(f"แถวผลตอบแทนที่ {number}: ผลตอบแทนต้องเป็นตัวเลข") from None
                if not math.isfinite(return_percent) or return_percent < -100:
                    raise ValueError(f"แถวผลตอบแทนที่ {number}: ผลตอบแทนต้องเป็นค่าจำกัดและไม่ต่ำกว่า -100%")
                returns_by_ticker[ticker] = return_percent / 100

        # เรียงเวกเตอร์ผลตอบแทนตามรายชื่อหุ้นในพอร์ตเสมอ
        returns = []
        for ticker in tickers:
            if ticker not in returns_by_ticker:
                raise ValueError(f"ไม่พบผลตอบแทนของ {ticker} ในไฟล์ตัวอย่าง")
            returns.append(returns_by_ticker[ticker])

        print("เวกเตอร์ผลตอบแทน:", returns)

        # 9. Dot Product: คู่น้ำหนักกับผลตอบแทน คูณทีละคู่ แล้วบวกทั้งหมด
        portfolio_return = 0.0
        for ticker, weight, stock_return in zip(tickers, weights, returns):
            contribution = weight * stock_return
            portfolio_return = portfolio_return + contribution
            print(f"{ticker}: {weight:.4f} x {stock_return:.4f} = {contribution:.6f}")

        print(f"ผลตอบแทนพอร์ตแบบทศนิยม: {portfolio_return:.6f}")
        print(f"ผลตอบแทนพอร์ตในวันสมมตินี้: {portfolio_return * 100:.2f}%")
    #------------------------------------------------------------------------------------------------------------
        # 10. อ่านข้อมูลหลายวัน: แต่ละแถวคือหนึ่งวัน แต่ละคอลัมน์หุ้นคือผลตอบแทน (%)
        history_path = EXAMPLES_DIR / "learning" / "multi_day_returns_example.csv"
        days = []
        returns_matrix = []

        with open(history_path, encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not {"day", *tickers}.issubset(reader.fieldnames):
                raise ValueError("ไฟล์หลายวันต้องมีคอลัมน์ day และชื่อหุ้นทุกตัวในพอร์ต")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("ไฟล์หลายวันมีชื่อคอลัมน์ซ้ำ")

            for row in reader:
                day = (row["day"] or "").strip()
                if not day or day in days:
                    raise ValueError("ชื่อวันต้องไม่ว่างและไม่ซ้ำ")

                daily_returns = []
                for ticker in tickers:
                    try:
                        value = float(row[ticker])
                    except (ValueError, TypeError):
                        raise ValueError(f"วัน {day}: ผลตอบแทนของ {ticker} ต้องเป็นตัวเลข") from None
                    if not math.isfinite(value) or value < -100:
                        raise ValueError(f"วัน {day}: ผลตอบแทนของ {ticker} ไม่ถูกต้อง")
                    daily_returns.append(value / 100)

                days.append(day)
                returns_matrix.append(daily_returns)

    if not returns_matrix:
        raise ValueError("ไฟล์หลายวันไม่มีข้อมูล")

    # 10.1 แบ่งตามเวลา: อดีตใช้สร้างแบบจำลอง อนาคตเก็บไว้ทดสอบ ไม่สุ่มสลับวัน
    all_days = days[:]
    all_returns_matrix = returns_matrix[:]
    test_days = []
    test_returns_matrix = []

    if data_mode == "1":
        # นับวันที่ใช้ได้ซึ่งอยู่ก่อน/ตรงเส้นแบ่ง 80% ของปฏิทินข้อมูลเดิม
        # หากไม่มี missing จะเท่ากับ int(len(all_days) * 0.8)
        train_boundary = price_audit["train_boundary_80pct"]
        split_index = sum(day <= train_boundary for day in all_days)
        train_days = all_days[:split_index]
        train_returns_matrix = all_returns_matrix[:split_index]
        test_days = all_days[split_index:]
        test_returns_matrix = all_returns_matrix[split_index:]

        if len(train_days) < 150 or len(test_days) < 50:
            raise ValueError("หลังแบ่งข้อมูล ต้องมี Train อย่างน้อย 150 วัน และ Test อย่างน้อย 50 วัน")
        if train_days[-1] >= test_days[0]:
            raise ValueError("วันที่ Train และ Test เรียงไม่ถูกต้อง")

        print("\n--- แบ่งข้อมูลตามเวลา: Train 80% / Test 20% ---")
        print(f"Train: {len(train_days):,} วัน | {train_days[0]} ถึง {train_days[-1]}")
        print(f"Test : {len(test_days):,} วัน | {test_days[0]} ถึง {test_days[-1]}")
        print("ข้อมูลที่ใช้คำนวณจากบรรทัดนี้เป็นต้นไป: Train เท่านั้น")
        print("Test เก็บไว้ใน test_returns_matrix ยังไม่นำมาคำนวณหรือเลือกพอร์ต")

        # ใช้ชื่อตัวแปรเดิม เพื่อให้สูตรในบทก่อนหน้าทำงานกับ Train โดยไม่ต้องเขียนใหม่
        days = train_days
        returns_matrix = train_returns_matrix
        data_label = "ข้อมูลราคาจริง: เฉพาะช่วง Train"
        split_summary = {
            "source": str(price_path.resolve()), "policy": "Chronological 80/20 before missing-date filtering",
            "calendar_boundary": train_boundary, "tickers": tickers,
            "train_days": len(train_days), "train_start": train_days[0], "train_end": train_days[-1],
            "test_days": len(test_days), "test_start": test_days[0], "test_end": test_days[-1],
        }
        (scratch_path / "last_split_summary.json").write_text(
            json.dumps(split_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print("\nโหมดตัวอย่างสมมติ: ใช้ข้อมูลทุกวันเพื่อฝึกสูตร ไม่แบ่ง Train/Test")

    print(f"\n--- เมทริกซ์ผลตอบแทนหลายวัน: {data_label} ---")
    print("คอลัมน์หุ้นเรียงตาม:", tickers)
    print(f"ขนาดเมทริกซ์: {len(days)} แถว x {len(tickers)} คอลัมน์")
    for day, daily_returns in list(zip(days, returns_matrix))[:5]:
        print(f"วัน {day}: {daily_returns}")
    if len(days) > 5:
        print(f"แสดง 5 แถวแรกจาก {len(days)} แถว; คำนวณด้วยทุกแถว")

    # 11. R คูณ w: ทำ Dot Product ของแต่ละแถวกับน้ำหนักชุดเดียวกัน
    portfolio_returns = []
    print("\nผลตอบแทนพอร์ตรายวัน (สมมติน้ำหนักเริ่มต้นทุกวันเท่าเดิม):")
    for day_index, (day, daily_returns) in enumerate(zip(days, returns_matrix)):
        daily_portfolio_return = 0.0
        for weight, stock_return in zip(weights, daily_returns):
            daily_portfolio_return += weight * stock_return
        portfolio_returns.append(daily_portfolio_return)
        if day_index < 5:
            print(f"วัน {day}: {daily_portfolio_return * 100:.2f}%")
#------------------------------------------------------------------------------------------------------------
    # 12. หาค่าเฉลี่ยแต่ละคอลัมน์หุ้น (ไม่ใช่ค่าเฉลี่ยข้ามหุ้นในหนึ่งวัน)
    number_of_days = len(returns_matrix)
    mean_returns = []
    print("\n--- ค่าเฉลี่ยผลตอบแทนรายวันของแต่ละหุ้น ---")

    for column_index, ticker in enumerate(tickers):
        total_return = 0.0
        for daily_returns in returns_matrix:
            total_return += daily_returns[column_index]
        mean_return = total_return / number_of_days
        mean_returns.append(mean_return)
        print(f"{ticker}: {mean_return:.6f} หรือ {mean_return * 100:.4f}% ต่อวัน")

    # 13. Centering: X = R - ค่าเฉลี่ยของแต่ละคอลัมน์
    # เก็บเป็นเมทริกซ์ใหม่ เพื่อให้ผลตอบแทนเดิมใน returns_matrix ยังอยู่
    centered_matrix = []
    for daily_returns in returns_matrix:
        centered_row = []
        for stock_return, mean_return in zip(daily_returns, mean_returns):
            centered_row.append(stock_return - mean_return)
        centered_matrix.append(centered_row)

    print("\nเมทริกซ์ X หลังลบค่าเฉลี่ย (หน่วยทศนิยม):")
    print("คอลัมน์หุ้นเรียงตาม:", tickers)
    for day, centered_row in list(zip(days, centered_matrix))[:5]:
        formatted_row = ", ".join(f"{value:.6f}" for value in centered_row)
        print(f"วัน {day}: [{formatted_row}]")

    # 14. ค่าเฉลี่ยแต่ละคอลัมน์หลัง centering ต้องใกล้ศูนย์
    print("\nตรวจค่าเฉลี่ยหลัง centering (ควรใกล้ 0):")
    for column_index, ticker in enumerate(tickers):
        centered_total = 0.0
        for centered_row in centered_matrix:
            centered_total += centered_row[column_index]
        centered_mean = centered_total / number_of_days
        print(f"{ticker}: {centered_mean:.10f}")
#------------------------------------------------------------------------------------------------------------
    # 15. Sample covariance: ผลรวมของค่าหลัง centering ที่คูณกัน / (จำนวนวัน - 1)
    if number_of_days < 2:
        raise ValueError("การคำนวณ sample covariance ต้องมีข้อมูลอย่างน้อย 2 วัน")

    # แสดงตัวอย่างหุ้นสองตัวแรกก่อน เพื่อให้ตรวจตามด้วยเครื่องคิดเลขได้
    if len(tickers) >= 2:
        print(f"\n--- ตัวอย่าง Covariance: {tickers[0]} กับ {tickers[1]} ---")
        product_sum = 0.0
        for day_index, (day, centered_row) in enumerate(zip(days, centered_matrix)):
            first_value = centered_row[0]
            second_value = centered_row[1]
            product = first_value * second_value
            product_sum += product
            if day_index < 5:
                print(f"วัน {day}: {first_value:.9f} x {second_value:.9f} = {product:.9f}")
        if len(days) > 5:
            print(f"แสดงผลคูณ 5 วันแรก แต่รวมครบ {len(days)} วัน")
        print(f"ผลรวมผลคูณ = {product_sum:.9f}")
        print(f"หารด้วยจำนวนวัน - 1 = {number_of_days - 1}")
        print(f"Covariance = {product_sum / (number_of_days - 1):.9f}")

    # 16. ทำแบบเดียวกันทุกคู่ รวมถึงหุ้นกับตัวเอง (ได้ variance บนแนวทแยง)
    # เทียบเท่าการคูณเมทริกซ์ X.T × X / (T - 1)
    covariance_matrix = []
    for first_column in range(len(tickers)):
        covariance_row = []
        for second_column in range(len(tickers)):
            product_sum = 0.0
            for centered_row in centered_matrix:
                product_sum += centered_row[first_column] * centered_row[second_column]
            covariance_row.append(product_sum / (number_of_days - 1))
        covariance_matrix.append(covariance_row)

    print("\nCovariance Matrix (คำนวณจากผลตอบแทนหน่วยทศนิยม):")
    print(f"{'':>12}" + "".join(f"{ticker:>15}" for ticker in tickers))
    for ticker, covariance_row in zip(tickers, covariance_matrix):
        print(f"{ticker:>12}" + "".join(f"{value:>15.9f}" for value in covariance_row))
    print("แนวทแยง = Variance ของแต่ละหุ้น; นอกแนวทแยง = Covariance ของหุ้นสองตัว")
#------------------------------------------------------------------------------------------------------------
    # 17. Standard deviation = sqrt(Variance บนแนวทแยง)
    standard_deviations = []
    print("\n--- ส่วนเบี่ยงเบนมาตรฐานของผลตอบแทนรายวัน ---")
    for column_index, ticker in enumerate(tickers):
        stock_variance = covariance_matrix[column_index][column_index]
        # ข้อมูลคงที่ไม่มีความผันผวน ตรวจตรง ๆ ป้องกันเศษทศนิยมจาก centering
        is_constant = all(row[column_index] == returns_matrix[0][column_index]
                        for row in returns_matrix)
        standard_deviation = 0.0 if is_constant else math.sqrt(stock_variance)
        standard_deviations.append(standard_deviation)
        print(f"{ticker}: sqrt({stock_variance:.9f}) = {standard_deviation:.9f}"
              f" หรือ {standard_deviation * 100:.4f}% ต่อวัน")

    # 18. Correlation(i,j) = Covariance(i,j) / (SD_i * SD_j)
    correlation_matrix = []
    for first_column in range(len(tickers)):
        correlation_row = []
        for second_column in range(len(tickers)):
            denominator = (standard_deviations[first_column]
                           * standard_deviations[second_column])
            if denominator == 0:
                # หารศูนย์ไม่ได้: ไม่มีนิยาม ไม่ใช่ correlation เท่ากับศูนย์
                correlation = None
            else:
                correlation = covariance_matrix[first_column][second_column] / denominator
                # ป้องกันเศษ floating point เช่น 1.0000000000000002
                correlation = max(-1.0, min(1.0, correlation))
            correlation_row.append(correlation)
        correlation_matrix.append(correlation_row)

    if len(tickers) >= 2 and correlation_matrix[0][1] is not None:
        print(f"\nตัวอย่าง Correlation: {tickers[0]} กับ {tickers[1]}")
        print(f"{covariance_matrix[0][1]:.9f} / "
              f"({standard_deviations[0]:.9f} x {standard_deviations[1]:.9f})")
        print(f"= {correlation_matrix[0][1]:.6f}")

    print("\nCorrelation Matrix (ไม่มีหน่วย):")
    print(f"{'':>12}" + "".join(f"{ticker:>15}" for ticker in tickers))
    for ticker, correlation_row in zip(tickers, correlation_matrix):
        display_values = ["N/A" if value is None else f"{value:.6f}"
                          for value in correlation_row]
        print(f"{ticker:>12}" + "".join(f"{value:>15}" for value in display_values))
    print("N/A = คำนวณไม่ได้ เพราะหุ้นอย่างน้อยหนึ่งตัวมีส่วนเบี่ยงเบนมาตรฐานเป็นศูนย์")
#------------------------------------------------------------------------------------------------------------
    # 19. ความแปรปรวนพอร์ต = w.T × Covariance × w
    # เริ่มจากเมทริกซ์คูณเวกเตอร์: Covariance × w
    covariance_times_weights = []
    print("\n--- ความเสี่ยงพอร์ต: w.T x Covariance x w ---")
    for ticker, covariance_row in zip(tickers, covariance_matrix):
        row_result = 0.0
        for covariance_value, weight in zip(covariance_row, weights):
            row_result += covariance_value * weight
        covariance_times_weights.append(row_result)
        print(f"แถว {ticker} คูณ w = {row_result:.9f}")

    # แล้วทำ Dot Product ของ w กับเวกเตอร์ที่ได้
    portfolio_variance = 0.0
    for ticker, weight, row_result in zip(tickers, weights, covariance_times_weights):
        term = weight * row_result
        portfolio_variance += term
        print(f"{ticker}: {weight:.4f} x {row_result:.9f} = {term:.9f}")

    if portfolio_variance < -1e-12:
        raise ValueError("ความแปรปรวนพอร์ตติดลบผิดปกติ กรุณาตรวจการคำนวณ")
    # กันเศษติดลบเล็กมากจาก floating point ในกรณีความแปรปรวนจริงเป็นศูนย์
    portfolio_variance = max(0.0, portfolio_variance)
    portfolio_volatility = math.sqrt(portfolio_variance)
    print(f"Variance ของพอร์ต = {portfolio_variance:.9f}")
    print(f"ความผันผวนรายวัน = sqrt(Variance) = {portfolio_volatility:.9f}")
    print(f"ความผันผวนรายวันของพอร์ต = {portfolio_volatility * 100:.4f}%")

    # 20. ตรวจอีกวิธี: sample variance ของผลตอบแทนพอร์ตในส่วนที่ 11
    mean_portfolio_return = sum(portfolio_returns) / number_of_days
    squared_difference_sum = 0.0
    for daily_portfolio_return in portfolio_returns:
        squared_difference_sum += (daily_portfolio_return - mean_portfolio_return) ** 2
    direct_portfolio_variance = squared_difference_sum / (number_of_days - 1)

    print("\nตรวจเทียบกับผลตอบแทนพอร์ตรายวันที่คำนวณไว้:")
    print(f"ค่าเฉลี่ยผลตอบแทนพอร์ต = {mean_portfolio_return * 100:.4f}% ต่อวัน")
    print(f"Variance จากผลตอบแทนพอร์ตโดยตรง = {direct_portfolio_variance:.9f}")
    if math.isclose(portfolio_variance, direct_portfolio_variance, rel_tol=1e-9, abs_tol=1e-14):
        print("ผ่าน: คำนวณสองวิธีได้ความแปรปรวนตรงกัน")
    else:
        raise ValueError("ความแปรปรวนสองวิธีไม่ตรงกัน กรุณาตรวจลำดับหุ้นและน้ำหนัก")
    print(f"แหล่งข้อมูล: {data_label}; ใช้น้ำหนักคงที่ทุกวัน")
    print("ความผันผวนนี้ไม่ใช่ผลตอบแทนหรือขาดทุนสูงสุด")
#------------------------------------------------------------------------------------------------------------
    # 21. หา Eigenvalue/Eigenvector จาก Covariance ของช่วงที่ใช้วิเคราะห์
    # ใช้ NumPy สำหรับ eigensolver; สูตรเตรียมข้อมูลยังเป็นขั้นตอนที่เราเขียนเอง
    import numpy as np

    covariance_array = np.array(covariance_matrix, dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance_array)
    # eigh คืนค่าจากน้อยไปมาก จึงเรียงใหม่และย้ายคอลัมน์ eigenvector ตามไปด้วย
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]
    # เครื่องหมายของแกนพลิกได้โดยความหมายไม่เปลี่ยน เลือกด้านให้แสดงผลสม่ำเสมอ
    for column in range(len(tickers)):
        largest_position = np.argmax(np.abs(eigenvectors[:, column]))
        if eigenvectors[largest_position, column] < 0:
            eigenvectors[:, column] *= -1

    print("\n--- PCA จาก Covariance: วิเคราะห์เฉพาะหุ้นในพอร์ตเดิม ---")
    total_variance = float(eigenvalues.sum())
    if total_variance <= 0 or all(sd == 0 for sd in standard_deviations):
        print("ข้อมูลไม่มีความแปรปรวน จึงไม่คำนวณสัดส่วนความแปรปรวนของ PCA")
    else:
        # 22. เลือกจำนวนแกนขั้นต่ำที่อธิบายความแปรปรวนสะสมอย่างน้อย 80%
        explained_ratios = eigenvalues / total_variance
        cumulative_ratios = np.cumsum(explained_ratios)
        pca_target = 0.95
        number_of_components = min(len(tickers), int(np.searchsorted(cumulative_ratios, pca_target)) + 1)
        for column in range(len(tickers)):
            print(f"PC{column + 1}: Eigenvalue = {eigenvalues[column]:.9f}, "
                  f"อธิบาย {explained_ratios[column] * 100:.2f}%, "
                  f"สะสม {cumulative_ratios[column] * 100:.2f}%")

        print("\nEigenvectors: แถวคือหุ้น คอลัมน์คือแกน PC (ไม่ใช่น้ำหนักลงทุน)")
        print(f"{'':>12}" + "".join(f"{'PC' + str(i + 1):>12}" for i in range(len(tickers))))
        for ticker, row in zip(tickers, eigenvectors):
            print(f"{ticker:>12}" + "".join(f"{value:>12.6f}" for value in row))
        print(f"เลือก {number_of_components} แกนจาก {len(tickers)} แกน "
              f"เพื่ออธิบายความแปรปรวนอย่างน้อย {pca_target * 100:.0f}%")

        # 23. Projection: X @ Q_k แปลงแต่ละวันจาก N หุ้นเป็น k คะแนนองค์ประกอบหลัก
        selected_axes = eigenvectors[:, :number_of_components]
        pca_scores = np.array(centered_matrix) @ selected_axes
        print(f"เมทริกซ์เดิม: {number_of_days} วัน x {len(tickers)} หุ้น")
        print(f"เมทริกซ์คะแนน PCA: {pca_scores.shape[0]} วัน x {pca_scores.shape[1]} องค์ประกอบ")
        for day, row in list(zip(days, pca_scores))[:5]:
            print(f"วัน {day}: [" + ", ".join(f"{value:.6f}" for value in row) + "]")
        print("คะแนนแต่ละแถวแทนวัน ไม่ใช่หุ้น; ยังไม่ได้เลือกหุ้นใหม่หรือเปลี่ยนน้ำหนักพอร์ต")
#------------------------------------------------------------------------------------------------------------
        # 24. Stock loadings: แทนหุ้นแต่ละตัวด้วยเวกเตอร์บนแกน PCA ที่เลือก
        # กำหนด L = Q_k * sqrt(lambda_k); L @ L.T คือ covariance ที่ประมาณด้วย k แกน
        stock_loadings = selected_axes * np.sqrt(eigenvalues[:number_of_components])
        print("\n--- Stock Loadings: แต่ละแถวแทนหุ้นหนึ่งตัว ---")
        print(f"{'':>12}" + "".join(f"{'PC' + str(i + 1):>12}" for i in range(number_of_components)))
        for ticker, loading in zip(tickers, stock_loadings):
            print(f"{ticker:>12}" + "".join(f"{value:>12.6f}" for value in loading))

        # 25. รวมเวกเตอร์หุ้นตามน้ำหนัก เพื่อสร้างเวกเตอร์ของพอร์ตในแกนเดียวกัน
        portfolio_loading = np.array(weights) @ stock_loadings
        print("เวกเตอร์พอร์ตบนแกน PCA:", [round(float(value), 6) for value in portfolio_loading])

        # 26. Cosine Similarity = dot(a,b) / (norm(a) * norm(b))
        # เทียบกับ correlation จริงจาก train เต็ม เพื่อเห็นผลของการลดมิติ
        similarity_results = []
        portfolio_loading_norm = float(np.linalg.norm(portfolio_loading))
        for column_index, (ticker, loading) in enumerate(zip(tickers, stock_loadings)):
            denominator = float(np.linalg.norm(loading)) * portfolio_loading_norm
            if denominator <= 1e-15:
                pca_cosine = None
            else:
                pca_cosine = float(np.clip(np.dot(loading, portfolio_loading) / denominator, -1, 1))

            full_denominator = standard_deviations[column_index] * portfolio_volatility
            full_correlation = None if full_denominator == 0 else max(-1.0, min(1.0,
                covariance_times_weights[column_index] / full_denominator))
            similarity_results.append((ticker, pca_cosine, full_correlation))

        print("\nความคล้ายของหุ้นกับพอร์ตเดิม (เรียง PCA cosine จากน้อยไปมาก):")
        print(f"{'Ticker':>12}{'PCA cosine':>16}{'Full correlation':>20}")
        for ticker, pca_cosine, full_correlation in sorted(
                similarity_results, key=lambda row: (row[1] is None, row[1] if row[1] is not None else 0, row[0])):
            pca_text = "N/A" if pca_cosine is None else f"{pca_cosine:.6f}"
            full_text = "N/A" if full_correlation is None else f"{full_correlation:.6f}"
            print(f"{ticker:>12}{pca_text:>16}{full_text:>20}")
        print("PCA cosine ใช้แกนที่เลือก; Full correlation ใช้ผลตอบแทน Train ครบทุกมิติ")
        print("N/A หมายถึงเวกเตอร์มีความยาวเป็นศูนย์/ใกล้ศูนย์ หรือไม่มีความผันผวน")
        if number_of_components == 1:
            print("เมื่อเหลือแกนเดียว cosine ของเวกเตอร์ที่ไม่เป็นศูนย์จะเป็น +1 หรือ -1 จึงแยกความคล้ายได้หยาบมาก")
        print("ตารางนี้วิเคราะห์หุ้นที่ถืออยู่แล้ว ไม่ใช่อันดับหุ้นที่ควรซื้อ; ค่าต่ำไม่ได้รับประกันว่าพอร์ตเสี่ยงลดลง")

    # 27–29. ขยาย universe ไปยังหุ้นนอกพอร์ต ด้วย Train วันเดียวกันเท่านั้น
    if data_mode == "1" and total_variance > 0 and not all(sd == 0 for sd in standard_deviations):
        from longtripletun.candidate_analysis import screen_candidates

        print("\n--- ขั้น 27: ตรวจข้อมูล Train ของหุ้นผู้สมัครจาก CSV ---")
        screening = screen_candidates(price_path, train_days, tickers, weights,
                                      pca_target=pca_target, shortlist_size=10)
        print(f"หุ้นที่พบในช่วง Train: {screening['stocks_seen_in_train']} ตัว")
        print(f"หุ้นที่ผ่าน: {len(screening['tickers'])} ตัว (รวมหุ้นเดิม {len(tickers)} ตัว)")
        print(f"หุ้นที่ตัดออก: {len(screening['excluded'])} ตัว; รายละเอียดใน candidate_exclusions.csv")
        print(f"หุ้นผู้สมัครนอกพอร์ต: {len(screening['candidates'])} ตัว")

        print("\n--- ขั้น 28: ทำ PCA ใหม่ร่วมกันทั้งหุ้นเดิมและหุ้นผู้สมัคร ---")
        print(f"Train: {len(train_days)} วัน x {len(screening['tickers'])} หุ้น")
        print(f"ใช้ {screening['components']} แกน อธิบายความแปรปรวน {screening['explained_variance']:.2%}")
        print("ผลนี้ต่างจาก PCA ของหุ้นเดิม 3 ตัว เพราะมีหุ้นและโครงสร้าง covariance เพิ่มขึ้น")

        print("\n--- ขั้น 29: หุ้นผู้สมัคร 10 อันดับแรกตาม PCA cosine ต่ำสุด ---")
        print(f"{'Ticker':>12}{'PCA cosine':>15}{'Full corr.':>15}{'Daily SD (%)':>16}")
        for item in screening['candidates']:
            if not item['shortlisted']:
                continue
            full_text = "N/A" if item['full_correlation'] is None else f"{item['full_correlation']:.6f}"
            print(f"{item['ticker']:>12}{item['pca_cosine']:>15.6f}{full_text:>15}"
                  f"{item['daily_volatility_percent']:>16.4f}")
        if not screening['shortlist']:
            print("ไม่พบหุ้นผู้สมัครที่คำนวณ cosine ได้ จึงยังไม่มี shortlist")
        for filename, rows, fields in [
            ("candidate_screening.csv", screening['candidates'],
             ["ticker", "pca_cosine", "full_correlation", "daily_volatility_percent",
              "max_absolute_train_return_percent", "shortlisted"]),
            ("candidate_exclusions.csv", screening['excluded'], ["ticker", "reason"]),
        ]:
            with (scratch_path / filename).open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        print("บันทึกอันดับทั้งหมดใน candidate_screening.csv (ผลการรันล่าสุด)")
        print("คัดตาม Train เท่านั้น ไม่ตรวจความครบถ้วน Test เพื่อเลือกหุ้น และไม่ได้เปลี่ยนน้ำหนักพอร์ต")
        print("ค่าต่ำหมายถึงรูปแบบต่างจากพอร์ตตาม PCA ไม่ได้แปลว่าควรซื้อหรือจะลดความเสี่ยงเสมอ")
        print("ก่อนใช้จริงควรตรวจผลตอบแทนสุดโต่งจากคอลัมน์ max_absolute_train_return_percent")
        print("ชุดหุ้นมาจากรายชื่อใน CSV; การใช้สมาชิกดัชนีปัจจุบันย้อนอดีตอาจมี survivorship bias")

        # ด่านคำแนะนำ: สร้างจาก Fit/Validation ภายใน Train ก่อนอ่านผล Test
        from longtripletun.recommendation import build_recommendation, concentration_summary, save_recommendation
        concentration = concentration_summary(screening['tickers'], screening['weights'], screening['covariance'])
        print("\nกำลังตรวจความคุ้มค่าด้วย Fit/Validation ภายใน Train; ไม่ใช้ Test เลือกคำแนะนำ")
        recommendation = build_recommendation(price_path, train_days, tickers, weights,
                                               pca_target=pca_target, fee_rate=0.001)
        print("ผลด่านความคุ้มค่า:", recommendation['reason'])
        print("ตารางขั้น 30–43 ต่อไปเป็นการวิเคราะห์เดิม; คำแนะนำที่ผ่านเกณฑ์จะสรุปอีกครั้งท้ายโปรแกรม")

        # 30. ทดลองทุกคู่ของหุ้นผู้สมัครกับสัดส่วน 5%, 10%, 15%, 20%
        from longtripletun.rebalance import try_rebalancing
        rebalancing = try_rebalancing(screening)
        print(f"\n--- ขั้น 30: ทดลองปรับพอร์ตทั้งหมด {len(rebalancing['trials'])} ทางเลือก ---")
        print("ใช้ Covariance เต็มของ Train; ไม่ใช้ covariance ที่ลดมิติด้วย PCA")
        print(f"{'Ticker':>12}{'New weight (%)':>18}{'Daily SD (%)':>18}{'Reduction (pp)':>18}")
        for item in rebalancing['trials'][:5]:
            print(f"{item['ticker']:>12}{item['new_stock_weight_percent']:>18.2f}"
                  f"{item['train_daily_volatility_percent']:>18.4f}"
                  f"{item['volatility_reduction_percentage_points']:>18.4f}")

        # 31. เปรียบเทียบกับพอร์ตเดิม และแสดงน้ำหนักของทางเลือกที่ผ่านเกณฑ์
        print("\n--- ขั้น 31: ทางเลือกที่ลดความผันผวน Train ได้มากที่สุดในชุดที่ทดลอง ---")
        if rebalancing['best'] is None:
            print("ไม่พบทางเลือกที่ลดความผันผวนได้ จึงคงพอร์ตเดิม")
        else:
            best = rebalancing['best']
            print(f"ทดลองเพิ่ม {best['ticker']} ที่ {best['new_stock_weight_percent']:.0f}%")
        print(f"ความผันผวนรายวันเดิม: {rebalancing['old_daily_volatility'] * 100:.4f}%")
        print(f"ความผันผวนรายวันใหม่: {rebalancing['new_daily_volatility'] * 100:.4f}%")
        print(f"{'Ticker':>12}{'Old (%)':>14}{'New (%)':>14}{'Change (pp)':>16}")
        for item in rebalancing['weight_changes']:
            print(f"{item['ticker']:>12}{item['old_weight_percent']:>14.2f}"
                  f"{item['new_weight_percent']:>14.2f}{item['change_percentage_points']:>16.2f}")

        # 32. ส่งออกทุกทางเลือกและน้ำหนักที่เสนอ โดยไม่แก้ portfolio.csv ของผู้ใช้
        for filename, rows, fields in [
            ("rebalance_trials.csv", rebalancing['trials'],
             ['ticker', 'new_stock_weight_percent', 'train_variance', 'train_daily_volatility_percent',
              'volatility_reduction_percentage_points', 'relative_volatility_reduction_percent']),
            ("proposed_weights.csv", rebalancing['weight_changes'],
             ['ticker', 'old_weight_percent', 'new_weight_percent', 'change_percentage_points']),
        ]:
            with (scratch_path / filename).open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        print("บันทึกผลล่าสุดใน rebalance_trials.csv และ proposed_weights.csv")
        print("การจัดอันดับข้างบนใช้ Train เท่านั้น; ต่อไปจะตรวจ Test โดยไม่เปลี่ยนคำแนะนำ")
        print("pp = จุดเปอร์เซ็นต์; ผลนี้ดีที่สุดเฉพาะหุ้นและสัดส่วนที่ทดลอง ไม่ใช่ทุกพอร์ตที่เป็นไปได้")

        # 33. ล็อกพอร์ตที่เลือกแล้ว ประเมิน Test โดยไม่มีการเลือกหุ้นใหม่
        from longtripletun.holdout import evaluate_holdout
        holdout_result = evaluate_holdout(price_path, train_days[-1], test_days,
                                          screening['tickers'], screening['weights'], rebalancing['weights'])
        print("\n--- ขั้น 33: ทดสอบพอร์ตที่ล็อกไว้บน Test ---")
        print(f"ช่วง Test: {test_days[0]} ถึง {test_days[-1]} ({len(test_days)} วัน)")
        print(f"สมมติจัดพอร์ตที่ราคาปิดปรับแล้ววันที่ {train_days[-1]} ก่อนเริ่ม Test; NAV เริ่ม 100")
        print("ถือไว้จนจบ Test น้ำหนักลอยตามราคา ไม่ปรับกลับทุกวัน; ยังไม่รวมค่าธรรมเนียม")
        print(f"{'Portfolio':>14}{'Total return (%)':>20}{'Daily SD (%)':>18}{'Final NAV':>16}")
        for row in holdout_result['summary']:
            if row['status'] != 'ok':
                print(f"{row['strategy']}: {row['status']}")
                continue
            print(f"{row['strategy']:>14}{row['total_return_percent']:>20.4f}"
                  f"{row['daily_volatility_percent']:>18.4f}{row['final_nav']:>16.4f}")

        # 34. เปรียบเทียบความผันผวนของสองพอร์ตใน Test ช่วงเดียวกัน
        comparisons = {row['strategy']: row for row in holdout_result['summary']}
        old_test, new_test = comparisons['original'], comparisons['proposed']
        if old_test['status'] == 'ok' and new_test['status'] == 'ok':
            difference = old_test['daily_volatility_percent'] - new_test['daily_volatility_percent']
            if abs(difference) < 1e-10:
                print("ผล Test: ความผันผวนรายวันของทั้งสองพอร์ตเท่ากัน")
            elif difference > 0:
                print(f"ผล Test: พอร์ตที่เสนอผันผวนน้อยกว่าพอร์ตเดิม {difference:.4f} จุดเปอร์เซ็นต์")
            else:
                print(f"ผล Test: พอร์ตที่เสนอผันผวนมากกว่าพอร์ตเดิม {-difference:.4f} จุดเปอร์เซ็นต์")
        else:
            print("เปรียบเทียบ Test ไม่ครบเพราะข้อมูลราคาไม่สมบูรณ์; คงคำแนะนำเดิม ไม่เลือกหุ้นใหม่จาก Test")

        # 35. บันทึกผล Test แยกจากการจัดอันดับ Train
        for filename, rows, fields in [
            ('holdout_summary.csv', holdout_result['summary'],
             ['strategy', 'status', 'test_days', 'total_return_percent', 'daily_volatility_percent', 'final_nav']),
            ('holdout_daily.csv', holdout_result['daily'], ['strategy', 'date', 'nav', 'daily_return_percent']),
            ('holdout_weights.csv', holdout_result['weights'],
             ['strategy', 'ticker', 'initial_weight_percent', 'final_weight_percent']),
        ]:
            with (scratch_path / filename).open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        (scratch_path / 'holdout_assumptions.json').write_text(json.dumps({
            'source': str(price_path.resolve()), 'anchor_day': holdout_result['anchor_day'],
            'test_start': holdout_result['test_start'], 'test_end': holdout_result['test_end'],
            'assumptions': holdout_result['assumptions'],
            'selected_on_train': rebalancing['best'], 'proposed_initial_weights': rebalancing['weight_changes'],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print("บันทึก holdout_summary.csv, holdout_daily.csv, holdout_weights.csv และ holdout_assumptions.json")
        print("Train ใช้น้ำหนักคงที่เพื่อประมาณความเสี่ยง แต่ Test จำลองถือยาว จึงให้น้ำหนักเปลี่ยนตามราคา")
        print("นี่เป็นการจำลองด้วยราคาปรับแล้ว ไม่ใช่คำสั่งซื้อขายจริง และยังไม่ประเมินต้นทุนการซื้อขาย")

        # 36. เพิ่ม baseline: แบ่งเท่ากันเฉพาะหุ้นเดิม และคิดค่าธรรมเนียมตั้งต้น
        from longtripletun.holdout import evaluate_costs
        fee_rate = 0.001  # ค่าธรรมเนียมสมมติ 0.1% ต่อมูลค่าซื้อหรือขาย ไม่ใช่อัตราของโบรกเกอร์จริง
        cost_result = evaluate_costs(price_path, train_days[-1], test_days,
                                    screening['tickers'], screening['weights'], rebalancing['weights'],
                                    fee_rate=fee_rate)
        print("\n--- ขั้น 36: เปรียบเทียบ 3 พอร์ต รวมค่าธรรมเนียมตั้งต้น ---")
        print(f"Equal weight: ลงทุนเท่ากันในหุ้นเดิม {len(tickers)} ตัว = ตัวละ {100 / len(tickers):.4f}%")
        print(f"อัตราสมมติ: {fee_rate * 100:.3f}% ต่อมูลค่าซื้อและขาย; คิดครั้งเดียวก่อนถือ Test")
        print("ต้นทุนประมาณการ = อัตราค่าธรรมเนียม x ผลรวม |น้ำหนักเป้าหมาย - น้ำหนักเดิม|")
        print("พอร์ตเดิมไม่ปรับสัดส่วนจึงไม่มีต้นทุนเพิ่ม; ไม่คิดค่าซื้อเดิมหรือขายทิ้งตอนจบ Test")
        print(f"{'Portfolio':>14}{'Fee/NAV (%)':>15}{'Gross return (%)':>19}{'Net return (%)':>18}{'Net daily SD (%)':>19}")
        for row in cost_result['summary']:
            if row['status'] != 'ok':
                print(f"{row['strategy']}: {row['status']}")
                continue
            print(f"{row['strategy']:>14}{row['initial_fee_percent_of_portfolio']:>15.4f}"
                  f"{row['gross_total_return_percent']:>19.4f}{row['net_total_return_percent']:>18.4f}"
                  f"{row['net_daily_volatility_percent']:>19.4f}")

        # 37. ส่งออกผลหลังต้นทุนแยกจากไฟล์ก่อนต้นทุนในขั้นที่ 35
        for filename, rows, fields in [
            ('cost_comparison.csv', cost_result['summary'], list(cost_result['summary'][0])),
            ('cost_daily.csv', cost_result['daily'],
             ['strategy', 'date', 'gross_nav', 'net_nav', 'net_daily_return_percent']),
            ('cost_weights.csv', cost_result['weights'],
             ['strategy', 'ticker', 'initial_weight_percent', 'final_weight_percent']),
        ]:
            with (scratch_path / filename).open('w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        (scratch_path / 'cost_assumptions.json').write_text(json.dumps({
            'fee_rate': fee_rate, 'assumptions': cost_result['assumptions'],
            'source': str(price_path.resolve()), 'anchor_day': train_days[-1],
            'test_start': test_days[0], 'test_end': test_days[-1],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print("บันทึก cost_comparison.csv, cost_daily.csv, cost_weights.csv และ cost_assumptions.json")
        print("ความผันผวนสุทธิรวม fee ในผลตอบแทนวันแรก; ตารางก่อนต้นทุนยังอยู่ใน holdout_summary.csv")
        print("ค่าธรรมเนียมเป็นแบบจำลองประมาณการ ไม่รวมภาษี slippage หรือ FX และไม่ได้เปลี่ยนหุ้นที่เลือกจาก Train")

        # 38–40. คำนวณ Drawdown สร้างกราฟ และเขียนทับรายงานล่าสุดชุดเดียว
        from longtripletun.report_charts import save_report
        report_context = {
            'portfolio_source': str(file_path.resolve()),
            'portfolio_holdings': [{'ticker': ticker, 'weight_percent': weight * 100}
                                   for ticker, weight in zip(tickers, weights)],
            'source': str(price_path.resolve()), 'train_start': train_days[0], 'train_end': train_days[-1],
            'train_days': len(train_days), 'test_start': test_days[0], 'test_end': test_days[-1],
            'test_days': len(test_days), 'fee_rate': fee_rate, 'pca_target': pca_target,
        }
        report_folder, report_metrics = save_report(cost_result, rebalancing, screening,
                                                    report_context, REPORTS_DIR)
        print("\n--- ขั้น 38–40: กราฟและ Maximum Drawdown หลังต้นทุน ---")
        for row in report_metrics:
            if row['max_drawdown_percent'] is not None:
                print(f"{row['strategy']}: Maximum Drawdown = {row['max_drawdown_percent']:.4f}%")
        print("Maximum Drawdown คือการลดจากจุดสูงสุดมากที่สุดในช่วง Test ไม่ใช่เพดานขาดทุนในอนาคต")
        print("บันทึกรายงานและกราฟไว้ที่:", report_folder)
        print("เปิด report.md แล้วกด Ctrl+Shift+V ใน VS Code เพื่ออ่านพร้อมกราฟ")
        # 41–43. เลือก 1–3 ระดับจาก Train แล้วอธิบายผล Test และตัวอย่างเงิน
        from longtripletun.risk_levels import evaluate_risk_levels, save_comparison
        level_result = evaluate_risk_levels(price_path, train_days[-1], test_days,
                                             screening, rebalancing, fee_rate=fee_rate,
                                             capital=100000.0)
        level_text = save_comparison(level_result, report_folder)
        with (report_folder / 'report.md').open('a', encoding='utf-8') as report_file:
            report_file.write('\n\n' + level_text)
        print("\n--- ขั้น 41–43: ทางเลือกความผันผวน 1–3 ระดับ ---")
        print("ตารางและกราฟ proposed ก่อนหน้านี้แสดงตัวเลือก Train ต่ำสุดเพียงตัวเดียว")
        print(level_text)
        print("ตารางทุกระดับและน้ำหนักอยู่ใน risk_levels.md, risk_levels.csv และ risk_level_weights.csv ในโฟลเดอร์รายงานรอบนี้")
        # 44. สรุปความกระจุกตัวและคำแนะนำสุดท้ายที่ผ่าน Validation เท่านั้น
        recommendation_text = save_recommendation(recommendation, concentration, price_path,
                                                   train_days[-1], test_days, report_folder)
        report_path = report_folder / 'report.md'
        report_path.write_text(recommendation_text + '\n\n---\n\n# ภาคผนวก: การวิเคราะห์เดิม (ไม่ใช่คำแนะนำสุดท้าย)\n\n'
                               + report_path.read_text(encoding='utf-8'), encoding='utf-8')
        print("\n--- ขั้น 44: คำแนะนำหลังตรวจความคุ้มค่า ---")
        print(recommendation_text)
        print("อ่าน recommendation.md และ recommended_weights.csv ในโฟลเดอร์รายงานรอบนี้")
        # เผยแพร่รายงาน เมื่อทำรายงานครบแล้วเท่านั้น รายงานก่อนหน้าจึงยังอยู่หากรอบใหม่ล้มเหลว
        from longtripletun.user_summary import write_user_summary
        from longtripletun.report_store import publish_report, stage_loose_outputs, remove_loose_outputs
        write_user_summary(report_folder, recommendation, concentration, level_result, report_context)
        loose_outputs = stage_loose_outputs(scratch_path, report_folder, protected=[file_path, price_path])
        report_folder, cleanup_warnings = publish_report(report_folder)
        remove_loose_outputs(scratch_path, loose_outputs)
        print("\nสรุปสำหรับผู้ใช้:", report_folder / 'report.md')
        print("รายงานล่าสุดอยู่ที่เดิมทุกครั้ง รายละเอียดคำนวณเก็บในโฟลเดอร์ details")
        for warning in cleanup_warnings:
            print("เก็บบางไฟล์เดิมไว้:", warning)
    elif data_mode == "2":
        print("\nขั้น 27–40 ใช้โหมดราคาจริง เพราะข้อมูลสมมติยังไม่มีหุ้นนอกพอร์ตให้คัดเลือก")

except FileNotFoundError:
    print("ไม่พบไฟล์ กรุณาตรวจชื่อไฟล์หรือพาธแล้วลองใหม่")
except ValueError as error:
    print("ข้อมูลไม่ถูกต้อง:", error)
except (OSError, UnicodeError, csv.Error) as error:
    print("อ่านหรือบันทึกไฟล์ไม่สำเร็จ:", error)
    print("หากรายงานปัจจุบัน ไม่เปลี่ยน แสดงว่ารอบนี้ยังเผยแพร่ไม่สำเร็จ โปรดดูข้อความผิดพลาดข้างบน")
except ImportError as error:
    print("โหลดไลบรารีไม่ได้:", error)
    print("ให้รัน python -m pip install numpy matplotlib แล้วลองใหม่")
