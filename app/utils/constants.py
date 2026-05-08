"""Enums and constants for LexOffice."""
import enum


# ── User Roles ──
class RoleName(str, enum.Enum):
    MANAGER = 'manager'          # مدير المكتب
    PARTNER = 'partner'          # شريك
    SENIOR = 'senior'            # محامي سينيور
    JUNIOR = 'junior'            # محامي جونيور
    ASSISTANT = 'assistant'      # مساعد قانوني
    ACCOUNTANT = 'accountant'    # محاسب


ROLE_NAMES_AR = {
    'manager': 'مدير المكتب',
    'partner': 'شريك',
    'senior': 'محامي سينيور',
    'junior': 'محامي جونيور',
    'assistant': 'مساعد قانوني',
    'accountant': 'محاسب',
}


# ── Subscription ──
class SubscriptionStatus(str, enum.Enum):
    TRIAL = 'trial'
    ACTIVE = 'active'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class PaymentMethodSubscription(str, enum.Enum):
    CREDIT_CARD = 'credit_card'
    VODAFONE_CASH = 'vodafone_cash'
    ETISALAT_CASH = 'etisalat_cash'


class SubscriptionPaymentStatus(str, enum.Enum):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'


# ── Client ──
class ClientType(str, enum.Enum):
    INDIVIDUAL = 'individual'    # فرد
    COMPANY = 'company'          # شركة
    GOVERNMENT = 'government'    # جهة حكومية


class ClientDocType(str, enum.Enum):
    NATIONAL_ID_FRONT = 'national_id_front'
    NATIONAL_ID_BACK = 'national_id_back'
    PASSPORT = 'passport'
    COMMERCIAL_REG = 'commercial_reg'
    TAX_CARD = 'tax_card'
    OTHER = 'other'


# ── Case ──
class CaseType(str, enum.Enum):
    CRIMINAL = 'criminal'            # جنائية
    CIVIL = 'civil'                  # مدنية
    COMMERCIAL = 'commercial'        # تجارية
    ADMINISTRATIVE = 'administrative'  # إدارية
    LABOR = 'labor'                  # عمالية
    FAMILY = 'family'                # أسرة
    CONSTITUTIONAL = 'constitutional'  # دستورية
    ENFORCEMENT = 'enforcement'      # تنفيذ


class CaseStatus(str, enum.Enum):
    NEW = 'new'                      # جديدة
    ACTIVE = 'active'                # نشطة
    AWAITING_JUDGMENT = 'awaiting_judgment'  # منتظرة حكم
    SUSPENDED = 'suspended'          # موقوفة
    CLOSED = 'closed'                # مغلقة


class CasePriority(str, enum.Enum):
    NORMAL = 'normal'                # عادية
    IMPORTANT = 'important'          # مهمة
    CRITICAL = 'critical'            # حرجة


class ClientCapacity(str, enum.Enum):
    PLAINTIFF = 'plaintiff'          # مدعي
    DEFENDANT = 'defendant'          # مدعى عليه
    APPELLANT = 'appellant'          # مستأنف
    RESPONDENT = 'respondent'        # مطعون ضده
    OTHER = 'other'


class FeeType(str, enum.Enum):
    FIXED = 'fixed'                  # مبلغ ثابت
    PERCENTAGE = 'percentage'        # نسبة من المحكوم به
    HOURLY = 'hourly'                # بالساعة
    MIXED = 'mixed'                  # مختلط


class PaymentSchedule(str, enum.Enum):
    UPFRONT = 'upfront'              # مقدم
    INSTALLMENTS = 'installments'    # أقساط
    OPEN = 'open'                    # مفتوح


# ── Court ──
class CourtType(str, enum.Enum):
    # Shared
    PRIMARY = 'primary'              # ابتدائي / عامة (KSA: General Courts)
    APPEAL = 'appeal'                # استئنافي
    CASSATION = 'cassation'          # نقض (EG)
    CONSTITUTIONAL = 'constitutional'  # دستوري
    ECONOMIC = 'economic'            # اقتصادي (EG)
    FAMILY = 'family'                # أسرة / أحوال شخصية
    MILITARY = 'military'            # عسكري
    STATE_COUNCIL = 'state_council'  # مجلس الدولة (EG) / ديوان المظالم (KSA)
    # KSA-specific additions
    SUPREME = 'supreme'              # المحكمة العليا (KSA top tier)
    CRIMINAL = 'criminal'            # المحاكم الجزائية
    COMMERCIAL = 'commercial'        # المحاكم التجارية
    LABOR = 'labor'                  # المحاكم العمالية
    ENFORCEMENT = 'enforcement'      # محاكم التنفيذ


# ── Session ──
class SessionType(str, enum.Enum):
    FIRST = 'first'                  # أولى
    EVIDENCE = 'evidence'            # إثبات
    PLEADING = 'pleading'            # مرافعة
    JUDGMENT = 'judgment'            # حكم
    EMERGENCY = 'emergency'          # طارئة
    POSTPONEMENT = 'postponement'    # تأجيل


class SessionResult(str, enum.Enum):
    POSTPONED = 'postponed'          # تأجيل
    JUDGMENT = 'judgment'            # حكم
    DECISION = 'decision'            # قرار
    EVIDENCE = 'evidence'            # إثبات
    ATTENDANCE = 'attendance'        # حضور
    ABSENCE = 'absence'              # غياب


# ── Judgment ──
class JudgmentType(str, enum.Enum):
    PRIMARY = 'primary'              # ابتدائي
    APPEAL = 'appeal'                # استئنافي
    CASSATION = 'cassation'          # نقض
    CONSTITUTIONAL = 'constitutional'  # دستوري


class JudgmentResult(str, enum.Enum):
    FULL_WIN = 'full_win'            # كسب كامل
    PARTIAL_WIN = 'partial_win'      # كسب جزئي
    LOSS = 'loss'                    # خسارة
    POSTPONEMENT = 'postponement'    # تأجيل
    PROCEDURAL = 'procedural'        # شكلي
    ABSENCE = 'absence'              # غيابي


class AppealType(str, enum.Enum):
    APPEAL = 'appeal'                # استئناف
    CASSATION = 'cassation'          # نقض


# ── Enforcement ──
class EnforcementType(str, enum.Enum):
    REAL_ESTATE_SEIZURE = 'real_estate_seizure'  # حجز عقاري
    FUNDS_SEIZURE = 'funds_seizure'              # حجز على أموال
    MOVABLES_SEIZURE = 'movables_seizure'        # حجز منقولات
    EVICTION = 'eviction'                        # إخلاء
    DELIVERY = 'delivery'                        # تسليم


class EnforcementStatus(str, enum.Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    SUSPENDED = 'suspended'


# ── Power of Attorney ──
class POAType(str, enum.Enum):
    GENERAL = 'general'              # عام
    SPECIAL = 'special'              # خاص
    JUDICIAL = 'judicial'            # قضائي
    BANKING = 'banking'              # بنكي
    REAL_ESTATE = 'real_estate'      # عقاري
    COMMERCIAL = 'commercial'        # تجاري


class POAStatus(str, enum.Enum):
    ACTIVE = 'active'                # ساري
    EXPIRING_SOON = 'expiring_soon'  # قريب الانتهاء
    EXPIRED = 'expired'              # منتهي


# ── Financial ──
class PaymentMethod(str, enum.Enum):
    CASH = 'cash'                    # كاش
    BANK_TRANSFER = 'bank_transfer'  # تحويل بنكي
    CHECK = 'check'                  # شيك
    VODAFONE_CASH = 'vodafone_cash'  # فودافون كاش
    CARD = 'card'                    # بطاقة


class InvoiceStatus(str, enum.Enum):
    DRAFT = 'draft'
    SENT = 'sent'
    PAID = 'paid'
    OVERDUE = 'overdue'
    CANCELLED = 'cancelled'


class InvoiceItemType(str, enum.Enum):
    FEES = 'fees'                    # أتعاب
    EXPENSES = 'expenses'            # مصاريف
    STAMP = 'stamp'                  # ختم
    TRANSPORT = 'transport'          # نقل
    OTHER = 'other'                  # غيره


class DiscountType(str, enum.Enum):
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'


class ExpenseType(str, enum.Enum):
    COURT_FEES = 'court_fees'        # رسوم محكمة
    TRANSPORT = 'transport'          # نقل
    STAMP = 'stamp'                  # ختم
    EXPERT = 'expert'                # خبير
    OTHER = 'other'


# ── Task ──
class TaskPriority(str, enum.Enum):
    URGENT = 'urgent'                # عاجل (أحمر)
    IMPORTANT = 'important'          # مهم (برتقالي)
    NORMAL = 'normal'                # عادي (رمادي)


class TaskStatus(str, enum.Enum):
    NEW = 'new'                      # جديد
    IN_PROGRESS = 'in_progress'      # قيد التنفيذ
    DONE = 'done'                    # منته


class RecurrenceType(str, enum.Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'


class AttendanceStatus(str, enum.Enum):
    PENDING = 'pending'
    ATTENDED = 'attended'
    NO_SHOW = 'no_show'
    RESCHEDULED = 'rescheduled'


# ── Document ──
class DocumentType(str, enum.Enum):
    DEFENSE_MEMO = 'defense_memo'        # مذكرة دفاع
    JUDGMENT = 'judgment'                # حكم
    CONTRACT = 'contract'                # عقد
    POA = 'poa'                          # توكيل
    RECEIPT = 'receipt'                  # إيصال
    CORRESPONDENCE = 'correspondence'    # مراسلة
    SESSION_MINUTES = 'session_minutes'  # محضر جلسة
    OTHER = 'other'                      # أخرى


class TemplateType(str, enum.Enum):
    FEE_CONTRACT = 'fee_contract'        # عقد أتعاب محاماة
    SPECIAL_POA = 'special_poa'          # توكيل خاص
    FEE_RECEIPT = 'fee_receipt'          # إيصال استلام أتعاب
    DEFENSE_MEMO = 'defense_memo'        # مذكرة دفاع
    CLIENT_LETTER = 'client_letter'      # خطاب إلى موكل


class TemplateOutputFormat(str, enum.Enum):
    PDF = 'pdf'
    DOCX = 'docx'


# ── Notification ──
class NotificationType(str, enum.Enum):
    SESSION_UPCOMING = 'session_upcoming'
    APPEAL_DEADLINE = 'appeal_deadline'
    POA_EXPIRING = 'poa_expiring'
    TASK_DEADLINE = 'task_deadline'
    TASK_OVERDUE = 'task_overdue'
    INVOICE_OVERDUE = 'invoice_overdue'
    FEES_REMINDER = 'fees_reminder'
    POA_EXPIRED = 'poa_expired'
    PAYMENT_RECEIVED = 'payment_received'
    DOCUMENT_UPLOADED = 'document_uploaded'
    GENERAL = 'general'


class NotificationPriority(str, enum.Enum):
    CRITICAL = 'critical'                # حرج
    IMPORTANT = 'important'              # مهم
    INFO = 'info'                        # معلومة


class NotificationChannel(str, enum.Enum):
    IN_APP = 'in_app'
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'


class DeliveryStatus(str, enum.Enum):
    PENDING = 'pending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    FAILED = 'failed'


# ── Sent Via ──
class SentVia(str, enum.Enum):
    EMAIL = 'email'
    WHATSAPP = 'whatsapp'
