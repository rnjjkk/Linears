"""เผยแพร่รายงานล่าสุดหลังเขียนครบ ลบเฉพาะไฟล์ผลลัพธ์ที่รู้จักในรากรายงาน."""
from pathlib import Path
import re
import uuid
import os
import shutil

GENERATED_FILES = {
    'report.md', 'recommendation.md', 'recommendation.json', 'recommended_weights.csv',
    'risk_levels.md', 'risk_levels.csv', 'risk_level_weights.csv', 'metrics.csv', 'daily.csv',
    'proposed_weights.csv', 'run_context.json', 'equity.png', 'drawdown.png', 'comparison.png',
    'comparison.csv', 'comparison.md', 'contexts.json',
    'candidate_screening.csv', 'candidate_exclusions.csv', 'rebalance_trials.csv',
    'holdout_summary.csv', 'holdout_daily.csv', 'holdout_weights.csv', 'holdout_assumptions.json',
    'cost_comparison.csv', 'cost_daily.csv', 'cost_weights.csv', 'cost_assumptions.json',
    'last_price_audit.json', 'last_split_summary.json',
}

LOOSE_OUTPUTS = {
    'candidate_screening.csv', 'candidate_exclusions.csv', 'rebalance_trials.csv', 'proposed_weights.csv',
    'holdout_summary.csv', 'holdout_daily.csv', 'holdout_weights.csv', 'holdout_assumptions.json',
    'cost_comparison.csv', 'cost_daily.csv', 'cost_weights.csv', 'cost_assumptions.json',
    'last_price_audit.json', 'last_split_summary.json',
}


def stage_loose_outputs(base, draft, protected=()):
    base, draft = Path(base).resolve(), Path(draft)
    protected = {Path(path).resolve() for path in protected}
    details = draft/'details'
    details.mkdir(exist_ok=True)
    saved = {}
    for name in LOOSE_OUTPUTS:
        path = base/name
        if path.is_file() and not path.is_symlink() and path.resolve() not in protected:
            content = path.read_bytes()
            (details/name).write_bytes(content)
            saved[name] = content
    return saved


def remove_loose_outputs(base, saved):
    base = Path(base).resolve()
    for name, content in saved.items():
        if name not in LOOSE_OUTPUTS:
            raise ValueError('ไม่ใช่ไฟล์ผลลัพธ์ที่อนุญาต')
        path = base/name
        if path.is_file() and not path.is_symlink() and path.parent.resolve() == base and path.read_bytes() == content:
            path.unlink()


def _safe_tree(folder, root):
    """ตรวจทั้งต้นไม้ก่อนลบ/ย้าย: ไม่ตาม symlink/junction ไม่แตะไฟล์ที่ไม่รู้จัก."""
    root = Path(root).resolve()
    folder = Path(folder)
    if folder.is_symlink() or folder.is_junction() or not folder.resolve().is_relative_to(root) or folder.resolve() == root:
        raise ValueError(f'ปฏิเสธจัดการพาธรายงานนอกขอบเขต: {folder}')
    for item in folder.rglob('*'):
        if item.is_symlink() or item.is_junction() or not item.resolve().is_relative_to(root):
            raise ValueError(f'พบลิงก์หรือพาธนอกขอบเขต: {item}')
        if item.is_file() and item.name not in GENERATED_FILES:
            raise ValueError(f'เก็บโฟลเดอร์ไว้เพราะมีไฟล์ที่โปรแกรมไม่ได้รู้จัก: {item}')
    return folder


def remove_generated(folder, root):
    folder = _safe_tree(folder, root)
    for item in sorted(folder.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
    folder.rmdir()


def begin_report(root):
    root = Path(root)
    if root.is_symlink() or root.is_junction():
        raise ValueError('รากรายงานต้องไม่เป็นลิงก์')
    root.mkdir(parents=True, exist_ok=True)
    folder = root / ('.building_' + uuid.uuid4().hex)
    folder.mkdir()
    return folder


def publish_report(folder):
    """สลับ latest หลังรายงานครบ; ถ้าสลับไม่สำเร็จคืนรายงานเดิม."""
    folder = Path(folder)
    root = folder.parent.resolve()
    if not re.fullmatch(r'\.building_[0-9a-f]{32}', folder.name):
        raise ValueError('เผยแพร่ได้เฉพาะโฟลเดอร์ที่ begin_report สร้าง')
    _safe_tree(folder, root)
    if not any((folder / name).is_file() for name in ('report.md', 'comparison.md')):
        raise ValueError('ยังไม่มีรายงานที่เสร็จสมบูรณ์')
    latest = root / 'latest'
    backup = root / ('.previous_' + uuid.uuid4().hex)
    if latest.exists():
        _safe_tree(latest, root)
        try:
            latest.rename(backup)
        except PermissionError:
            # Windows อาจล็อกโฟลเดอร์ที่เปิดใน Explorer/VS Code แต่ยังอัปเดตไฟล์ข้างในได้
            return _publish_in_place(folder, latest, backup, root)
    try:
        folder.rename(latest)
    except OSError:
        if backup.exists():
            backup.rename(latest)
        raise
    warnings = []
    for old in root.iterdir():
        if old.is_dir() and (old == backup or re.fullmatch(r'\d{8}_\d{6}_\d{6}', old.name)):
            try:
                remove_generated(old, root)
            except (ValueError, OSError) as error:
                warnings.append(str(error))
    return latest, warnings


def _replace_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name('.update_' + uuid.uuid4().hex)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _publish_in_place(folder, latest, backup, root):
    """สำรองก่อนเขียน อัปเดตหน้ารายงานเป็นไฟล์สุดท้าย คืนไฟล์เดิมเมื่อเขียนไม่สำเร็จ."""
    _safe_tree(folder, root)
    _safe_tree(latest, root)
    shutil.copytree(latest, backup)
    sources = [p for p in folder.rglob('*') if p.is_file()]
    # หน้ารายงานหลักเป็นจุดเผยแพร่หลังไฟล์ประกอบพร้อมทั้งหมด
    sources.sort(key=lambda p: (p.relative_to(folder).as_posix() in ('report.md', 'comparison.md'), str(p)))
    changed = []
    try:
        for source in sources:
            relative = source.relative_to(folder)
            _replace_file(source, latest/relative)
            changed.append(relative)
    except OSError as error:
        for relative in reversed(changed):
            if (backup/relative).exists():
                _replace_file(backup/relative, latest/relative)
            else:
                (latest/relative).unlink()
        remove_generated(backup, root)
        raise OSError('อัปเดตรายงานไม่สำเร็จ คืนไฟล์เดิมแล้ว กรุณาปิดไฟล์รายงานที่ถูกล็อกแล้วลองใหม่') from error
    warnings = []
    expected = {p.relative_to(folder) for p in sources}
    # ตรวจขอบเขตอีกครั้งก่อนลบไฟล์ที่รอบใหม่ไม่ได้ใช้
    _safe_tree(latest, root)
    for item in sorted(latest.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        try:
            if item.is_file() and item.relative_to(latest) not in expected:
                item.unlink()
            elif item.is_dir() and not any(item.iterdir()):
                item.rmdir()
        except OSError as error:
            warnings.append(str(error))
    for old in (folder, backup):
        try:
            remove_generated(old, root)
        except OSError as error:
            warnings.append(str(error))
    os.utime(latest, None)
    return latest, warnings
