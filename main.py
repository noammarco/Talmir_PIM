import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
import config
from logic import currency_manager, product_processor
from utils import excel_manager, tracker

def main():
    print("--- 🚀 Talmir PIM: Start Update Process (Multi-Vendor) ---")
    
    # 1. אתחול
    change_tracker = tracker.ChangeTracker()
    rates = {
        'GBP': currency_manager.get_rate('GBP'),
        'USD': currency_manager.get_rate('USD'),
        'EUR': currency_manager.get_rate('EUR')
    }
    
    # 2. טעינת נתונים
    df_db = excel_manager.load_or_create_db()
    
    try:
        df_input = pd.read_excel(config.INPUT_FILENAME, dtype=str)
        input_skus = df_input['SKU'].dropna().str.strip().tolist()
        print(f"📋 Loaded {len(input_skus)} SKUs from input.")
    except FileNotFoundError:
        print(f"❌ Error: '{config.INPUT_FILENAME}' not found.")
        return

    # 3. לולאת הריצה הראשית
    updated_count = 0
    skipped_count = 0
    new_products_count = 0

    for i, input_sku in enumerate(input_skus):
        print(f"[{i+1}/{len(input_skus)}]", end=" ")
        
        # קריאה ל-Processor החדש שמבצע את כל העבודה השחורה
        status, row_data, row_index = product_processor.process_single_item(
            input_sku, df_db, rates, change_tracker
        )
        
        # עדכון ה-DataFrame בהתאם לתוצאה
        if status == 'skipped':
            skipped_count += 1
        
        elif status == 'updated':
            if row_index is not None:
                df_db.iloc[row_index] = pd.Series(row_data)
            updated_count += 1
            
        elif status == 'new':
            df_row = pd.DataFrame([row_data])
            df_db = pd.concat([df_db, df_row], ignore_index=True)
            updated_count += 1
            new_products_count += 1

    # 4. סיום ושמירה
    if updated_count > 0:
        excel_manager.save_styled_db(df_db, rates)
        change_tracker.save_logs()
        
        print(f"\n🎉 Process Complete Summary:")
        print(f"   - Processed/Updated: {updated_count}")
        print(f"   - New Products Added: {new_products_count}")
        print(f"   - Skipped: {skipped_count}")
    else:
        print("\n⚠️ No changes were made to the database.")

if __name__ == "__main__":
    main()