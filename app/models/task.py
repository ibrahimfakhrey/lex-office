from datetime import datetime, date
from app.extensions import db
from app.models._encryption import EncryptedFieldsMixin, register_encrypt_on_flush


class Task(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    _description = db.Column('description', db.Text, nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    # When this task was auto-issued as a reminder for a court session, we
    # link back to it so editing/deleting the session can keep the reminder
    # in sync. ON DELETE CASCADE: deleting a session drops its reminder.
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('sessions.id', ondelete='CASCADE'),
        nullable=True, index=True,
    )
    priority = db.Column(db.String(20), default='normal')
    deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='new')
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_type = db.Column(db.String(20), nullable=True)
    # ALMUSTSHAR-19: how many days before `deadline` to fire a reminder.
    # NULL = no reminder. `reminder_sent_at` is set once the dispatcher
    # has sent the reminder so we don't re-fire on every cron tick.
    # When `deadline` is edited, `reminder_sent_at` is reset.
    reminder_before_days = db.Column(db.Integer, nullable=True)
    reminder_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_tasks')
    assigner = db.relationship('User', foreign_keys=[assigned_by])

    @property
    def description(self):
        return self._enc_get(self._description)

    @description.setter
    def description(self, value):
        self._description = self._enc_set(value)

    @property
    def is_overdue(self):
        if self.deadline and self.status != 'done':
            return datetime.utcnow() > self.deadline
        return False

    @property
    def priority_color(self):
        colors = {'urgent': 'danger', 'important': 'warning', 'normal': 'secondary'}
        return colors.get(self.priority, 'secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'assignee_name': self.assignee.full_name if self.assignee else None,
            'assigned_by': self.assigned_by,
            'assigner_name': self.assigner.full_name if self.assigner else None,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'client_id': self.case.client_id if self.case else None,
            'client_name': self.case.client.full_name if (self.case and self.case.client) else None,
            'session_id': self.session_id,
            'priority': self.priority,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status': self.status,
            'is_recurring': self.is_recurring,
            'recurrence_type': self.recurrence_type,
            'reminder_before_days': self.reminder_before_days,
            'reminder_sent_at': self.reminder_sent_at.isoformat() if self.reminder_sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_overdue': self.is_overdue,
            'priority_color': self.priority_color,
        }

    def __repr__(self):
        return f'<Task {self.title}>'


register_encrypt_on_flush(Task, ['_description'])


class Appointment(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    _notes = db.Column('notes', db.Text, nullable=True)
    confirmation_sent = db.Column(db.Boolean, default=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    attendance_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lawyer = db.relationship('User', backref='lawyer_appointments')

    @property
    def notes(self):
        return self._enc_get(self._notes)

    @notes.setter
    def notes(self, value):
        self._notes = self._enc_set(value)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'lawyer_id': self.lawyer_id,
            'lawyer_name': self.lawyer.full_name if self.lawyer else None,
            'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
            'appointment_time': self.appointment_time.strftime('%H:%M') if self.appointment_time else None,
            'notes': self.notes,
            'confirmation_sent': self.confirmation_sent,
            'reminder_sent': self.reminder_sent,
            'attendance_status': self.attendance_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Appointment {self.appointment_date} - Client {self.client_id}>'


register_encrypt_on_flush(Appointment, ['_notes'])
