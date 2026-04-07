"""Onboarding routes: Office setup, plan selection, team invitations."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, role_required, permission_required, manager_only
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.models.user import User, Role, Invitation
from app.models.case import Court
from app.utils.helpers import generate_token
from app.services.email_service import send_invitation_email

onboarding_bp = Blueprint('onboarding', __name__, template_folder='../../templates/onboarding')


@onboarding_bp.route('/setup-office', methods=['GET', 'POST'])
@login_required
def setup_office():
    """Step 1: Configure office details after registration."""
    tenant = Tenant.query.get(g.tenant_id)

    if request.method == 'POST':
        tenant.name = request.form.get('office_name', '').strip()
        tenant.address = request.form.get('address', '').strip()
        tenant.bar_registration_no = request.form.get('bar_registration_no', '').strip()
        tenant.primary_court = request.form.get('primary_court', '').strip()
        tenant.phone = request.form.get('phone', '').strip()
        tenant.fax = request.form.get('fax', '').strip()
        tenant.email = request.form.get('email', '').strip()

        # Handle logo upload
        logo = request.files.get('logo')
        if logo and logo.filename:
            import os
            from werkzeug.utils import secure_filename
            filename = secure_filename(logo.filename)
            upload_dir = os.path.join('app', 'static', 'uploads', 'logos')
            os.makedirs(upload_dir, exist_ok=True)
            logo_path = os.path.join(upload_dir, f'tenant_{g.tenant_id}_{filename}')
            logo.save(logo_path)
            tenant.logo_path = logo_path

        # Handle courts (multi-select)
        courts = request.form.getlist('courts')
        if courts:
            import json
            tenant.courts = json.dumps(courts)

        errors = []
        if not tenant.name:
            errors.append('اسم المكتب مطلوب')

        if errors:
            for err in errors:
                flash(err, 'danger')
            courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
            return render_template('onboarding/setup_office.html', tenant=tenant, courts=courts)

        db.session.commit()
        flash('تم حفظ بيانات المكتب بنجاح', 'success')
        return redirect(url_for('onboarding.choose_plan'))

    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    return render_template('onboarding/setup_office.html', tenant=tenant, courts=courts)


@onboarding_bp.route('/choose-plan', methods=['GET', 'POST'])
@login_required
def choose_plan():
    """Step 2: Select subscription plan."""
    plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    tenant = Tenant.query.get(g.tenant_id)

    if request.method == 'POST':
        plan_id = request.form.get('plan_id', type=int)
        billing_cycle = request.form.get('billing_cycle', 'monthly')

        plan = SubscriptionPlan.query.get(plan_id)
        if not plan:
            flash('الخطة غير موجودة', 'danger')
            return render_template('onboarding/choose_plan.html', plans=plans, tenant=tenant)

        tenant.subscription_plan_id = plan.id
        tenant.subscription_status = 'trial'
        tenant.trial_ends_at = datetime.utcnow() + timedelta(days=14)
        db.session.commit()

        flash(f'تم اختيار خطة {plan.name_ar} - تجربة مجانية 14 يوم', 'success')
        return redirect(url_for('onboarding.invite_team'))

    return render_template('onboarding/choose_plan.html', plans=plans, tenant=tenant)


@onboarding_bp.route('/invite-team', methods=['GET', 'POST'])
@login_required
def invite_team():
    """Step 3: Invite team members."""
    roles = Role.query.all()

    if request.method == 'POST':
        emails = request.form.getlist('email')
        role_ids = request.form.getlist('role_id')

        invited_count = 0
        for email, role_id in zip(emails, role_ids):
            email = email.strip().lower()
            if not email:
                continue

            # Check if already invited or exists
            existing_user = User.query.filter_by(email=email, tenant_id=g.tenant_id).first()
            existing_invite = Invitation.query.filter_by(email=email, tenant_id=g.tenant_id).first()
            if existing_user or existing_invite:
                flash(f'{email} مدعو بالفعل أو مسجل', 'warning')
                continue

            token = generate_token()
            invitation = Invitation(
                tenant_id=g.tenant_id,
                email=email,
                role_id=int(role_id),
                token=token,
                invited_by=g.current_user.id,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.session.add(invitation)
            invited_count += 1

            # Send invitation email
            tenant = Tenant.query.get(g.tenant_id)
            role = Role.query.get(int(role_id))
            send_invitation_email(email, token, tenant.name, role.name_ar if role else '')

        if invited_count > 0:
            db.session.commit()
            flash(f'تم إرسال {invited_count} دعوة بنجاح', 'success')

        return redirect(url_for('dashboard.index'))

    return render_template('onboarding/invite_team.html', roles=roles)


@onboarding_bp.route('/skip-invite', methods=['POST'])
@login_required
def skip_invite():
    """Skip team invitation step."""
    flash('يمكنك دعوة فريقك لاحقاً من الإعدادات', 'info')
    return redirect(url_for('dashboard.index'))
