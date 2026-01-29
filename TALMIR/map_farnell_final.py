import pandas as pd
import requests
import hashlib
import hmac
import base64
from datetime import datetime, timezone
import time
import os

# --- הגדרות והרשאות (מהפרויקט שלך) ---
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

# --- הגדרות קבצים ---
INPUT_FILE = 'talmir_mapped_test.csv'      # קובץ הקלט משלב א'
OUTPUT_FILE = 'talmir_farnell_dictionary.csv' # קובץ התוצאה

# --- נתיבים ---
script_dir = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(script_dir, INPUT_FILE)
output_path = os.path.join(script_dir, OUTPUT_FILE)

# --- פונקציות עזר לחתימה (מה-ADAPTER שלך) ---
def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

def generate_signature(op_name, timestamp):
    data = op_name + timestamp
    signature = hmac.new(
        key=FARNELL_SECRET_KEY.encode('utf-8'),
        msg=data.encode('utf-8'),
        digestmod=hashlib.sha1
    ).digest()
    return base64.b64encode(signature).decode('utf-8')

def get_commodity_code(farnell_sku):
    """מבצע קריאה מאובטחת ל-API ושולף את קוד הקטגוריה"""
    
    timestamp = get_timestamp()
    # לפי ה-Adapter שלך, הם משתמשים ב-Operation Name הזה עבור חתימה
    op_name = 'searchByPremierFarnellPartNumber' 
    signature = generate_signature(op_name, timestamp)
    
    base_url = "https://api.element14.com/catalog/products"
    
    params = {
        'term': f'id:{farnell_sku}',
        'storeInfo.id': FARNELL_STORE_ID,
        'resultsSettings.responseGroup': 'large,attributes', # ביקשנו attributes כדי לוודא שנקבל את הקוד
        'callInfo.responseDataFormat': 'JSON',
        'resultsSettings.numberOfResults': 1,
        'callInfo.apiKey': FARNELL_API_KEY,
        'userInfo.customerId': FARNELL_CUSTOMER_ID,
        'userInfo.timestamp': timestamp,
        'userInfo.signature': signature
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # בדיקה אם חזרו תוצאות
            products = []
            if data.get('premierFarnellPartNumberReturn') and data['premierFarnellPartNumberReturn'].get('products'):
                 products = data['premierFarnellPartNumberReturn']['products']
            elif data.get('keywordSearchReturn') and data['keywordSearchReturn'].get('products'):
                 products = data['keywordSearchReturn']['products']

            if products:
                product = products[0]
                # שליפת הנתון
                comm_code = product.get('commodityClassCode', 'N/A')
                return comm_code
            else:
                return "Not Found / Obsolete"
        else:
            return f"API Error {response.status_code}"
            
    except Exception as e:
        return f"Request Error: {e}"

# --- ראשי ---
print("--- מתחיל מיפוי פארנל (עם חתימה מאובטחת) ---")

try:
    # קריאת הקובץ (חשוב: dtype=str כדי לשמור אפסים)
    df = pd.read_csv(input_path, dtype={'Talmir_SKU': str})
except FileNotFoundError:
    print(f"שגיאה: לא מוצא את הקובץ {INPUT_FILE}")
    exit()

results = []
print(f"מעבד {len(df)} שורות...")

for index, row in df.iterrows():
    talmir_sku = str(row['Talmir_SKU']).strip()
    talmir_cat = str(row['Category'])
    talmir_url = str(row['URL'])

    # דילוג על שורות לא תקינות משלב א'
    if "Not Found" in talmir_cat or "N/A" in talmir_url or pd.isna(talmir_url):
        continue
    
    # היפוך מק"ט
    farnell_sku = talmir_sku[::-1]
    
    print(f"[{index+1}] טלמיר: {talmir_sku} -> פארנל: {farnell_sku}...", end=" ")
    
    # קריאה ל-API
    comm_code = get_commodity_code(farnell_sku)
    
    print(f"קוד: {comm_code}")
    
    results.append({
        'Talmir_SKU': talmir_sku,
        'Talmir_Category': talmir_cat,
        'Farnell_SKU': farnell_sku,
        'Commodity_Code': comm_code
    })
    
    # השהייה קצרה (חשוב!)
    time.sleep(0.2)

# שמירה
pd.DataFrame(results).to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n--- סיימנו! הקובץ מוכן: {OUTPUT_FILE} ---")