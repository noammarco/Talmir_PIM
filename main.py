import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
from datetime import datetime
import config
from adapters import farnell_adapter
from logic import slot_manager, recalculator, currency_manager
from utils import excel_manager, assets_manager

# --- פונקציית עזר לתיקון הנתונים ---
def sanitize_row_data(row_data):
    clean_data = {}
    for k, v in row_data.items():
        if v is None:
            clean_data[k] = ""
        else:
            clean_data[k] = str(v)
    return clean_data

# --- פונקציית חיפוש מבוססת מק"ט יצרן ---
def find_row_in_db(df_db, mpn_from_api, input_search_term):
    """
    מחפש את השורה ב-DB לפי סדר עדיפויות:
    1. חיפוש לפי מק"ט יצרן (MPN) - העוגן האמיתי.
    2. חיפוש לפי מק"ט ספק (במקרה של כישלון API או חוסר ב-MPN).
    """
    # 1. חיפוש לפי MPN (מק"ט יצרן)
    if mpn_from_api:
        # מנקים רווחים כדי לוודא התאמה
        clean_mpn = str(mpn_from_api).strip()
        # מסננים ב-DB איפה שיש התאמה בעמודת היצרן
        matches = df_db.index[df_db['Manufacturer Part Number'] == clean_mpn].tolist()
        if matches:
            return matches[0]

    # 2. חיפוש לפי מק"ט ספק (Fallback)
    # סורקים את עמודות הספקים כדי לראות אם הקלט (למשל 654321) קיים אצל פארנל
    if input_search_term:
        clean_input = str(input_search_term).strip()
        for i in range(1, config.MAX_SUPPLIERS + 1):
            supplier_sku_col = f"Supplier {i} SKU"
            supplier_name_col = f"Supplier {i} Name"
            
            # בדיקה: המק"ט תואם לקלט AND שם הספק הוא FARNELL
            matches = df_db.index[
                (df_db[supplier_sku_col] == clean_input) & 
                (df_db[supplier_name_col] == 'FARNELL')
            ].tolist()
            
            if matches:
                return matches[0]

    return None

# --- פונקציה למילוי נתונים סטטיים (רק למוצר חדש!) ---
def fill_static_data(row_data, api_data):
    """
    ממלאת שדות כמו שם, יצרן, תיאור, ומק"ט פנימי ראשוני.
    פונקציה זו רצה אך ורק כשנוצרת שורה חדשה.
    """
    # מיפוי ידני של השדות הסטטיים לפי config.FIELD_MAPPING
    row_data['Product Name'] = api_data.get('1_Product_Name', '')
    row_data['SKU'] = api_data.get('2_My_SKU', '') # מק"ט התחלתי (היפוך), המשתמש יכול לשנות אח"כ
    row_data['Manufacturer'] = api_data.get('4_Manufacturer', '')
    row_data['Manufacturer Part Number'] = api_data.get('4a_MPN', '')
    row_data['Description'] = api_data.get('9_Short_Description', '')
    row_data['Hazardous'] = api_data.get('Hazardous', '')
    row_data['US Stock'] = api_data.get('is_us_stock', '')
    # Image ו-Datasheet מטופלים בנפרד ע"י assets_manager
    return row_data

def main():
    print("--- 🚀 Talmir PIM: Start Update Process (Multi-Vendor) ---")
    
    rates = {
        'GBP': currency_manager.get_rate('GBP'),
        'USD': currency_manager.get_rate('USD'),
        'EUR': currency_manager.get_rate('EUR')
    }
    
    df_db = excel_manager.load_or_create_db()
    
    try:
        df_input = pd.read_excel(config.INPUT_FILENAME, dtype=str)
        input_skus = df_input['SKU'].dropna().str.strip().tolist()
        print(f"📋 Loaded {len(input_skus)} SKUs from input.")
    except FileNotFoundError:
        print(f"❌ Error: '{config.INPUT_FILENAME}' not found.")
        return

    updated_count = 0
    skipped_count = 0
    new_products_count = 0

    for i, input_sku in enumerate(input_skus):
        print(f"[{i+1}/{len(input_skus)}] Processing SKU: {input_sku}...", end=" ")
        
        # 1. שליפת נתונים
        data = farnell_adapter.fetch_product_data(input_sku)
        
        # 2. זיהוי השורה ב-DB (לפי MPN או מק"ט ספק)
        mpn_from_api = data.get('4a_MPN') if data else None
        
        # קריאה לפונקציית החיפוש החדשה
        row_index = find_row_in_db(df_db, mpn_from_api, input_sku)
        
        row_data = None
        is_new_product = False

        if row_index is not None:
            # מוצר קיים
            row_data = df_db.iloc[row_index].to_dict()
        else:
            # מוצר חדש
            is_new_product = True
            row_data = {col: "" for col in config.FINAL_COLUMNS} # שורה ריקה

        # --- תרחיש א': ה-API לא החזיר נתונים (Not Found) ---
        if not data:
            if not is_new_product:
                # מצאנו את המוצר ב-DB (לפי מק"ט ספק בקלט), אבל ה-API החזיר כלום.
                print(f"⚠️ Not found in Farnell (Updating Status)...", end=" ")
                
                row_data = slot_manager.mark_supplier_not_found(row_data, 'FARNELL')
                row_data = recalculator.recalculate_row(row_data, rates)
                row_data = sanitize_row_data(row_data) 
                
                df_db.iloc[row_index] = pd.Series(row_data)
                updated_count += 1
                print("Done (Updated to Not Found).")
            else:
                # מוצר חדש + לא נמצא ב-API -> אין מה לעשות איתו
                print(f"⏭️ Skipped (Not found & New).")
                skipped_count += 1
            continue

        # --- תרחיש ב': ה-API החזיר נתונים ---
        
        # שומר הסף (Gatekeeper) למוצרים חדשים בלבד
        if is_new_product:
            calculated_status = slot_manager.determine_detailed_status(data)
            if calculated_status != config.STATUS_VALID:
                print(f"⛔ Skipped (New & Invalid Status: {calculated_status}).")
                skipped_count += 1
                continue
            
            # --- מילוי נתונים סטטיים (רק למוצר חדש!) ---
            # כאן אנחנו ממלאים את השם, היצרן, והמק"ט הפנימי הראשוני
            row_data = fill_static_data(row_data, data)
            print("✨ New Product...", end=" ")
            new_products_count += 1
        else:
            print("🔄 Updating Existing...", end=" ")

        # ניהול נכסים (תמונות)
        # לוגיקה: מורידים רק אם אין תמונה קיימת בשורה
        my_sku_for_file = row_data.get('SKU', 'unknown') # משתמשים במק"ט הפנימי הקיים (או החדש)
        
        image_url = data.get('Extra_Image')
        if image_url:
            existing_img = row_data.get('Image')
            if not existing_img:
                local_image_path = assets_manager.download_image(image_url, my_sku_for_file)
                row_data['Image'] = local_image_path 
            # אחרת: משאירים את התמונה הקיימת ולא דורסים!

        ds_url = data.get('Extra_Datasheet')
        if ds_url:
            existing_ds = row_data.get('Datasheet')
            if not existing_ds:
                local_ds_path = assets_manager.download_datasheet(ds_url, my_sku_for_file)
                row_data['Datasheet'] = local_ds_path
            # אחרת: משאירים את הקיים

        # עדכון ה-Slots (נתוני הספק)
        # זה קורה תמיד (גם בחדש וגם בקיים)
        row_data = slot_manager.update_product_slots(row_data, data, 'FARNELL')

        # חישוב מנצח
        row_data = recalculator.recalculate_row(row_data, rates)

        # שמירה
        row_data = sanitize_row_data(row_data)

        if not is_new_product:
            df_db.iloc[row_index] = pd.Series(row_data)
        else:
            df_row = pd.DataFrame([row_data])
            df_db = pd.concat([df_db, df_row], ignore_index=True)
        
        updated_count += 1
        print("✅ Done.")

    # שמירה סופית
    if updated_count > 0:
        excel_manager.save_styled_db(df_db, rates)
        print(f"\n🎉 Process Complete Summary:")
        print(f"   - Processed/Updated: {updated_count}")
        print(f"   - New Products Added: {new_products_count}")
        print(f"   - Skipped: {skipped_count}")
    else:
        print("\n⚠️ No changes were made to the database.")

if __name__ == "__main__":
    main()