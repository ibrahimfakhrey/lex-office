"""LexOffice REST API v1 — Blueprint registration and error handlers."""
from flask import Blueprint, jsonify
from app.extensions import csrf

api_bp = Blueprint('api', __name__)
csrf.exempt(api_bp)


@api_bp.errorhandler(404)
def api_not_found(e):
    return jsonify({'success': False, 'error': 'not_found', 'message': 'المورد غير موجود'}), 404


@api_bp.errorhandler(500)
def api_server_error(e):
    return jsonify({'success': False, 'error': 'server_error', 'message': 'خطأ في الخادم'}), 500


@api_bp.errorhandler(429)
def api_rate_limited(e):
    return jsonify({'success': False, 'error': 'rate_limited', 'message': 'تم تجاوز حد الطلبات'}), 429


# Import sub-modules to register routes on api_bp
from app.api import auth          # noqa: E402, F401
from app.api import onboarding    # noqa: E402, F401
from app.api import dashboard     # noqa: E402, F401
from app.api import clients       # noqa: E402, F401
from app.api import cases         # noqa: E402, F401
from app.api import sessions      # noqa: E402, F401
from app.api import judgments     # noqa: E402, F401
from app.api import enforcement   # noqa: E402, F401
from app.api import poa           # noqa: E402, F401
from app.api import financial     # noqa: E402, F401
from app.api import tasks         # noqa: E402, F401
from app.api import documents     # noqa: E402, F401
from app.api import templates_legal  # noqa: E402, F401
from app.api import notifications # noqa: E402, F401
from app.api import reports       # noqa: E402, F401
from app.api import settings      # noqa: E402, F401
from app.api import lookups       # noqa: E402, F401
