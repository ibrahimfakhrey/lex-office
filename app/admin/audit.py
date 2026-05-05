"""Audit log viewer + CSV export."""
from datetime import datetime, timedelta
import csv
import io

from flask import render_template, request, Response
from sqlalchemy import or_
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, admin_permission_required
from app.models.admin import AdminAuditLog, AdminUser


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None


@admin_bp.route('/audit')
@admin_permission_required('audit_log', 'view')
def audit_log():
    """Full audit log with filters."""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    search = (request.args.get('q') or '').strip()
    action_type = (request.args.get('action_type') or '').strip()
    entity_type = (request.args.get('entity_type') or '').strip()
    admin_id = request.args.get('admin_id', type=int)
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))

    query = AdminAuditLog.query

    if search:
        query = query.filter(or_(
            AdminAuditLog.action_type.ilike(f'%{search}%'),
            AdminAuditLog.description.ilike(f'%{search}%'),
        ))
    if action_type:
        query = query.filter(AdminAuditLog.action_type == action_type)
    if entity_type:
        query = query.filter(AdminAuditLog.entity_type == entity_type)
    if admin_id:
        query = query.filter(AdminAuditLog.admin_id == admin_id)
    if date_from:
        query = query.filter(AdminAuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AdminAuditLog.created_at < date_to + timedelta(days=1))

    pagination = query.order_by(AdminAuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )

    # Distinct values for filter dropdowns
    action_types = [r[0] for r in AdminAuditLog.query.with_entities(
        AdminAuditLog.action_type
    ).distinct().order_by(AdminAuditLog.action_type).all() if r[0]]
    entity_types = [r[0] for r in AdminAuditLog.query.with_entities(
        AdminAuditLog.entity_type
    ).distinct().order_by(AdminAuditLog.entity_type).all() if r[0]]
    admins = AdminUser.query.order_by(AdminUser.full_name).all()

    return render_template(
        'admin/audit/log.html',
        pagination=pagination,
        action_types=action_types,
        entity_types=entity_types,
        admins=admins,
        filters={
            'q': search, 'action_type': action_type, 'entity_type': entity_type,
            'admin_id': admin_id,
            'date_from': request.args.get('date_from', ''),
            'date_to': request.args.get('date_to', ''),
        },
    )


@admin_bp.route('/audit/export')
@admin_permission_required('audit_log', 'view')
def audit_export():
    """Export filtered audit log to CSV."""
    search = (request.args.get('q') or '').strip()
    action_type = (request.args.get('action_type') or '').strip()
    entity_type = (request.args.get('entity_type') or '').strip()

    query = AdminAuditLog.query
    if search:
        query = query.filter(or_(
            AdminAuditLog.action_type.ilike(f'%{search}%'),
            AdminAuditLog.description.ilike(f'%{search}%'),
        ))
    if action_type:
        query = query.filter(AdminAuditLog.action_type == action_type)
    if entity_type:
        query = query.filter(AdminAuditLog.entity_type == entity_type)

    rows = query.order_by(AdminAuditLog.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Timestamp', 'Admin', 'Action', 'Entity Type', 'Entity ID',
        'Description', 'IP Address', 'Old Value', 'New Value',
    ])
    for log in rows:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
            log.admin.full_name if log.admin else '',
            log.action_type,
            log.entity_type or '',
            log.entity_id or '',
            log.description or '',
            log.ip_address or '',
            str(log.old_value) if log.old_value else '',
            str(log.new_value) if log.new_value else '',
        ])
    return Response(
        buf.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=audit_log_{datetime.utcnow().strftime("%Y%m%d")}.csv'},
    )
