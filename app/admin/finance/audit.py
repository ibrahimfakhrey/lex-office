"""Audit log helper for the internal finance module.

Writes to `op_finance_audit_logs` (separate from the main `admin_audit_logs`).
Caller is responsible for committing the session.
"""
from flask import g, request
from app.extensions import db
from app.models.op_finance import OpFinanceAuditLog


def log_finance_action(action_type, entity_type, entity_id=None,
                       old_value=None, new_value=None, description=None):
    admin = getattr(g, 'current_admin', None)
    log = OpFinanceAuditLog(
        admin_id=admin.id if admin else None,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        description=description,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(log)
    return log
