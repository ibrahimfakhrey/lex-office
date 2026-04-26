"""API response helpers and utilities."""
from datetime import datetime
from flask import jsonify, request


def success_response(data=None, message=None, status_code=200, meta=None):
    """Standard success response."""
    response = {'success': True}
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    if meta:
        response['meta'] = meta
    return jsonify(response), status_code


def error_response(message, error_code='error', status_code=400, errors=None):
    """Standard error response."""
    response = {
        'success': False,
        'error': error_code,
        'message': message,
    }
    if errors:
        response['errors'] = errors
    return jsonify(response), status_code


def validation_error(errors):
    """Return 422 with field-level validation errors."""
    return error_response(
        message='بيانات غير صالحة',
        error_code='validation_error',
        status_code=422,
        errors=errors,
    )


def paginated_response(query, page=None, per_page=20, serialize_fn=None):
    """Paginate a SQLAlchemy query and return standardized response."""
    if page is None:
        page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', per_page, type=int)
    per_page = min(per_page, 100)  # cap at 100

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    if serialize_fn:
        items = [serialize_fn(item) for item in pagination.items]
    else:
        items = [item.to_dict() for item in pagination.items]

    return success_response(
        data=items,
        meta={
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        },
    )


def parse_date(date_str):
    """Parse ISO date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def parse_datetime(dt_str):
    """Parse ISO datetime string."""
    if not dt_str:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def parse_time(time_str):
    """Parse time string HH:MM."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return None


def get_json_or_form():
    """Get request data from JSON body or form data."""
    data = request.get_json(silent=True)
    if data:
        return data
    return request.form.to_dict()
