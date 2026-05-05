"""Admin RBAC — roles management page.

Layout matches the user's mockup:
  - left pane: list of roles (system role pinned at top, custom roles below + "new role" button)
  - right pane: tabs for Permissions (toggle matrix) and Admins (assign/remove)
"""
from flask import render_template, request, redirect, url_for, flash, g, abort
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action, admin_permission_required
from app.admin.permissions import (
    PERMISSION_CATALOGUE, ACTION_LABELS, is_known_permission,
)
from app.models.admin_rbac import AdminRole, AdminRolePermission
from app.models.admin import AdminUser


def _get_or_404(role_id):
    role = AdminRole.query.get_or_404(role_id)
    return role


def _list_roles_with_active(active_id=None):
    roles = AdminRole.query.order_by(
        AdminRole.is_system.desc(), AdminRole.created_at
    ).all()
    if active_id is None and roles:
        active_id = roles[0].id
    active = next((r for r in roles if r.id == active_id), None)
    return roles, active


@admin_bp.route('/settings/roles')
@admin_permission_required('admin_roles', 'view')
def admin_roles_list():
    role_id = request.args.get('id', type=int)
    roles, active = _list_roles_with_active(role_id)
    permission_set = active.permission_set() if active else set()
    # Admins not yet assigned to the active role (for the "add admin" modal)
    if active:
        unassigned_admins = AdminUser.query.filter(
            AdminUser.is_active.is_(True),
            db.or_(AdminUser.role_id.is_(None), AdminUser.role_id != active.id),
        ).order_by(AdminUser.full_name).all()
    else:
        unassigned_admins = []
    return render_template(
        'admin/settings/roles.html',
        roles=roles,
        active=active,
        permission_set=permission_set,
        unassigned_admins=unassigned_admins,
        catalogue=PERMISSION_CATALOGUE,
        action_labels=ACTION_LABELS,
    )


@admin_bp.route('/settings/roles/new', methods=['POST'])
@admin_permission_required('admin_roles', 'add')
def admin_roles_create():
    name = (request.form.get('name') or '').strip().lower().replace(' ', '_')
    name_ar = (request.form.get('name_ar') or '').strip()
    description = (request.form.get('description') or '').strip() or None

    if not name or not name_ar:
        flash('اسم الدور (إنجليزي + عربي) مطلوب', 'danger')
        return redirect(url_for('admin.admin_roles_list'))

    if AdminRole.query.filter_by(name=name).first():
        flash(f'اسم الدور "{name}" موجود مسبقاً', 'danger')
        return redirect(url_for('admin.admin_roles_list'))

    role = AdminRole(name=name, name_ar=name_ar, description=description, is_system=False)
    db.session.add(role)
    db.session.flush()
    log_action(
        'ADMIN_ROLE_CREATED', entity_type='AdminRole', entity_id=role.id,
        new_value={'name': name, 'name_ar': name_ar},
        description=f'إنشاء دور: {name_ar}',
    )
    db.session.commit()
    flash(f'تم إنشاء الدور "{name_ar}". اضبط صلاحياته الآن.', 'success')
    return redirect(url_for('admin.admin_roles_list', id=role.id))


@admin_bp.route('/settings/roles/<int:role_id>/rename', methods=['POST'])
@admin_permission_required('admin_roles', 'edit')
def admin_roles_rename(role_id):
    role = _get_or_404(role_id)
    if role.is_system:
        flash('لا يمكن إعادة تسمية دور النظام', 'danger')
        return redirect(url_for('admin.admin_roles_list', id=role.id))

    new_name_ar = (request.form.get('name_ar') or '').strip()
    new_description = (request.form.get('description') or '').strip() or None
    if not new_name_ar:
        flash('الاسم العربي مطلوب', 'danger')
        return redirect(url_for('admin.admin_roles_list', id=role.id))

    old = {'name_ar': role.name_ar, 'description': role.description}
    role.name_ar = new_name_ar
    role.description = new_description
    log_action(
        'ADMIN_ROLE_RENAMED', entity_type='AdminRole', entity_id=role.id,
        old_value=old, new_value={'name_ar': new_name_ar, 'description': new_description},
        description=f'تعديل دور: {new_name_ar}',
    )
    db.session.commit()
    flash('تم حفظ التعديلات', 'success')
    return redirect(url_for('admin.admin_roles_list', id=role.id))


@admin_bp.route('/settings/roles/<int:role_id>/delete', methods=['POST'])
@admin_permission_required('admin_roles', 'delete')
def admin_roles_delete(role_id):
    role = _get_or_404(role_id)
    if role.is_system:
        flash('لا يمكن حذف دور النظام', 'danger')
        return redirect(url_for('admin.admin_roles_list', id=role.id))
    if role.admins:
        flash(
            f'لا يمكن حذف الدور — مرتبط بـ {len(role.admins)} أدمن. '
            'انقلهم لدور آخر أولاً.',
            'danger',
        )
        return redirect(url_for('admin.admin_roles_list', id=role.id))

    name_ar = role.name_ar
    log_action(
        'ADMIN_ROLE_DELETED', entity_type='AdminRole', entity_id=role.id,
        old_value={'name': role.name, 'name_ar': name_ar},
        description=f'حذف دور: {name_ar}',
    )
    db.session.delete(role)
    db.session.commit()
    flash(f'تم حذف الدور "{name_ar}"', 'warning')
    return redirect(url_for('admin.admin_roles_list'))


@admin_bp.route('/settings/roles/<int:role_id>/permissions', methods=['POST'])
@admin_permission_required('admin_roles', 'edit')
def admin_roles_save_permissions(role_id):
    role = _get_or_404(role_id)
    if role.is_system:
        flash('صلاحيات دور النظام لا يمكن تعديلها', 'danger')
        return redirect(url_for('admin.admin_roles_list', id=role.id))

    # Form sends one checkbox per (module, action), name="perm__<module>__<action>"
    granted = set()
    for key in request.form.keys():
        if not key.startswith('perm__'):
            continue
        try:
            _, module, action = key.split('__', 2)
        except ValueError:
            continue
        if not is_known_permission(module, action):
            continue   # silently drop unknown pairs
        granted.add((module, action))

    old_set = role.permission_set()
    # Wipe + re-insert (simpler than diff; small table)
    AdminRolePermission.query.filter_by(role_id=role.id).delete()
    db.session.flush()
    for module, action in granted:
        db.session.add(AdminRolePermission(role_id=role.id, module=module, action=action))

    log_action(
        'ADMIN_ROLE_PERMISSIONS_UPDATED', entity_type='AdminRole', entity_id=role.id,
        old_value=sorted(list(old_set)),
        new_value=sorted(list(granted)),
        description=f'تحديث صلاحيات دور: {role.name_ar}',
    )
    db.session.commit()
    flash(f'تم حفظ صلاحيات "{role.name_ar}" ({len(granted)} صلاحية)', 'success')
    return redirect(url_for('admin.admin_roles_list', id=role.id))


# ─── Assign / unassign admin to role ───
@admin_bp.route('/settings/roles/<int:role_id>/admins/add', methods=['POST'])
@admin_permission_required('admin_roles', 'edit')
def admin_roles_assign_admin(role_id):
    role = _get_or_404(role_id)
    admin_id = request.form.get('admin_id', type=int)
    admin = AdminUser.query.get_or_404(admin_id)

    old_role = admin.admin_role.name_ar if admin.admin_role else '—'
    admin.role_id = role.id
    log_action(
        'ADMIN_ROLE_ASSIGNED', entity_type='AdminUser', entity_id=admin.id,
        old_value={'role': old_role}, new_value={'role': role.name_ar},
        description=f'ربط {admin.full_name} بدور: {role.name_ar}',
    )
    db.session.commit()
    flash(f'تم ربط {admin.full_name} بدور "{role.name_ar}"', 'success')
    return redirect(url_for('admin.admin_roles_list', id=role.id))


@admin_bp.route('/settings/roles/<int:role_id>/admins/<int:admin_id>/remove', methods=['POST'])
@admin_permission_required('admin_roles', 'edit')
def admin_roles_remove_admin(role_id, admin_id):
    role = _get_or_404(role_id)
    admin = AdminUser.query.get_or_404(admin_id)
    if admin.role_id != role.id:
        abort(404)

    # Safety: never leave Super Admin role with zero active admins
    if role.is_system:
        active_supers = AdminUser.query.filter(
            AdminUser.role_id == role.id,
            AdminUser.is_active.is_(True),
        ).count()
        if active_supers <= 1:
            flash('لا يمكن إزالة آخر Super Admin نشط', 'danger')
            return redirect(url_for('admin.admin_roles_list', id=role.id))

    admin.role_id = None
    log_action(
        'ADMIN_ROLE_UNASSIGNED', entity_type='AdminUser', entity_id=admin.id,
        old_value={'role': role.name_ar}, new_value={'role': None},
        description=f'إزالة {admin.full_name} من دور: {role.name_ar}',
    )
    db.session.commit()
    flash(f'تم إزالة {admin.full_name} من الدور', 'warning')
    return redirect(url_for('admin.admin_roles_list', id=role.id))
