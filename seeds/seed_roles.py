"""Seed default roles and RBAC permission matrix."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.user import Role, Permission, RolePermission
from app.utils.constants import RoleName

# Full RBAC permission matrix from SRS
# Format: module -> action -> list of allowed roles
PERMISSION_MATRIX = {
    'dashboard': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT, RoleName.ACCOUNTANT],
    },
    'clients': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT, RoleName.ACCOUNTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'delete': [RoleName.MANAGER],
    },
    'cases': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT, RoleName.ACCOUNTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'delete': [RoleName.MANAGER],
        'assign': [RoleName.MANAGER, RoleName.PARTNER],
    },
    'sessions': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'delete': [RoleName.MANAGER],
    },
    'judgments': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'delete': [RoleName.MANAGER],
    },
    'enforcement': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'delete': [RoleName.MANAGER],
    },
    'poa': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.ASSISTANT],
        'delete': [RoleName.MANAGER],
    },
    'financial': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.ACCOUNTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.ACCOUNTANT],
        'edit': [RoleName.MANAGER, RoleName.ACCOUNTANT],
        'delete': [RoleName.MANAGER],
        'approve': [RoleName.MANAGER, RoleName.PARTNER],
    },
    'tasks': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'delete': [RoleName.MANAGER],
        'assign': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
    },
    'documents': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'upload': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'delete': [RoleName.MANAGER, RoleName.PARTNER],
        'share': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
    },
    'templates': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT],
        'create': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'edit': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR],
        'delete': [RoleName.MANAGER],
    },
    'notifications': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.SENIOR, RoleName.JUNIOR, RoleName.ASSISTANT, RoleName.ACCOUNTANT],
        'settings': [RoleName.MANAGER],
    },
    'reports': {
        'view': [RoleName.MANAGER, RoleName.PARTNER, RoleName.ACCOUNTANT],
        'export': [RoleName.MANAGER, RoleName.PARTNER, RoleName.ACCOUNTANT],
    },
    'settings': {
        'view': [RoleName.MANAGER],
        'edit': [RoleName.MANAGER],
        'manage_users': [RoleName.MANAGER],
        'manage_subscription': [RoleName.MANAGER],
    },
}

ARABIC_NAMES = {
    RoleName.MANAGER: 'مدير المكتب',
    RoleName.PARTNER: 'شريك',
    RoleName.SENIOR: 'محامي سينيور',
    RoleName.JUNIOR: 'محامي جونيور',
    RoleName.ASSISTANT: 'مساعد إداري',
    RoleName.ACCOUNTANT: 'محاسب',
}


def seed():
    with app.app_context():
        # Create roles
        roles = {}
        for role_name in RoleName:
            role = Role.query.filter_by(name=role_name.value).first()
            if not role:
                role = Role(
                    name=role_name.value,
                    name_ar=ARABIC_NAMES[role_name],
                    description=f'{ARABIC_NAMES[role_name]} - {role_name.value}'
                )
                db.session.add(role)
            roles[role_name] = role

        db.session.flush()

        # Create permissions and role-permission mappings
        for module, actions in PERMISSION_MATRIX.items():
            for action, allowed_roles in actions.items():
                perm = Permission.query.filter_by(module=module, action=action).first()
                if not perm:
                    perm = Permission(module=module, action=action)
                    db.session.add(perm)
                    db.session.flush()

                for role_name in allowed_roles:
                    existing = RolePermission.query.filter_by(
                        role_id=roles[role_name].id, permission_id=perm.id
                    ).first()
                    if not existing:
                        db.session.add(RolePermission(role_id=roles[role_name].id, permission_id=perm.id))

        db.session.commit()
        print(f"Seeded {len(roles)} roles and {sum(len(a) for a in PERMISSION_MATRIX.values())} permissions.")


if __name__ == '__main__':
    seed()
