import os
from datetime import datetime
from flask import Flask, redirect, url_for, request, g
from config import config
from app.extensions import db, migrate, jwt, mail, csrf, limiter


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return redirect(url_for('auth.login'))

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return redirect(url_for('auth.login'))

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
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
            task, document, notification, audit
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
        from app.utils.helpers import egypt_today
        current_user = None
        unread_count = 0
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
        except Exception:
            pass
        return dict(current_user=current_user, now=datetime.utcnow,
                    today=egypt_today(), unread_count=unread_count)
