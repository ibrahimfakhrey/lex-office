import json
from datetime import datetime
from app.extensions import db
from app.models._encryption import EncryptedFieldsMixin, register_encrypt_on_flush


class Judgment(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'judgments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    judgment_date = db.Column(db.Date, nullable=False)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=True)
    judgment_type = db.Column(db.String(30), nullable=False)
    result = db.Column(db.String(30), nullable=False)
    # Encrypted at rest. Access via the `judgment_text` hybrid_property.
    _judgment_text = db.Column('judgment_text', db.Text, nullable=True)
    judgment_file_path = db.Column(db.String(500), nullable=True)
    judge_name = db.Column(db.String(200), nullable=True)
    awarded_amount = db.Column(db.Numeric(12, 2), nullable=True)
    _notes = db.Column('notes', db.Text, nullable=True)
    # Structured analysis returned by Claude when the lawyer uploads a judgment
    # PDF/DOCX on /judgments/create. Holds the keys: court_name, judgment_date,
    # judgment_type, result, judge_name, case_number, awarded_amount,
    # parties{plaintiff,defendant}, summary_ar, key_points_ar.
    #
    # Column type stays JSON for schema compatibility — Postgres accepts a JSON
    # string as a valid JSON value. We store the ciphertext as `"enc:v1:..."`
    # (JSON-quoted) so legacy dict rows (plaintext) and encrypted rows coexist.
    # Access via `ai_analysis` hybrid_property — consumers see a dict as before.
    _ai_analysis = db.Column('ai_analysis', db.JSON, nullable=True)

    # Appeal tracking
    appeal_tracking_enabled = db.Column(db.Boolean, default=False)
    appeal_type = db.Column(db.String(20), nullable=True)
    appeal_deadline = db.Column(db.Date, nullable=True)
    appeal_notification_30d = db.Column(db.Boolean, default=False)
    appeal_notification_14d = db.Column(db.Boolean, default=False)
    appeal_notification_7d = db.Column(db.Boolean, default=False)
    appeal_notification_3d = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    court = db.relationship('Court')
    enforcement = db.relationship('Enforcement', backref='judgment', uselist=False)

    @property
    def judgment_text(self):
        return self._enc_get(self._judgment_text)

    @judgment_text.setter
    def judgment_text(self, value):
        self._judgment_text = self._enc_set(value)

    @property
    def notes(self):
        return self._enc_get(self._notes)

    @notes.setter
    def notes(self, value):
        self._notes = self._enc_set(value)

    @property
    def ai_analysis(self):
        """Decrypted dict view. Returns None / dict / (legacy plaintext dict)."""
        raw = self._ai_analysis
        if raw is None:
            return None
        # Legacy row: stored as a JSON object/dict → return as-is.
        if isinstance(raw, dict):
            return raw
        # New encrypted row: stored as a JSON string containing "enc:v1:..."
        if isinstance(raw, str):
            from app.services.encryption import decrypt, is_encrypted
            if is_encrypted(raw) and self.tenant_id:
                try:
                    pt = decrypt(raw, self.tenant_id)
                    return json.loads(pt) if pt else None
                except Exception:
                    return None
            # Plain JSON string — try to parse, else return as-is.
            try:
                return json.loads(raw)
            except (ValueError, TypeError):
                return raw
        return raw

    @ai_analysis.setter
    def ai_analysis(self, value):
        if value is None:
            self._ai_analysis = None
            return
        if not self.tenant_id:
            # tenant_id not yet known — keep as dict; flush hook will encrypt.
            self._ai_analysis = value
            return
        from app.services.encryption import encrypt
        # Serialize dict → JSON → encrypt → store as JSON string in DB.
        serialized = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self._ai_analysis = encrypt(serialized, self.tenant_id)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'judgment_date': self.judgment_date.isoformat() if self.judgment_date else None,
            'court_id': self.court_id,
            'court_name': self.court.name if self.court else None,
            'judgment_type': self.judgment_type,
            'result': self.result,
            'judgment_text': self.judgment_text,
            'judgment_file_path': self.judgment_file_path,
            'judge_name': self.judge_name,
            'awarded_amount': float(self.awarded_amount) if self.awarded_amount is not None else None,
            'notes': self.notes,
            'ai_analysis': self.ai_analysis,
            'appeal_tracking_enabled': self.appeal_tracking_enabled,
            'appeal_type': self.appeal_type,
            'appeal_deadline': self.appeal_deadline.isoformat() if self.appeal_deadline else None,
            'appeal_notification_30d': self.appeal_notification_30d,
            'appeal_notification_14d': self.appeal_notification_14d,
            'appeal_notification_7d': self.appeal_notification_7d,
            'appeal_notification_3d': self.appeal_notification_3d,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Judgment {self.judgment_date} - {self.result}>'


# Flush hook — encrypt _judgment_text and _notes the standard way, and
# JSON-serialize-then-encrypt _ai_analysis if it slipped through as a dict.
register_encrypt_on_flush(Judgment, ['_judgment_text', '_notes'])


from sqlalchemy import event as _sa_event  # noqa: E402

@_sa_event.listens_for(Judgment, 'before_insert')
@_sa_event.listens_for(Judgment, 'before_update')
def _encrypt_judgment_ai_analysis(mapper, connection, target):
    from app.services.encryption import encrypt, is_encrypted
    val = target._ai_analysis
    if val is None or not target.tenant_id:
        return
    # Already encrypted JSON-string ciphertext → skip.
    if isinstance(val, str) and is_encrypted(val):
        return
    # Dict (legacy or freshly assigned) → JSON-serialize then encrypt.
    if isinstance(val, dict):
        serialized = json.dumps(val, ensure_ascii=False)
        target._ai_analysis = encrypt(serialized, target.tenant_id)
    elif isinstance(val, str):
        # Plain JSON string (legacy) → encrypt as-is.
        target._ai_analysis = encrypt(val, target.tenant_id)
