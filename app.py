# app.py

from flask import Flask, request, jsonify
import sqlite3
from flask_cors import CORS
import re
import logging

app = Flask(__name__)
CORS(app)

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


def get_db_connection():
    conn = sqlite3.connect('drugs.db')
    conn.row_factory = sqlite3.Row
    return conn

def normalize_arabic(text):
    if not isinstance(text, str):
        return text
    # توحيد أشكال الألف والياء والتاء المربوطة
    text = text.replace('أ', 'ا')
    text = text.replace('إ', 'ا')
    text = text.replace('آ', 'ا')
    text = text.replace('ى', 'ي')
    text = text.replace('ة', 'ه')
    return text

def reverse_concentration_format(concentration):
    if not concentration or not isinstance(concentration, str):
        return concentration
    
    concentration = concentration.lower().strip()

    # استبدال الكلمات العربية الشائعة بوحداتها الإنجليزية المكافئة
    concentration = concentration.replace('ملجم', 'mg')
    concentration = concentration.replace('مجم', 'mg')
    concentration = concentration.replace('جرام', 'gm')
    concentration = concentration.replace('جم', 'gm')
    concentration = concentration.replace('مللتر', 'ml')
    concentration = concentration.replace('مل', 'ml')
    concentration = concentration.replace('وحده', 'unit')
    concentration = concentration.replace('وحدة', 'unit')
    concentration = concentration.replace('ميكروجرام', 'mcg')
    concentration = concentration.replace('ميكروجم', 'mcg')
    concentration = concentration.replace('نانوجرام', 'ng')
    concentration = concentration.replace('نانوجم', 'ng')

    # إزالة المسافات لجعلها متجانسة للبحث
    concentration = re.sub(r'\s+', '', concentration)
    
    return concentration

@app.route('/api/drugs', methods=['GET'])
def get_drugs():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        search = request.args.get('search', '').lower().strip()
        search_type = request.args.get('searchType', 'trade')
        concentration = request.args.get('concentration', '').lower().strip()
        manufacturer = request.args.get('manufacturer', '').lower().strip()
        form = request.args.get('form', '').strip()
        item_count = request.args.get('itemCount', '').strip() # لا تزال تأتي كمعامل منفصل
        price = float(request.args.get('price', 1000))
        sort_by = request.args.get('sortBy', 'name').lower()
        sort_order = request.args.get('sortOrder', 'asc').upper()
        exact_match = request.args.get('exactMatch', 'false').lower() == 'true'

        query = 'SELECT * FROM drugs WHERE price <= ?'
        params = [price]

        # دالة SQL لتوحيد النصوص العربية (وغير العربية) في الأعمدة للبحث
        normalize_column_sql = "LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(?, 'أ', 'ا'), 'إ', 'ا'), 'آ', 'ا'), 'ى', 'ي'), 'ة', 'ه'))"

        if search:
            normalized_search_term = normalize_arabic(search)
            if search_type == 'trade':
                # البحث في الاسم التجاري
                query += f" AND ({normalize_column_sql.replace('?', 'name')} LIKE ? OR {normalize_column_sql.replace('?', 'SUBSTR(name, INSTR(name, \' \') + 1)')} LIKE ?)"
                params.append(f'%{normalized_search_term}%')
                params.append(f'%{normalized_search_term}%')
            elif search_type == 'active':
                # البحث في المادة الفعالة
                query += f" AND {normalize_column_sql.replace('?', 'active_ingredient')} LIKE ?"
                params.append(f'%{normalized_search_term}%')

        if concentration:
            normalized_concentration_for_search = reverse_concentration_format(concentration)

            replacements = [
                ("'ملجم'", "'mg'"), ("'مجم'", "'mg'"),
                ("'جرام'", "'gm'"), ("'جم'", "'gm'"),
                ("'مللتر'", "'ml'"), ("'مل'", "'ml'"),
                ("'وحده'", "'unit'"), ("'وحدة'", "'unit'"),
                ("'ميكروجرام'", "'mcg'"), ("'ميكروجم'", "'mcg'"),
                ("'نانوجرام'", "'ng'"), ("'نانوجم'", "'ng'"),
                ("' '", "''") 
            ]
            
            concentration_column_sql_processed = "LOWER(concentration)"
            for old, new in replacements:
                concentration_column_sql_processed = f"REPLACE({concentration_column_sql_processed}, {old}, {new})"

            final_normalized_concentration_column_sql = normalize_column_sql.replace('?', concentration_column_sql_processed)

            if exact_match:
                query += f" AND {final_normalized_concentration_column_sql} = ?"
                params.append(normalized_concentration_for_search)
            else:
                query += f" AND {final_normalized_concentration_column_sql} LIKE ?"
                params.append(f'%{normalized_concentration_for_search}%')

        if manufacturer:
            normalized_manufacturer_input = normalize_arabic(manufacturer)
            
            # تنظيف حقل المصنع لإزالة الأقواس أو الرموز الزائدة
            manufacturer_cleaned_sql_initial = (
                "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(manufacturer, ' < ', '<'), '< ', '<'), ' <', '<'), "
                "' > ', '>'), '> ', '>'), ' >', '>') "
            )
            manufacturer_cleaned_sql = f"REPLACE({manufacturer_cleaned_sql_initial}, '>', '<')"

            query += f" AND (" \
                     f"{normalize_column_sql.replace('?', 'TRIM(SUBSTR(' + manufacturer_cleaned_sql + ', 1, INSTR(' + manufacturer_cleaned_sql + ', \'<\') - 1))')} LIKE ? OR " \
                     f"({normalize_column_sql.replace('?', 'TRIM(SUBSTR(' + manufacturer_cleaned_sql + ', INSTR(' + manufacturer_cleaned_sql + ', \'<\') + 1))')} LIKE ? AND INSTR({manufacturer_cleaned_sql}, \'<\') > 0) OR " \
                     f"({normalize_column_sql.replace('?', 'TRIM(' + manufacturer_cleaned_sql + ')')} LIKE ? AND INSTR({manufacturer_cleaned_sql}, \'<\') = 0)" \
                     f")"
            
            params.append(f'{normalized_manufacturer_input}%') 
            params.append(f'{normalized_manufacturer_input}%') 
            params.append(f'{normalized_manufacturer_input}%') 

        if form:
            normalized_form_input = normalize_arabic(form).lower()
            
            form_conditions = []
            form_params = []

            # تعريف الكلمات المفتاحية بالترتيب الذي تريده (قرص أولاً، ثم أقراص، ثم tablet، ثم tablets)
            tablet_ar_single = 'قرص'
            tablet_ar_plural = 'اقراص'
            tablet_en_single = 'tablet'
            tablet_en_plural = 'tablets'

            capsule_ar_single = 'كبسول'
            capsule_ar_plural = 'كبسولات'
            capsule_en_single = 'capsule'
            capsule_en_plural = 'capsules'

            if 'اقراص' in normalized_form_input:
                if item_count and item_count.isdigit():
                    # البحث عن "العدد + قرص/أقراص/tablet/tablets"
                    search_patterns = [
                        f'{item_count} {normalize_arabic(tablet_ar_single)}',
                        f'{item_count} {normalize_arabic(tablet_ar_plural)}',
                        f'{item_count} {tablet_en_single}',
                        f'{item_count} {tablet_en_plural}',
                        # نضيف أيضاً احتمال عدم وجود مسافة بين العدد والشكل (مثلاً "14قرص")
                        f'{item_count}{normalize_arabic(tablet_ar_single)}',
                        f'{item_count}{normalize_arabic(tablet_ar_plural)}',
                        f'{item_count}{tablet_en_single}',
                        f'{item_count}{tablet_en_plural}'
                    ]
                    for pattern in search_patterns:
                        form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                        form_params.append(f'{pattern}%') # نستخدم % في النهاية للبحث عن بداية السلسلة
                else:
                    # البحث عن "قرص/أقراص/tablet/tablets" فقط بدون عدد
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{normalize_arabic(tablet_ar_single)}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{normalize_arabic(tablet_ar_plural)}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{tablet_en_single}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{tablet_en_plural}%')

            elif 'كبسولات' in normalized_form_input:
                if item_count and item_count.isdigit():
                    # البحث عن "العدد + كبسول/كبسولات/capsule/capsules"
                    search_patterns = [
                        f'{item_count} {normalize_arabic(capsule_ar_single)}',
                        f'{item_count} {normalize_arabic(capsule_ar_plural)}',
                        f'{item_count} {capsule_en_single}',
                        f'{item_count} {capsule_en_plural}',
                        # نضيف أيضاً احتمال عدم وجود مسافة بين العدد والشكل
                        f'{item_count}{normalize_arabic(capsule_ar_single)}',
                        f'{item_count}{normalize_arabic(capsule_ar_plural)}',
                        f'{item_count}{capsule_en_single}',
                        f'{item_count}{capsule_en_plural}'
                    ]
                    for pattern in search_patterns:
                        form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                        form_params.append(f'{pattern}%') # نستخدم % في النهاية للبحث عن بداية السلسلة
                else:
                    # البحث عن "كبسول/كبسولات/capsule/capsules" فقط بدون عدد
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{normalize_arabic(capsule_ar_single)}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{normalize_arabic(capsule_ar_plural)}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{capsule_en_single}%')
                    form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                    form_params.append(f'%{capsule_en_plural}%')

            # الأشكال الصيدلانية الأخرى (لم تتغير)
            elif 'فيال' in normalized_form_input:
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%فيال%')
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%vial%')
            elif 'محلول' in normalized_form_input:
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%محلول%')
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%solution%')
            elif 'شراب' in normalized_form_input:
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%شراب%')
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%syrup%')
            else:
                # بحث عام إذا لم يكن من الأشكال المعروفة
                form_conditions.append(f"{normalize_column_sql.replace('?', 'form')} LIKE ?")
                form_params.append(f'%{normalized_form_input}%')

            if form_conditions:
                query += f" AND ({' OR '.join(form_conditions)})"
                params.extend(form_params)

        # جزء الترتيب (Sort)
        if sort_by in ['name', 'concentration', 'price']:
            sort_column = sort_by
        else:
            sort_column = 'name'
        if sort_order not in ['ASC', 'DESC']:
            sort_order = 'ASC'
        query += f" ORDER BY {sort_column} {sort_order}"

        c.execute(query, params)
        drugs = c.fetchall()
        conn.close()

        return jsonify([{
            'id': drug['id'],
            'name': drug['name'],
            'active_ingredient': drug['active_ingredient'],
            'concentration': drug['concentration'],
            'form': drug['form'],
            'price': drug['price'],
            'manufacturer': drug['manufacturer'],
            'category': drug['category']
        } for drug in drugs])

    except Exception as e:
        app.logger.error("Error in get_drugs: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/api/drug/<int:drug_id>', methods=['GET'])
def get_drug(drug_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM drugs WHERE id = ?', (drug_id,))
        drug = c.fetchone()
        conn.close()

        if not drug:
            return jsonify({'error': 'الدواء غير موجود'}), 404

        return jsonify({
            'id': drug['id'],
            'name': drug['name'],
            'active_ingredient': drug['active_ingredient'],
            'concentration': drug['concentration'],
            'form': drug['form'],
            'price': drug['price'],
            'manufacturer': drug['manufacturer'],
            'category': drug['category'],
            'uses': drug['uses'],
            'contraindications': drug['contraindications'],
            'precautions': drug['precautions'],
            'interactions': drug['interactions'],
            'storage_conditions': drug['storage_conditions'],
            'how_to_use': drug['how_to_use']
        })

    except Exception as e:
        app.logger.error("Error in get_drug: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        query = request.args.get('query', '').lower().strip()
        search_type = request.args.get('type', 'trade')

        if not query:
            conn.close()
            return jsonify([])

        normalize_column_sql_suggestion = "LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(?, 'أ', 'ا'), 'إ', 'ا'), 'آ', 'ا'), 'ى', 'ي'), 'ة', 'ه'))"
        normalized_query = normalize_arabic(query)

        if search_type == 'trade':
            c.execute(f'''
                SELECT DISTINCT name
                FROM drugs
                WHERE
                    {normalize_column_sql_suggestion.replace("?", "name")} LIKE ? OR
                    {normalize_column_sql_suggestion.replace("?", "SUBSTR(name, INSTR(name, ' ') + 1)")} LIKE ?
                LIMIT 10
            ''', (f'{normalized_query}%', f'{normalized_query}%'))
        elif search_type == 'active':
            c.execute(f'''
                SELECT DISTINCT active_ingredient
                FROM drugs
                WHERE
                    {normalize_column_sql_suggestion.replace("?", "active_ingredient")} LIKE ? OR
                    {normalize_column_sql_suggestion.replace("?", "SUBSTR(active_ingredient, INSTR(active_ingredient, ' ') + 1)")} LIKE ?
                LIMIT 10
            ''', (f'{normalized_query}%', f'{normalized_query}%'))

        suggestions = [row[0] for row in c.fetchall() if row[0] and row[0].strip()]
        conn.close()
        return jsonify(suggestions)

    except Exception as e:
        app.logger.error("Error in get_suggestions: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/api/concentrations', methods=['GET'])
def get_concentrations():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        search = request.args.get('search', '').lower().strip()
        search_type = request.args.get('type', 'trade')

        query_main = 'SELECT DISTINCT concentration FROM drugs WHERE concentration IS NOT NULL'
        params = []
        
        replacements_for_suggestions = [
            ("'ملجم'", "'mg'"), ("'مجم'", "'mg'"),
            ("'جرام'", "'gm'"), ("'جم'", "'gm'"),
            ("'مللتر'", "'ml'"), ("'مل'", "'ml'"),
            ("'وحده'", "'unit'"), ("'وحدة'", "'unit'"),
            ("'ميكروجرام'", "'mcg'"), ("'ميكروجم'", "'mcg'"),
            ("'نانوجرام'", "'ng'"), ("'نانوجم'", "'ng'"),
            ("' '", "''")
        ]
        
        concentration_column_sql_processed_for_suggestions = "LOWER(concentration)"
        for old, new in replacements_for_suggestions:
            concentration_column_sql_processed_for_suggestions = f"REPLACE({concentration_column_sql_processed_for_suggestions}, {old}, {new})"

        normalize_column_sql_for_suggestions = "LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(?, 'أ', 'ا'), 'إ', 'ا'), 'آ', 'ا'), 'ى', 'ي'), 'ة', 'ه'))"
        final_normalized_concentration_column_sql_for_suggestions = normalize_column_sql_for_suggestions.replace('?', concentration_column_sql_processed_for_suggestions)


        if search:
            normalized_search_term = normalize_arabic(search)
            if search_type == 'trade':
                query_main += f" AND ({normalize_column_sql_for_suggestions.replace('?', 'name')} LIKE ? OR {normalize_column_sql_for_suggestions.replace('?', 'SUBSTR(name, INSTR(name, \' \') + 1)')} LIKE ?)"
                params.append(f'%{normalized_search_term}%')
                params.append(f'%{normalized_search_term}%')
            elif search_type == 'active':
                query_main += f" AND {normalize_column_sql_for_suggestions.replace('?', 'active_ingredient')} LIKE ?"
                params.append(f'%{normalized_search_term}%')

        c.execute(f'SELECT DISTINCT {final_normalized_concentration_column_sql_for_suggestions} AS normalized_concentration FROM drugs WHERE concentration IS NOT NULL', params)
        concentrations = [row['normalized_concentration'] for row in c.fetchall() if row['normalized_concentration'] and row['normalized_concentration'].strip()]
        conn.close()
        return jsonify(concentrations)

    except Exception as e:
        app.logger.error("Error in get_concentrations: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/api/drugs', methods=['POST'])
def add_drug():
    try:
        new_drug_data = request.json
        required_fields = ['name', 'active_ingredient', 'concentration', 'form', 'price', 'manufacturer']
        if not all(field in new_drug_data and new_drug_data[field] is not None for field in required_fields):
            return jsonify({'error': 'Please provide all essential fields (Trade Name, Active Ingredient, Concentration, Form, Price, Manufacturer).'}), 400

        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO drugs (name, active_ingredient, concentration, form, price, manufacturer,
                                        category, uses, contraindications, precautions, interactions,
                                        storage_conditions, how_to_use)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (new_drug_data.get('name'),
                   new_drug_data.get('active_ingredient'),
                   new_drug_data.get('concentration'),
                   new_drug_data.get('form'),
                   new_drug_data.get('price'),
                   new_drug_data.get('manufacturer'),
                   new_drug_data.get('category', 'N/A'),
                   new_drug_data.get('uses', 'N/A'),
                   new_drug_data.get('contraindications', 'N/A'),
                   new_drug_data.get('precautions', 'N/A'),
                   new_drug_data.get('interactions', 'N/A'),
                   new_drug_data.get('storage_conditions', 'N/A'),
                   new_drug_data.get('how_to_use', 'N/A')))
        conn.commit()
        drug_id = c.lastrowid
        conn.close()
        return jsonify({'message': 'Drug added successfully', 'id': drug_id}), 201
    except Exception as e:
        app.logger.error("Error in add_drug: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/api/drug/<int:drug_id>', methods=['PUT'])
def update_drug(drug_id):
    try:
        updated_data = request.json
        conn = get_db_connection()
        c = conn.cursor()

        set_clauses = []
        params = []
        allowed_fields = [
            'name', 'active_ingredient', 'concentration', 'form', 'price',
            'manufacturer', 'category', 'uses', 'contraindications', 'precautions',
            'interactions', 'storage_conditions', 'how_to_use'
        ]
        for key, value in updated_data.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return jsonify({'error': 'No valid data provided for update'}), 400

        params.append(drug_id)
        query = f"UPDATE drugs SET {', '.join(set_clauses)} WHERE id = ?"
        c.execute(query, params)
        conn.commit()

        if c.rowcount == 0:
            return jsonify({'error': 'Drug not found'}), 404

        conn.close()
        return jsonify({'message': 'Drug updated successfully'}), 200
    except Exception as e:
        app.logger.error("Error in update_drug: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/api/drug/<int:drug_id>', methods=['DELETE'])
def delete_drug(drug_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM drugs WHERE id = ?', (drug_id,))
        conn.commit()

        if c.rowcount == 0:
            return jsonify({'error': 'Drug not found'}), 404

        conn.close()
        return jsonify({'message': 'Drug deleted successfully'}), 200
    except Exception as e:
        app.logger.error("Error in delete_drug: %s", str(e))
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
    