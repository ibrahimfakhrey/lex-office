"""Helpers for at-rest field encryption on SQLAlchemy models.

`EncryptedFieldsMixin` provides two methods, `_enc_get` and `_enc_set`,
that handle the encrypt/decrypt round-trip using `self.tenant_id`.
Models declare `_fieldname = db.Column('fieldname', db.Text)` then expose
the public name via a `@hybrid_property` that calls these helpers.

`register_encrypt_on_flush(Model, field_names)` wires a single
before_insert/before_update event handler that encrypts any value still
in plaintext at flush time. Idempotent — already-encrypted values are
detected via the enc:v1: prefix.
"""
from sqlalchemy import event


class EncryptedFieldsMixin:
    """Add to any SQLAlchemy model that has a `tenant_id` and at least one
    encrypted field. Provides the two helpers used by hybrid_property getters
    and setters.
    """

    def _enc_get(self, raw):
        if raw is None:
            return None
        if not self.tenant_id:
            return raw
        from app.services.encryption import decrypt
        try:
            return decrypt(raw, self.tenant_id)
        except Exception:
            # Never crash a list/detail page on bad ciphertext.
            return raw

    def _enc_set(self, value):
        if value is None or value == '':
            return None
        if not self.tenant_id:
            return value
        from app.services.encryption import encrypt
        return encrypt(value, self.tenant_id)


def register_encrypt_on_flush(Model, field_names):
    """Install a before_insert/before_update event that encrypts any of
    `field_names` (the underscored storage names) still in plaintext.
    """
    fields = tuple(field_names)

    def _on_flush(mapper, connection, target):
        from app.services.encryption import encrypt, is_encrypted
        if not target.tenant_id:
            return
        for col in fields:
            val = getattr(target, col, None)
            if val and not is_encrypted(val):
                setattr(target, col, encrypt(val, target.tenant_id))

    event.listen(Model, 'before_insert', _on_flush)
    event.listen(Model, 'before_update', _on_flush)
