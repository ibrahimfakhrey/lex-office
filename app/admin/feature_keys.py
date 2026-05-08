"""Canonical list of feature keys used across plans and overrides.

These are the features the admin can toggle per plan or per tenant. The actual
application code should use `tenant_has_feature(tenant, key)` from
`app.admin.feature_utils` to check entitlement.
"""

# Quantity limits (numeric). 0 or absence = unlimited; -1 also treated as unlimited.
LIMIT_FEATURES = [
    {'key': 'max_cases',            'label': 'الحد الأقصى للقضايا',          'group': 'limits'},
    {'key': 'max_clients',          'label': 'الحد الأقصى للموكلين',         'group': 'limits'},
    {'key': 'max_storage_gb',       'label': 'حد التخزين (GB)',              'group': 'limits'},
    {'key': 'max_legal_templates',  'label': 'الحد الأقصى للقوالب القانونية', 'group': 'limits'},
    {'key': 'ai_calls_per_month',   'label': 'حد طلبات الذكاء الاصطناعي شهرياً', 'group': 'limits'},
]

# Boolean feature flags
BOOLEAN_FEATURES = [
    # Core modules
    {'key': 'clients',                'label': 'الموكلون',                    'group': 'core'},
    {'key': 'cases',                  'label': 'القضايا',                     'group': 'core'},
    {'key': 'sessions',               'label': 'الجلسات',                     'group': 'core'},
    {'key': 'judgments',              'label': 'الأحكام',                     'group': 'core'},
    {'key': 'enforcement',            'label': 'التنفيذ',                     'group': 'core'},
    {'key': 'poa',                    'label': 'التوكيلات',                   'group': 'core'},
    {'key': 'documents',              'label': 'المستندات',                   'group': 'core'},
    {'key': 'tasks',                  'label': 'المهام',                      'group': 'core'},
    {'key': 'templates',              'label': 'النماذج القانونية',           'group': 'core'},

    # Financial
    {'key': 'financial_basic',        'label': 'النظام المالي الأساسي',       'group': 'financial'},
    {'key': 'financial_advanced',    'label': 'النظام المالي المتقدم',       'group': 'financial'},

    # Reports
    {'key': 'reports_basic',          'label': 'تقارير أساسية',               'group': 'reports'},
    {'key': 'advanced_reports',       'label': 'تقارير متقدمة',               'group': 'reports'},

    # Notifications
    {'key': 'notifications_email',    'label': 'إشعارات البريد الإلكتروني',   'group': 'notifications'},
    {'key': 'sms_notifications',      'label': 'إشعارات SMS',                  'group': 'notifications'},
    {'key': 'whatsapp_notifications', 'label': 'إشعارات WhatsApp',             'group': 'notifications'},

    # AI / Advanced
    {'key': 'ai_enabled',             'label': 'الذكاء الاصطناعي (مفعّل)',     'group': 'advanced'},
    {'key': 'ai_summary',             'label': 'الملخص الذكي (AI)',           'group': 'advanced'},
    {'key': 'api_access',             'label': 'الوصول للـ API',              'group': 'advanced'},
    {'key': 'mobile_app',             'label': 'تطبيق الموبايل',              'group': 'advanced'},
]

ALL_FEATURES = LIMIT_FEATURES + BOOLEAN_FEATURES

GROUPS = {
    'limits':        'الحدود الكمية',
    'core':          'الوحدات الأساسية',
    'financial':     'النظام المالي',
    'reports':       'التقارير',
    'notifications': 'الإشعارات',
    'advanced':      'ميزات متقدمة',
}


def features_by_group():
    """Group all features by their group key."""
    grouped = {g: [] for g in GROUPS}
    for f in ALL_FEATURES:
        grouped[f['group']].append(f)
    return grouped


_FEATURE_LABELS = {f['key']: f['label'] for f in ALL_FEATURES}


def label_for(key):
    """Return the Arabic display name for a feature key, falling back to the key itself."""
    return _FEATURE_LABELS.get(key, key)
