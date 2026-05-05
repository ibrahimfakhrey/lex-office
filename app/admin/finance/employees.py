"""Employees — source of truth for the internal payroll system.

Each employee is recorded once here. Other screens (payroll payments,
payroll summary, dashboard) read from this table via dropdown.
"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, admin_permission_required
from app.admin.finance.audit import log_finance_action
from app.models.op_finance import OpEmployee


EMPLOYMENT_TYPES = [
    ('full_time', 'Full-time'),
    ('freelance', 'Freelance'),
    ('part_time', 'Part-time'),
]
STATUS_OPTIONS = [
    ('active', 'نشط'),
    ('paused', 'متوقف'),
    ('terminated', 'منتهي'),
]


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


@admin_bp.route('/finance/employees')
@admin_permission_required('finance_employees', 'view')
def finance_employees_list():
    employees = OpEmployee.query.order_by(OpEmployee.created_at.desc()).all()
    return render_template(
        'admin/finance/employees/list.html',
        employees=employees,
        employment_types=EMPLOYMENT_TYPES,
        status_options=STATUS_OPTIONS,
    )


@admin_bp.route('/finance/employees/new', methods=['POST'])
@admin_permission_required('finance_employees', 'add')
def finance_employees_create():
    try:
        emp = OpEmployee(
            full_name=request.form['full_name'].strip(),
            employment_type=request.form['employment_type'],
            monthly_salary=request.form['monthly_salary'],
            joined_at=_parse_date(request.form['joined_at']),
            contact_phone=(request.form.get('contact_phone') or '').strip() or None,
            status=request.form.get('status', 'active'),
            notes=(request.form.get('notes') or '').strip() or None,
        )
        db.session.add(emp)
        db.session.flush()
        log_finance_action(
            action_type='CREATE',
            entity_type='OpEmployee',
            entity_id=emp.id,
            new_value={'full_name': emp.full_name, 'monthly_salary': float(emp.monthly_salary)},
            description=f'إضافة موظف: {emp.full_name}',
        )
        db.session.commit()
        flash(f'تم إضافة الموظف "{emp.full_name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر إضافة الموظف: {e}', 'danger')
    return redirect(url_for('admin.finance_employees_list'))


@admin_bp.route('/finance/employees/<int:emp_id>/edit', methods=['POST'])
@admin_permission_required('finance_employees', 'edit')
def finance_employees_edit(emp_id):
    emp = OpEmployee.query.get_or_404(emp_id)
    try:
        old = {
            'full_name': emp.full_name,
            'monthly_salary': float(emp.monthly_salary),
            'status': emp.status,
        }
        emp.full_name = request.form['full_name'].strip()
        emp.employment_type = request.form['employment_type']
        emp.monthly_salary = request.form['monthly_salary']
        emp.joined_at = _parse_date(request.form['joined_at'])
        emp.contact_phone = (request.form.get('contact_phone') or '').strip() or None
        emp.status = request.form.get('status', 'active')
        emp.notes = (request.form.get('notes') or '').strip() or None
        log_finance_action(
            action_type='UPDATE',
            entity_type='OpEmployee',
            entity_id=emp.id,
            old_value=old,
            new_value={'full_name': emp.full_name, 'monthly_salary': float(emp.monthly_salary), 'status': emp.status},
            description=f'تعديل بيانات: {emp.full_name}',
        )
        db.session.commit()
        flash('تم حفظ التعديلات', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر حفظ التعديلات: {e}', 'danger')
    return redirect(url_for('admin.finance_employees_list'))


@admin_bp.route('/finance/employees/<int:emp_id>/delete', methods=['POST'])
@admin_permission_required('finance_employees', 'delete')
def finance_employees_delete(emp_id):
    emp = OpEmployee.query.get_or_404(emp_id)
    name = emp.full_name
    try:
        log_finance_action(
            action_type='DELETE',
            entity_type='OpEmployee',
            entity_id=emp.id,
            old_value={'full_name': name},
            description=f'حذف موظف: {name}',
        )
        db.session.delete(emp)
        db.session.commit()
        flash(f'تم حذف الموظف "{name}" وكل دفعاته', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_employees_list'))


@admin_bp.route('/finance/employees/json')
@admin_permission_required('finance_employees', 'view')
def finance_employees_json():
    """Lightweight dropdown source for payroll payment forms."""
    employees = OpEmployee.query.filter(OpEmployee.status != 'terminated').order_by(OpEmployee.full_name).all()
    return jsonify([
        {'id': e.id, 'name': e.full_name, 'salary': float(e.monthly_salary)}
        for e in employees
    ])
