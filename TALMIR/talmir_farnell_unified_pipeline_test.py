import pandas as pd
import requests
import time
import os
import re
import hashlib
import hmac
import base64
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# --- הגדרות API ---
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

# --- הגדרות קבצים לטסט ---
INPUT_FILE = 'talmir_skus_only.csv'        # קובץ המקור
OUTPUT_FILE = 'TEST_RESULT_SORTED.csv'     # קובץ תוצאה לטסט
BATCH_SIZE = 1                             # שומר כל שורה

# --- נתיבים ---
script_dir = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(script_dir, INPUT_FILE)
output_path = os.path.join(script_dir, OUTPUT_FILE)
base_talmir_url = "https://www.talmir.co.il"

# ==========================================
# פונקציות עזר
# ==========================================

def find_link_by_sku_text(soup, sku):
    target_elements = soup.find_all(string=re.compile(re.escape(str(sku))))
    for element in target_elements:
        parent = element.parent
        current = parent
        for _ in range(5):
            if current is None: break
            if current.name == 'a' and 'href' in current.attrs:
                return current['href']
            link = current.find('a', href=True)
            if link and "/product/" in link['href']:
                return link['href']
            current = current.parent
    return None

def get_talmir_data(sku, session):
    search_url = f"https://www.talmir.co.il/s?q={sku}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = session.get(search_url, headers=headers, timeout=10)
        product_url = None
        if "/product/" in response.url and "searchphrase" not in response.url:
             product_url = response.url
        else:
            soup = BeautifulSoup(response.content, 'html.parser')
            found_href = find_link_by_sku_text(soup, sku)
            if found_href:
                product_url = found_href if found_href.startswith("http") else base_talmir_url + (found_href if found_href.startswith('/') else '/' + found_href)
        
        if not product_url: return None

        prod_response = session.get(product_url, headers=headers, timeout=10)
        prod_soup = BeautifulSoup(prod_response.content, 'html.parser')
        breadcrumb_span = prod_soup.find('span', class_='prodBreadcrumb')
        if breadcrumb_span:
            raw_text = breadcrumb_span.get_text(" ", strip=True)
            return raw_text.replace('»', '>').replace('  ', ' ').strip()
        return None
    except: return None

def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

def generate_signature(op_name, timestamp):
    data = op_name + timestamp
    signature = hmac.new(key=FARNELL_SECRET_KEY.encode('utf-8'), msg=data.encode('utf-8'), digestmod=hashlib.sha1).digest()
    return base64.b64encode(signature).decode('utf-8')

def get_farnell_code(farnell_sku):
    timestamp = get_timestamp()
    op_name = 'searchByPremierFarnellPartNumber'
    signature = generate_signature(op_name, timestamp)
    url = "https://api.element14.com/catalog/products"
    params = {
        'term': f'id:{farnell_sku}',
        'storeInfo.id': FARNELL_STORE_ID,
        'resultsSettings.responseGroup': 'large,attributes',
        'callInfo.responseDataFormat': 'JSON',
        'resultsSettings.numberOfResults': 1,
        'callInfo.apiKey': FARNELL_API_KEY,
        'userInfo.customerId': FARNELL_CUSTOMER_ID,
        'userInfo.timestamp': timestamp,
        'userInfo.signature': signature
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            products = []
            if data.get('premierFarnellPartNumberReturn') and data['premierFarnellPartNumberReturn'].get('products'):
                 products = data['premierFarnellPartNumberReturn']['products']
            elif data.get('keywordSearchReturn') and data['keywordSearchReturn'].get('products'):
                 products = data['keywordSearchReturn']['products']
            if products:
                return products[0].get('commodityClassCode')
    except: pass
    return None

# ==========================================
# ריצת הטסט
# ==========================================

print("--- מתחיל טסט (10 מוצרים ראשונים) ---")

try:
    df_input = pd.read_csv(input_path, dtype=str)
    all_skus = df_input.iloc[:, 0].dropna().unique().tolist()
    
    # --- מגבלה ל-10 הראשונים בלבד ---
    all_skus = all_skus[:10] 
    
    print(f"נבחרו {len(all_skus)} מק\"טים לבדיקה.")
except FileNotFoundError:
    print(f"שגיאה: הקובץ {INPUT_FILE} לא נמצא.")
    exit()

# מחיקת קובץ טסט ישן
if os.path.exists(output_path):
    os.remove(output_path)

# יצירת כותרות
pd.DataFrame(columns=['Talmir_SKU', 'Talmir_Category', 'Farnell_SKU', 'Commodity_Code']).to_csv(output_path, index=False, encoding='utf-8-sig')

session = requests.Session()
batch = []

for i, talmir_sku in enumerate(all_skus):
    talmir_sku = str(talmir_sku).strip()
    print(f"[{i+1}/{len(all_skus)}] בודק {talmir_sku}...", end=" ")

    # 1. טלמיר
    talmir_cat = get_talmir_data(talmir_sku, session)
    if not talmir_cat:
        print("דילוג (לא נמצא בטלמיר)")
        continue

    # 2. פארנל
    farnell_sku = talmir_sku[::-1]
    comm_code = get_farnell_code(farnell_sku)
    
    if not comm_code:
        print(f"דילוג (פארנל {farnell_sku} לא נמצא)")
        continue

    print(f"הצלחה! קוד: {comm_code}")
    
    batch.append({
        'Talmir_SKU': talmir_sku,
        'Talmir_Category': talmir_cat,
        'Farnell_SKU': farnell_sku,
        'Commodity_Code': comm_code
    })

    # שמירה מיידית
    pd.DataFrame(batch).to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig')
    batch = [] 
    time.sleep(0.5)

# ==========================================
# שלב המיון (Sorting)
# ==========================================
print("\n--- סיימנו את הריצה. כעת ממיין את התוצאות... ---")

if os.path.exists(output_path):
    try:
        # טוען את הקובץ שנוצר הרגע (הכל כ-String כדי לשמור אפסים מובילים)
        df_final = pd.read_csv(output_path, dtype=str)
        
        if not df_final.empty:
            # מיון לפי Commodity_Code
            df_final = df_final.sort_values(by='Commodity_Code')
            
            # שמירה מחדש
            df_final.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            print(f"✅ הקובץ מוין ונשמר בהצלחה: {OUTPUT_FILE}")
            print("פתח את הקובץ כדי לראות את התוצאות מסודרות.")
        else:
            print("לא נמצאו נתונים למיין.")
    except Exception as e:
        print(f"שגיאה במיון: {e}")
else:
    print("לא נוצר קובץ פלט.")