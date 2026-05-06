"""Internal operations finance — Manasety company books.

Distinct from tenant-side `Payment`/`Invoice`/`Expense` models. These tables
track the SaaS company's own employees, loans, expenses, and income; they
have no `tenant_id` because they are company-wide.
"""
from datetime import datetime, date
from app.extensions import db


# ─────────────────────── Employees ───────────────────────
class OpEmployee(db.Model):
    __tablename__ = 'op_employees'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    employment_type = db.Column(db.String(20), nullable=False)  # full_time / freelance / part_time
    monthly_salary = db.Column(db.Numeric(12, 2), nullable=False)
    joined_at = db.Column(db.Date, nullable=False)
    contact_phone = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False)  # active / paused / terminated
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship(
        'OpPayrollPayment',
        backref='employee',
        cascade='all, delete-orphan',
        order_by='OpPayrollPayment.payment_date.desc()',
    )

    @property
    def months_since_joining(self) -> int:
        # Excel DATEDIF(start, end, "M") — completed full months only.
        # Joined Feb 4, today May 4 → exactly 3 months.
        # Joined Feb 4, today May 3 → 2 months (anniversary day not yet reached).
        today = date.today()
        if not self.joined_at or self.joined_at > today:
            return 0
        months = (today.year - self.joined_at.year) * 12 + (today.month - self.joined_at.month)
        if today.day < self.joined_at.day:
            months -= 1
        return max(months, 0)

    @property
    def total_due(self) -> float:
        return float(self.monthly_salary or 0) * self.months_since_joining

    @property
    def total_paid(self) -> float:
        return float(sum((p.amount or 0) for p in self.payments))

    @property
    def balance(self) -> float:
        return self.total_due - self.total_paid

    @property
    def payment_count(self) -> int:
        return len(self.payments)

    @property
    def last_payment_date(self):
        return self.payments[0].payment_date if self.payments else None


# ─────────────────────── Payroll Payments ───────────────────────
class OpPayrollPayment(db.Model):
    __tablename__ = 'op_payroll_payments'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('op_employees.id'), nullable=False, index=True)
    payment_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── Lenders (loans) ───────────────────────
class OpLender(db.Model):
    __tablename__ = 'op_lenders'

    id = db.Column(db.Integer, primary_key=True)
    lender_name = db.Column(db.String(200), nullable=False, index=True)
    original_amount = db.Column(db.Numeric(12, 2), nullable=False)
    loan_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship(
        'OpLoanPayment',
        backref='lender',
        cascade='all, delete-orphan',
        order_by='OpLoanPayment.payment_date.desc()',
    )

    @property
    def total_paid(self) -> float:
        return float(sum((p.amount or 0) for p in self.payments))

    @property
    def balance(self) -> float:
        return float(self.original_amount or 0) - self.total_paid

    @property
    def payment_count(self) -> int:
        return len(self.payments)

    @property
    def last_payment_date(self):
        return self.payments[0].payment_date if self.payments else None


# ─────────────────────── Loan Payments ───────────────────────
class OpLoanPayment(db.Model):
    __tablename__ = 'op_loan_payments'

    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(db.Integer, db.ForeignKey('op_lenders.id'), nullable=False, index=True)
    payment_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── Expense Categories ───────────────────────
class OpExpenseCategory(db.Model):
    __tablename__ = 'op_expense_categories'
    __table_args__ = (
        db.UniqueConstraint('category_name', 'item_name', name='uq_op_category_item'),
    )

    id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(120), nullable=False, index=True)
    item_name = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def display_label(self) -> str:
        return f'{self.category_name} — {self.item_name}'


# ─────────────────────── Monthly Expenses ───────────────────────
class OpMonthlyExpense(db.Model):
    __tablename__ = 'op_monthly_expenses'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('op_expense_categories.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Optional receipt/invoice file (stored under app/static/uploads/op_finance/)
    attachment_path = db.Column(db.String(500), nullable=True)
    attachment_filename = db.Column(db.String(255), nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('OpExpenseCategory')


# ─────────────────────── Fixed Expenses (reference only) ───────────────────────
class OpFixedExpense(db.Model):
    __tablename__ = 'op_fixed_expenses'

    id = db.Column(db.Integer, primary_key=True)
    expense_name = db.Column(db.String(200), nullable=False)
    estimated_amount = db.Column(db.Numeric(12, 2), nullable=True)
    recurrence = db.Column(db.String(20), nullable=False)  # monthly / yearly / lifetime
    month_if_yearly = db.Column(db.Integer, nullable=True)  # 1-12, when recurrence == yearly
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── Income (manual entries) ───────────────────────
class OpIncome(db.Model):
    __tablename__ = 'op_incomes'

    id = db.Column(db.Integer, primary_key=True)
    income_date = db.Column(db.Date, nullable=False, index=True)
    source_label = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── Audit Log (separate from AdminAuditLog) ───────────────────────
class OpFinanceAuditLog(db.Model):
    __tablename__ = 'op_finance_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    action_type = db.Column(db.String(60), nullable=False, index=True)  # CREATE / UPDATE / DELETE
    entity_type = db.Column(db.String(60), nullable=False, index=True)  # OpEmployee / OpPayrollPayment / ...
    entity_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    description = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
