"""Egyptian national ID — image extraction (Tier 1 free OCR + Tier 2 Claude vision).

Tier 1 (free):
    extract_id_number_from_image(image_bytes) → 14-digit string or None.
    Uses Tesseract with ara+eng. The 14-digit number is large, clean digits;
    Tesseract reads it reliably even on phone photos. Combine with
    `app.utils.national_id.parse_national_id` to get DOB / governorate /
    gender at zero cost.

Tier 2 (opt-in, Claude vision, tracked via ai_usage):
    extract_full_id_via_claude(image_bytes, tenant, user) →
    dict with full_name, address, profession, national_id (best-effort).
    The lawyer presses a button — never auto-called.

Both functions are resilient to bad images: they return cleanly with
`success=False` rather than raising.
"""
from __future__ import annotations

import base64
import io
import logging
import re
from typing import Optional

from flask import current_app

from app.utils.national_id import parse_national_id

log = logging.getLogger(__name__)


# ── Tier 1: Tesseract ─────────────────────────────────────────────────────────

# Arabic-Indic ↔ Latin digit map (Egyptian IDs use both depending on year).
_ARABIC_INDIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

# Tesseract config: digits-only PSM modes give the best 14-number recall.
# PSM 6: assume a single uniform block of text (the back of the ID has the number on its own line).
# PSM 11: sparse text, useful for the front where the number is buried among other lines.
_TESS_CONFIGS = [
    '--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789٠١٢٣٤٥٦٧٨٩',
    '--oem 1 --psm 11 -c tessedit_char_whitelist=0123456789٠١٢٣٤٥٦٧٨٩',
    '--oem 1 --psm 6',
    '--oem 1 --psm 11',
]


def _normalize_digits(text: str) -> str:
    return text.translate(_ARABIC_INDIC_DIGITS)


def _candidate_ids(text: str) -> list[str]:
    """Pull every run of exactly 14 digits from the OCR output.

    The number on real ID cards is always 14 digits — we accept the first
    valid one (parses cleanly via parse_national_id). We also accept runs
    that include digit separators that Tesseract sometimes injects.
    """
    normalized = _normalize_digits(text)
    # Strip non-digit characters between digits so 123 456 78901234 also matches.
    only_digits_runs = re.findall(r'(?:\d[\D]{0,2}){12,16}\d', normalized)
    candidates = set()
    for run in only_digits_runs:
        digits = re.sub(r'\D', '', run)
        # Slide 14-digit windows across long runs (Tesseract sometimes joins lines).
        for i in range(0, max(1, len(digits) - 13)):
            chunk = digits[i:i + 14]
            if len(chunk) == 14:
                candidates.add(chunk)
    # Also include bare 14-digit substrings (defensive).
    for m in re.finditer(r'\d{14}', normalized):
        candidates.add(m.group(0))
    return list(candidates)


def _preprocess(image_bytes: bytes):
    """Decode, auto-orient via EXIF, convert to grayscale. Returns a PIL.Image."""
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(image_bytes))
    # ImageOps.exif_transpose rotates the image to its on-screen orientation.
    img = ImageOps.exif_transpose(img)
    # Convert RGBA → RGB → L so Tesseract sees clean grayscale.
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img = ImageOps.grayscale(img)
    # Mild upscale helps Tesseract on phone photos where the number is small.
    if min(img.size) < 1000:
        ratio = 1000 / min(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size)
    return img


def extract_id_number_from_image(image_bytes: bytes) -> dict:
    """Tier 1 — read the 14-digit national ID from an uploaded photo (free).

    Returns:
        {'success': True, 'national_id': '29001011212345', 'parsed': {...}}
        {'success': False, 'error': '...'}                  on failure
    """
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return {
            'success': False,
            'error': 'مكتبة OCR غير مثبتة على الخادم',
        }

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return {'success': False, 'error': 'Pillow غير مثبت'}

    try:
        img = _preprocess(image_bytes)
    except Exception as e:
        log.warning('ID OCR: image preprocessing failed: %s', e)
        return {'success': False, 'error': 'تعذّر قراءة الصورة'}

    import pytesseract  # re-import for use
    seen: set[str] = set()
    for cfg in _TESS_CONFIGS:
        try:
            text = pytesseract.image_to_string(img, lang='ara+eng', config=cfg)
        except pytesseract.TesseractNotFoundError:
            return {
                'success': False,
                'error': 'Tesseract OCR غير مثبت على الخادم',
            }
        except Exception as e:
            log.info('ID OCR pass (%s) failed: %s', cfg, e)
            continue

        for candidate in _candidate_ids(text):
            if candidate in seen:
                continue
            seen.add(candidate)
            parsed = parse_national_id(candidate)
            if parsed.get('valid'):
                return {
                    'success': True,
                    'national_id': candidate,
                    'parsed': parsed,
                }

    if seen:
        # We saw 14-digit runs but none validated — probably mis-OCR'd digits.
        return {
            'success': False,
            'error': 'تم قراءة أرقام لكن لم يتعرف على رقم قومي صحيح — جرّب صورة أوضح',
        }
    return {
        'success': False,
        'error': 'لم يتم العثور على رقم قومي بالصورة',
    }


# ── Tier 2: Claude vision (opt-in) ───────────────────────────────────────────

_TIER2_FEATURE_KEY = 'national_id_extract'
_TIER2_MODEL = 'claude-haiku-4-5'  # vision-capable; cheapest option that handles Arabic well

_TIER2_TOOL = {
    'name': 'save_national_id_data',
    'description': 'حفظ البيانات المستخرجة من صورة البطاقة الشخصية المصرية.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'national_id':     {'type': ['string', 'null'], 'description': 'الرقم القومي (14 رقم)'},
            'full_name_ar':    {'type': ['string', 'null'], 'description': 'الاسم الرباعي كاملاً بالعربية'},
            'address':         {'type': ['string', 'null'], 'description': 'العنوان كاملاً كما هو مكتوب'},
            'governorate':     {'type': ['string', 'null'], 'description': 'المحافظة (من العنوان)'},
            'city':            {'type': ['string', 'null'], 'description': 'المدينة أو المركز'},
            'district':        {'type': ['string', 'null'], 'description': 'الحي أو القرية'},
            'street':          {'type': ['string', 'null'], 'description': 'الشارع'},
            'profession':      {'type': ['string', 'null'], 'description': 'المهنة'},
            'date_of_birth':   {'type': ['string', 'null'], 'description': 'تاريخ الميلاد بصيغة YYYY-MM-DD'},
            'gender':          {'type': ['string', 'null'], 'enum': ['male', 'female', None]},
        },
        'required': [],
    },
}

_TIER2_SYSTEM = (
    'أنت مساعد متخصص في قراءة بيانات البطاقة الشخصية المصرية. '
    'مهمتك استخراج البيانات المنظمة من الصورة المرفوعة. '
    'إذا لم تستطع قراءة حقل بثقة، أرجع null بدلاً من التخمين. '
    'الرقم القومي 14 رقم بالضبط — تحقق دائماً.'
)


def extract_full_id_via_claude(image_bytes: bytes, *, tenant, user) -> dict:
    """Tier 2 — Claude vision extracts every field on the ID (opt-in, tracked).

    Caller MUST run ai_usage.check_can_use(tenant, 'national_id_extract')
    before calling this; we don't double-check here.

    Returns dict with success flag and the extracted fields.
    """
    try:
        from anthropic import Anthropic
        import anthropic
    except ImportError:
        return {'success': False, 'error': 'مكتبة Claude غير مثبتة'}

    api_key = current_app.config.get('ANTHROPIC_API_KEY') or ''
    if not api_key:
        return {'success': False, 'error': 'مفتاح Claude غير مُعدّ'}

    from app.services import ai_usage

    media_type = _sniff_media_type(image_bytes)
    if media_type is None:
        return {'success': False, 'error': 'تنسيق الصورة غير مدعوم — استخدم JPG أو PNG'}

    image_b64 = base64.b64encode(image_bytes).decode('ascii')

    messages = [
        {
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': image_b64,
                    },
                },
                {
                    'type': 'text',
                    'text': (
                        'استخرج البيانات من صورة البطاقة الشخصية المصرية. '
                        'احفظ النتيجة عبر أداة save_national_id_data. '
                        'إذا كانت الصورة لا تحتوي على بطاقة شخصية، استدع الأداة بحقول null.'
                    ),
                },
            ],
        }
    ]

    client = Anthropic(api_key=api_key)
    response = None
    try:
        response = client.messages.create(
            model=_TIER2_MODEL,
            max_tokens=1024,
            system=_TIER2_SYSTEM,
            messages=messages,
            tools=[_TIER2_TOOL],
            tool_choice={'type': 'tool', 'name': _TIER2_TOOL['name']},
        )
    except anthropic.AuthenticationError as e:
        ai_usage.record(tenant, user, feature=_TIER2_FEATURE_KEY,
                        model=_TIER2_MODEL, response=None, success=False,
                        error=f'auth: {e}')
        return {'success': False, 'error': 'فشل التحقق من مفتاح Claude'}
    except anthropic.RateLimitError as e:
        ai_usage.record(tenant, user, feature=_TIER2_FEATURE_KEY,
                        model=_TIER2_MODEL, response=None, success=False,
                        error=f'rate_limit: {e}')
        return {'success': False, 'error': 'تم تجاوز حد الطلبات — جرّب بعد دقيقة'}
    except anthropic.BadRequestError as e:
        ai_usage.record(tenant, user, feature=_TIER2_FEATURE_KEY,
                        model=_TIER2_MODEL, response=None, success=False,
                        error=f'bad_request: {getattr(e, "message", str(e))}')
        return {'success': False, 'error': 'تعذّر تحليل الصورة — جرّب صورة أوضح أو أصغر'}
    except Exception as e:
        ai_usage.record(tenant, user, feature=_TIER2_FEATURE_KEY,
                        model=_TIER2_MODEL, response=None, success=False,
                        error=f'unexpected: {e}')
        log.exception('Claude ID extract failed')
        return {'success': False, 'error': 'حدث خطأ غير متوقع أثناء التحليل'}

    # Pull the tool_use block's parsed input.
    tool_input = None
    for block in (response.content or []):
        if getattr(block, 'type', '') == 'tool_use' \
                and getattr(block, 'name', '') == _TIER2_TOOL['name']:
            tool_input = getattr(block, 'input', {}) or {}
            break

    ai_usage.record(tenant, user, feature=_TIER2_FEATURE_KEY,
                    model=_TIER2_MODEL, response=response, success=True)

    if not tool_input:
        return {'success': False, 'error': 'لم تستطع الأداة استخراج بيانات منظمة'}

    # If Claude returned an ID number, validate + augment with the local parser
    # so the form can autofill DOB / governorate / gender from the digits too.
    extracted_id = tool_input.get('national_id')
    if extracted_id:
        parsed = parse_national_id(extracted_id)
        if parsed.get('valid'):
            tool_input['parsed_from_number'] = {
                'date_of_birth': parsed.get('date_of_birth'),
                'governorate': parsed.get('governorate'),
                'gender': parsed.get('gender'),
            }

    return {'success': True, 'data': tool_input}


def _sniff_media_type(image_bytes: bytes) -> Optional[str]:
    """Detect image media type from magic bytes. Returns None if unsupported."""
    if len(image_bytes) < 12:
        return None
    if image_bytes.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return 'image/gif'
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return 'image/webp'
    return None
