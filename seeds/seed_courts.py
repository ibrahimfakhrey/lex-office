"""Seed Egyptian courts list."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.case import Court
from app.utils.constants import CourtType

COURTS = [
    # محاكم النقض
    {'name': 'محكمة النقض', 'name_en': 'Court of Cassation', 'court_type': CourtType.CASSATION.value, 'governorate': 'القاهرة', 'market': 'eg'},

    # محاكم الاستئناف
    {'name': 'محكمة استئناف القاهرة', 'name_en': 'Cairo Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'القاهرة'},
    {'name': 'محكمة استئناف الإسكندرية', 'name_en': 'Alexandria Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'الإسكندرية'},
    {'name': 'محكمة استئناف طنطا', 'name_en': 'Tanta Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'طنطا'},
    {'name': 'محكمة استئناف المنصورة', 'name_en': 'Mansoura Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'المنصورة'},
    {'name': 'محكمة استئناف الإسماعيلية', 'name_en': 'Ismailia Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'الإسماعيلية'},
    {'name': 'محكمة استئناف بني سويف', 'name_en': 'Beni Suef Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'بني سويف'},
    {'name': 'محكمة استئناف أسيوط', 'name_en': 'Assiut Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'أسيوط'},
    {'name': 'محكمة استئناف قنا', 'name_en': 'Qena Court of Appeal', 'court_type': CourtType.APPEAL.value, 'governorate': 'قنا'},

    # محاكم ابتدائية (عينة من المحاكم الرئيسية)
    {'name': 'محكمة شمال القاهرة الابتدائية', 'name_en': 'North Cairo Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'القاهرة'},
    {'name': 'محكمة جنوب القاهرة الابتدائية', 'name_en': 'South Cairo Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'القاهرة'},
    {'name': 'محكمة الجيزة الابتدائية', 'name_en': 'Giza Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'الجيزة'},
    {'name': 'محكمة الإسكندرية الابتدائية', 'name_en': 'Alexandria Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'الإسكندرية'},
    {'name': 'محكمة طنطا الابتدائية', 'name_en': 'Tanta Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'طنطا'},
    {'name': 'محكمة المنصورة الابتدائية', 'name_en': 'Mansoura Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'المنصورة'},
    {'name': 'محكمة الزقازيق الابتدائية', 'name_en': 'Zagazig Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'الزقازيق'},
    {'name': 'محكمة بنها الابتدائية', 'name_en': 'Benha Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'بنها'},
    {'name': 'محكمة دمنهور الابتدائية', 'name_en': 'Damanhur Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'دمنهور'},
    {'name': 'محكمة أسيوط الابتدائية', 'name_en': 'Assiut Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'أسيوط'},
    {'name': 'محكمة سوهاج الابتدائية', 'name_en': 'Sohag Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'سوهاج'},
    {'name': 'محكمة الأقصر الابتدائية', 'name_en': 'Luxor Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'الأقصر'},
    {'name': 'محكمة أسوان الابتدائية', 'name_en': 'Aswan Court', 'court_type': CourtType.PRIMARY.value, 'governorate': 'أسوان'},

    # محاكم اقتصادية
    {'name': 'المحكمة الاقتصادية بالقاهرة', 'name_en': 'Cairo Economic Court', 'court_type': CourtType.ECONOMIC.value, 'governorate': 'القاهرة'},
    {'name': 'المحكمة الاقتصادية بالإسكندرية', 'name_en': 'Alexandria Economic Court', 'court_type': CourtType.ECONOMIC.value, 'governorate': 'الإسكندرية'},

    # محاكم الأسرة
    {'name': 'محكمة الأسرة بالقاهرة', 'name_en': 'Cairo Family Court', 'court_type': CourtType.FAMILY.value, 'governorate': 'القاهرة'},
    {'name': 'محكمة الأسرة بالجيزة', 'name_en': 'Giza Family Court', 'court_type': CourtType.FAMILY.value, 'governorate': 'الجيزة'},
    {'name': 'محكمة الأسرة بالإسكندرية', 'name_en': 'Alexandria Family Court', 'court_type': CourtType.FAMILY.value, 'governorate': 'الإسكندرية'},

    # محاكم إدارية
    {'name': 'محكمة القضاء الإداري', 'name_en': 'Administrative Court', 'court_type': CourtType.STATE_COUNCIL.value, 'governorate': 'القاهرة'},
    {'name': 'المحكمة الإدارية العليا', 'name_en': 'Supreme Administrative Court', 'court_type': CourtType.STATE_COUNCIL.value, 'governorate': 'القاهرة'},

    # محاكم عسكرية
    {'name': 'المحكمة العسكرية العليا', 'name_en': 'Supreme Military Court', 'court_type': CourtType.MILITARY.value, 'governorate': 'القاهرة'},

    # المحكمة الدستورية
    {'name': 'المحكمة الدستورية العليا', 'name_en': 'Supreme Constitutional Court', 'court_type': CourtType.CONSTITUTIONAL.value, 'governorate': 'القاهرة'},
]


def seed():
    with app.app_context():
        count = 0
        backfilled = 0
        for court_data in COURTS:
            data = dict(court_data)
            data.setdefault('market', 'eg')
            existing = Court.query.filter_by(name=data['name']).first()
            if not existing:
                db.session.add(Court(**data))
                count += 1
            elif existing.market != data['market']:
                # Backfill market on legacy rows seeded before multi-market support.
                existing.market = data['market']
                backfilled += 1
        db.session.commit()
        msg = f"Seeded {count} EG courts"
        if backfilled:
            msg += f" (+{backfilled} backfilled with market='eg')"
        msg += f" — total in DB: {Court.query.count()}."
        print(msg)


if __name__ == '__main__':
    seed()
