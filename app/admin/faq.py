"""FAQ Admin — إدارة قاعدة معرفة المحامي الذكي."""
import psycopg2
import psycopg2.extras
from flask import render_template_string, request, redirect, url_for, flash, g
from app.admin import admin_bp
from app.admin.decorators import super_admin_required

FAQ_DB = {
    'host': '172.18.0.4',
    'dbname': 'lexoffice_ai',
    'user': 'n8n',
    'password': '1246964b132e43a62b441892e0d6786fcd7008142259ba470c05dee35a153fbe',
}

def get_faq_conn():
    return psycopg2.connect(**FAQ_DB)

HTML = """
{% extends 'admin/base.html' %}
{% block title %}إدارة FAQ — المحامي الذكي{% endblock %}
{% block content %}
<div class="container-fluid py-4" dir="rtl">
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h3 class="mb-0">🤖 قاعدة معرفة المحامي الذكي</h3>
    <a href="{{ url_for('admin.faq_new') }}" class="btn btn-primary">+ إضافة سؤال</a>
  </div>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in messages %}
      <div class="alert alert-{{ 'success' if cat == 'success' else 'danger' }}">{{ msg }}</div>
    {% endfor %}
  {% endwith %}
  <div class="mb-3">
    <form method="get" class="d-flex gap-2 align-items-center">
      <label class="mb-0">الفئة:</label>
      <select name="cat" class="form-select w-auto" onchange="this.form.submit()">
        <option value="">الكل</option>
        {% for c in categories %}
          <option value="{{ c.id }}" {{ 'selected' if request.args.get('cat')|int == c.id }}>{{ c.name }}</option>
        {% endfor %}
      </select>
      <label class="mb-0 me-2">الحالة:</label>
      <select name="status" class="form-select w-auto" onchange="this.form.submit()">
        <option value="">الكل</option>
        <option value="active" {{ 'selected' if request.args.get('status') == 'active' }}>فعّال</option>
        <option value="inactive" {{ 'selected' if request.args.get('status') == 'inactive' }}>معطّل</option>
      </select>
    </form>
  </div>
  <div class="card shadow-sm">
    <div class="card-body p-0">
      <table class="table table-hover mb-0">
        <thead class="table-light">
          <tr><th>#</th><th>الفئة</th><th>السؤال</th><th>الإجابة</th><th>الأولوية</th><th>الحالة</th><th>إجراءات</th></tr>
        </thead>
        <tbody>
          {% for e in entries %}
          <tr>
            <td>{{ e.id }}</td>
            <td><span class="badge bg-secondary">{{ e.cat_name or '—' }}</span></td>
            <td style="max-width:250px">{{ e.question }}</td>
            <td style="max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ e.answer[:80] }}{% if e.answer|length > 80 %}...{% endif %}</td>
            <td>{{ e.priority }}</td>
            <td>{% if e.is_active %}<span class="badge bg-success">فعّال</span>{% else %}<span class="badge bg-danger">معطّل</span>{% endif %}</td>
            <td>
              <a href="{{ url_for('admin.faq_edit', id=e.id) }}" class="btn btn-sm btn-outline-primary">تعديل</a>
              <form method="post" action="{{ url_for('admin.faq_toggle', id=e.id) }}" class="d-inline">
                <button class="btn btn-sm btn-outline-{{ 'warning' if e.is_active else 'success' }}">{{ 'تعطيل' if e.is_active else 'تفعيل' }}</button>
              </form>
              <form method="post" action="{{ url_for('admin.faq_delete', id=e.id) }}" class="d-inline" onsubmit="return confirm('حذف السؤال ده؟')">
                <button class="btn btn-sm btn-outline-danger">حذف</button>
              </form>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="7" class="text-center text-muted py-4">مفيش نتايج</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  <div class="mt-2 text-muted small">إجمالي: {{ entries|length }} سؤال</div>
</div>
{% endblock %}
"""

FORM_HTML = """
{% extends 'admin/base.html' %}
{% block title %}{{ 'تعديل' if entry else 'إضافة' }} سؤال — FAQ{% endblock %}
{% block content %}
<div class="container py-4" dir="rtl" style="max-width:700px">
  <h4 class="mb-4">{{ 'تعديل' if entry else 'إضافة' }} سؤال</h4>
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="mb-3">
      <label class="form-label fw-bold">الفئة</label>
      <select name="category_id" class="form-select">
        <option value="">— بدون فئة —</option>
        {% for c in categories %}
          <option value="{{ c.id }}" {{ 'selected' if entry and entry.category_id == c.id }}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label fw-bold">السؤال *</label>
      <input type="text" name="question" class="form-control" required value="{{ entry.question if entry else '' }}">
    </div>
    <div class="mb-3">
      <label class="form-label fw-bold">الإجابة *</label>
      <textarea name="answer" class="form-control" rows="6" required>{{ entry.answer if entry else '' }}</textarea>
    </div>
    <div class="mb-3">
      <label class="form-label fw-bold">الكلمات المفتاحية (مفصولة بفاصلة)</label>
      <input type="text" name="keywords" class="form-control" value="{{ entry.keywords|join(', ') if entry and entry.keywords else '' }}">
    </div>
    <div class="mb-3">
      <label class="form-label fw-bold">الأولوية (1-10)</label>
      <input type="number" name="priority" class="form-control" min="1" max="10" value="{{ entry.priority if entry else 5 }}">
    </div>
    <div class="mb-4 form-check">
      <input type="checkbox" name="is_active" class="form-check-input" id="isActive" {{ 'checked' if not entry or entry.is_active }}>
      <label class="form-check-label" for="isActive">فعّال</label>
    </div>
    <div class="d-flex gap-2">
      <button type="submit" class="btn btn-primary">💾 حفظ</button>
      <a href="{{ url_for('admin.faq_list') }}" class="btn btn-outline-secondary">إلغاء</a>
    </div>
  </form>
</div>
{% endblock %}
"""

def get_categories(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, name FROM faq_categories ORDER BY name")
        return cur.fetchall()

@admin_bp.route('/faq')
@super_admin_required
def faq_list():
    conn = get_faq_conn()
    cats = get_categories(conn)
    cat_filter = request.args.get('cat', type=int)
    status_filter = request.args.get('status', '')
    query = "SELECT e.*, c.name as cat_name FROM faq_entries e LEFT JOIN faq_categories c ON e.category_id = c.id WHERE 1=1"
    params = []
    if cat_filter:
        query += " AND e.category_id = %s"
        params.append(cat_filter)
    if status_filter == 'active':
        query += " AND e.is_active = TRUE"
    elif status_filter == 'inactive':
        query += " AND e.is_active = FALSE"
    query += " ORDER BY e.priority DESC, e.id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        entries = cur.fetchall()
    conn.close()
    return render_template_string(HTML, entries=entries, categories=cats, request=request)

@admin_bp.route('/faq/new', methods=['GET', 'POST'])
@super_admin_required
def faq_new():
    conn = get_faq_conn()
    cats = get_categories(conn)
    if request.method == 'POST':
        kw = [k.strip() for k in request.form.get('keywords', '').split(',') if k.strip()]
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO faq_entries (category_id, question, answer, keywords, priority, is_active) VALUES (%s,%s,%s,%s,%s,%s)",
                (request.form.get('category_id') or None, request.form['question'].strip(),
                 request.form['answer'].strip(), kw or None, int(request.form.get('priority', 5)), 'is_active' in request.form)
            )
        conn.commit()
        conn.close()
        flash('تم إضافة السؤال بنجاح ✅', 'success')
        return redirect(url_for('admin.faq_list'))
    conn.close()
    return render_template_string(FORM_HTML, entry=None, categories=cats)

@admin_bp.route('/faq/<int:id>/edit', methods=['GET', 'POST'])
@super_admin_required
def faq_edit(id):
    conn = get_faq_conn()
    cats = get_categories(conn)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM faq_entries WHERE id = %s", (id,))
        entry = cur.fetchone()
    if not entry:
        conn.close()
        flash('السؤال مش موجود', 'danger')
        return redirect(url_for('admin.faq_list'))
    if request.method == 'POST':
        kw = [k.strip() for k in request.form.get('keywords', '').split(',') if k.strip()]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE faq_entries SET category_id=%s,question=%s,answer=%s,keywords=%s,priority=%s,is_active=%s,updated_at=NOW() WHERE id=%s",
                (request.form.get('category_id') or None, request.form['question'].strip(),
                 request.form['answer'].strip(), kw or None, int(request.form.get('priority', 5)),
                 'is_active' in request.form, id)
            )
        conn.commit()
        conn.close()
        flash('تم التعديل بنجاح ✅', 'success')
        return redirect(url_for('admin.faq_list'))
    conn.close()
    return render_template_string(FORM_HTML, entry=entry, categories=cats)

@admin_bp.route('/faq/<int:id>/toggle', methods=['POST'])
@super_admin_required
def faq_toggle(id):
    conn = get_faq_conn()
    with conn.cursor() as cur:
        cur.execute("UPDATE faq_entries SET is_active = NOT is_active WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    flash('تم تغيير الحالة ✅', 'success')
    return redirect(url_for('admin.faq_list'))

@admin_bp.route('/faq/<int:id>/delete', methods=['POST'])
@super_admin_required
def faq_delete(id):
    conn = get_faq_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM faq_entries WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    flash('تم الحذف ✅', 'success')
    return redirect(url_for('admin.faq_list'))
