import os

# --- הגדרת נתיבים (Paths) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_FILENAME = os.path.join(DATA_DIR, 'products_db.xlsx')
INPUT_FILENAME = os.path.join(DATA_DIR, 'input.xlsx')

# --- API Keys & IDs (Farnell) ---
# המפתחות המקוריים שלך שעובדים
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

# --- מיפוי שדות (Adapter -> Excel) ---
FIELD_MAPPING = {
    '1_Product_Name': 'Product Name',
    '2_My_SKU': 'SKU',
    '4_Manufacturer': 'Manufacturer',
    '4a_MPN': 'Manufacturer Part Number',
    '5_Cost_Buy': 'Cost',
    '5_Currency_Buy': 'Buy Currency',
    
    # מיפוי נתוני ספק (פארנל הולך ל-Supplier 1)
    '8_Supplier_Name': "Supplier 1 Name",
    '8_Supplier_SKU': "Supplier 1 SKU",
    'Lead_Time': "Supplier 1 Lead Time",
    'Extra_Stock': "Supplier 1 Stock",
    '3_Category_Farnell': "Supplier 1 Category",
    
    '9_Short_Description': 'Description',
    'Hazardous': 'Hazardous',
    '11_MOQ': 'MOQ',
    '12_Order_Multiple': 'Multiple',
    'Extra_Image': 'Image',
    'Extra_Datasheet': 'Datasheet',

    # --- התוספת החדשה ---
    'is_us_stock': 'US Stock'
}

# --- רשימת השדות הדינמיים (מותרים לדריסה בעדכון) ---
# הותאם לשמות העמודות הספציפיים שלך!
DYNAMIC_COLUMNS = [
    'Cost', 
    'Buy Currency', 
    'Supplier 1 Stock', 
    'Supplier 1 Lead Time', # שים לב: זה השם אצלך בקובץ שעובד
    'US Stock', 
    'Date Updated',
    'MOQ',
    'Multiple',
    'Hazardous'
]

# --- עמודות האקסל הסופי (מורחב) ---
FINAL_COLUMNS = [
    # --- פרטי מוצר בסיסיים ---
    "Product Name", "SKU", "Manufacturer", "Manufacturer Part Number", "Description",
    
    # --- פיננסי ---
    "Cost", "Buy Currency", "Real ILS Cost", "Price No VAT", "VAT", "Price With VAT", "Sell Currency",
    
    # --- לוגיסטיקה כללית ---
    "MOQ", "Multiple", "Hazardous",
    "US Stock", # <--- הוספנו כאן
    
    # --- ספק 1 (ראשי - פארנל) ---
    "Supplier 1 Name", "Supplier 1 SKU", "Supplier 1 Category", "Supplier 1 Stock", "Supplier 1 Lead Time",
    
    # --- ספק 2 (משני - עתידי) ---
    "Supplier 2 Name", "Supplier 2 SKU", "Supplier 2 Stock", "Supplier 2 Lead Time",
    
    # --- ספק 3 (שלישוני - עתידי) ---
    "Supplier 3 Name", "Supplier 3 SKU", "Supplier 3 Stock", "Supplier 3 Lead Time",
    
    # --- נכסים ועדכון ---
    "Image", "Datasheet", "Date Updated"
]

# --- נתונים פיננסיים ---
VAT_PERCENT = 0.18