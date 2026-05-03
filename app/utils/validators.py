"""Input validation helpers."""
import re


def validate_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    """Validate Egyptian mobile number — accepts any format normalize_phone() handles."""
    if not phone:
        return True
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    return bool(re.match(r'^01[0125]\d{8}$', normalized))


def normalize_phone(phone):
    """Normalize an Egyptian phone number to canonical 11-digit local form (01XXXXXXXXX).

    Strips spaces/dashes/parens and the +20 / 0020 / 20 country prefix when present.
    Returns None if the input is empty after stripping. Returns the raw digit-stripped
    string if it doesn't match the Egyptian shape — uniqueness still works, but
    callers should pair this with validate_phone() for shape enforcement.
    """
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return None
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
