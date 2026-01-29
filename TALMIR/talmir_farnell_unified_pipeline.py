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

# --- קבצים ---
INPUT_FILE = 'talmir_skus_only.csv'        
OUTPUT_FILE = 'talmir_farnell_unified.csv' 
BATCH_SIZE = 5                             

# --- הגדרות קצב ובטיחות ---
NORMAL_SLEEP = 2.0      # האטה ל-2 שניות בין מוצרים (יותר בטוח)

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

# ==========================================
# הפונקציה החכמה - Exponential Backoff
# ==========================================
def get_farnell_code_smart(farnell_sku):
    url = "https://api.element14.com/catalog/products"
    
    # זמני המתנה במידה ויש חסימה (בשניות): דקה, 5 דקות, 15 דקות, שעה
    wait_times = [60, 300, 900, 3600] 
    
    for attempt, wait_time in enumerate(wait_times):
        timestamp = get_timestamp()
        op_name = 'searchByPremierFarnellPartNumber'
        signature = generate_signature(op_name, timestamp)
        
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
            
            # --- הצלחה ---
            if response.status_code == 200:
                data = response.json()
                products = []
                if data.get('premierFarnellPartNumberReturn') and data['premierFarnellPartNumberReturn'].get('products'):
                     products = data['premierFarnellPartNumberReturn']['products']
                elif data.get('keywordSearchReturn') and data['keywordSearchReturn'].get('products'):
                     products = data['keywordSearchReturn']['products']

                if products:
                    return products[0].get('commodityClassCode'), False 
                else:
                    return None, False 
            
            # --- חסימה (403/429) ---
            elif response.status_code in [403, 429]:
                print(f"\n⚠️ חסימה (קוד {response.status_code}). ניסיון {attempt+1}. נכנס להמתנה של {wait_time/60} דקות...")
                time.sleep(wait_time) # הולך לישון ומנסה שוב באותה לולאה
                continue 
            
            else:
                # שגיאות אחרות (500 וכו') - המתנה קצרה
                time.sleep(5)
                continue

        except Exception as e:
            time.sleep(5)
            continue
            
    # אם הגענו לפה, נכשלו כל שלבי ההמתנה
    print(f"\n❌ כישלון טוטאלי עבור {farnell_sku}. מוותר עליו.")
    return None, True # True = שגיאה קריטית

# ==========================================
# Main Loop
# ==========================================
print("--- ריצה חכמה (Exponential Backoff) ---")

# 1. Load Data
try:
    df_input = pd.read_csv(input_path, dtype=str) 
    all_skus = [str(x).strip() for x in df_input.iloc[:, 0].dropna().unique().tolist()]
    print(f"סה\"כ מק\"טים: {len(all_skus)}")
except FileNotFoundError:
    print("קובץ חסר.")
    exit()

# 2. Resume Logic
start_index = 0
if os.path.exists(output_path):
    try:
        df_existing = pd.read_csv(output_path, dtype=str)
        if not df_existing.empty:
            last_sku_found = str(df_existing.iloc[-1]['Talmir_SKU']).strip()
            try:
                found_index = all_skus.index(last_sku_found)
                start_index = found_index + 1
                print(f"ממשיך מאינדקס: {start_index} (אחרי {last_sku_found})")
            except:
                print("לא מצאתי את האחרון, מתחיל מ-0")
    except: pass
else:
    pd.DataFrame(columns=['Talmir_SKU', 'Talmir_Category', 'Farnell_SKU', 'Commodity_Code']).to_csv(output_path, index=False, encoding='utf-8-sig')

# 3. Processing
session = requests.Session()
batch = []

for i in range(start_index, len(all_skus)):
    talmir_sku = all_skus[i]
    print(f"[{i+1}/{len(all_skus)}] מעבד {talmir_sku}...", end=" ")

    # Talmir Scraping
    talmir_cat = get_talmir_data(talmir_sku, session)
    if not talmir_cat:
        print("Skipped (חסר בטלמיר)")
        continue 

    farnell_sku = talmir_sku[::-1]
    
    # Smart Farnell Call
    comm_code, is_critical = get_farnell_code_smart(farnell_sku)
    
    if is_critical:
        # אם נכשלנו גם אחרי המתנה של שעה - עוצרים הכל
        print("עצירת חירום סופית.")
        if batch: pd.DataFrame(batch).to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig')
        break

    if comm_code:
        print(f"OK! Code: {comm_code}")
        batch.append({
            'Talmir_SKU': talmir_sku,
            'Talmir_Category': talmir_cat,
            'Farnell_SKU': farnell_sku,
            'Commodity_Code': comm_code
        })
    else:
        print("Skipped")

    if len(batch) >= BATCH_SIZE:
        pd.DataFrame(batch).to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig')
        batch = []
        
    time.sleep(NORMAL_SLEEP)

if batch:
    pd.DataFrame(batch).to_csv(output_path, mode='a', header=False, index=False, encoding='utf-8-sig')