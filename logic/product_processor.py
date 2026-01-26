import pandas as pd
import config
from adapters import farnell_adapter
from logic import slot_manager, recalculator
from utils import assets_manager, tracker

# --- פונקציות עזר ---

def sanitize_row_data(row_data):
    clean_data = {}
    for k, v in row_data.items():
        if v is None: clean_data[k] = ""
        else: clean_data[k] = str(v)
    return clean_data

def resolve_snapshot_data(row_data, rates):
    """
    מתקן נתונים ב-Snapshot לפני ההשוואה (מתמודד עם נוסחאות אקסל שלא חושבו).
    1. מתקן את שם הספק המנצח (Best Supplier Name).
    2. מחשב מחדש את מחיר המכירה (Price With VAT).
    """
    try:
        # 1. תיקון שם ספק מנצח
        slot_val = row_data.get('Best Supplier Slot')
        if pd.isna(slot_val): str_slot = ""
        else:
            str_slot = str(slot_val).strip()
            if str_slot.endswith('.0'): str_slot = str_slot[:-2]

        if str_slot in ['1', '2', '3']:
            supplier_name = row_data.get(f"Supplier {str_slot} Name")
            if supplier_name: row_data['Best Supplier Name'] = supplier_name
            
            # 2. חישוב מחיר מכירה (Price With VAT) עבור ה-Snapshot
            # שולפים עלות ומטבע מהספק המנצח (כי העמודות הראשיות עשויות להיות נוסחאות)
            cost = row_data.get(f"Supplier {str_slot} Cost")
            currency = row_data.get(f"Supplier {str_slot} Currency")
            
            if cost and currency:
                try:
                    rate = rates.get(currency, 1.0)
                    cost_float = float(cost)
                    # הנוסחה: עלות * שער * (1 + מע"מ)
                    calc_price = cost_float * rate * (1 + config.VAT_PERCENT)
                    row_data['Price With VAT'] = f"{calc_price:.2f}"
                except:
                    pass # אם החישוב נכשל, נשארים עם מה שיש (0)
        else:
             row_data['Best Supplier Name'] = "None"
             
    except: pass 
    return row_data

def find_row_in_db(df_db, mpn_from_api, input_search_term):
    if mpn_from_api:
        clean_mpn = str(mpn_from_api).strip()
        matches = df_db.index[df_db['Manufacturer Part Number'] == clean_mpn].tolist()
        if matches: return matches[0]

    if input_search_term:
        clean_input = str(input_search_term).strip()
        for i in range(1, config.MAX_SUPPLIERS + 1):
            supplier_sku_col = f"Supplier {i} SKU"
            supplier_name_col = f"Supplier {i} Name"
            matches = df_db.index[
                (df_db[supplier_sku_col] == clean_input) & 
                (df_db[supplier_name_col] == 'FARNELL')
            ].tolist()
            if matches: return matches[0]
    return None

def fill_static_data(row_data, api_data):
    row_data['Product Name'] = api_data.get('1_Product_Name', '')
    row_data['SKU'] = api_data.get('2_My_SKU', '') 
    row_data['Manufacturer'] = api_data.get('4_Manufacturer', '')
    row_data['Manufacturer Part Number'] = api_data.get('4a_MPN', '')
    row_data['Description'] = api_data.get('9_Short_Description', '')
    row_data['Hazardous'] = api_data.get('Hazardous', '')
    row_data['US Stock'] = api_data.get('is_us_stock', '')
    return row_data

# --- הפונקציה הראשית לעיבוד פריט בודד ---
def process_single_item(input_sku, df_db, rates, change_tracker):
    print(f"Processing SKU: {input_sku}...", end=" ")
    
    data = farnell_adapter.fetch_product_data(input_sku)
    mpn_from_api = data.get('4a_MPN') if data else None
    
    row_index = find_row_in_db(df_db, mpn_from_api, input_sku)
    
    row_data = None
    old_data_snapshot = {} 
    is_new_product = False

    if row_index is not None:
        row_data = df_db.iloc[row_index].to_dict()
        # --- תיקון הנתונים הקריטי (שם מנצח + מחיר) ---
        row_data = resolve_snapshot_data(row_data, rates) 
        old_data_snapshot = row_data.copy()
    else:
        is_new_product = True
        row_data = {col: "" for col in config.FINAL_COLUMNS}
        old_data_snapshot = {} 

    if not data:
        if not is_new_product:
            print(f"⚠️ Not found in Farnell (Updating Status)...", end=" ")
            row_data = slot_manager.mark_supplier_not_found(row_data, 'FARNELL')
            row_data = recalculator.recalculate_row(row_data, rates)
            row_data = sanitize_row_data(row_data) 
            
            my_sku_check = row_data.get('SKU', 'unknown')
            change_tracker.track_changes(my_sku_check, old_data_snapshot, row_data, rates)
            print("Done (Updated to Not Found).")
            return 'updated', row_data, row_index
        else:
            print(f"⏭️ Skipped (Not found & New).")
            return 'skipped', None, None

    if is_new_product:
        calculated_status = slot_manager.determine_detailed_status(data)
        if calculated_status != config.STATUS_VALID:
            print(f"⛔ Skipped (New & Invalid Status: {calculated_status}).")
            return 'skipped', None, None
        
        row_data = fill_static_data(row_data, data)
        print("✨ New Product...", end=" ")
    else:
        print("🔄 Updating Existing...", end=" ")

    my_sku_for_file = row_data.get('SKU', 'unknown')
    image_url = data.get('Extra_Image')
    if image_url:
        existing_img = row_data.get('Image')
        if not existing_img:
            local_image_path = assets_manager.download_image(image_url, my_sku_for_file)
            row_data['Image'] = local_image_path 

    ds_url = data.get('Extra_Datasheet')
    if ds_url:
        existing_ds = row_data.get('Datasheet')
        if not existing_ds:
            local_ds_path = assets_manager.download_datasheet(ds_url, my_sku_for_file)
            row_data['Datasheet'] = local_ds_path

    row_data = slot_manager.update_product_slots(row_data, data, 'FARNELL')
    row_data = recalculator.recalculate_row(row_data, rates)
    row_data = sanitize_row_data(row_data)

    change_tracker.track_changes(my_sku_for_file, old_data_snapshot, row_data, rates)
    print("✅ Done.")

    if is_new_product:
        return 'new', row_data, None
    else:
        return 'updated', row_data, row_index