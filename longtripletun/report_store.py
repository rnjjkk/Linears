# เขียนทับรายงานชุดเดิมอย่างปลอดภัยและจัดการไฟล์ชั่วคราว
"""เผยแพร่รายงานล่าสุดหลังเขียนครบ ลบเฉพาะไฟล์ผลลัพธ์ที่รู้จักในรากรายงาน."""
from pathlib import Path
import re
import uuid
import os
import shutil
import json

GENERATED_FILES = {
    '.report_files.json',
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
    # คัดลอกผลคำนวณชั่วคราวเข้าโฟลเดอร์รายละเอียดรายงาน
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
    # ลบไฟล์ชั่วคราวที่บันทึกแล้วโดยไม่แตะไฟล์นำเข้า
    base = Path(base).resolve()
    for name, content in saved.items():
        if name not in LOOSE_OUTPUTS:
            raise ValueError('ไม่ใช่ไฟล์ผลลัพธ์ที่อนุญาต')
        path = base/name
        if path.is_file() and not path.is_symlink() and path.parent.resolve() == base and path.read_bytes() == content:
            path.unlink()


def _safe_tree(folder, root):
    # ตรวจว่าต้นไม้โฟลเดอร์อยู่ในขอบเขตและมีเฉพาะไฟล์ผลลัพธ์
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
    # ลบโฟลเดอร์ผลลัพธ์ที่ผ่านการตรวจขอบเขตแล้ว
    folder = _safe_tree(folder, root)
    for item in sorted(folder.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
    folder.rmdir()


def begin_report(root):
    # เตรียมพื้นที่ชั่วคราวโดยเก็บรายงานที่เสร็จแล้วไว้
    """Build in a reusable temporary folder without changing the completed report."""
    root = Path(root)
    if root.is_symlink() or root.is_junction():
        raise ValueError('รากรายงานต้องไม่เป็นลิงก์')
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / '.previous_current').exists():
        raise ValueError('พบข้อมูลสำรองจากการเผยแพร่ที่ถูกขัดจังหวะ กรุณาตรวจข้อมูลสำรองก่อนรันใหม่')
    folder = root / '.building_current'
    if folder.exists():
        remove_generated(folder, root)
    folder.mkdir()
    return folder


def _checked_path(root, relative):
    # ตรวจว่าพาธไฟล์รายงานปลอดภัยและอยู่ในโฟลเดอร์ที่กำหนด
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0].startswith('.'):
        raise ValueError('พาธไฟล์รายงานไม่ถูกต้อง')
    target = root / path
    if target.name not in GENERATED_FILES or not target.resolve().is_relative_to(root):
        raise ValueError('พาธอยู่นอกขอบเขตไฟล์รายงาน')
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError('ไฟล์รายงานต้องไม่ผ่านลิงก์')
    return target


def _existing_files(root):
    # อ่านรายการไฟล์ผลลัพธ์ที่รายงานเดิมใช้อยู่
    manifest = root / '.report_files.json'
    if manifest.exists():
        if manifest.is_symlink():
            raise ValueError('manifest ต้องไม่เป็นลิงก์')
        paths = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ValueError('manifest รายงานไม่ถูกต้อง')
        return {str(_checked_path(root, p).relative_to(root).as_posix()) for p in paths}
    # Adopt flat reports written before a manifest existed; leave unrelated folders intact.
    files = {p.name for p in root.iterdir() if p.is_file() and p.name in GENERATED_FILES and not p.name.startswith('.')}
    for folder in root.iterdir():
        if folder.is_dir() and (folder.name == 'details' or re.fullmatch(r'portfolio|[0-9]{2}_[A-Za-z0-9_]+', folder.name)):
            _safe_tree(folder, root)
            files.update(p.relative_to(root).as_posix() for p in folder.rglob('*') if p.is_file())
    for name in files:
        _checked_path(root, name)
    return files


def publish_report(folder):
    # เขียนทับผลรายงานและคืนไฟล์เดิมหากบันทึกไม่สำเร็จ
    """Replace files directly in the report root; restore old files if writing fails."""
    folder = Path(folder)
    root = folder.parent.resolve()
    if folder.name != '.building_current':
        raise ValueError('เผยแพร่ได้เฉพาะโฟลเดอร์ที่ begin_report สร้าง')
    _safe_tree(folder, root)
    if not any((folder / name).is_file() for name in ('report.md', 'comparison.md')):
        raise ValueError('ยังไม่มีรายงานที่เสร็จสมบูรณ์')
    before = _existing_files(root)
    sources = [p for p in folder.rglob('*') if p.is_file()]
    expected = {p.relative_to(folder).as_posix() for p in sources}
    for name in expected:
        _checked_path(root, name)
    backup = root / '.previous_current'
    if backup.exists():
        raise ValueError('พบข้อมูลสำรองที่ยังไม่ได้ตรวจสอบ')
    backup.mkdir()
    for name in before:
        source = _checked_path(root, name)
        if source.is_file():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    manifest = root / '.report_files.json'
    original_manifest = manifest.read_bytes() if manifest.exists() else None
    sources.sort(key=lambda p: (p.relative_to(folder).as_posix() in ('report.md', 'comparison.md'), str(p)))
    changed = []
    try:
        for source in sources:
            relative = source.relative_to(folder).as_posix()
            _replace_file(source, _checked_path(root, relative))
            changed.append(relative)
        for name in before - expected:
            target = _checked_path(root, name)
            if target.is_file():
                target.unlink()
        staged_manifest = folder / '.report_files.json'
        staged_manifest.write_text(json.dumps(sorted(expected), indent=2), encoding='utf-8')
        _replace_file(staged_manifest, manifest)
    except OSError as error:
        for name in before:
            saved = backup / name
            if saved.is_file():
                _replace_file(saved, _checked_path(root, name))
        for name in set(changed) - before:
            _checked_path(root, name).unlink(missing_ok=True)
        if original_manifest is None:
            manifest.unlink(missing_ok=True)
        else:
            manifest.write_bytes(original_manifest)
        remove_generated(backup, root)
        raise OSError('อัปเดตรายงานไม่สำเร็จ คืนไฟล์รายงานเดิมแล้ว') from error
    warnings = []
    # Remove empty output directories only; preserve comparison reports and user files.
    parents = {parent for name in before - expected for parent in (root / name).parents if parent != root and parent.is_relative_to(root)}
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    for old in [folder, backup, *[p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d{8}_\d{6}_\d{6}', p.name)]]:
        try:
            remove_generated(old, root)
        except (ValueError, OSError) as error:
            warnings.append(str(error))
    return root, warnings


def _replace_file(source, target):
    # แทนที่ไฟล์ปลายทางผ่านไฟล์ชั่วคราว
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name('.update_' + uuid.uuid4().hex)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


