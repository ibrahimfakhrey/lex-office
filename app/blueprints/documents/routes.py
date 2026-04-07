"""Document management routes."""
import os
from datetime import datetime, timedelta
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, send_file, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.document import Document
from app.models.case import Case
from app.models.client import Client

documents_bp = Blueprint('documents', __name__, template_folder='../../templates/documents')

DOC_TYPES = [
    ('contract', 'عقد'), ('power_of_attorney', 'توكيل'), ('court_filing', 'صحيفة دعوى'),
    ('court_decision', 'قرار محكمة'), ('evidence', 'مستند إثبات'), ('correspondence', 'مراسلة'),
    ('id_document', 'مستند هوية'), ('financial', 'مستند مالي'), ('other', 'أخرى'),
]

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/')
@permission_required('documents', 'view')
def index():
    """List all documents with filters."""
    page = request.args.get('page', 1, type=int)
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

    documents = query.order_by(Document.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('documents/index.html', documents=documents, case_id=case_id,
                           client_id=client_id, doc_type=doc_type, search=search,
                           doc_types=DOC_TYPES)


@documents_bp.route('/upload', methods=['GET', 'POST'])
@permission_required('documents', 'upload')
def upload():
    """Upload a new document."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        errors = []
        file = request.files.get('file')
        name = request.form.get('name', '').strip()
        doc_type = request.form.get('doc_type', '')

        if not file or not file.filename:
            errors.append('يجب اختيار ملف')
        elif not allowed_file(file.filename):
            errors.append(f'نوع الملف غير مسموح. الأنواع المسموحة: {", ".join(ALLOWED_EXTENSIONS)}')

        if not doc_type:
            errors.append('نوع المستند مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('documents/upload.html', cases=cases, clients=clients,
                                   form=request.form, doc_types=DOC_TYPES)

        filename = secure_filename(file.filename)
        if not name:
            name = filename

        upload_base = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, 'static', 'uploads')
        upload_dir = os.path.join(upload_base, 'documents', str(g.tenant_id))
        os.makedirs(upload_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        saved_filename = f'{timestamp}_{filename}'
        file_path = os.path.join(upload_dir, saved_filename)
        file.save(file_path)

        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        file_size = os.path.getsize(file_path)

        doc_date = None
        if request.form.get('doc_date'):
            doc_date = datetime.strptime(request.form['doc_date'], '%Y-%m-%d').date()

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
        flash('تم رفع المستند بنجاح', 'success')
        return redirect(url_for('documents.show', id=document.id))

    pre_case = request.args.get('case_id', type=int)
    pre_client = request.args.get('client_id', type=int)
    return render_template('documents/upload.html', cases=cases, clients=clients,
                           form=request.args, doc_types=DOC_TYPES,
                           pre_case_id=pre_case, pre_client_id=pre_client)


@documents_bp.route('/<int:id>')
@permission_required('documents', 'view')
def show(id):
    """Show document details."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    type_map = dict(DOC_TYPES)
    return render_template('documents/show.html', document=document, type_map=type_map)


@documents_bp.route('/<int:id>/download')
@permission_required('documents', 'view')
def download(id):
    """Download a document file."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    if os.path.exists(document.file_path):
        return send_file(document.file_path, as_attachment=True,
                         download_name=f'{document.name}.{document.file_type}')
    flash('الملف غير موجود', 'danger')
    return redirect(url_for('documents.show', id=document.id))


@documents_bp.route('/<int:id>/share', methods=['POST'])
@permission_required('documents', 'share')
def share(id):
    """Generate a share link for a document."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    days = request.form.get('days', 7, type=int)
    document.share_token = secrets.token_urlsafe(32)
    document.share_expires_at = datetime.utcnow() + timedelta(days=days)
    db.session.commit()
    flash(f'تم إنشاء رابط المشاركة (صالح لمدة {days} أيام)', 'success')
    return redirect(url_for('documents.show', id=document.id))


@documents_bp.route('/shared/<token>')
def shared_view(token):
    """Public shared document view (no login required)."""
    document = Document.query.filter_by(share_token=token).first_or_404()
    if not document.is_share_active:
        return render_template('documents/shared_expired.html'), 410
    return send_file(document.file_path, as_attachment=False, download_name=document.name)


@documents_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('documents', 'delete')
def delete(id):
    """Delete a document."""
    document = Document.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    # Try to delete the file
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except OSError:
            pass
    db.session.delete(document)
    db.session.commit()
    flash('تم حذف المستند', 'warning')
    return redirect(url_for('documents.index'))
