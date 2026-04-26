"""API Onboarding routes: Office setup, plan selection, team invitations."""
import json
import os
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import success_response, error_response, validation_error, paginated_response, get_json_or_form, parse_date
from app.extensions import db, limiter
from flask import g, request, current_app
from werkzeug.utils import secure_filename
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.models.user import User, Role, Invitation
from app.utils.helpers import generate_token
from app.services.email_service import send_invitation_email, send_subscription_receipt


# ---------- GET /onboarding/office ----------
@api_bp.route('/onboarding/office', methods=['GET'])
@api_login_required
def api_get_office():
    """Return tenant data for the office setup form."""
    tenant = Tenant.query.get(g.tenant_id)
    if not tenant:
        return error_response('المكتب غير موجود', error_code='not_found', status_code=404)

    return success_response(data=tenant.to_dict())


# ---------- PUT /onboarding/office ----------
@api_bp.route('/onboarding/office', methods=['PUT'])
@api_login_required
def api_update_office():
    """Update office details (accepts JSON or multipart for logo upload)."""
    tenant = Tenant.query.get(g.tenant_id)
    if not tenant:
        return error_response('المكتب غير موجود', error_code='not_found', status_code=404)

    # Accept both JSON and form data (multipart for logo)
    if request.content_type and 'multipart' in request.content_type:
        data = request.form.to_dict()
    else:
        data = get_json_or_form()

    # Update fields
    if 'office_name' in data:
        tenant.name = data['office_name'].strip()
    if 'address' in data:
        tenant.address = data['address'].strip()
    if 'bar_registration_no' in data:
        tenant.bar_registration_no = data['bar_registration_no'].strip()
    if 'primary_court' in data:
        tenant.primary_court = data['primary_court'].strip()
    if 'phone' in data:
        tenant.phone = data['phone'].strip()
    if 'fax' in data:
        tenant.fax = data['fax'].strip()
    if 'email' in data:
        tenant.email = data['email'].strip()

    # Handle courts list
    courts = data.get('courts')
    if courts is not None:
        if isinstance(courts, list):
            tenant.courts = json.dumps(courts)
        elif isinstance(courts, str):
            # Could be a JSON string
            try:
                parsed = json.loads(courts)
                tenant.courts = json.dumps(parsed) if isinstance(parsed, list) else json.dumps([courts])
            except (json.JSONDecodeError, ValueError):
                tenant.courts = json.dumps([courts])
    # Also check form getlist for multipart
    if request.content_type and 'multipart' in request.content_type:
        courts_list = request.form.getlist('courts')
        if courts_list:
            tenant.courts = json.dumps(courts_list)

    # Handle logo file upload
    logo = request.files.get('logo')
    if logo and logo.filename:
        filename = secure_filename(logo.filename)
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
        os.makedirs(upload_dir, exist_ok=True)
        logo_filename = f'tenant_{g.tenant_id}_{filename}'
        logo.save(os.path.join(upload_dir, logo_filename))
        tenant.logo_path = f'uploads/logos/{logo_filename}'

    # Validate
    if not tenant.name:
        return validation_error({'office_name': 'اسم المكتب مطلوب'})

    db.session.commit()

    return success_response(
        data=tenant.to_dict(),
        message='تم حفظ بيانات المكتب بنجاح',
    )


# ---------- GET /onboarding/plans ----------
@api_bp.route('/onboarding/plans', methods=['GET'])
@api_login_required
def api_get_plans():
    """Return all active subscription plans."""
    plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    return success_response(data=[plan.to_dict() for plan in plans])


# ---------- POST /onboarding/choose-plan ----------
@api_bp.route('/onboarding/choose-plan', methods=['POST'])
@api_login_required
def api_choose_plan():
    """Select a subscription plan for the tenant."""
    data = get_json_or_form()
    plan_id = data.get('plan_id')
    billing_cycle = data.get('billing_cycle', 'monthly')

    if not plan_id:
        return error_response('معرّف الخطة مطلوب', error_code='missing_fields')

    plan = SubscriptionPlan.query.get(plan_id)
    if not plan or not plan.is_active:
        return error_response('الخطة غير موجودة', error_code='not_found', status_code=404)

    tenant = Tenant.query.get(g.tenant_id)
    tenant.subscription_plan_id = plan.id
    tenant.subscription_status = 'trial'
    tenant.trial_ends_at = datetime.utcnow() + timedelta(days=14)
    db.session.commit()

    # Send subscription receipt email
    user = g.current_user
    send_subscription_receipt(
        email=user.email,
        plan_name_ar=plan.name_ar,
        office_name=tenant.name,
        trial_ends_at=tenant.trial_ends_at.strftime('%Y-%m-%d'),
    )

    return success_response(
        message=f'تم اختيار خطة {plan.name_ar} - تجربة مجانية 14 يوم',
        data=tenant.to_dict(),
    )


# ---------- POST /onboarding/invite-team ----------
@api_bp.route('/onboarding/invite-team', methods=['POST'])
@api_login_required
def api_invite_team():
    """Send team invitations."""
    data = get_json_or_form()
    invitations_list = data.get('invitations', [])

    if not invitations_list or not isinstance(invitations_list, list):
        return error_response('قائمة الدعوات مطلوبة', error_code='missing_fields')

    tenant = Tenant.query.get(g.tenant_id)
    invited_count = 0
    skipped = []

    for inv in invitations_list:
        email = (inv.get('email') or '').strip().lower()
        role_id = inv.get('role_id')

        if not email or not role_id:
            continue

        # Check if already invited or exists
        existing_user = User.query.filter_by(email=email, tenant_id=g.tenant_id).first()
        existing_invite = Invitation.query.filter_by(email=email, tenant_id=g.tenant_id).first()
        if existing_user or existing_invite:
            skipped.append(email)
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
        role = Role.query.get(int(role_id))
        send_invitation_email(email, token, tenant.name, role.name_ar if role else '')

    if invited_count > 0:
        db.session.commit()

    return success_response(
        data={
            'invited_count': invited_count,
            'skipped': skipped,
        },
        message=f'تم إرسال {invited_count} دعوة بنجاح',
    )
