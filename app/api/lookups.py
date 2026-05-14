"""API routes for lookup/dropdown data used by the mobile app."""
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request

from app.models.case import Court
from app.models.user import Role, User

EGYPTIAN_GOVERNORATES = [
    'القاهرة', 'الجيزة', 'الإسكندرية', 'الدقهلية', 'البحر الأحمر',
    'البحيرة', 'الفيوم', 'الغربية', 'الإسماعيلية', 'المنوفية',
    'المنيا', 'القليوبية', 'الوادي الجديد', 'السويس', 'أسوان',
    'أسيوط', 'بني سويف', 'بورسعيد', 'دمياط', 'الشرقية',
    'جنوب سيناء', 'كفر الشيخ', 'مطروح', 'الأقصر', 'قنا',
    'شمال سيناء', 'سوهاج',
]


@api_bp.route('/lookups/courts', methods=['GET'])
@api_login_required
def api_lookups_courts():
    """Return all active courts."""
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    return success_response(data=[c.to_dict() for c in courts])


@api_bp.route('/lookups/roles', methods=['GET'])
@api_login_required
def api_lookups_roles():
    """Return all roles."""
    roles = Role.query.order_by(Role.id).all()
    return success_response(data=[r.to_dict() for r in roles])


@api_bp.route('/lookups/users', methods=['GET'])
@api_login_required
def api_lookups_users():
    """Return active users in the tenant (for assigning cases/tasks).

    Any authenticated user can call this — needed by case/task forms to
    pick a responsible lawyer or assignee.
    """
    users = (
        User.query
        .filter_by(tenant_id=g.tenant_id, is_active=True)
        .order_by(User.full_name)
        .all()
    )
    return success_response(data=[{
        'id': u.id,
        'full_name': u.full_name,
        'email': u.email,
        'role_name': u.role.name_ar if u.role else None,
    } for u in users])


@api_bp.route('/lookups/governorates', methods=['GET'])
@api_login_required
def api_lookups_governorates():
    """Return the list of Egyptian governorates."""
    return success_response(data=EGYPTIAN_GOVERNORATES)


@api_bp.route('/lookups/enums', methods=['GET'])
@api_login_required
def api_lookups_enums():
    """Return all dropdown enums for the mobile app."""

    def to_enum_list(pairs):
        return [{'value': v, 'label_ar': l} for v, l in pairs]

    enums = {
        # Cases
        'case_types': to_enum_list([
            ('criminal', 'جنائية'), ('civil', 'مدنية'), ('commercial', 'تجارية'),
            ('administrative', 'إدارية'), ('labor', 'عمالية'), ('family', 'أسرة'),
            ('constitutional', 'دستورية'), ('enforcement', 'تنفيذ'),
        ]),
        'case_statuses': to_enum_list([
            ('new', 'جديدة'), ('active', 'نشطة'), ('awaiting_judgment', 'منتظرة حكم'),
            ('suspended', 'موقوفة'), ('closed', 'مغلقة'),
        ]),
        'priorities': to_enum_list([
            ('normal', 'عادية'), ('important', 'مهمة'), ('critical', 'حرجة'),
        ]),
        'capacities': to_enum_list([
            ('plaintiff', 'مدعي'), ('defendant', 'مدعى عليه'),
            ('appellant', 'مستأنف'), ('respondent', 'مطعون ضده'), ('other', 'أخرى'),
        ]),
        'fee_types': to_enum_list([
            ('fixed', 'مبلغ ثابت'), ('percentage', 'نسبة'),
            ('hourly', 'بالساعة'), ('mixed', 'مختلط'),
        ]),
        'payment_schedules': to_enum_list([
            ('upfront', 'مقدم'), ('installments', 'أقساط'), ('after_judgment', 'بعد الحكم'),
        ]),

        # Sessions
        'session_types': to_enum_list([
            ('first', 'أولى'), ('evidence', 'إثبات'), ('pleading', 'مرافعة'),
            ('judgment', 'حكم'), ('emergency', 'طارئة'), ('postponement', 'تأجيل'),
        ]),
        'session_results': to_enum_list([
            ('postponed', 'تأجيل'), ('judgment', 'حكم'), ('decision', 'قرار'),
            ('evidence', 'إثبات'), ('attendance', 'حضور'), ('absence', 'غياب'),
        ]),

        # Judgments
        'judgment_types': to_enum_list([
            ('primary', 'ابتدائي'), ('appeal', 'استئنافي'),
            ('cassation', 'نقض'), ('constitutional', 'دستوري'),
        ]),
        'judgment_results': to_enum_list([
            ('full_win', 'كسب كامل'), ('partial_win', 'كسب جزئي'), ('loss', 'خسارة'),
            ('postponement', 'تأجيل'), ('procedural', 'شكلي'), ('absence', 'غيابي'),
        ]),

        # Enforcement
        'enforcement_types': to_enum_list([
            ('real_estate_seizure', 'حجز عقاري'), ('funds_seizure', 'حجز على أموال'),
            ('movables_seizure', 'حجز منقولات'), ('eviction', 'إخلاء'), ('delivery', 'تسليم'),
        ]),
        'enforcement_statuses': to_enum_list([
            ('active', 'نشط'), ('completed', 'مكتمل'),
            ('suspended', 'معلق'), ('cancelled', 'ملغي'),
        ]),

        # Financial
        'payment_methods': to_enum_list([
            ('cash', 'نقدي'), ('bank_transfer', 'تحويل بنكي'), ('check', 'شيك'),
            ('credit_card', 'بطاقة ائتمان'), ('online', 'دفع إلكتروني'),
        ]),
        'expense_types': to_enum_list([
            ('court_fees', 'رسوم محكمة'), ('registration', 'رسوم تسجيل'),
            ('transportation', 'مواصلات'), ('copies', 'تصوير مستندات'),
            ('expert_fees', 'أتعاب خبير'), ('office', 'مصاريف مكتبية'),
            ('other', 'أخرى'),
        ]),
        'invoice_statuses': to_enum_list([
            ('draft', 'مسودة'), ('sent', 'مرسلة'), ('paid', 'مدفوعة'),
            ('partially_paid', 'مدفوعة جزئياً'), ('overdue', 'متأخرة'), ('cancelled', 'ملغاة'),
        ]),
        'item_types': to_enum_list([
            ('fees', 'أتعاب'), ('consultation', 'استشارة'), ('court_fees', 'رسوم محكمة'),
            ('expenses', 'مصاريف'), ('other', 'أخرى'),
        ]),

        # Documents
        'doc_types': to_enum_list([
            ('contract', 'عقد'), ('power_of_attorney', 'توكيل'), ('court_filing', 'صحيفة دعوى'),
            ('court_decision', 'قرار محكمة'), ('evidence', 'مستند إثبات'),
            ('correspondence', 'مراسلة'), ('id_document', 'مستند هوية'),
            ('financial', 'مستند مالي'), ('other', 'أخرى'),
        ]),
        'template_types': to_enum_list([
            ('contract', 'عقد'), ('power_of_attorney', 'توكيل'), ('court_filing', 'صحيفة دعوى'),
            ('memo', 'مذكرة'), ('letter', 'خطاب'), ('agreement', 'اتفاقية'), ('other', 'أخرى'),
        ]),

        # Notifications
        'notification_types': to_enum_list([
            ('session_reminder', 'تذكير بجلسة'), ('task_assigned', 'مهمة جديدة'),
            ('deadline_alert', 'تنبيه موعد نهائي'), ('payment_received', 'دفعة جديدة'),
            ('appeal_deadline', 'موعد استئناف'), ('case_update', 'تحديث قضية'),
        ]),
    }

    return success_response(data=enums)
