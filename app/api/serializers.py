"""JSON serialization helpers for API responses."""
from decimal import Decimal
from datetime import date, datetime, time


def serialize_value(val):
    """Convert Python types to JSON-serializable values."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, time):
        return val.strftime('%H:%M')
    return val


def file_url(relative_path):
    """Build full URL for a static file path."""
    if not relative_path:
        return None
    from flask import request
    return f"{request.host_url}static/{relative_path}"
