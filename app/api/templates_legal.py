"""API routes for legal document templates."""
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request

from app.models.document import LegalTemplate
from app.models.case import Case
from app.models.client import Client
from app.models.tenant import Tenant


@api_bp.route('/templates', methods=['GET'])
@api_permission_required('templates', 'view')
def api_templates_list():
    """List legal templates with optional type filter."""
    template_type = request.args.get('type', '').strip()

    query = LegalTemplate.query.filter(
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).filter_by(is_active=True)

    if template_type:
        query = query.filter_by(template_type=template_type)

    query = query.order_by(LegalTemplate.name)
    return paginated_response(query)


@api_bp.route('/templates', methods=['POST'])
@api_permission_required('templates', 'create')
def api_templates_create():
    """Create a new legal template."""
    data = get_json_or_form()
    errors = {}

    name = (data.get('name') or '').strip()
    if not name:
        errors['name'] = 'اسم القالب مطلوب'

    template_type = (data.get('template_type') or '').strip()
    if not template_type:
        errors['template_type'] = 'نوع القالب مطلوب'

    template_content = (data.get('template_content') or '').strip()
    if not template_content:
        errors['template_content'] = 'محتوى القالب مطلوب'

    if errors:
        return validation_error(errors)

    name_ar = (data.get('name_ar') or '').strip() or name

    template = LegalTemplate(
        tenant_id=g.tenant_id,
        name=name,
        name_ar=name_ar,
        template_type=template_type,
        output_format=data.get('output_format', 'html'),
        template_content=template_content,
    )
    db.session.add(template)
    db.session.commit()

    return success_response(data=template.to_dict(), message='تم إنشاء القالب بنجاح', status_code=201)


@api_bp.route('/templates/<int:id>', methods=['GET'])
@api_permission_required('templates', 'view')
def api_templates_show(id):
    """Show a single legal template."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first()
    if not template:
        return error_response('القالب غير موجود', error_code='not_found', status_code=404)

    return success_response(data=template.to_dict())


@api_bp.route('/templates/<int:id>', methods=['PUT'])
@api_permission_required('templates', 'edit')
def api_templates_update(id):
    """Update a legal template (tenant-owned only)."""
    template = LegalTemplate.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not template:
        return error_response('القالب غير موجود أو لا يمكن تعديله', error_code='not_found', status_code=404)

    data = get_json_or_form()

    if 'name' in data:
        template.name = (data['name'] or '').strip() or template.name
    if 'name_ar' in data:
        template.name_ar = (data['name_ar'] or '').strip() or template.name_ar
    if 'template_type' in data:
        template.template_type = data['template_type'] or template.template_type
    if 'output_format' in data:
        template.output_format = data['output_format'] or template.output_format
    if 'template_content' in data:
        template.template_content = (data['template_content'] or '').strip() or template.template_content

    db.session.commit()
    return success_response(data=template.to_dict(), message='تم تحديث القالب بنجاح')


@api_bp.route('/templates/<int:id>', methods=['DELETE'])
@api_permission_required('templates', 'delete')
def api_templates_delete(id):
    """Delete a legal template (tenant-owned only)."""
    template = LegalTemplate.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not template:
        return error_response('القالب غير موجود', error_code='not_found', status_code=404)

    db.session.delete(template)
    db.session.commit()
    return success_response(message='تم حذف القالب')


@api_bp.route('/templates/<int:id>/use', methods=['POST'])
@api_permission_required('templates', 'view')
def api_templates_use(id):
    """Generate content from a template with variable substitution."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first()
    if not template:
        return error_response('القالب غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()
    case_id = data.get('case_id')
    client_id = data.get('client_id')

    # Coerce to int if string
    try:
        case_id = int(case_id) if case_id else None
    except (TypeError, ValueError):
        case_id = None
    try:
        client_id = int(client_id) if client_id else None
    except (TypeError, ValueError):
        client_id = None

    case = Case.query.get(case_id) if case_id else None
    client = Client.query.get(client_id) if client_id else None
    tenant = Tenant.query.get(g.tenant_id)

    from app.blueprints.templates_legal.routes import substitute_variables
    generated_content = substitute_variables(template.template_content, case=case,
                                             client=client, tenant=tenant)

    return success_response(data={
        'template_id': template.id,
        'template_name': template.name,
        'generated_content': generated_content,
    })


@api_bp.route('/templates/<int:id>/preview', methods=['GET'])
@api_permission_required('templates', 'view')
def api_templates_preview(id):
    """Preview raw template content."""
    template = LegalTemplate.query.filter(
        LegalTemplate.id == id,
        (LegalTemplate.tenant_id == g.tenant_id) | (LegalTemplate.tenant_id.is_(None))
    ).first()
    if not template:
        return error_response('القالب غير موجود', error_code='not_found', status_code=404)

    return success_response(data={
        'template_id': template.id,
        'template_name': template.name,
        'template_content': template.template_content,
    })
