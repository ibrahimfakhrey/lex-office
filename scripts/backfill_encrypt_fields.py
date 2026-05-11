"""Backfill: encrypt plaintext rows for at-rest encryption phases 1-4.

Idempotent — already-encrypted rows are detected via the enc:v1: prefix and
skipped. Safe to run repeatedly. Encrypts in batches of 500.

Usage:
    python -m scripts.backfill_encrypt_fields              # run for all fields
    python -m scripts.backfill_encrypt_fields --field client.internal_notes
"""
import argparse
import sys

from app import create_app
from app.extensions import db
from app.services.encryption import encrypt, is_encrypted


# Each entry: (Model, db_column_attr_name, friendly_label).
# We assign to the storage attribute (the underscored one) to bypass the
# hybrid_property setter — which would re-encrypt an already-handled value.
FIELDS = [
    ('app.models.client', 'Client', '_internal_notes', 'client.internal_notes'),
    # client.national_id is handled by _do_client_national_id (encrypt + blind index)
    ('app.models.case', 'Case', '_internal_notes', 'case.internal_notes'),
    ('app.models.case', 'Case', '_subject', 'case.subject'),
    ('app.models.document', 'Document', '_notes', 'document.notes'),
    ('app.models.document', 'Document', '_ai_summary', 'document.ai_summary'),
    ('app.models.financial', 'Payment', '_notes', 'payment.notes'),
    ('app.models.financial', 'Invoice', '_notes', 'invoice.notes'),
    ('app.models.financial', 'Expense', '_description', 'expense.description'),
    ('app.models.judgment', 'Judgment', '_judgment_text', 'judgment.judgment_text'),
    ('app.models.judgment', 'Judgment', '_notes', 'judgment.notes'),
    # ai_analysis is JSON — handled separately below.
    ('app.models.task', 'Task', '_description', 'task.description'),
    ('app.models.task', 'Appointment', '_notes', 'appointment.notes'),
    ('app.models.session', 'Session', '_preparation_notes', 'session.preparation_notes'),
    ('app.models.session', 'Session', '_result_summary', 'session.result_summary'),
    ('app.models.enforcement', 'Enforcement', '_notes', 'enforcement.notes'),
]


def _do_field(module_path, class_name, attr_name, label, dry_run=False):
    mod = __import__(module_path, fromlist=[class_name])
    Model = getattr(mod, class_name)

    rows = Model.query.all()
    total = len(rows)
    encrypted = 0
    already = 0
    skipped = 0

    for i, row in enumerate(rows, 1):
        raw = getattr(row, attr_name)
        if raw is None or raw == '':
            skipped += 1
            continue
        if is_encrypted(raw):
            already += 1
            continue
        if not row.tenant_id:
            skipped += 1
            continue
        new_ct = encrypt(raw, row.tenant_id)
        if not dry_run:
            setattr(row, attr_name, new_ct)
        encrypted += 1
        if i % 500 == 0 and not dry_run:
            db.session.commit()
            print(f'  [{label}] committed batch at row {i}/{total}')

    if not dry_run:
        db.session.commit()
    print(f'[{label}] total={total}  encrypted_now={encrypted}  already={already}  skipped={skipped}  dry_run={dry_run}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--field', default='all',
                        help='comma-separated labels (e.g. "client.internal_notes") or "all"')
    parser.add_argument('--dry-run', action='store_true',
                        help="don't commit, just count")
    args = parser.parse_args()

    selected_labels = set(args.field.split(',')) if args.field != 'all' else None

    app = create_app()
    with app.app_context():
        for module_path, class_name, attr_name, label in FIELDS:
            if selected_labels and label not in selected_labels:
                continue
            _do_field(module_path, class_name, attr_name, label, dry_run=args.dry_run)

        # Judgment.ai_analysis — JSON column with dict legacy values.
        if not selected_labels or 'judgment.ai_analysis' in selected_labels:
            _do_judgment_ai_analysis(dry_run=args.dry_run)

        # Client.national_id — encrypt ciphertext + compute blind index.
        if not selected_labels or 'client.national_id' in selected_labels:
            _do_client_national_id(dry_run=args.dry_run)


def _do_client_national_id(dry_run=False):
    """Backfill Client.national_id: encrypt + populate blind index."""
    from app.models.client import Client
    from app.services.encryption import encrypt, is_encrypted, blind_index

    rows = Client.query.all()
    encrypted = already = skipped = indexed = 0
    for c in rows:
        raw = c._national_id
        if raw is None or raw == '':
            skipped += 1
            continue
        if not c.tenant_id:
            skipped += 1
            continue
        normalized = ''.join(ch for ch in str(raw) if ch.isdigit()) if not is_encrypted(raw) else None
        if is_encrypted(raw):
            already += 1
        else:
            if not dry_run:
                c._national_id = encrypt(raw, c.tenant_id)
            encrypted += 1
        # Always (re)compute blind index if missing
        if not c._national_id_idx:
            # If raw was already encrypted, decrypt to get plaintext for indexing
            if normalized is None:
                from app.services.encryption import decrypt
                try:
                    plain = decrypt(c._national_id if not dry_run or is_encrypted(raw) else raw, c.tenant_id)
                    normalized = ''.join(ch for ch in str(plain or '') if ch.isdigit())
                except Exception:
                    normalized = ''
            if normalized:
                if not dry_run:
                    c._national_id_idx = blind_index(normalized, c.tenant_id)
                indexed += 1
    if not dry_run:
        db.session.commit()
    print(f'[client.national_id] total={len(rows)}  encrypted_now={encrypted}  already={already}  indexed={indexed}  skipped={skipped}  dry_run={dry_run}')


def _do_judgment_ai_analysis(dry_run=False):
    """Backfill the JSON column ai_analysis on judgments. Serializes dicts
    to JSON, encrypts, stores as JSON string (Postgres-valid)."""
    import json
    from app.models.judgment import Judgment
    from app.services.encryption import encrypt, is_encrypted

    rows = Judgment.query.all()
    encrypted = already = skipped = 0
    for j in rows:
        raw = j._ai_analysis
        if raw is None:
            skipped += 1
            continue
        if isinstance(raw, str) and is_encrypted(raw):
            already += 1
            continue
        if not j.tenant_id:
            skipped += 1
            continue
        serialized = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        if not dry_run:
            j._ai_analysis = encrypt(serialized, j.tenant_id)
        encrypted += 1
    if not dry_run:
        db.session.commit()
    print(f'[judgment.ai_analysis] total={len(rows)}  encrypted_now={encrypted}  already={already}  skipped={skipped}  dry_run={dry_run}')


if __name__ == '__main__':
    sys.exit(main())
