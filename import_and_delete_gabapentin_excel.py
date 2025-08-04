import pandas as pd
import sqlite3
import os
import sys
import logging

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# قائمة بملفات الإكسيل المراد استيرادها
excel_files = ["Book1.xlsx", "drugs.xlsx"]

# دالة لقراءة ملف إكسيل
def read_excel_file(file_path):
    if not os.path.exists(file_path):
        logger.error(f"ملف الإكسيل '{file_path}' غير موجود في مجلد المشروع!")
        return None
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        logger.info(f"تم قراءة ملف {file_path} بنجاح، عدد الصفوف: {len(df)}")
        logger.info(f"أسماء الأعمدة الأصلية في {file_path}: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الإكسيل {file_path}: {e}")
        return None

# تحويل الأعمدة إلى أسماء باللغة الإنجليزية لتتطابق مع قاعدة البيانات
column_mapping = {
    'الاسم التجاري': 'name',
    'المادة الفعالة': 'active_ingredient',
    'التركيز': 'concentration',
    'الشكل الصيدلي': 'form',
    'السعر': 'price',
    'الشركة المصنعة': 'manufacturer',
    'الفئة': 'category',
    'الاستخدامات': 'uses',
    'موانع الاستخدام': 'contraindications',
    'احتياطات الاستخدام': 'precautions',
    'التدخلات الدوائية': 'interactions',
    'ظروف التخزين': 'storage_conditions',
    'كيفية الاستخدام': 'how_to_use'
}

# فتح قاعدة البيانات
try:
    conn = sqlite3.connect('drugs.db')
    c = conn.cursor()
    logger.info("تم فتح قاعدة البيانات بنجاح")
except sqlite3.Error as e:
    logger.error(f"خطأ في فتح قاعدة البيانات: {e}")
    sys.exit(1)

# حذف كل البيانات القديمة من جدول drugs
try:
    c.execute("DELETE FROM drugs")
    conn.commit()
    logger.info("تم حذف كل البيانات القديمة من جدول drugs بنجاح")
except sqlite3.Error as e:
    logger.error(f"خطأ في حذف البيانات القديمة: {e}")
    conn.close()
    sys.exit(1)

# دالة لإضافة دواء إلى قاعدة البيانات
def add_drug_to_db(drug_data, conn):
    c = conn.cursor()
    try:
        name = drug_data.get('name', '').strip()
        # التأكد من وجود مسافة بين الاسم العربي والإنجليزي
        if ' ' not in name:
            name = f"{name} {name}"  # إذا مفيش اسم إنجليزي، كرر العربي (أو العكس)
        c.execute('''INSERT INTO drugs (
                        name, active_ingredient, concentration, form, price, manufacturer,
                        category, uses, contraindications, precautions, interactions,
                        storage_conditions, how_to_use
                     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (
                      name,
                      drug_data.get('active_ingredient', ''),
                      drug_data.get('concentration', ''),
                      drug_data.get('form', ''),
                      float(drug_data.get('price', 0)),
                      drug_data.get('manufacturer', ''),
                      drug_data.get('category', 'غير متوفر'),
                      drug_data.get('uses', 'غير متوفر'),
                      drug_data.get('contraindications', 'غير متوفر'),
                      drug_data.get('precautions', 'غير متوفر'),
                      drug_data.get('interactions', 'غير متوفر'),
                      drug_data.get('storage_conditions', 'غير متوفر'),
                      drug_data.get('how_to_use', 'غير متوفر')
                  ))
        conn.commit()
        logger.info(f"تم إضافة {name} بنجاح")
    except sqlite3.Error as e:
        logger.error(f"خطأ في إضافة {name}: {e}")

# معالجة كل ملف إكسيل
for excel_file in excel_files:
    df = read_excel_file(excel_file)
    if df is None:
        continue

    # إزالة المسافات البيضاء من أسماء الأعمدة
    df.columns = df.columns.str.strip()
    logger.info(f"أسماء الأعمدة بعد إزالة المسافات في {excel_file}: {list(df.columns)}")

    # إعادة تسمية الأعمدة
    df.rename(columns=column_mapping, inplace=True)
    logger.info(f"أسماء الأعمدة بعد إعادة التسمية في {excel_file}: {list(df.columns)}")

    # التحقق من وجود الأعمدة المطلوبة
    required_columns = ['name', 'active_ingredient', 'concentration', 'form', 'price', 'manufacturer']
    if not all(col in df.columns for col in required_columns):
        logger.error(f"ملف الإكسيل {excel_file} يجب أن يحتوي على الأعمدة: {required_columns}")
        logger.error(f"الأعمدة الفعلية بعد إعادة التسمية: {list(df.columns)}")
        continue

    # معالجة كل صف في ملف الإكسيل
    for index, row in df.iterrows():
        drug_data = {
            'name': str(row.get('name', '')),
            'active_ingredient': str(row.get('active_ingredient', '')),
            'concentration': str(row.get('concentration', '')),
            'form': str(row.get('form', '')),
            'price': float(row.get('price', 0)) if pd.notnull(row.get('price')) else 0,
            'manufacturer': str(row.get('manufacturer', '')),
            'category': str(row.get('category', '')),
            'uses': str(row.get('uses', '')),
            'contraindications': str(row.get('contraindications', '')),
            'precautions': str(row.get('precautions', '')),
            'interactions': str(row.get('interactions', '')),
            'storage_conditions': str(row.get('storage_conditions', '')),
            'how_to_use': str(row.get('how_to_use', ''))
        }

        # تجاهل الصف إذا كانت القيم الأساسية (مثل الاسم أو التركيز) فارغة
        if not drug_data['name'] or not drug_data['concentration']:
            logger.warning(f"تخطي الصف {index + 2} في {excel_file}: بيانات غير مكتملة (الاسم: '{drug_data['name']}', التركيز: '{drug_data['concentration']}')")
            continue

        add_drug_to_db(drug_data, conn)

# إغلاق قاعدة البيانات
conn.close()
logger.info("تم إغلاق قاعدة البيانات بنجاح.")