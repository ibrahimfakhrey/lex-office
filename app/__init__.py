import os
from datetime import datetime
from flask import Flask, redirect, url_for, request, g, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from app.extensions import db, migrate, jwt, mail, csrf, limiter


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # Trust X-Forwarded-* headers from a single proxy hop (Cloudflare, nginx,
    # PythonAnywhere). Required so request.remote_addr / rate-limiting / GeoIP
    # see the real client IP rather than the proxy IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Silent market detection (EG / SA). Sets g.market on every request.
    from app.utils.market import install_market_hook
    install_market_hook(app)

    # JWT error handlers — return JSON for API, redirect for web
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'token_expired', 'message': 'انتهت صلاحية الرمز'}), 401
        return redirect(url_for('auth.login'))

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'unauthorized', 'message': 'مطلوب تسجيل الدخول'}), 401
        return redirect(url_for('auth.login'))

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'invalid_token', 'message': 'رمز غير صالح'}), 401
        return redirect(url_for('auth.login'))

    # Register blueprints
    _register_blueprints(app)

    # Register template context processors
    _register_context_processors(app)

    # Onboarding check is handled in the login_required decorator

    # Create tables on first request (dev only)
    with app.app_context():
        from app.models import (
            tenant, user, subscription, client, case, session,
            judgment, enforcement, power_of_attorney, financial,
            task, document, notification, audit, admin, op_finance,
            admin_rbac, ai_usage,
        )

    return app


def _register_blueprints(app):
    """Register all blueprints."""
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.onboarding.routes import onboarding_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.clients.routes import clients_bp
    from app.blueprints.cases.routes import cases_bp
    from app.blueprints.sessions.routes import sessions_bp
    from app.blueprints.judgments.routes import judgments_bp
    from app.blueprints.enforcement.routes import enforcement_bp
    from app.blueprints.poa.routes import poa_bp
    from app.blueprints.financial.routes import financial_bp
    from app.blueprints.tasks.routes import tasks_bp
    from app.blueprints.documents.routes import documents_bp
    from app.blueprints.templates_legal.routes import templates_legal_bp
    from app.blueprints.notifications.routes import notifications_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.settings.routes import settings_bp
    from app.blueprints.public.routes import public_bp

    app.register_blueprint(public_bp)  # /terms, /privacy, /account/delete
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(onboarding_bp, url_prefix='/onboarding')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(cases_bp, url_prefix='/cases')
    app.register_blueprint(sessions_bp, url_prefix='/sessions')
    app.register_blueprint(judgments_bp, url_prefix='/judgments')
    app.register_blueprint(enforcement_bp, url_prefix='/enforcement')
    app.register_blueprint(poa_bp, url_prefix='/poa')
    app.register_blueprint(financial_bp, url_prefix='/financial')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    app.register_blueprint(templates_legal_bp, url_prefix='/templates')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(settings_bp, url_prefix='/settings')

    # REST API v1
    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # Super Admin Panel — uses ADMIN_URL_MODE env var (prefix or subdomain)
    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    # Admin CLI commands (flask create-admin, flask list-admins)
    from app.admin.cli import register_admin_cli
    register_admin_cli(app)
    from app.cli_encryption import register_encryption_cli
    register_encryption_cli(app)
    from app.cli_tasks import register_tasks_cli
    register_tasks_cli(app)

    # Landing page
    @app.route('/')
    def index():
        from flask import render_template as rt
        return rt('landing.html')


def _register_context_processors(app):
    """Register Jinja2 context processors."""
    @app.context_processor
    def inject_globals():
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
        from app.utils.helpers import egypt_today, generate_chatwoot_token
        current_user = None
        unread_count = 0
        chatwoot_hash = None
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                from app.models.user import User
                current_user = User.query.get(int(user_id))
                if current_user:
                    from app.models.notification import Notification
                    unread_count = Notification.query.filter_by(
                        user_id=current_user.id, is_read=False
                    ).count()
                    chatwoot_hash = generate_chatwoot_token(current_user.id)
        except Exception:
            pass
        # Brand identity from SystemSetting — used by sidebars, login pages,
        # email subjects, etc. Falls back to safe defaults so templates never
        # break before settings exist.
        try:
            from app.models.admin import SystemSetting
            product_name = SystemSetting.get('product_name', 'LexOffice') or 'LexOffice'
            product_logo = SystemSetting.get('product_logo_url', '') or ''
            privacy_url = SystemSetting.get('privacy_url', '') or ''
            terms_url = SystemSetting.get('terms_url', '') or ''
            support_email = SystemSetting.get('support_email', '') or ''
        except Exception:
            product_name = 'LexOffice'
            product_logo = ''
            privacy_url = ''
            terms_url = ''
            support_email = ''

        # Egypt-only mode: ignore any tenant.market value (could be 'sa' from
        # earlier signups) and force everyone to the EG market. To re-enable
        # multi-market, restore the original logic that prefers tenant.market.
        from app.utils.market_config import get_config, DEFAULT_MARKET
        effective_market = DEFAULT_MARKET
        market_cfg = get_config(effective_market)

        return dict(
            current_user=current_user,
            now=datetime.utcnow,
            today=egypt_today(),
            unread_count=unread_count,
            chatwoot_hash=chatwoot_hash,
            product_name=product_name,
            product_logo=product_logo,
            privacy_url=privacy_url,
            terms_url=terms_url,
            support_email=support_email,
            market=effective_market,
            market_config=market_cfg,
        )
