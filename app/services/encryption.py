"""At-rest field encryption — envelope encryption with per-tenant DEKs.

Architecture:
    ENCRYPTION_MASTER_KEY (env)
        encrypts ─→ Tenant.encryption_key   (DEK ciphertext stored in DB)
                        decrypts ─→ field values  (per-row ciphertexts)

Public API:
    encrypt(plaintext, tenant_id) -> str   # base64 Fernet token, random IV
    decrypt(ciphertext, tenant_id) -> str
    blind_index(value, tenant_id) -> str   # HMAC-SHA256 hex, deterministic
    is_encrypted(token) -> bool            # heuristic for migration co-existence

Notes:
    * Fernet = AES-128-CBC + HMAC-SHA256, random IV per write. Same plaintext
      written twice yields different ciphertexts — cannot be searched directly.
    * Blind index uses a SEPARATE HMAC key (ENCRYPTION_BLIND_INDEX_KEY) and
      a per-tenant salt drawn from the DEK, so two tenants storing the same
      phone number get different blind indexes. Prevents cross-tenant inference.
    * DEKs are lazy-generated: first encrypt() call for a tenant creates and
      stores its DEK. No upfront backfill needed.
    * The DEK cache is per-process (dict); cleared on app restart. Decryption
      requires a DB hit only on cache miss.

Loss policy:
    Lose ENCRYPTION_MASTER_KEY → tenant DEKs unreadable → all encrypted fields
    permanently unrecoverable. Multiple offline backups required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


# ── module-private state ───────────────────────────────────────────────────

# Decrypted DEKs cached per-process for performance. tenant_id -> Fernet instance.
_DEK_CACHE: dict[int, Fernet] = {}


# ── key loading helpers ────────────────────────────────────────────────────

def _master_fernet() -> Fernet:
    """Return the master Fernet instance built from ENCRYPTION_MASTER_KEY.

    Raises RuntimeError if the env var is missing/invalid — we never silently
    fall back to plaintext.
    """
    key = (os.getenv('ENCRYPTION_MASTER_KEY') or '').strip()
    if not key:
        # Allow current_app config as a fallback for tests that set it there.
        try:
            key = (current_app.config.get('ENCRYPTION_MASTER_KEY') or '').strip()
        except RuntimeError:
            key = ''
    if not key:
        raise RuntimeError(
            'ENCRYPTION_MASTER_KEY is not configured. Refusing to encrypt.'
        )
    try:
        return Fernet(key.encode())
    except Exception as e:  # invalid base64 / wrong length
        raise RuntimeError(f'ENCRYPTION_MASTER_KEY is invalid: {e}') from e


def _blind_index_key() -> bytes:
    """Return the raw bytes of the HMAC key for blind indexes."""
    key = (os.getenv('ENCRYPTION_BLIND_INDEX_KEY') or '').strip()
    if not key:
        try:
            key = (current_app.config.get('ENCRYPTION_BLIND_INDEX_KEY') or '').strip()
        except RuntimeError:
            key = ''
    if not key:
        raise RuntimeError(
            'ENCRYPTION_BLIND_INDEX_KEY is not configured. Refusing to compute blind index.'
        )
    # The key is base64-encoded for env transport; raw bytes for HMAC.
    try:
        return base64.urlsafe_b64decode(key.encode())
    except Exception as e:
        raise RuntimeError(f'ENCRYPTION_BLIND_INDEX_KEY is invalid base64: {e}') from e


# ── tenant DEK lifecycle ───────────────────────────────────────────────────

def _load_or_create_dek(tenant_id: int) -> Fernet:
    """Fetch and decrypt the tenant's DEK; create one on first call."""
    if tenant_id in _DEK_CACHE:
        return _DEK_CACHE[tenant_id]

    # Import here to avoid circular import at module load time.
    from app.extensions import db
    from app.models.tenant import Tenant

    tenant = Tenant.query.get(tenant_id)
    if tenant is None:
        raise ValueError(f'Tenant {tenant_id} not found')

    master = _master_fernet()

    if tenant.encryption_key:
        # Decrypt existing DEK with master.
        try:
            raw_dek = master.decrypt(tenant.encryption_key.encode())
        except InvalidToken as e:
            raise RuntimeError(
                f'Tenant {tenant_id} DEK fails master verification — '
                f'master key may have been rotated/lost'
            ) from e
        dek = Fernet(raw_dek)
    else:
        # First use: generate a fresh DEK, store its ciphertext.
        raw_dek = Fernet.generate_key()
        tenant.encryption_key = master.encrypt(raw_dek).decode()
        db.session.add(tenant)
        db.session.commit()
        dek = Fernet(raw_dek)

    _DEK_CACHE[tenant_id] = dek
    return dek


def invalidate_dek_cache(tenant_id: Optional[int] = None):
    """Drop one or all cached DEKs. Call after admin key-rotation actions."""
    if tenant_id is None:
        _DEK_CACHE.clear()
    else:
        _DEK_CACHE.pop(tenant_id, None)


# ── public encryption API ──────────────────────────────────────────────────

# Distinctive prefix so we can detect already-encrypted vs plaintext during
# the dual-read phase of each field migration. Fernet tokens start with
# "gAAAAA" (base64 of version byte 0x80), so a regular prefix on top is safe.
_CIPHERTEXT_PREFIX = 'enc:v1:'


def encrypt(plaintext: Optional[str], tenant_id: int) -> Optional[str]:
    """Encrypt a UTF-8 string with the tenant's DEK. None → None."""
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)
    dek = _load_or_create_dek(tenant_id)
    token = dek.encrypt(plaintext.encode('utf-8')).decode('ascii')
    return _CIPHERTEXT_PREFIX + token


def decrypt(ciphertext: Optional[str], tenant_id: int) -> Optional[str]:
    """Decrypt a previously-encrypted string. Plaintext / None → returned as-is.

    The plaintext passthrough enables a safe dual-read phase: existing rows
    written before the field was encrypted will return their original value.
    """
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        return ciphertext
    if not ciphertext.startswith(_CIPHERTEXT_PREFIX):
        # Legacy plaintext row — return unchanged.
        return ciphertext
    token = ciphertext[len(_CIPHERTEXT_PREFIX):]
    dek = _load_or_create_dek(tenant_id)
    try:
        return dek.decrypt(token.encode('ascii')).decode('utf-8')
    except InvalidToken as e:
        raise RuntimeError(
            f'Failed to decrypt field for tenant {tenant_id} — '
            f'tenant DEK may be wrong or ciphertext corrupted'
        ) from e


def is_encrypted(value: Optional[str]) -> bool:
    """True if `value` is one of our ciphertexts. Used by backfill scripts."""
    return isinstance(value, str) and value.startswith(_CIPHERTEXT_PREFIX)


# ── blind index for searchable encrypted fields ────────────────────────────

def blind_index(value: Optional[str], tenant_id: int) -> Optional[str]:
    """Deterministic HMAC of a normalized value, for `WHERE x_idx = ?` lookups.

    Same plaintext + same tenant → same hash, allowing exact-match search.
    Different tenants → different hashes (per-tenant salt drawn from DEK),
    preventing cross-tenant correlation.

    Normalization: strip + lowercase. Phone numbers / national IDs should
    pre-normalize digits before calling (the caller knows the field rules).
    """
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    base_key = _blind_index_key()
    # Mix the tenant's DEK first 16 bytes as a per-tenant salt. We never expose
    # raw DEK bytes elsewhere, so this is safe.
    dek = _load_or_create_dek(tenant_id)
    salt = dek._signing_key[:16]  # noqa: SLF001 — internal Fernet bytes
    keyed = hmac.new(base_key + salt, normalized.encode('utf-8'), hashlib.sha256)
    return keyed.hexdigest()
