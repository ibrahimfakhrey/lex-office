"""Permission catalogue — single source of truth for the admin RBAC system.

Used by:
  - Roles UI (renders the toggle-switch matrix)
  - Migration seed (grants all permissions to the Super Admin system role)
  - Decorators (validate that requested (module, action) is a known pair)

A grant is one row in `admin_role_permissions` (role_id, module, action).
Absence of a row = denied. The Super Admin system role short-circuits all checks.
"""

PERMISSION_CATALOGUE = [
    {
        'group_key': 'tenants_mgmt',
        'group_ar': 'إدارة المكاتب',
        'modules': [
            {'key': 'tenants',   'label_ar': 'المكاتب',  'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
            {'key': 'plans',     'label_ar': 'الخطط',     'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
            {'key': 'features',  'label_ar': 'الميزات',   'actions': ['view', 'edit'],                  'scoped': False},
        ],
    },
    {
        'group_key': 'subscription_billing',
        'group_ar': 'المالية (الاشتراكات)',
        'modules': [
            {'key': 'billing', 'label_ar': 'الفواتير', 'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
        ],
    },
    {
        'group_key': 'internal_finance',
        'group_ar': 'الإدارة المالية الداخلية',
        'modules': [
            {'key': 'finance_dashboard', 'label_ar': 'لوحة المالية',     'actions': ['view'],                          'scoped': False},
            {'key': 'finance_employees', 'label_ar': 'الموظفون',          'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
            {'key': 'finance_payroll',   'label_ar': 'دفعات الرواتب',     'actions': ['view', 'add', 'delete'],         'scoped': True},
            {'key': 'finance_lenders',   'label_ar': 'القروض',            'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
            {'key': 'finance_expenses',  'label_ar': 'المصاريف',          'actions': ['view', 'add', 'edit', 'delete'], 'scoped': True},
            {'key': 'finance_income',    'label_ar': 'الإيرادات',         'actions': ['view', 'add', 'delete'],         'scoped': True},
        ],
    },
    {
        'group_key': 'operations',
        'group_ar': 'العمليات',
        'modules': [
            {'key': 'notifications', 'label_ar': 'الإشعارات',     'actions': ['view', 'send'], 'scoped': False},
            {'key': 'audit_log',     'label_ar': 'سجل العمليات', 'actions': ['view'],          'scoped': False},
        ],
    },
    {
        'group_key': 'system',
        'group_ar': 'النظام',
        'modules': [
            {'key': 'settings',     'label_ar': 'الإعدادات',     'actions': ['view', 'edit'],                   'scoped': False},
            {'key': 'admin_users',  'label_ar': 'حسابات الأدمن', 'actions': ['view', 'add', 'edit', 'delete'], 'scoped': False},
            {'key': 'admin_roles',  'label_ar': 'الأدوار',        'actions': ['view', 'add', 'edit', 'delete'], 'scoped': False},
        ],
    },
]


SCOPE_OPTIONS = [
    ('all', 'كل السجلات'),
    ('own', 'السجلات اللي أضافها هو فقط'),
]


ACTION_LABELS = {
    'view':   'عرض',
    'add':    'إضافة',
    'edit':   'تعديل',
    'delete': 'حذف',
    'send':   'إرسال',
}


def all_permission_pairs():
    """Yield every (module, action) pair in the catalogue."""
    for group in PERMISSION_CATALOGUE:
        for module in group['modules']:
            for action in module['actions']:
                yield (module['key'], action)


def is_known_permission(module, action):
    return (module, action) in set(all_permission_pairs())
