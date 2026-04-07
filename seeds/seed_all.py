"""Run all seed scripts."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db

print("Creating all tables...")
with app.app_context():
    db.create_all()
    print("Tables created.")

print("\n--- Seeding Roles & Permissions ---")
from seeds.seed_roles import seed as seed_roles
seed_roles()

print("\n--- Seeding Courts ---")
from seeds.seed_courts import seed as seed_courts
seed_courts()

print("\n--- Seeding Subscription Plans ---")
from seeds.seed_subscriptions import seed as seed_subscriptions
seed_subscriptions()

print("\nAll seeds completed successfully!")
