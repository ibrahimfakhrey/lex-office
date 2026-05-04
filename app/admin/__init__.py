"""LexOffice Super Admin Panel — Blueprint registration.

Routing modes (controlled by ADMIN_URL_MODE env var):
  - prefix    : admin lives at /admin/* (default — works in dev and on PythonAnywhere)
  - subdomain : admin lives at adminlexoffice.<SERVER_NAME>/* (production)

The same blueprint is used in both modes; only the URL prefix / subdomain differ.
"""
import os
from flask import Blueprint

# Choose mode based on env var
ADMIN_URL_MODE = os.getenv('ADMIN_URL_MODE', 'prefix')

if ADMIN_URL_MODE == 'subdomain':
    admin_bp = Blueprint(
        'admin',
        __name__,
        subdomain='adminlexoffice',
        template_folder='templates',
        static_folder='static',
        static_url_path='/admin-static',
    )
else:
    admin_bp = Blueprint(
        'admin',
        __name__,
        url_prefix='/admin',
        template_folder='templates',
        static_folder='static',
        static_url_path='/admin-static',
    )


# Import sub-modules so their routes get registered on admin_bp
from app.admin import auth          # noqa: E402, F401
from app.admin import dashboard     # noqa: E402, F401
from app.admin import tenants       # noqa: E402, F401
from app.admin import plans         # noqa: E402, F401
from app.admin import features      # noqa: E402, F401
from app.admin import billing       # noqa: E402, F401
from app.admin import notifications # noqa: E402, F401
from app.admin import settings      # noqa: E402, F401
from app.admin import audit         # noqa: E402, F401

# Internal finance sub-package (Manasety company books)
from app.admin.finance import employees as _finance_employees   # noqa: E402, F401
from app.admin.finance import payroll as _finance_payroll       # noqa: E402, F401
from app.admin.finance import lenders as _finance_lenders       # noqa: E402, F401
from app.admin.finance import expenses as _finance_expenses     # noqa: E402, F401
from app.admin.finance import income as _finance_income         # noqa: E402, F401
from app.admin.finance import dashboard as _finance_dashboard   # noqa: E402, F401
