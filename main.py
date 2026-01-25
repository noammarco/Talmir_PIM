import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
from datetime import datetime
import config
from adapters import farnell_adapter
from logic import slot_manager, recalculator, currency_manager
from utils import excel_manager, assets_manager

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
        
        # 1. שליפת נתונים מהספק
        data = farnell_adapter.fetch_product_data(input_sku)
        
        # הכנה לניהול השורה
        row_index = None
        row_data = None
        
        target_sku_for_search = data.get('2_My_SKU') if data else input_sku
        existing_indices = df_db.index[df_db['SKU'] == target_sku_for_search].tolist()
        
        if existing_indices:
            row_index = existing_indices[0]
            row_data = df_db.iloc[row_index].to_dict()
        
        # --- תרחיש א': ה-API לא החזיר נתונים ---
        if not data:
            if row_data:
                print(f"⚠️ Not found in Farnell (Updating Status)...", end=" ")
                row_data = slot_manager.mark_supplier_not_found(row_data, 'FARNELL')
                row_data = recalculator.recalculate_row(row_data)
                df_db.iloc[row_index] = pd.Series(row_data)
                updated_count += 1
                print("Done.")
            else:
                print(f"⏭️ Skipped (Not found & New).")
                skipped_count += 1
            continue

        # --- תרחיש ב': ה-API החזיר נתונים ---
        
        # === התיקון הקריטי: שומר הסף למוצרים חדשים ===
        # אם המוצר חדש, אנחנו בודקים את הסטטוס שלו לפני שממשיכים.
        if row_index is None:
            # נותנים ל-Slot Manager לחשב את הסטטוס המדויק (כולל לוגיקת ארה"ב, NLS וכו')
            calculated_status = slot_manager.determine_detailed_status(data)
            
            # אם הסטטוס הוא לא Valid (כלומר הוא NLM, NLS, או Direct Ship בעייתי) -> מדלגים!
            if calculated_status != config.STATUS_VALID:
                print(f"⛔ Skipped (New & Invalid Status: {calculated_status}).")
                skipped_count += 1
                continue

        # אם עברנו את השומר, ממשיכים כרגיל...

        # 2. ניהול נכסים
        my_sku = data.get('2_My_SKU')
        image_url = data.get('Extra_Image')
        if image_url:
            existing_img = row_data.get('Image') if row_data else None
            if not existing_img:
                local_image_path = assets_manager.download_image(image_url, my_sku)
                data['Extra_Image'] = local_image_path 
            else:
                data['Extra_Image'] = existing_img 

        ds_url = data.get('Extra_Datasheet')
        if ds_url:
            existing_ds = row_data.get('Datasheet') if row_data else None
            if not existing_ds:
                local_ds_path = assets_manager.download_datasheet(ds_url, my_sku)
                data['Extra_Datasheet'] = local_ds_path
            else:
                data['Extra_Datasheet'] = existing_ds

        # 3. עדכון ה-Slots
        if row_data:
            row_data = slot_manager.update_product_slots(row_data, data, 'FARNELL')
            print("🔄 Updated Slot...", end=" ")
        else:
            row_data = {col: "" for col in config.FINAL_COLUMNS}
            row_data = slot_manager.update_product_slots(row_data, data, 'FARNELL')
            print("✨ New Product...", end=" ")
            new_products_count += 1

        # 4. חישוב מנצח
        row_data = recalculator.recalculate_row(row_data)

        # 5. שמירה ל-DataFrame
        if row_index is not None:
            df_db.iloc[row_index] = pd.Series(row_data)
        else:
            df_row = pd.DataFrame([row_data])
            df_db = pd.concat([df_db, df_row], ignore_index=True)
        
        updated_count += 1
        print("✅ Done.")

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