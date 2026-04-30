"""Admin CLI commands — register on the Flask app."""
import getpass
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models.admin import AdminUser
from app.utils.validators import validate_email, validate_password


def register_admin_cli(app):
    """Register admin CLI commands on the Flask app."""

    @app.cli.command('create-admin')
    @click.option('--email', prompt='البريد الإلكتروني', help='Admin email')
    @click.option('--name', prompt='الاسم الكامل', help='Admin full name')
    @click.option('--password', default=None, help='Admin password (will prompt if not provided)')
    @click.option('--role', default='super_admin', show_default=True,
                  type=click.Choice(['super_admin', 'support_agent', 'finance_admin']))
    @with_appcontext
    def create_admin(email, name, password, role):
        """Create a new admin user (interactive)."""
        email = email.strip().lower()
        if not validate_email(email):
            click.echo(click.style('❌ Invalid email format', fg='red'))
            return

        existing = AdminUser.query.filter_by(email=email).first()
        if existing:
            click.echo(click.style(f'❌ Admin with email {email} already exists (id={existing.id})', fg='red'))
            return

        if not password:
            password = getpass.getpass('كلمة المرور: ')
            confirm = getpass.getpass('تأكيد كلمة المرور: ')
            if password != confirm:
                click.echo(click.style('❌ Passwords do not match', fg='red'))
                return

        valid, msg = validate_password(password)
        if not valid:
            click.echo(click.style(f'❌ {msg}', fg='red'))
            return

        admin = AdminUser(
            email=email,
            full_name=name,
            role=role,
            is_active=True,
            mfa_enabled=False,  # admin can enable later
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        click.echo(click.style(f'✓ Admin created: {email} (id={admin.id}, role={role})', fg='green'))
        click.echo(click.style('  Login at: http://127.0.0.1:5000/admin/login', fg='cyan'))

    @app.cli.command('list-admins')
    @with_appcontext
    def list_admins():
        """List all admin users."""
        admins = AdminUser.query.order_by(AdminUser.created_at).all()
        if not admins:
            click.echo('No admins found. Create one with: flask create-admin')
            return
        click.echo(f'\n{"ID":<4} {"Email":<35} {"Name":<25} {"Role":<15} Active')
        click.echo('-' * 90)
        for a in admins:
            active = '✓' if a.is_active else '✗'
            click.echo(f'{a.id:<4} {a.email:<35} {a.full_name:<25} {a.role:<15} {active}')
