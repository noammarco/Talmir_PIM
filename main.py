import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
from datetime import datetime
import config
from adapters import farnell_adapter
from logic import currency_manager, filters
from utils import excel_manager, assets_manager

def main():
    print("--- 🚀 Talmir PIM: Start Update Process ---")
    
    # 1. הכנת שערים
    rates = {
        'GBP': currency_manager.get_rate('GBP'),
        'USD': currency_manager.get_rate('USD')
    }
    
    # 2. טעינת מסד נתונים
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

    for i, sku in enumerate(input_skus):
        print(f"[{i+1}/{len(input_skus)}] Processing SKU: {sku}...", end=" ")
        
        # 1. שליפה
        data = farnell_adapter.fetch_product_data(sku)
        
        # 2. סינון
        is_valid, reason = filters.is_valid_product(data, supplier_name='FARNELL')
        
        if is_valid:
            # הכנת השורה החדשה (בזיכרון, עוד לא באקסל)
            api_row = {}
            for adapter_key, excel_col in config.FIELD_MAPPING.items():
                api_row[excel_col] = data.get(adapter_key, '')
            
            my_sku = data.get('2_My_SKU', 'unknown')
            
            # בדיקה האם המוצר כבר קיים
            existing_indices = df_db.index[df_db['SKU'] == my_sku].tolist()
            
            # --- לוגיקת נכסים (תמונות/דפי נתונים) ---
            existing_datasheet = ""
            existing_image = ""
            
            if existing_indices:
                idx = existing_indices[0]
                existing_datasheet = str(df_db.at[idx, 'Datasheet']).strip()
                existing_image = str(df_db.at[idx, 'Image']).strip()
                if existing_datasheet == 'nan': existing_datasheet = ""
                if existing_image == 'nan': existing_image = ""

            # תמונה: מוריד רק אם אין קיימת
            adapter_image_url = data.get('Extra_Image', '')
            if existing_image:
                api_row['Image'] = existing_image 
            elif adapter_image_url:
                api_row['Image'] = assets_manager.download_image(adapter_image_url, my_sku)
            
            # דף נתונים: מוריד רק אם אין קיים
            adapter_ds_url = data.get('Extra_Datasheet', '')
            if existing_datasheet:
                api_row['Datasheet'] = existing_datasheet
            elif adapter_ds_url:
                api_row['Datasheet'] = assets_manager.download_datasheet(adapter_ds_url, my_sku)
            else:
                api_row['Datasheet'] = ""

            # שדות קבועים לעדכון
            api_row['Sell Currency'] = 'ILS'
            api_row['Date Updated'] = datetime.now()
            
            # --- ה-Upsert החכם (Smart Logic) ---
            if existing_indices:
                idx = existing_indices[0]
                # מעבר על כל שדה שמגיע מה-API
                for col, val in api_row.items():
                    if col not in df_db.columns: df_db[col] = ""
                    
                    # 1. האם זה שדה דינמי (מחיר/מלאי)? -> דרוס תמיד
                    if col in config.DYNAMIC_COLUMNS:
                         df_db.at[idx, col] = val
                    
                    # 2. האם השדה הקיים באקסל ריק? -> מלא אותו (Fill gaps)
                    else:
                        current_val = str(df_db.at[idx, col]).strip()
                        if current_val == "" or current_val == "nan":
                             df_db.at[idx, col] = val
                        # אחרת: אל תיגע! (שמור על הטקסט הקיים/מתורגם)

                print(f"✅ Updated (Smart).")
            else:
                # מוצר חדש לגמרי - מכניסים הכל
                row_df = pd.DataFrame([api_row])
                row_df = row_df.dropna(axis=1, how='all')
                df_db = pd.concat([df_db, row_df], ignore_index=True)
                print(f"✅ Added new.")
            
            updated_count += 1
            
        else:
            skipped_count += 1
            if data is None:
                print("❌ Failed / Not Found.")
            else:
                print(f"⛔ Filtered Out: {reason}")

    if updated_count > 0:
        excel_manager.save_styled_db(df_db, rates)
        print(f"🎉 Process Complete. {updated_count} processed, {skipped_count} skipped.")
    else:
        print("⚠️ No products were updated.")

if __name__ == "__main__":
    main()