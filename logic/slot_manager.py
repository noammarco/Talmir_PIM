import datetime
import config
from logic import filters

def get_current_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def determine_detailed_status(adapter_data):
    """
    מנתח את הנתונים הגולמיים וקובע את הסטטוס הסופי (Enum) לאקסל.
    הלוגיקה תואמת אחד-לאחד ל-utils/filters.py.
    """
    if not adapter_data:
        return config.STATUS_NOT_FOUND

    # 1. בדיקת תקינות בסיסית
    valid_bool, valid_reason = filters.is_valid_product(adapter_data, adapter_data.get('8_Supplier_Name', 'UNKNOWN'))
    
    # חילוץ נתונים לצורך קביעת התווית המדויקת
    status_raw = str(adapter_data.get('_status', '')).upper()
    stock = int(adapter_data.get('Extra_Stock', 0))
    is_direct = adapter_data.get('_is_direct_ship', False)
    warehouse = str(adapter_data.get('_warehouse', '')).upper()
    is_usa = warehouse in ['USA', 'US']

    # 2. אם הפילטר הראשי החזיר שהמוצר תקין (TRUE)
    if valid_bool:
        # זה יכול להיות Valid רגיל, או Direct Ship מארה"ב (שזה גם תקין אצלנו)
        # אבל אנחנו נחזיר תמיד Valid כי עבור האתר זה אותו דבר
        return config.STATUS_VALID

    # 3. אם הפילטר החזיר FALSE - אנחנו צריכים להבין למה, כדי לתת את התווית הנכונה
    
    # א. בדיקת Direct Ship (שנכשל כי הוא לא מארה"ב)
    if status_raw == 'DIRECT_SHIP' or is_direct:
        if not is_usa:
            return config.STATUS_DIRECT_SHIP
            
    # ב. בדיקת סטטוס יצרן/מלאי (NLS / NLM)
    bad_statuses = ['NO_LONGER_STOCKED', 'NO_LONGER_MANUFACTURED', 'NLS', 'NLM', 'OBSOLETE']
    if status_raw in bad_statuses and stock == 0:
        if status_raw in ['NO_LONGER_MANUFACTURED', 'NLM']:
            return config.STATUS_NLM
        else:
            return config.STATUS_NLS

    # ג. שגיאות אחרות (מחיר 0, שם חסר וכו')
    if "Zero Cost" in valid_reason or "Missing" in valid_reason:
        return config.STATUS_ERROR

    # ברירת מחדל למקרים לא ידועים
    return config.STATUS_NOT_FOUND


def find_target_slot(row, supplier_name):
    """
    מחפש איפה הספק יושב.
    מחזיר: (index, is_new_slot)
    index: מספר ה-Slot (1, 2, 3) או None אם אין מקום.
    is_new_slot: האם זה סלוט חדש שתפסנו הרגע?
    """
    supplier_name = supplier_name.upper()

    # 1. חיפוש: האם הספק כבר קיים בשורה?
    for i in range(1, config.MAX_SUPPLIERS + 1):
        col_name = f"Supplier {i} Name"
        existing_name = str(row.get(col_name, '')).upper()
        if existing_name == supplier_name:
            return i, False # מצאנו, זה עדכון

    # 2. אם לא מצאנו - נחפש חריץ ריק
    for i in range(1, config.MAX_SUPPLIERS + 1):
        col_name = f"Supplier {i} Name"
        if not row.get(col_name): # אם התא ריק
            return i, True # מצאנו מקום חדש

    return None, False # אין מקום


def update_product_slots(existing_row, adapter_data, supplier_name="FARNELL"):
    """
    הפונקציה הראשית: מקבלת שורה ונתונים חדשים, ומעדכנת את ה-Slot המתאים.
    """
    # קביעת הסטטוס החדש
    new_status = determine_detailed_status(adapter_data)
    current_time = get_current_timestamp()

    # מציאת המקום לשמירה
    slot_index, is_new = find_target_slot(existing_row, supplier_name)

    if slot_index is None:
        print(f"⚠️ Warning: No empty slots for {supplier_name} in SKU {existing_row.get('SKU')}")
        return existing_row # מחזירים בלי שינוי

    prefix = f"Supplier {slot_index}"

    # --- עדכון שדות ה-Slot ---
    
    # 1. שדות חובה שחישבנו עכשיו
    existing_row[f"{prefix} Name"] = supplier_name
    existing_row[f"{prefix} Status"] = new_status
    existing_row[f"{prefix} Last Check"] = current_time

    # 2. מיפוי שאר השדות מהאדפטר לפי Config
    supplier_columns = config.get_supplier_slots(slot_index) # רשימת העמודות של הספק הזה (כדי לא להמציא עמודות)
    
    for adapter_key, internal_key in config.FIELD_MAPPING.items():
        if adapter_key in adapter_data:
            # אנחנו צריכים לבדוק אם המפתח הפנימי (למשל Cost) שייך ל-Slot הזה
            # המפתח באקסל נראה כמו "Supplier 1 Cost"
            target_col = f"{prefix} {internal_key}"
            
            # בדיקה: האם העמודה הזו קיימת ברשימת העמודות המותרות לספק?
            if target_col in supplier_columns:
                existing_row[target_col] = adapter_data[adapter_key]

    # --- עדכון שדות סטטיים (רק אם חסר או שזה ספק ראשי/חדש) ---
    # אם תמונת המוצר חסרה באקסל - נמלא אותה מהספק הזה
    for static_col in config.STATIC_COLUMNS:
        mapped_key = None
        # מציאת המפתח המקביל באדפטר
        for k, v in config.FIELD_MAPPING.items():
            if v == static_col:
                mapped_key = k
                break
        
        # אם יש מידע באדפטר, והשדה באקסל ריק -> נמלא אותו
        if mapped_key and adapter_data.get(mapped_key):
             if not existing_row.get(static_col): 
                 existing_row[static_col] = adapter_data[mapped_key]

    return existing_row


def mark_supplier_not_found(existing_row, supplier_name):
    """
    פונקציה למקרה שהמוצר קיים באקסל, אבל ה-API לא מצא אותו בריצה הנוכחית.
    אנחנו לא מוחקים, אלא מעדכנים סטטוס ל-Not Found.
    """
    slot_index, _ = find_target_slot(existing_row, supplier_name)
    
    if slot_index:
        prefix = f"Supplier {slot_index}"
        existing_row[f"{prefix} Status"] = config.STATUS_NOT_FOUND
        existing_row[f"{prefix} Stock"] = 0
        existing_row[f"{prefix} Last Check"] = get_current_timestamp()
        # לא מאפסים עלות, כדי שיישאר רפרנס היסטורי (אופציונלי)
    
    return existing_row