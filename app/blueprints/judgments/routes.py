"""Judgment management routes."""
import os
import uuid
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g,
    jsonify, current_app,
)
from werkzeug.utils import secure_filename
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.judgment import Judgment
from app.models.case import Case, Court

judgments_bp = Blueprint('judgments', __name__, template_folder='../../templates/judgments')

JUDGMENT_TYPES = [
    ('primary', 'ابتدائي'), ('appeal', 'استئنافي'),
    ('cassation', 'نقض'), ('constitutional', 'دستوري'),
]
JUDGMENT_RESULTS = [
    ('full_win', 'كسب كامل'), ('partial_win', 'كسب جزئي'), ('loss', 'خسارة'),
    ('postponement', 'تأجيل'), ('procedural', 'شكلي'), ('absence', 'غيابي'),
]
APPEAL_DAYS = {'primary': 40, 'appeal': 60, 'cassation': 60}

ALLOWED_UPLOAD_EXTS = {'.pdf', '.docx'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _save_uploaded_judgment(file_storage):
    """Save the uploaded judgment file under static/uploads/judgments/<tenant>/.

    Returns (absolute_path, web_relative_path) — web path is what we store on
    the model so url_for('static', filename=...) can serve it.
    """
    filename = secure_filename(file_storage.filename or 'judgment')
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        from app.services.judgment_extractor import UnsupportedFileTypeError
        raise UnsupportedFileTypeError(
            'نوع الملف غير مدعوم — يرجى رفع PDF أو DOCX فقط'
        )

    upload_dir = os.path.join(
        current_app.root_path, 'static', 'uploads', 'judgments',
        f'tenant_{g.tenant_id}',
    )
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f'{uuid.uuid4().hex[:12]}_{filename}'
    abs_path = os.path.join(upload_dir, unique_name)
    file_storage.save(abs_path)
    web_path = f'uploads/judgments/tenant_{g.tenant_id}/{unique_name}'
    return abs_path, web_path


@judgments_bp.route('/')
@permission_required('judgments', 'view')
def index():
    """List all judgments with filters."""
    page = request.args.get('page', 1, type=int)
    case_id = request.args.get('case_id', '', type=str)
    result = request.args.get('result', '')

    query = Judgment.query.filter_by(tenant_id=g.tenant_id)
    if case_id:
        query = query.filter_by(case_id=int(case_id))
    if result:
        query = query.filter_by(result=result)

    judgments = query.order_by(Judgment.judgment_date.desc()).paginate(page=page, per_page=20)
    return render_template('judgments/index.html', judgments=judgments, case_id=case_id,
                           result=result, judgment_results=JUDGMENT_RESULTS)


@judgments_bp.route('/extract', methods=['POST'])
@permission_required('judgments', 'create')
def extract():
    """AJAX: receive an uploaded PDF/DOCX, extract text, run Claude analysis,
    return structured JSON for client-side form pre-filling.

    Saves the uploaded file so a follow-up POST /judgments/create can attach
    it to the new Judgment row by passing back ``upload_path`` from this
    response (round-tripped through a hidden form field).
    """
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'ok': False, 'error': 'لم يتم اختيار ملف'}), 400

    # Size check (Flask config has MAX_CONTENT_LENGTH, but this gives a nicer
    # Arabic error than the framework's 413).
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return jsonify({
            'ok': False,
            'error': 'حجم الملف يتجاوز الحد المسموح (10 ميجا)'
        }), 413

    try:
        abs_path, web_path = _save_uploaded_judgment(file)
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    # Extract text
    from app.services.judgment_extractor import (
        extract_text, ExtractionError, ScannedPdfError,
    )
    try:
        extracted = extract_text(abs_path)
    except ScannedPdfError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'scanned': True}), 422
    except ExtractionError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 422

    # Analyze with Claude (governance-aware: quota + per-call usage log)
    from app.services.judgment_ai import (
        analyze_judgment, AnalysisError, AnalysisRateLimitError,
    )
    from app.services.ai_usage import (
        AIDisabledError, FeatureDisabledError,
        QuotaExceededError, FeatureQuotaExceededError, QuotaError,
    )
    from app.models.tenant import Tenant
    tenant = Tenant.query.get(g.tenant_id)
    try:
        analysis = analyze_judgment(extracted.text, tenant=tenant, user=g.current_user)
    except AIDisabledError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': 'ai_disabled'}), 402
    except FeatureDisabledError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': 'feature_disabled'}), 402
    except FeatureQuotaExceededError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': 'feature_quota_exceeded'}), 402
    except QuotaExceededError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': 'quota_exceeded'}), 402
    except QuotaError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': 'quota_blocked'}), 402
    except AnalysisRateLimitError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 429
    except AnalysisError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 502

    return jsonify({
        'ok': True,
        'upload_path': web_path,
        'extracted_text': extracted.text,
        'analysis': analysis.model_dump(),
        'page_count': extracted.page_count,
        'char_count': extracted.char_count,
    })


@judgments_bp.route('/create', methods=['GET', 'POST'])
@permission_required('judgments', 'create')
def create():
    """Record a new judgment."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active', 'awaiting_judgment'])
    ).order_by(Case.case_number).all()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()

    if request.method == 'POST':
        errors = []
        case_id = request.form.get('case_id', type=int)
        judgment_date_str = request.form.get('judgment_date', '')
        judgment_type = request.form.get('judgment_type', '')
        result = request.form.get('result', '')

        if not case_id:
            errors.append('يجب اختيار القضية')
        if not judgment_date_str:
            errors.append('تاريخ الحكم مطلوب')
        if not judgment_type:
            errors.append('نوع الحكم مطلوب')
        if not result:
            errors.append('نتيجة الحكم مطلوبة')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('judgments/create.html', cases=cases, courts=courts,
                                   form=request.form, judgment_types=JUDGMENT_TYPES,
                                   judgment_results=JUDGMENT_RESULTS)

        judgment_date = datetime.strptime(judgment_date_str, '%Y-%m-%d').date()

        # Auto-calculate appeal deadline
        appeal_deadline = None
        appeal_tracking = request.form.get('appeal_tracking_enabled') == 'yes'
        if appeal_tracking:
            days = APPEAL_DAYS.get(judgment_type, 40)
            appeal_deadline = judgment_date + timedelta(days=days)
            # Allow manual override
            if request.form.get('appeal_deadline'):
                appeal_deadline = datetime.strptime(request.form['appeal_deadline'], '%Y-%m-%d').date()

        # Round-tripped from /judgments/extract — both optional. The hidden
        # field carries either a JSON-serialised analysis dict or empty string.
        ai_analysis_raw = (request.form.get('ai_analysis_json') or '').strip()
        ai_analysis_data = None
        if ai_analysis_raw:
            try:
                import json as _json
                ai_analysis_data = _json.loads(ai_analysis_raw)
            except (ValueError, TypeError):
                ai_analysis_data = None

        judgment_file_path = (request.form.get('judgment_file_path') or '').strip() or None

        judgment = Judgment(
            tenant_id=g.tenant_id,
            case_id=case_id,
            judgment_date=judgment_date,
            court_id=request.form.get('court_id', type=int) or None,
            judgment_type=judgment_type,
            result=result,
            judgment_text=request.form.get('judgment_text', '').strip() or None,
            judgment_file_path=judgment_file_path,
            judge_name=request.form.get('judge_name', '').strip() or None,
            awarded_amount=request.form.get('awarded_amount', type=float) or None,
            notes=request.form.get('notes', '').strip() or None,
            appeal_tracking_enabled=appeal_tracking,
            appeal_type=judgment_type,
            appeal_deadline=appeal_deadline,
            ai_analysis=ai_analysis_data,
        )
        db.session.add(judgment)

        # Update case status
        case = Case.query.get(case_id)
        if case:
            case.status = 'awaiting_judgment' if result in ('postponement',) else 'closed' if judgment_type == 'cassation' else case.status

        db.session.commit()

        from app.services.notification_service import notify_tenant_users
        notify_tenant_users(
            tenant_id=g.tenant_id,
            notification_type='appeal_deadline',
            title=f'تم تسجيل حكم للقضية: {case.case_number or "-"}',
            body=f'النتيجة: {result} — موعد الاستئناف: {appeal_deadline.strftime("%Y-%m-%d") if appeal_deadline else "غير محدد"}',
            priority='important',
            related_type='judgment',
            related_id=judgment.id,
            actor_name=g.current_user.full_name,
            exclude_user_id=g.current_user.id,
        )
        db.session.commit()

        flash('تم تسجيل الحكم بنجاح', 'success')
        return redirect(url_for('judgments.show', id=judgment.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('judgments/create.html', cases=cases, courts=courts,
                           form=request.args, judgment_types=JUDGMENT_TYPES,
                           judgment_results=JUDGMENT_RESULTS, pre_case_id=pre_case)


@judgments_bp.route('/<int:id>')
@permission_required('judgments', 'view')
def show(id):
    """Show judgment details with appeal tracking."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    type_map = dict(JUDGMENT_TYPES)
    result_map = dict(JUDGMENT_RESULTS)

    # Calculate days until appeal deadline
    days_until_appeal = None
    if judgment.appeal_deadline:
        days_until_appeal = (judgment.appeal_deadline - datetime.utcnow().date()).days

    return render_template('judgments/show.html', judgment=judgment, type_map=type_map,
                           result_map=result_map, days_until_appeal=days_until_appeal)


@judgments_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('judgments', 'edit')
def edit(id):
    """Edit judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()

    if request.method == 'POST':
        judgment.judgment_date = datetime.strptime(request.form['judgment_date'], '%Y-%m-%d').date()
        judgment.court_id = request.form.get('court_id', type=int) or None
        judgment.judgment_type = request.form.get('judgment_type', judgment.judgment_type)
        judgment.result = request.form.get('result', judgment.result)
        judgment.judgment_text = request.form.get('judgment_text', '').strip() or None
        judgment.judge_name = request.form.get('judge_name', '').strip() or None
        judgment.awarded_amount = request.form.get('awarded_amount', type=float) or None
        judgment.notes = request.form.get('notes', '').strip() or None

        if request.form.get('appeal_deadline'):
            judgment.appeal_deadline = datetime.strptime(request.form['appeal_deadline'], '%Y-%m-%d').date()
            judgment.appeal_tracking_enabled = True

        db.session.commit()
        flash('تم تحديث الحكم بنجاح', 'success')
        return redirect(url_for('judgments.show', id=judgment.id))

    return render_template('judgments/edit.html', judgment=judgment, courts=courts,
                           judgment_types=JUDGMENT_TYPES, judgment_results=JUDGMENT_RESULTS)


@judgments_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('judgments', 'delete')
def delete(id):
    """Delete a judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    case_id = judgment.case_id
    db.session.delete(judgment)
    db.session.commit()
    flash('تم حذف الحكم', 'warning')
    return redirect(url_for('cases.show', id=case_id))
