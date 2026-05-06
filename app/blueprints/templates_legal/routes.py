"""Legal document templates routes."""
import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.admin.feature_utils import tenant_feature_limit
from app.models.tenant import Tenant
from app.models.document import LegalTemplate, Document
from app.models.case import Case
from app.models.client import Client


def _templates_quota(tenant_id):
    """Return (used, limit) for `tenant_id`. limit==None means unlimited.

    Only counts templates owned by the tenant; global templates (tenant_id
    IS NULL) are shared and don't consume the tenant's quota.
    """
    if not tenant_id:
        return 0, None
    used = LegalTemplate.query.filter_by(tenant_id=tenant_id, is_active=True).count()
    tenant = Tenant.query.get(tenant_id)
    raw = tenant_feature_limit(tenant, 'max_legal_templates', default=None)
    # Treat 0, negative, or None as "unlimited"
    limit = int(raw) if (raw is not None and int(raw) > 0) else None
    return used, limit

templates_legal_bp = Blueprint('templates_legal', __name__, template_folder='../../templates/templates_legal')

TEMPLATE_TYPES = [
    ('contract', 'عقد'), ('power_of_attorney', 'توكيل'), ('court_filing', 'صحيفة دعوى'),
    ('memo', 'مذكرة'), ('letter', 'خطاب'), ('agreement', 'اتفاقية'), ('other', 'أخرى'),
]
OUTPUT_FORMATS = [('html', 'HTML'), ('docx', 'Word')]

# Available variables for auto-fill
AVAILABLE_VARIABLES = {
    'client_name': 'اسم الموكل',
    'client_national_id': 'الرقم القومي',
    'client_phone': 'هاتف الموكل',
    'client_address': 'عنوان الموكل',
    'case_number': 'رقم القضية',
    'case_subject': 'موضوع القضية',
    'case_type': 'نوع القضية',
    'court_name': 'اسم المحكمة',
    'lawyer_name': 'اسم المحامي',
    'opponent_name': 'اسم الخصم',
    'today_date': 'تاريخ اليوم',
    'today_hijri': 'التاريخ الهجري',
    'office_name': 'اسم المكتب',
}


def substitute_variables(content, case=None, client=None, tenant=None):
    """Replace {{variable}} placeholders with actual values."""
    from datetime import date
    replacements = {
        'today_date': date.today().strftime('%Y-%m-%d'),
        'office_name': tenant.name if tenant else '',
    }

    if client:
        replacements['client_name'] = client.full_name or ''
        replacements['client_national_id'] = client.national_id or ''
        replacements['client_phone'] = client.phone_primary or ''
        replacements['client_address'] = f'{client.governorate or ""} {client.city or ""} {client.street or ""}'.strip()

    if case:
        replacements['case_number'] = case.case_number or ''
        replacements['case_subject'] = case.subject or ''
        replacements['case_type'] = case.case_type or ''
        replacements['opponent_name'] = case.opponent_name or ''
        if case.court:
            replacements['court_name'] = case.court.name
        if case.responsible_lawyer:
            replacements['lawyer_name'] = case.responsible_lawyer.full_name

    # Replace {{var}} patterns
    def replace_match(match):
        var = match.group(1).strip()
        return replacements.get(var, f'{{{{{var}}}}}')

    return re.sub(r'\{\{(\w+)\}\}', replace_match, content)


@templates_legal_bp.route('/')
@permission_required('templates', 'view')
def index():
    """List all legal templates."""
    page = request.args.get('page', 1, type=int)
    template_type = request.args.get('type', '')

    query = LegalTemplate.query.filter(
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).filter_by(is_active=True)

    if template_type:
        query = query.filter_by(template_type=template_type)

    templates = query.order_by(LegalTemplate.name).paginate(page=page, per_page=20)
    used, limit = _templates_quota(g.tenant_id)
    return render_template('templates_legal/index.html', templates=templates,
                           template_type=template_type, template_types=TEMPLATE_TYPES,
                           templates_used=used, templates_limit=limit)


@templates_legal_bp.route('/create', methods=['GET', 'POST'])
@permission_required('templates', 'create')
def create():
    """Create a new legal template."""
    # Plan-based quota — block both GET (form) and POST (submission) once
    # the tenant has hit their cap, with a friendly Arabic message.
    used, limit = _templates_quota(g.tenant_id)
    if limit is not None and used >= limit:
        flash(
            f'لقد وصلت للحد الأقصى ({limit}) من القوالب المتاحة لخطتك. '
            'احذف قالباً غير مستخدم أو رقّ خطتك لإضافة المزيد.',
            'warning',
        )
        return redirect(url_for('templates_legal.index'))

    if request.method == 'POST':
        errors = []
        name = request.form.get('name', '').strip()
        name_ar = request.form.get('name_ar', '').strip()
        template_type = request.form.get('template_type', '')
        template_content = request.form.get('template_content', '').strip()

        if not name:
            errors.append('اسم القالب مطلوب')
        if not name_ar:
            name_ar = name
        if not template_type:
            errors.append('نوع القالب مطلوب')
        if not template_content:
            errors.append('محتوى القالب مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('templates_legal/create.html', form=request.form,
                                   template_types=TEMPLATE_TYPES, output_formats=OUTPUT_FORMATS,
                                   available_variables=AVAILABLE_VARIABLES)

        template = LegalTemplate(
            tenant_id=g.tenant_id,
            name=name,
            name_ar=name_ar,
            template_type=template_type,
            output_format=request.form.get('output_format', 'html'),
            template_content=template_content,
        )
        db.session.add(template)
        db.session.commit()
        flash('تم إنشاء القالب بنجاح', 'success')
        return redirect(url_for('templates_legal.show', id=template.id))

    return render_template('templates_legal/create.html', form={},
                           template_types=TEMPLATE_TYPES, output_formats=OUTPUT_FORMATS,
                           available_variables=AVAILABLE_VARIABLES)


@templates_legal_bp.route('/<int:id>')
@permission_required('templates', 'view')
def show(id):
    """Show template details."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first_or_404()
    type_map = dict(TEMPLATE_TYPES)
    return render_template('templates_legal/show.html', template=template, type_map=type_map)


@templates_legal_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('templates', 'edit')
def edit(id):
    """Edit a legal template."""
    template = LegalTemplate.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    if request.method == 'POST':
        template.name = request.form.get('name', template.name).strip()
        template.name_ar = request.form.get('name_ar', template.name_ar).strip()
        template.template_type = request.form.get('template_type', template.template_type)
        template.output_format = request.form.get('output_format', template.output_format)
        template.template_content = request.form.get('template_content', template.template_content)
        db.session.commit()
        flash('تم تحديث القالب بنجاح', 'success')
        return redirect(url_for('templates_legal.show', id=template.id))

    return render_template('templates_legal/edit.html', template=template,
                           template_types=TEMPLATE_TYPES, output_formats=OUTPUT_FORMATS,
                           available_variables=AVAILABLE_VARIABLES)


@templates_legal_bp.route('/<int:id>/use', methods=['GET', 'POST'])
@permission_required('templates', 'view')
def use_template(id):
    """Generate a document from a template with variable substitution."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first_or_404()

    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        case_id = request.form.get('case_id', type=int)
        client_id = request.form.get('client_id', type=int)

        case = Case.query.get(case_id) if case_id else None
        client = Client.query.get(client_id) if client_id else None
        from app.models.tenant import Tenant
        tenant = Tenant.query.get(g.tenant_id)

        generated_content = substitute_variables(template.template_content, case=case,
                                                  client=client, tenant=tenant)

        return render_template('templates_legal/generated.html', template=template,
                               generated_content=generated_content, case=case, client=client)

    return render_template('templates_legal/use_template.html', template=template,
                           cases=cases, clients=clients)


@templates_legal_bp.route('/<int:id>/preview')
@permission_required('templates', 'view')
def preview(id):
    """Preview a template with placeholder text."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first_or_404()
    return render_template('templates_legal/preview.html', template=template)


@templates_legal_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('templates', 'delete')
def delete(id):
    """Delete a legal template."""
    template = LegalTemplate.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(template)
    db.session.commit()
    flash('تم حذف القالب', 'warning')
    return redirect(url_for('templates_legal.index'))
