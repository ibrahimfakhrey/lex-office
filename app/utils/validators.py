"""Input validation helpers."""
import re

from app.utils.market_config import get_config, normalize_market, DEFAULT_MARKET


def validate_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone, market=None):
    """Validate a mobile number for the given market (defaults to 'eg').

    Empty input is considered valid (caller decides if the field is required).
    """
    if not phone:
        return True
    market = normalize_market(market or DEFAULT_MARKET)
    normalized = normalize_phone(phone, market)
    if not normalized:
        return False
    return bool(re.match(get_config(market)['phone_regex'], normalized))


def normalize_phone(phone, market=None):
    """Normalize a phone number to canonical local form for the given market.

    EG → 01XXXXXXXXX (11 digits, strips +20 / 0020 / 20)
    SA → 05XXXXXXXX  (10 digits, strips +966 / 00966 / 966)

    Strips spaces/dashes/parens. Returns None if input is empty after stripping.
    Returns the raw digit-stripped string if shape doesn't match — uniqueness
    still works, but callers should pair with validate_phone() for shape checks.
    """
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return None

    market = normalize_market(market or DEFAULT_MARKET)

    if market == 'sa':
        # Strip 966 / 00966 country prefix
        if digits.startswith('00966'):
            digits = digits[5:]
        elif digits.startswith('966') and len(digits) >= 12:
            digits = digits[3:]
        # Saudi mobile is 9 digits starting with 5; prepend 0 to canonicalize
        if digits.startswith('5') and len(digits) == 9:
            digits = '0' + digits
        return digits

    # EG (default)
    if digits.startswith('0020'):
        digits = digits[4:]
    elif digits.startswith('20') and len(digits) == 12:
        digits = digits[2:]
    if not digits.startswith('0') and len(digits) == 10:
        digits = '0' + digits
    return digits


def validate_national_id(nid):
    """Validate Egyptian National ID (14 digits)."""
    if not nid:
        return True
    return bool(re.match(r'^\d{14}$', nid.strip()))


def validate_password(password):
    """Validate password policy: 8+ chars, uppercase, number, symbol."""
    if len(password) < 8:
        return False, 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'
    if not re.search(r'[A-Z]', password):
        return False, 'كلمة المرور يجب أن تحتوي على حرف كبير'
    if not re.search(r'\d', password):
        return False, 'كلمة المرور يجب أن تحتوي على رقم'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'كلمة المرور يجب أن تحتوي على رمز خاص'
    return True, ''


def sanitize_string(s):
    """Basic sanitization for text input."""
    if not s:
        return s
    # Remove potential XSS
    s = s.replace('<script', '&lt;script')
    s = s.replace('</script', '&lt;/script')
    return s.strip()
