"""Egyptian national ID (14-digit) decoder.

The 14-digit Egyptian national ID encodes a lot of data in its structure:

    1     century code: 2 → 19xx, 3 → 20xx
    2-3   year of birth (within the century)
    4-5   month of birth (01–12)
    6-7   day of birth (01–31)
    8-9   governorate-of-birth code
    10-12 serial within the day (no semantics we use)
    13    gender: odd = male, even = female
    14    checksum (algorithm is publicly debated; we don't enforce it)

This is a Layer-1 (free, no AI, no OCR) extractor used by the add/edit
client form to autofill date_of_birth, governorate, gender on input.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional, TypedDict


# Governorate codes (positions 8–9) → Arabic name as used in
# app.blueprints.clients.routes.EGYPTIAN_GOVERNORATES. Strings here MUST
# match that list verbatim so the <select> option preselects correctly.
GOVERNORATE_CODES: dict[str, str] = {
    '01': 'القاهرة',
    '02': 'الإسكندرية',
    '03': 'بورسعيد',
    '04': 'السويس',
    '11': 'دمياط',
    '12': 'الدقهلية',
    '13': 'الشرقية',
    '14': 'القليوبية',
    '15': 'كفر الشيخ',
    '16': 'الغربية',
    '17': 'المنوفية',
    '18': 'البحيرة',
    '19': 'الإسماعيلية',
    '21': 'الجيزة',
    '22': 'بني سويف',
    '23': 'الفيوم',
    '24': 'المنيا',
    '25': 'أسيوط',
    '26': 'سوهاج',
    '27': 'قنا',
    '28': 'أسوان',
    '29': 'الأقصر',
    '31': 'البحر الأحمر',
    '32': 'الوادي الجديد',
    '33': 'مطروح',
    '34': 'شمال سيناء',
    '35': 'جنوب سيناء',
    '88': 'مواليد خارج جمهورية مصر العربية',
}


class ParsedNationalId(TypedDict, total=False):
    valid: bool
    date_of_birth: Optional[str]     # ISO 'YYYY-MM-DD'
    governorate: Optional[str]       # Arabic name (matches EGYPTIAN_GOVERNORATES)
    governorate_code: Optional[str]
    gender: Optional[str]            # 'male' | 'female'
    gender_ar: Optional[str]
    error: Optional[str]


def parse_national_id(nid: Optional[str]) -> ParsedNationalId:
    """Decode a 14-digit Egyptian national ID into its embedded fields.

    Returns {'valid': False, 'error': '...'} on any structural problem,
    {'valid': True, ...} with the decoded fields otherwise. Never raises.
    """
    if not nid:
        return {'valid': False, 'error': 'الرقم القومي مطلوب'}

    digits = re.sub(r'\D', '', str(nid))
    if len(digits) != 14:
        return {'valid': False, 'error': 'الرقم القومي يجب أن يكون 14 رقم'}

    century_digit = digits[0]
    if century_digit == '2':
        century_base = 1900
    elif century_digit == '3':
        century_base = 2000
    else:
        return {'valid': False, 'error': 'الرقم القومي يبدأ بـ 2 أو 3 فقط'}

    try:
        year = century_base + int(digits[1:3])
        month = int(digits[3:5])
        day = int(digits[5:7])
        dob = date(year, month, day)
    except (ValueError, TypeError):
        return {'valid': False, 'error': 'تاريخ الميلاد المضمن غير صالح'}

    if dob > date.today():
        return {'valid': False, 'error': 'تاريخ الميلاد في المستقبل'}

    gov_code = digits[7:9]
    governorate = GOVERNORATE_CODES.get(gov_code)
    # An unknown governorate code is not a hard failure — older / foreign-born
    # cards occasionally use codes we don't list. Return the digits anyway.

    gender_digit = int(digits[12])
    is_male = (gender_digit % 2) == 1

    return {
        'valid': True,
        'date_of_birth': dob.isoformat(),
        'governorate': governorate,
        'governorate_code': gov_code,
        'gender': 'male' if is_male else 'female',
        'gender_ar': 'ذكر' if is_male else 'أنثى',
        'error': None,
    }
