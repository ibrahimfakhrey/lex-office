"""Seed Saudi Arabian courts list (market='sa').

Hierarchy follows the Saudi Ministry of Justice + Saudipedia + Chambers 2026:
  - Supreme Court (المحكمة العليا) — Riyadh
  - Courts of Appeal (محاكم الاستئناف) — one per region
  - First-instance specialized courts:
      General (عامة), Criminal (جزائية), Commercial (تجارية),
      Labor (عمالية), Personal Status / Family (أحوال شخصية)
  - Enforcement Courts (محاكم التنفيذ)
  - Board of Grievances (ديوان المظالم) — administrative hierarchy

Idempotent: upserts by (name, market='sa').
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.case import Court
from app.utils.constants import CourtType

# Major-city set used for general / criminal / family / enforcement courts
_MAJOR_CITIES = [
    ('الرياض', 'Riyadh'),
    ('جدة', 'Jeddah'),
    ('مكة المكرمة', 'Makkah'),
    ('المدينة المنورة', 'Madinah'),
    ('الدمام', 'Dammam'),
    ('الخبر', 'Khobar'),
    ('الجبيل', 'Jubail'),
    ('أبها', 'Abha'),
    ('خميس مشيط', 'Khamis Mushait'),
    ('تبوك', 'Tabuk'),
    ('حائل', 'Hail'),
    ('بريدة', 'Buraydah'),
    ('عنيزة', 'Unaizah'),
    ('جازان', 'Jazan'),
    ('نجران', 'Najran'),
    ('الباحة', 'Al-Bahah'),
    ('عرعر', 'Arar'),
    ('سكاكا', 'Sakaka'),
]

# Labor courts — official 7 cities per Saudipedia
_LABOR_CITIES = [
    ('الرياض', 'Riyadh'),
    ('مكة المكرمة', 'Makkah'),
    ('جدة', 'Jeddah'),
    ('أبها', 'Abha'),
    ('الدمام', 'Dammam'),
    ('بريدة', 'Buraydah'),
    ('المدينة المنورة', 'Madinah'),
]

# Commercial courts — 3 cities per Chambers 2026 / Saudipedia
_COMMERCIAL_CITIES = [
    ('الرياض', 'Riyadh'),
    ('جدة', 'Jeddah'),
    ('الدمام', 'Dammam'),
]

# 13 regional Courts of Appeal
_APPEAL_REGIONS = [
    ('محكمة استئناف منطقة الرياض', 'Riyadh Court of Appeal', 'الرياض'),
    ('محكمة استئناف منطقة مكة المكرمة', 'Makkah Court of Appeal', 'مكة المكرمة'),
    ('محكمة استئناف المنطقة الشرقية', 'Eastern Region Court of Appeal', 'الدمام'),
    ('محكمة استئناف منطقة عسير', 'Asir Court of Appeal', 'أبها'),
    ('محكمة استئناف منطقة المدينة المنورة', 'Madinah Court of Appeal', 'المدينة المنورة'),
    ('محكمة استئناف منطقة القصيم', 'Qassim Court of Appeal', 'بريدة'),
    ('محكمة استئناف منطقة تبوك', 'Tabuk Court of Appeal', 'تبوك'),
    ('محكمة استئناف منطقة حائل', 'Hail Court of Appeal', 'حائل'),
    ('محكمة استئناف منطقة جازان', 'Jazan Court of Appeal', 'جازان'),
    ('محكمة استئناف منطقة نجران', 'Najran Court of Appeal', 'نجران'),
    ('محكمة استئناف منطقة الباحة', 'Al-Bahah Court of Appeal', 'الباحة'),
    ('محكمة استئناف منطقة الحدود الشمالية', 'Northern Borders Court of Appeal', 'عرعر'),
    ('محكمة استئناف منطقة الجوف', 'Al-Jouf Court of Appeal', 'سكاكا'),
]


def _build():
    rows = []

    # 1. Supreme Court
    rows.append({
        'name': 'المحكمة العليا',
        'name_en': 'Supreme Court',
        'court_type': CourtType.SUPREME.value,
        'governorate': 'الرياض',
    })

    # 2. Appeal courts
    for name_ar, name_en, region in _APPEAL_REGIONS:
        rows.append({
            'name': name_ar, 'name_en': name_en,
            'court_type': CourtType.APPEAL.value,
            'governorate': region,
        })

    # 3. General courts (المحاكم العامة) in major cities
    for ar, en in _MAJOR_CITIES:
        rows.append({
            'name': f'المحكمة العامة بـ{ar}',
            'name_en': f'{en} General Court',
            'court_type': CourtType.PRIMARY.value,
            'governorate': ar,
        })

    # 4. Criminal courts (المحاكم الجزائية) in major cities
    for ar, en in _MAJOR_CITIES:
        rows.append({
            'name': f'المحكمة الجزائية بـ{ar}',
            'name_en': f'{en} Criminal Court',
            'court_type': CourtType.CRIMINAL.value,
            'governorate': ar,
        })

    # 5. Commercial courts (3 cities)
    for ar, en in _COMMERCIAL_CITIES:
        rows.append({
            'name': f'المحكمة التجارية بـ{ar}',
            'name_en': f'{en} Commercial Court',
            'court_type': CourtType.COMMERCIAL.value,
            'governorate': ar,
        })

    # 6. Labor courts (7 cities)
    for ar, en in _LABOR_CITIES:
        rows.append({
            'name': f'المحكمة العمالية بـ{ar}',
            'name_en': f'{en} Labor Court',
            'court_type': CourtType.LABOR.value,
            'governorate': ar,
        })

    # 7. Personal Status / Family courts in major cities
    for ar, en in _MAJOR_CITIES:
        rows.append({
            'name': f'محكمة الأحوال الشخصية بـ{ar}',
            'name_en': f'{en} Personal Status Court',
            'court_type': CourtType.FAMILY.value,
            'governorate': ar,
        })

    # 8. Enforcement courts in major cities
    for ar, en in _MAJOR_CITIES:
        rows.append({
            'name': f'محكمة التنفيذ بـ{ar}',
            'name_en': f'{en} Enforcement Court',
            'court_type': CourtType.ENFORCEMENT.value,
            'governorate': ar,
        })

    # 9. Board of Grievances — administrative hierarchy
    rows.extend([
        {'name': 'المحكمة الإدارية العليا',
         'name_en': 'Supreme Administrative Court',
         'court_type': CourtType.STATE_COUNCIL.value,
         'governorate': 'الرياض'},
        {'name': 'محكمة الاستئناف الإدارية بالرياض',
         'name_en': 'Riyadh Administrative Court of Appeal',
         'court_type': CourtType.STATE_COUNCIL.value,
         'governorate': 'الرياض'},
        {'name': 'محكمة الاستئناف الإدارية بمكة المكرمة',
         'name_en': 'Makkah Administrative Court of Appeal',
         'court_type': CourtType.STATE_COUNCIL.value,
         'governorate': 'مكة المكرمة'},
        {'name': 'محكمة الاستئناف الإدارية بالدمام',
         'name_en': 'Dammam Administrative Court of Appeal',
         'court_type': CourtType.STATE_COUNCIL.value,
         'governorate': 'الدمام'},
    ])
    # Administrative first-instance courts in major cities
    for ar, en in [('الرياض', 'Riyadh'), ('جدة', 'Jeddah'),
                   ('الدمام', 'Dammam'), ('أبها', 'Abha'),
                   ('بريدة', 'Buraydah'), ('المدينة المنورة', 'Madinah'),
                   ('تبوك', 'Tabuk'), ('حائل', 'Hail'),
                   ('جازان', 'Jazan'), ('نجران', 'Najran')]:
        rows.append({
            'name': f'المحكمة الإدارية بـ{ar}',
            'name_en': f'{en} Administrative Court',
            'court_type': CourtType.STATE_COUNCIL.value,
            'governorate': ar,
        })

    # Tag everything as KSA
    for r in rows:
        r['market'] = 'sa'
    return rows


def seed():
    courts = _build()
    with app.app_context():
        added, updated = 0, 0
        for data in courts:
            existing = Court.query.filter_by(name=data['name'], market='sa').first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.session.add(Court(**data))
                added += 1
        db.session.commit()
        total_sa = Court.query.filter_by(market='sa').count()
        print(f"KSA courts: {added} added, {updated} updated. Total SA in DB: {total_sa}.")


if __name__ == '__main__':
    seed()
