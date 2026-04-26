"""API routes for Document management."""
import os
from datetime import datetime, timedelta
import secrets
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_datetime)
from app.extensions import db
from flask import g, request, send_file, current_app, url_for
from werkzeug.utils import secure_filename
from app.models.document import Document
from app.models.case import Case
from app.models.client import Client

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===================== DOCUMENTS LIST =====================

@api_bp.route('/documents', methods=['GET'])
@api_permission_required('documents', 'view')
def api_list_documents():
    """List all documents with filters."""
    case_id = request.args.get('case_id', '', type=str)
    client_id = request.args.get('client_id', '', type=str)
    doc_type = request.args.get('doc_type', '')
    search = request.args.get('q', '')

    query = Document.query.filter_by(tenant_id=g.tenant_id)
    if case_id:
        query = query.filter_by(case_id=int(case_id))
    if client_id:
        query = query.filter_by(client_id=int(client_id))
    if doc_type:
        query = query.filter_by(doc_type=doc_type)
    if search:
        query = query.filter(Document.name.ilike(f'%{search}%'))

    query = query.order_by(Document.created_at.desc())
    return paginated_response(query)


# ===================== UPLOAD DOCUMENT =====================

@api_bp.route('/documents', methods=['POST'])
@api_permission_required('documents', 'upload')
def api_upload_document():
    """Upload a new document (multipart/form-data)."""
    errors = {}

    file = request.files.get('file')
    name = request.form.get('name', '').strip()
    doc_type = request.form.get('doc_type', '')

    if not file or not file.filename:
        errors['file'] = 'يجب اختيار ملف'
    elif not allowed_file(file.filename):
        errors['file'] = f'نوع الملف غير مسموح. الأنواع المسموحة: {", ".join(ALLOWED_EXTENSIONS)}'

    if not doc_type:
        errors['doc_type'] = 'نوع المستند مطلوب'

    if errors:
        return validation_error(errors)

    filename = secure_filename(file.filename)
    if not name:
        name = filename

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'documents', str(g.tenant_id))
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    saved_filename = f'{timestamp}_{filename}'
    abs_path = os.path.join(upload_dir, saved_filename)
    file.save(abs_path)

    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    file_size = os.path.getsize(abs_path)
    file_path = f'uploads/documents/{g.tenant_id}/{saved_filename}'

    doc_date = None
    if request.form.get('doc_date'):
        doc_date = parse_date(request.form['doc_date'])

    document = Document(
        tenant_id=g.tenant_id,
        client_id=request.form.get('client_id', type=int) or None,
        case_id=request.form.get('case_id', type=int) or None,
        doc_type=doc_type,
        name=name,
        file_path=file_path,
        file_type=file_ext,
        file_size=file_size,
        doc_date=doc_date,
        notes=request.form.get('notes', '').strip() or None,
        uploaded_by=g.current_user.id,
    )
    db.session.add(document)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='document_uploaded',
        title=f'تم رفع مستند جديد: {name}',
        body=f'النوع: {doc_type}',
        related_type='document',
        related_id=document.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=document.to_dict(), message='تم رفع المستند بنجاح', status_code=201)


# ===================== SHOW DOCUMENT =====================

@api_bp.route('/documents/<int:id>', methods=['GET'])
@api_permission_required('documents', 'view')
def api_show_document(id):
    """Show document details."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return success_response(data=document.to_dict())


# ===================== DOWNLOAD DOCUMENT =====================

@api_bp.route('/documents/<int:id>/download', methods=['GET'])
@api_permission_required('documents', 'view')
def api_download_document(id):
    """Download a document file."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    # Support both relative (new) and absolute (legacy) paths
    if os.path.isabs(document.file_path):
        abs_path = document.file_path
    else:
        abs_path = os.path.join(current_app.root_path, 'static', document.file_path)

    if not os.path.exists(abs_path):
        return error_response('الملف غير موجود', error_code='file_not_found', status_code=404)

    return send_file(abs_path, as_attachment=True,
                     download_name=f'{document.name}.{document.file_type}')


# ===================== SHARE DOCUMENT =====================

@api_bp.route('/documents/<int:id>/share', methods=['POST'])
@api_permission_required('documents', 'share')
def api_share_document(id):
    """Generate a share link for a document."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    data = get_json_or_form()
    days = int(data.get('days', 7))

    document.share_token = secrets.token_urlsafe(32)
    document.share_expires_at = datetime.utcnow() + timedelta(days=days)
    db.session.commit()

    share_url = url_for('api.api_shared_document', token=document.share_token, _external=True)

    return success_response(data={
        'share_token': document.share_token,
        'share_url': share_url,
        'expires_at': document.share_expires_at.isoformat(),
    }, message=f'تم إنشاء رابط المشاركة (صالح لمدة {days} أيام)')


# ===================== DELETE DOCUMENT =====================

@api_bp.route('/documents/<int:id>', methods=['DELETE'])
@api_permission_required('documents', 'delete')
def api_delete_document(id):
    """Delete a document (file + DB record)."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    # Try to delete the file from disk
    if document.file_path:
        if os.path.isabs(document.file_path):
            abs_path = document.file_path
        else:
            abs_path = os.path.join(current_app.root_path, 'static', document.file_path)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass

    db.session.delete(document)
    db.session.commit()
    return success_response(message='تم حذف المستند')


# ===================== PUBLIC SHARED DOCUMENT =====================

@api_bp.route('/documents/shared/<token>', methods=['GET'])
def api_shared_document(token):
    """Public shared document download (no authentication required)."""
    document = Document.query.filter_by(share_token=token).first_or_404()

    if not document.is_share_active:
        return error_response('رابط المشاركة منتهي الصلاحية', error_code='share_expired', status_code=410)

    if os.path.isabs(document.file_path):
        abs_path = document.file_path
    else:
        abs_path = os.path.join(current_app.root_path, 'static', document.file_path)

    if not os.path.exists(abs_path):
        return error_response('الملف غير موجود', error_code='file_not_found', status_code=404)

    return send_file(abs_path, as_attachment=False, download_name=document.name)
