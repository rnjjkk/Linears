# กำหนดตำแหน่งไฟล์และโฟลเดอร์ให้ค้นจากรากโปรเจกต์
"""Project paths independent of the terminal working directory."""
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / 'examples'
CONFIG_DIR = PROJECT_ROOT / 'config'
DATA_DIR = PROJECT_ROOT / 'data'
REPORTS_DIR = PROJECT_ROOT / 'reports'


def default_price_path():
    # ค้นหา CSV ราคาในตำแหน่งเริ่มต้นที่โปรแกรมรองรับ
    candidates = [DATA_DIR / 'raw' / 'sp500_daily_5years.csv',
                  PROJECT_ROOT / 'sp500_daily_5years.csv',
                  PROJECT_ROOT.parent / 'sp500_daily_5years.csv',
                  PROJECT_ROOT.parent.parent / 'sp500_daily_5years.csv']
    return next((p for p in candidates if p.is_file()), candidates[0])


def resolve_portfolio(filename):
    # ค้นหา CSV พอร์ตจากชื่อไฟล์หรือพาธที่ผู้ใช้กรอก
    path = Path(filename)
    if path.is_absolute():
        return path
    candidates = [PROJECT_ROOT / path, EXAMPLES_DIR / path, EXAMPLES_DIR / 'portfolios' / path]
    if path.parts and path.parts[0] == 'example_portfolios':
        candidates.append(EXAMPLES_DIR / 'portfolios' / Path(*path.parts[1:]))
    return next((p for p in candidates if p.is_file()), candidates[0])
