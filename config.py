import os

# --- הגדרת נתיבים ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_FILENAME = os.path.join(DATA_DIR, 'products_db.xlsx')
INPUT_FILENAME = os.path.join(DATA_DIR, 'input.xlsx')

# --- API Keys & IDs (Farnell) ---
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

# --- הגדרות מערכת ---
VAT_PERCENT = 0.18
MAX_SUPPLIERS = 3 

# --- סטטוסים אפשריים (Enums) ---
# עודכן בהתאם ללוגיקה ב-filters.py
STATUS_VALID = "Valid"             # תקין למכירה (כולל Direct Ship מארה"ב)
STATUS_DIRECT_SHIP = "Direct Ship" # לא תקין (Direct Ship שאינו מארה"ב)
STATUS_NLS = "NLS"                 # לא תקין (No Longer Stocked ואין מלאי)
STATUS_NLM = "NLM"                 # לא תקין (No Longer Manufactured ואין מלאי)
STATUS_NOT_FOUND = "Not Found"     # לא נמצא ב-API
STATUS_ERROR = "Error"             # שגיאה טכנית

# --- מיפוי שדות (Adapter -> Internal Keys) ---
FIELD_MAPPING = {
    '1_Product_Name': 'Product Name',
    '2_My_SKU': 'SKU',
    '4_Manufacturer': 'Manufacturer',
    '4a_MPN': 'Manufacturer Part Number',
    '9_Short_Description': 'Description',
    'Hazardous': 'Hazardous',
    'Extra_Image': 'Image',
    'Extra_Datasheet': 'Datasheet',
    
    # שדות שיילכו ל-Slot של הספק הספציפי
    '8_Supplier_Name': 'Name',       
    '8_Supplier_SKU': 'SKU',         
    '3_Category_Farnell': 'Category', 
    '5_Cost_Buy': 'Cost',
    '5_Currency_Buy': 'Currency',
    'Lead_Time': 'Lead Time',
    'Extra_Stock': 'Stock',
    '11_MOQ': 'MOQ',
    '12_Order_Multiple': 'Multiple',
    'is_us_stock': 'US Stock'
}

# --- עמודות האקסל הסופי ---

# 1. עמודות כלליות (Static Info)
STATIC_COLUMNS = [
    "Product Name", "SKU", "Manufacturer", "Manufacturer Part Number", "Description",
    "Image", "Datasheet", "Hazardous", "US Stock"
]

# 2. עמודות "המנצח" (Winner Info) - מסודרות כאן כדי שיופיעו באמצע האקסל
WINNER_COLUMNS = [
    "Cost", "Buy Currency", "Real ILS Cost", "Price No VAT", "VAT", "Price With VAT", "Sell Currency",
    "Stock", "Lead Time", "MOQ", "Multiple",
    "Date Updated"
]

# 3. עמודות ניהול (Management)
MANAGEMENT_COLUMNS = [
    "Best Supplier Name", 
    "Best Supplier Slot", # <--- הוסף: שומר את האינדקס (1/2/3) לקישור דינמי
    "Show in Website",    
    "Drop Date"           
]

# 4. עמודות ספציפיות לכל ספק (Supplier Slots)
def get_supplier_slots(index):
    prefix = f"Supplier {index}"
    return [
        f"{prefix} Name",
        f"{prefix} SKU",
        f"{prefix} Category",    
        f"{prefix} Status",      
        f"{prefix} Cost",
        f"{prefix} Currency",
        f"{prefix} Cost ILS",    
        f"{prefix} Stock",
        f"{prefix} Lead Time",
        f"{prefix} MOQ",
        f"{prefix} Multiple",
        f"{prefix} Last Check"   
    ]

# --- הרכבת הרשימה הסופית ---
FINAL_COLUMNS = STATIC_COLUMNS + WINNER_COLUMNS + MANAGEMENT_COLUMNS

for i in range(1, MAX_SUPPLIERS + 1):
    FINAL_COLUMNS.extend(get_supplier_slots(i))

# --- שדות דינמיים (מותרים לדריסה בעמודות הראשיות) ---
# רשימה זו קובעת רק מה מותר לדרוס *באמצעות מידע חיצוני*.
# נוסחאות מתעדכנות בכל מקרה ע"י ה-Excel Manager.
DYNAMIC_COLUMNS = [
    'Cost', 'Buy Currency', 'Stock', 'Lead Time', 'Date Updated', 
    'MOQ', 'Multiple', 'Show in Website', 'Drop Date', 'Best Supplier Name', 'Best Supplier Slot'
]

# --- הגדרות לוגים ומעקב (Module E) ---
CHANGES_LOG_FILENAME = os.path.join(DATA_DIR, 'changes_log.xlsx')
LOG_RETENTION_DAYS = 180

# שדות למעקב כללי (ערכים פשוטים)
# הסרנו מכאן את Best Supplier Name ואת Price With VAT כדי לטפל בהם בנפרד
TRACKED_SIMPLE_FIELDS = [
    'SKU',                
    'MOQ', 
    'Multiple', 
    'Show in Website', 
    'Product Name', 
    'Description'
]

# שדות נכסים
TRACKED_ASSETS = ['Image', 'Datasheet']

# --- הגדרות עיצוב לוג (צבעי רקע) ---
# הערה: אלו קודי צבע HEX עבור אקסל
LOG_COLORS = {
    'New Product': "#8BC5FF",          # כחול בהיר
    'Cost Increase 📈': "#FF5E00",     # כתום
    'Cost Decrease 📉': "#40FFB6",     # תכלת/ציאן
    'Supplier Added': "#C9AB00",       # צהוב
    'Supplier Status Change': "#FFFF6D", # צהוב בהיר יותר
    'Update': "#FF63B1",               # ורוד
    'Supplier Removed': "#666363",     # אפור
    'Selling Price Update': "#AAAAFA", # סגול בהיר (Lavender)
    'Initial Cost': "#CEFFFD",         # לבן
    'Asset Added': "#ECFF99",          # סגול לילך
    'Asset Removed': "#7D8F5C",        # חום בהיר (Tan)
    'Price Change': '#FF99CC'          # גיבוי (כמו Update)
}