"""Helper functions for LexOffice."""
import os
import secrets
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import current_app


def generate_otp():
    """Generate a 6-digit OTP code."""
    return str(secrets.randbelow(900000) + 100000)


def generate_token(length=32):
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def allowed_file(filename):
    """Check if file extension is allowed."""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'docx', 'png', 'jpg', 'jpeg', 'xlsx'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_uploaded_file(file, subfolder='general'):
    """Save an uploaded file and return the relative path."""
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    # Add UUID to prevent collisions
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)
    file.save(file_path)
    return os.path.join(subfolder, unique_name)


def get_file_size(file_path):
    """Get file size in bytes."""
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
    if os.path.exists(full_path):
        return os.path.getsize(full_path)
    return 0


def format_currency(amount, currency='ج.م'):
    """Format number as Egyptian currency."""
    if amount is None:
        return f'0 {currency}'
    return f'{float(amount):,.2f} {currency}'


def get_date_display(d, include_time=False):
    """Format date for Arabic display."""
    if not d:
        return ''
    if include_time and isinstance(d, datetime):
        return d.strftime('%Y/%m/%d %H:%M')
    if hasattr(d, 'strftime'):
        return d.strftime('%Y/%m/%d')
    return str(d)


def calculate_appeal_deadline(judgment_date, appeal_type):
    """Calculate appeal deadline based on Egyptian law.

    - استئناف (Appeal): 40 days from judgment date
    - نقض (Cassation): 60 days from judgment date
    """
    if appeal_type == 'appeal':
        return judgment_date + timedelta(days=40)
    elif appeal_type == 'cassation':
        return judgment_date + timedelta(days=60)
    return None


def paginate_query(query, page, per_page=None):
    """Paginate a SQLAlchemy query."""
    if per_page is None:
        per_page = current_app.config.get('ITEMS_PER_PAGE', 20)
    return query.paginate(page=page, per_page=per_page, error_out=False)
