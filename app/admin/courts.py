"""Courts management — list / create / edit / delete (per market)."""
from flask import render_template, request, redirect, url_for, flash, abort, g
from sqlalchemy import or_

from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import admin_permission_required, log_action
from app.models.case import Court
from app.utils.constants import CourtType
from app.utils.market_config import SUPPORTED_MARKETS, normalize_market


# Reuse the 'settings' RBAC module — courts are a system registry. Splitting
# into its own module would require seeding new admin_permissions rows.
_PERM = 'settings'


def _court_or_404(court_id):
    c = Court.query.get(court_id)
    if not c:
        abort(404)
    return c


@admin_bp.route('/courts')
@admin_permission_required(_PERM, 'view')
def courts_list():
    """List courts with market filter + search."""
    market = (request.args.get('market') or '').strip().lower()
    search = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)

    query = Court.query
    if market in SUPPORTED_MARKETS:
        query = query.filter_by(market=market)
    if search:
        query = query.filter(or_(
            Court.name.ilike(f'%{search}%'),
            Court.name_en.ilike(f'%{search}%'),
            Court.governorate.ilike(f'%{search}%'),
        ))

    pagination = query.order_by(
        Court.market.asc(), Court.court_type.asc(), Court.name.asc()
    ).paginate(page=page, per_page=50, error_out=False)

    return render_template(
        'admin/courts/list.html',
        pagination=pagination,
        filter_market=market,
        search=search,
    )


@admin_bp.route('/courts/create', methods=['GET', 'POST'])
@admin_permission_required(_PERM, 'edit')
def courts_create():
    """Add a new court."""
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash('اسم المحكمة مطلوب', 'danger')
            return render_template('admin/courts/form.html', court=None,
                                   court_types=list(CourtType),
                                   markets=SUPPORTED_MARKETS, form=request.form)
        court = Court(
            name=name,
            name_en=(request.form.get('name_en') or '').strip() or None,
            court_type=request.form.get('court_type') or CourtType.PRIMARY.value,
            governorate=(request.form.get('governorate') or '').strip() or None,
            market=normalize_market(request.form.get('market')),
            is_active=request.form.get('is_active') == 'on',
        )
        db.session.add(court)
        db.session.flush()
        log_action(
            'COURT_CREATED', entity_type='Court', entity_id=court.id,
            new_value=court.to_dict(),
            description=f'Created court {court.name} ({court.market})',
        )
        db.session.commit()
        flash(f'تم إنشاء المحكمة: {court.name}', 'success')
        return redirect(url_for('admin.courts_list', market=court.market))

    return render_template('admin/courts/form.html', court=None,
                           court_types=list(CourtType),
                           markets=SUPPORTED_MARKETS, form={})


@admin_bp.route('/courts/<int:court_id>/edit', methods=['GET', 'POST'])
@admin_permission_required(_PERM, 'edit')
def courts_edit(court_id):
    """Edit a court."""
    court = _court_or_404(court_id)
    if request.method == 'POST':
        old = court.to_dict()
        court.name = (request.form.get('name') or court.name).strip()
        court.name_en = (request.form.get('name_en') or '').strip() or None
        court.court_type = request.form.get('court_type') or court.court_type
        court.governorate = (request.form.get('governorate') or '').strip() or None
        court.market = normalize_market(request.form.get('market') or court.market)
        court.is_active = request.form.get('is_active') == 'on'

        log_action(
            'COURT_UPDATED', entity_type='Court', entity_id=court.id,
            old_value=old, new_value=court.to_dict(),
            description=f'Updated court {court.name}',
        )
        db.session.commit()
        flash(f'تم تحديث: {court.name}', 'success')
        return redirect(url_for('admin.courts_list', market=court.market))

    form = {
        'name': court.name, 'name_en': court.name_en or '',
        'court_type': court.court_type,
        'governorate': court.governorate or '',
        'market': court.market, 'is_active': court.is_active,
    }
    return render_template('admin/courts/form.html', court=court,
                           court_types=list(CourtType),
                           markets=SUPPORTED_MARKETS, form=form)


@admin_bp.route('/courts/<int:court_id>/delete', methods=['POST'])
@admin_permission_required(_PERM, 'edit')
def courts_delete(court_id):
    """Soft-delete (deactivate) a court — never hard-delete to avoid breaking
    historical references from cases/sessions/judgments.
    """
    court = _court_or_404(court_id)
    if not court.is_active:
        # Already inactive — caller probably wants reactivate
        court.is_active = True
        action = 'COURT_REACTIVATED'
        msg = f'تم تفعيل: {court.name}'
        flash_kind = 'success'
    else:
        court.is_active = False
        action = 'COURT_DEACTIVATED'
        msg = f'تم تعطيل: {court.name}'
        flash_kind = 'warning'

    log_action(action, entity_type='Court', entity_id=court.id,
               new_value={'is_active': court.is_active},
               description=msg)
    db.session.commit()
    flash(msg, flash_kind)
    return redirect(url_for('admin.courts_list', market=court.market))
