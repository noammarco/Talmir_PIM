import sys
import os

# --- תיקון הנתיב (Path Fix) ---
# מוסיפים את התיקייה הראשית (אבא של Tests) לנתיב החיפוש של פייתון
# כדי שנוכל לייבא את config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# עכשיו אפשר לייבא את הקונפיגורציה מהתיקייה הראשית
import config

import requests
import hashlib
import hmac
import base64
import json
from datetime import datetime, timezone

# --- הגדרות חיבור ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Connection': 'keep-alive'
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

def inspect_sku(sku):
    print(f"\n🔬 INSPECTING RAW DATA FOR SKU: {sku}")
    print("=" * 60)
    
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
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return

        data = response.json()
        
        # הדפסה יפה של כל ה-JSON
        print(json.dumps(data, indent=4))
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_sku = input("Enter SKU to inspect: ")
    inspect_sku(test_sku)