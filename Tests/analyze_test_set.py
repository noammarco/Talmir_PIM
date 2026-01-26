import sys
import os
import json
import requests
import hashlib
import hmac
import base64
from datetime import datetime, timezone

# --- תיקון הנתיב כדי לייבא את config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import config

# --- רשימת הזהב לבדיקה ---
TEST_SKUS = [
    "9339060",  # נגד (Passive)
    "1310331",  # מחבר/טרמינל
    "3371040",  # כבל אודיו
    "1369171",  # לד (Optoelectronics)
    "3238895",  # טרמינל בלוק
    "2491567",  # מתאם תקשורת
    "1139520"   # לד נוסף
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

def generate_signature(op_name, timestamp):
    data = op_name + timestamp
    signature = hmac.new(
        key=config.FARNELL_SECRET_KEY.encode('utf-8'),
        msg=data.encode('utf-8'),
        digestmod=hashlib.sha1
    ).digest()
    return base64.b64encode(signature).decode('utf-8')

def fetch_raw_data(sku):
    timestamp = get_timestamp()
    op_name = 'searchByPremierFarnellPartNumber'
    signature = generate_signature(op_name, timestamp)
    
    base_url = "https://api.element14.com/catalog/products"
    
    params = {
        'term': f'id:{sku}',
        'storeInfo.id': config.FARNELL_STORE_ID,
        'resultsSettings.responseGroup': 'large,prices,inventory,datasheets,images,attributes', 
        'callInfo.responseDataFormat': 'JSON',
        'resultsSettings.numberOfResults': 1,
        'callInfo.apiKey': config.FARNELL_API_KEY,
        'userInfo.customerId': config.FARNELL_CUSTOMER_ID,
        'userInfo.timestamp': timestamp,
        'userInfo.signature': signature
    }

    try:
        print(f"🔄 Fetching data for {sku}...", end=" ")
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('premierFarnellPartNumberReturn', {}).get('numberOfResults', 0) > 0:
                print("✅ Found.")
                return data['premierFarnellPartNumberReturn']['products'][0]
        print("❌ Not Found / Error.")
        return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

def main():
    results = {}
    print("--- 🕵️ HUNTING FOR CATEGORIES ---")
    
    for sku in TEST_SKUS:
        raw_data = fetch_raw_data(sku)
        if raw_data:
            # כאן השינוי הגדול: אנחנו שומרים את כל השדות החשודים כקטגוריה
            results[sku] = {
                "displayName": raw_data.get("displayName"),
                # ניסיון 1: שדה ישיר
                "category": raw_data.get("category"), 
                # ניסיון 2: משפחה
                "family": raw_data.get("family"),
                # ניסיון 3: הורים (בד"כ מכיל את הנתיב המלא)
                "parents": raw_data.get("parents"),
                # ניסיון 4: קבוצה
                "merchandiseCategory": raw_data.get("merchandiseCategory"),
                # ניסיון 5: מזהה קבוצה
                "feGroup": raw_data.get("feGroup")
            }
    
    # שמירה לקובץ
    output_file = os.path.join(parent_dir, 'category_test_dump.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)
    
    print(f"\n📄 Category Dump saved to: {output_file}")
    print("👉 Please send me the content of this file so we can map it!")

if __name__ == "__main__":
    main()