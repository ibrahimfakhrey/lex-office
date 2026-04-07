"""Input validation helpers."""
import re


def validate_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    """Validate Egyptian phone number."""
    if not phone:
        return True
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    # Egyptian numbers: 01xxxxxxxxx or +201xxxxxxxxx
    pattern = r'^(\+?2)?01[0125]\d{8}$'
    return bool(re.match(pattern, cleaned))


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
