# อ่านและตรวจค่าตั้งการวิเคราะห์ร่วมกันจาก config เดียว
"""Shared validated settings for the application and analysis utilities."""
import json
import math
from pathlib import Path
from .project_paths import CONFIG_DIR

KEYS = {'train_fraction', 'minimum_train_days', 'minimum_test_days', 'pca_target',
        'shortlist_size', 'candidate_weights', 'fee_rate', 'fit_fraction_of_train',
        'minimum_fit_days', 'minimum_validation_days', 'minimum_sd_reduction_percent',
        'maximum_return_loss_pp', 'maximum_drawdown_worsening_pp'}


def validate_policy(values):
    # ตรวจช่วงค่าและชนิดข้อมูลก่อนนำไปแบ่งข้อมูลหรือคำนวณ
    if not isinstance(values, dict) or set(values) != KEYS:
        raise ValueError('config มีชื่อค่าขาดหรือเกิน กรุณาตรวจชื่อใน recommendation_policy.json')
    policy = dict(values)
    for name in KEYS - {'candidate_weights'}:
        value = policy[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'ค่า config ไม่ถูกต้อง: {name}')
    for name in ('train_fraction', 'fit_fraction_of_train'):
        if not 0 < policy[name] < 1:
            raise ValueError(f'{name} ต้องมากกว่า 0 และน้อยกว่า 1')
    if not 0 < policy['pca_target'] <= 1:
        raise ValueError('pca_target ต้องอยู่ใน (0,1]')
    for name, minimum in [('minimum_train_days', 150), ('minimum_fit_days', 150),
                          ('minimum_test_days', 2), ('minimum_validation_days', 2), ('shortlist_size', 1)]:
        if policy[name] < minimum or int(policy[name]) != policy[name]:
            raise ValueError(f'{name} ต้องเป็นจำนวนเต็มอย่างน้อย {minimum}')
        policy[name] = int(policy[name])
    if not 0 <= policy['fee_rate'] <= 0.01:
        raise ValueError('fee_rate ต้องอยู่ระหว่าง 0 และ 0.01')
    if not 0 <= policy['minimum_sd_reduction_percent'] <= 100:
        raise ValueError('minimum_sd_reduction_percent ต้องอยู่ระหว่าง 0 และ 100')
    if min(policy['maximum_return_loss_pp'], policy['maximum_drawdown_worsening_pp']) < 0:
        raise ValueError('เกณฑ์ยอมรับผลที่แย่ลงต้องไม่ติดลบ')
    weights = policy['candidate_weights']
    if not isinstance(weights, list) or not weights:
        raise ValueError('candidate_weights ต้องเป็นรายการที่ไม่ว่าง')
    if any(isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a) or not 0 < a < 1 for a in weights):
        raise ValueError('น้ำหนักทดลองทุกค่าต้องมากกว่า 0 และน้อยกว่า 1')
    if len(set(weights)) != len(weights):
        raise ValueError('candidate_weights ต้องไม่มีค่าซ้ำ')
    policy['candidate_weights'] = list(weights)
    return policy


def load_policy(path=None):
    # อ่านไฟล์ config ใหม่ตอนเริ่มรัน และแจ้งข้อผิดพลาดที่แก้ไขได้
    path = Path(path) if path is not None else CONFIG_DIR / 'recommendation_policy.json'
    try:
        values = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'อ่าน config ไม่สำเร็จ: {path}: {error}') from error
    return validate_policy(values)


def split_days(days, boundary, policy):
    # แบ่งวันจากเส้นแบ่งปฏิทินเดิม แล้วตรวจจำนวนวันขั้นต่ำ
    train = [day for day in days if day <= boundary]
    test = [day for day in days if day > boundary]
    if len(train) < policy['minimum_train_days'] or len(test) < policy['minimum_test_days']:
        raise ValueError(f"หลังแบ่งข้อมูล ต้องมี Train อย่างน้อย {policy['minimum_train_days']} วัน และ Test อย่างน้อย {policy['minimum_test_days']} วัน")
    return train, test
