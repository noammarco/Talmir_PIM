import sys
import os
import json
import requests
import hashlib
import hmac
import base64
from datetime import datetime, timezone

# --- תיקון הנתיב ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import config

TARGET_SKU = "9339060" # הנגד הקלאסי שלנו

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

def get_legacy_full_dump():
    timestamp = get_timestamp()
    op_name = 'searchByPremierFarnellPartNumber'
    signature = generate_signature(op_name, timestamp)
    
    base_url = "https://api.element14.com/catalog/products"
    
    # הוספתי כאן את 'merchandiseCategory' ו-'classifications' לרשימת הבקשות
    # בתקווה שאחד מהם יחזיר את הזהב
    response_group = 'large,prices,inventory,datasheets,images,attributes,merchandiseCategory,classifications'

    params = {
        'term': f'id:{TARGET_SKU}',
        'storeInfo.id': config.FARNELL_STORE_ID,
        'resultsSettings.responseGroup': response_group,
        'callInfo.responseDataFormat': 'JSON',
        'resultsSettings.numberOfResults': 1,
        'callInfo.apiKey': config.FARNELL_API_KEY,
        'userInfo.customerId': config.FARNELL_CUSTOMER_ID,
        'userInfo.timestamp': timestamp,
        'userInfo.signature': signature
    }

    print(f"🔄 Fetching FULL LEGACY data for {TARGET_SKU}...", end=" ")
    
    try:
        response = requests.get(base_url, params=params, headers={'Accept': 'application/json'}, timeout=15)
        
        if response.status_code != 200:
            print(f"\n❌ Error: HTTP {response.status_code}")
            return

        data = response.json()
        
        # שמירה לתיקיית Output
        output_dir = os.path.join(current_dir, 'Output')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_file = os.path.join(output_dir, 'legacy_full_dump.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        print("✅ Done!")
        print(f"📄 Saved to: {output_file}")
        print("👉 Please upload this file so we can find the category field.")

    except Exception as e:
        print(f"\n⚠️ Exception: {e}")

if __name__ == "__main__":
    get_legacy_full_dump()