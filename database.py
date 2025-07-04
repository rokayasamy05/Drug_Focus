# database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('drugs.db')
    c = conn.cursor()
    
    # إنشاء الجدول إذا لم يكن موجودًا بالفعل
    c.execute('''CREATE TABLE IF NOT EXISTS drugs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  active_ingredient TEXT,
                  concentration TEXT,
                  form TEXT,
                  price REAL,
                  manufacturer TEXT,
                  category TEXT,
                  uses TEXT,
                  contraindications TEXT,
                  precautions TEXT,
                  interactions TEXT,
                  storage_conditions TEXT,
                  how_to_use TEXT)''')
    conn.commit()
    conn.close()
    print("تم التأكد من وجود جدول drugs في قاعدة البيانات drugs.db.")
    print("الآن يمكنك إضافة أو تحديث أو حذف الأدوية باستخدام الـ API أو أداة SQLite.")

if __name__ == '__main__':
    init_db()