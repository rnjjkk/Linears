# ใช้ Covariance และ PCA คัดหุ้นที่มีรูปแบบต่างจากพอร์ต
"""ขั้นที่ 27–29: คัดหุ้นผู้สมัครด้วยข้อมูล Train เท่านั้น

PCA รอบนี้ fit หุ้นเดิมและผู้สมัครร่วมกัน เพื่อให้เวกเตอร์ทุกตัวอยู่บนแกนเดียวกัน
ยังไม่ทดลองน้ำหนักและไม่ใช้ Test เลือกหุ้น
"""

import csv
import math
from datetime import date
from pathlib import Path
import numpy as np
from .settings import load_policy, validate_policy


def screen_candidates(csv_path, train_days, portfolio_tickers, portfolio_weights,
                      pca_target=None, shortlist_size=None, *, policy=None):
    # สร้าง PCA จากช่วงฝึกแล้วคัดหุ้นที่มีรูปแบบต่างจากพอร์ต
    policy = load_policy() if policy is None else validate_policy(policy)
    pca_target = policy['pca_target'] if pca_target is None else pca_target
    shortlist_size = policy['shortlist_size'] if shortlist_size is None else shortlist_size
    if not 0 < pca_target <= 1 or shortlist_size < 1:
        raise ValueError("PCA target ต้องอยู่ใน (0,1] และ shortlist ต้องไม่น้อยกว่า 1")
    if len(train_days) < policy['minimum_fit_days'] or train_days != sorted(set(train_days)):
        raise ValueError(f"วันฝึกต้องเรียง ไม่ซ้ำ และมีอย่างน้อย {policy['minimum_fit_days']} วัน")
    if len(portfolio_tickers) != len(portfolio_weights) or len(set(portfolio_tickers)) != len(portfolio_tickers):
        raise ValueError("รายชื่อหุ้นและน้ำหนักจับคู่ไม่ถูกต้อง")
    if not all(math.isfinite(w) and w > 0 for w in portfolio_weights) or not math.isclose(sum(portfolio_weights), 1, abs_tol=1e-8):
        raise ValueError("น้ำหนักพอร์ตต้องเป็นบวกและรวมเป็น 1")

    prices = {}
    calendar = set()
    duplicate_tickers = set()
    # ไม่อ่านค่าราคาของ Test แม้จะอยู่ในไฟล์เดียวกัน
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not {"Date", "Ticker", "Close"}.issubset(reader.fieldnames or []):
            raise ValueError("ไฟล์ราคาต้องมี Date,Ticker,Close")
        for row in reader:
            day = date.fromisoformat((row["Date"] or "").strip()).isoformat()
            if day > train_days[-1]:
                continue
            ticker = (row["Ticker"] or "").strip().upper()
            if not ticker:
                raise ValueError("พบชื่อหุ้นว่างใน CSV ราคา Train")
            calendar.add(day)
            history = prices.setdefault(ticker, {})
            if day in history:
                duplicate_tickers.add(ticker)
                continue
            try:
                close = float(row["Close"])
            except (ValueError, TypeError):
                close = math.nan
            history[day] = close if math.isfinite(close) and close > 0 else None

    calendar = sorted(calendar)
    previous_date = dict(zip(calendar[1:], calendar[:-1]))
    if any(day not in previous_date for day in train_days):
        raise ValueError("ไม่มีราคาวันก่อนหน้าสำหรับวัน Train ที่กำหนด")
    names, columns, excluded = [], [], []
    for ticker, history in sorted(prices.items()):
        reason = "duplicate_train_price" if ticker in duplicate_tickers else None
        values = []
        if reason is None:
            for day in train_days:
                before, current = history.get(previous_date[day]), history.get(day)
                if before is None or current is None:
                    reason = "missing_or_invalid_train_price"
                    break
                value = current / before - 1
                if not math.isfinite(value):
                    reason = "nonfinite_train_return"
                    break
                values.append(value)
        if reason is None and np.std(values, ddof=1) <= 1e-12:
            reason = "zero_or_negligible_train_variance"
        if reason:
            excluded.append({"ticker": ticker, "reason": reason})
        else:
            names.append(ticker)
            columns.append(values)

    missing_holdings = sorted(set(portfolio_tickers) - set(names))
    if missing_holdings:
        raise ValueError("หุ้นเดิมไม่ผ่านเกณฑ์ Train จึงหยุด ไม่ลบหุ้นออกเอง: " + ", ".join(missing_holdings))
    r = np.array(columns, dtype=float).T
    x = r - r.mean(axis=0)
    covariance = x.T @ x / (len(train_days) - 1)
    weights_by_ticker = dict(zip(portfolio_tickers, portfolio_weights))
    # หุ้นนอกพอร์ตมีน้ำหนักเริ่มต้นเป็น 0 ไม่ได้ถูกซื้อเพียงเพราะอยู่ใน universe
    universe_weights = np.array([weights_by_ticker.get(ticker, 0.0) for ticker in names])
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0)
    eigenvectors = eigenvectors[:, order]
    ratios = eigenvalues / eigenvalues.sum()
    cumulative = np.cumsum(ratios)
    k = min(len(names), int(np.searchsorted(cumulative, pca_target)) + 1)
    loadings = eigenvectors[:, :k] * np.sqrt(eigenvalues[:k])
    portfolio_loading = universe_weights @ loadings
    portfolio_norm = float(np.linalg.norm(portfolio_loading))
    portfolio_sd = math.sqrt(max(0, float(universe_weights @ covariance @ universe_weights)))
    stock_portfolio_covariance = covariance @ universe_weights

    candidates = []
    for position, ticker in enumerate(names):
        if ticker in weights_by_ticker:
            continue
        loading = loadings[position]
        denominator = float(np.linalg.norm(loading)) * portfolio_norm
        cosine = None if denominator <= 1e-15 else float(np.clip(loading @ portfolio_loading / denominator, -1, 1))
        sd = math.sqrt(float(covariance[position, position]))
        full_correlation = None if sd * portfolio_sd == 0 else float(np.clip(
            stock_portfolio_covariance[position] / (sd * portfolio_sd), -1, 1))
        candidates.append({
            "ticker": ticker, "pca_cosine": cosine, "full_correlation": full_correlation,
            "daily_volatility_percent": sd * 100,
            "max_absolute_train_return_percent": float(np.abs(r[:, position]).max() * 100),
        })
    candidates.sort(key=lambda item: (item['pca_cosine'] is None,
        item['pca_cosine'] if item['pca_cosine'] is not None else 0, item['ticker']))
    # ค่า cosine ที่ไม่มีนิยามไม่นำมาใส่ shortlist อย่างเงียบ ๆ
    shortlist = [item['ticker'] for item in candidates if item['pca_cosine'] is not None][:shortlist_size]
    for item in candidates:
        item['shortlisted'] = item['ticker'] in shortlist
    return {
        "tickers": names, "train_returns": r, "covariance": covariance,
        "weights": universe_weights, "loadings": loadings,
        "candidates": candidates, "shortlist": shortlist, "excluded": excluded,
        "stocks_seen_in_train": len(prices), "components": k,
        "explained_variance": float(cumulative[k-1]), "train_days": list(train_days),
    }
