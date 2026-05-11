"""CLI commands for at-rest encryption management.

Commands:
    flask encrypt-backfill            Idempotent backfill of all encrypted fields.
    flask encrypt-rotate-master       Re-encrypt every tenant DEK with a NEW master key.
    flask encrypt-status              Print summary of which fields/rows are encrypted.
"""
import os
import click
from flask.cli import with_appcontext


def register_encryption_cli(app):
    @app.cli.command('encrypt-backfill')
    @click.option('--dry-run', is_flag=True, help="Don't commit, just count.")
    @with_appcontext
    def encrypt_backfill(dry_run):
        """Encrypt any plaintext rows that weren't encrypted yet. Idempotent."""
        from scripts.backfill_encrypt_fields import FIELDS, _do_field, _do_judgment_ai_analysis
        for module_path, class_name, attr_name, label in FIELDS:
            _do_field(module_path, class_name, attr_name, label, dry_run=dry_run)
        _do_judgment_ai_analysis(dry_run=dry_run)
        click.echo(click.style('Backfill complete.', fg='green'))

    @app.cli.command('encrypt-status')
    @with_appcontext
    def encrypt_status():
        """Print how many rows are encrypted vs plaintext per field."""
        from scripts.backfill_encrypt_fields import FIELDS
        from app.services.encryption import is_encrypted
        click.echo(f'\n{"Field":<35} {"Total":>8} {"Encrypted":>10} {"Plaintext":>10} {"Null":>6}')
        click.echo('-' * 78)
        for module_path, class_name, attr_name, label in FIELDS:
            mod = __import__(module_path, fromlist=[class_name])
            Model = getattr(mod, class_name)
            total = Model.query.count()
            enc = 0
            plain = 0
            null = 0
            for row in Model.query.all():
                v = getattr(row, attr_name)
                if v is None or v == '':
                    null += 1
                elif is_encrypted(v):
                    enc += 1
                else:
                    plain += 1
            click.echo(f'{label:<35} {total:>8} {enc:>10} {plain:>10} {null:>6}')

    @app.cli.command('encrypt-rotate-master')
    @click.option('--new-key', required=True, help='New master Fernet key (base64).')
    @click.option('--yes', is_flag=True, help='Skip confirmation.')
    @with_appcontext
    def encrypt_rotate_master(new_key, yes):
        """Rotate the master key. Re-encrypts every tenant DEK with the new key.

        Row-level field ciphertexts are unchanged (still encrypted with the
        same DEKs); only the tenant.encryption_key envelope is re-wrapped.

        Steps to roll out:
          1. Generate new key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
          2. flask encrypt-rotate-master --new-key <newkey>
          3. Replace ENCRYPTION_MASTER_KEY in .env with <newkey>
          4. Restart workers.
          5. After verifying, scrub old key from backup vaults if compromised.
        """
        from cryptography.fernet import Fernet, InvalidToken
        from app.extensions import db
        from app.models.tenant import Tenant
        from app.services.encryption import invalidate_dek_cache

        old_key = (os.getenv('ENCRYPTION_MASTER_KEY') or '').strip()
        if not old_key:
            click.echo(click.style('ENCRYPTION_MASTER_KEY not set — nothing to rotate from.', fg='red'))
            return
        try:
            old_f = Fernet(old_key.encode())
            new_f = Fernet(new_key.encode())
        except Exception as e:
            click.echo(click.style(f'Invalid key: {e}', fg='red'))
            return

        tenants = Tenant.query.filter(Tenant.encryption_key.isnot(None)).all()
        click.echo(f'About to re-wrap DEKs for {len(tenants)} tenants.')
        if not yes:
            click.confirm('Proceed?', abort=True)

        rotated = 0
        failed = []
        for t in tenants:
            try:
                raw_dek = old_f.decrypt(t.encryption_key.encode())
            except InvalidToken:
                failed.append(t.id)
                continue
            t.encryption_key = new_f.encrypt(raw_dek).decode()
            rotated += 1

        db.session.commit()
        invalidate_dek_cache()  # so the next encrypt() reads the new envelope

        click.echo(click.style(f'\n✓ Rotated {rotated} tenant DEKs.', fg='green'))
        if failed:
            click.echo(click.style(
                f'✗ Failed for {len(failed)} tenants (DEK unreadable with old key): {failed}',
                fg='red',
            ))
        click.echo(click.style(
            '\nIMPORTANT: now update ENCRYPTION_MASTER_KEY in your .env to the new value '
            'and restart all app workers.',
            fg='yellow',
        ))
