import sys
import os
import requests
import hashlib
import hmac
import base64
from datetime import datetime, timezone

# --- חיבור לקונפיגורציה ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# המוצרים שבחרת לבדיקה
HIERARCHY_TEST = [
    {
        "sku": "4307319", 
        "desc": "AV Control (Level 2 Direct)",
        "expected_path": "Audio Visual -> Control & Automation"
    },
    {
        "sku": "3402280", 
        "desc": "AV Over CAT (Level 3)",
        "expected_path": "Audio Visual -> Distribution -> Over CAT"
    },
    {
        "sku": "3531143", 
        "desc": "Amplifiers/Splitters (Level 3)",
        "expected_path": "Audio Visual -> Distribution -> Amplifiers"
    },
    {
        "sku": "4158927", 
        "desc": "Wireless (Level 3)",
        "expected_path": "Audio Visual -> Distribution -> Wireless"
    }
]

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

def get_code(sku):
    url = "https://api.element14.com/catalog/products"
    timestamp = get_timestamp()
    op_name = 'searchByPremierFarnellPartNumber'
    signature = generate_signature(op_name, timestamp)
    
    # מבקשים רק את הקוד
    params = {
        'term': f'id:{sku}',
        'storeInfo.id': config.FARNELL_STORE_ID,
        'resultsSettings.responseGroup': 'large,commodityClassCode',
        'callInfo.responseDataFormat': 'JSON',
        'resultsSettings.numberOfResults': 1,
        'callInfo.apiKey': config.FARNELL_API_KEY,
        'userInfo.customerId': config.FARNELL_CUSTOMER_ID,
        'userInfo.timestamp': timestamp,
        'userInfo.signature': signature
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200: return "Error"
        data = response.json()
        
        if data.get('premierFarnellPartNumberReturn', {}).get('numberOfResults', 0) > 0:
            return data['premierFarnellPartNumberReturn']['products'][0].get('commodityClassCode', 'None')
        return "Not Found"
    except Exception as e:
        return "Exception"

def main():
    print(f"{'SKU':<10} | {'Category Code':<15} | {'Description'}")
    print("-" * 70)
    
    codes_seen = set()
    
    for item in HIERARCHY_TEST:
        code = get_code(item['sku'])
        codes_seen.add(code)
        print(f"{item['sku']:<10} | {code:<15} | {item['desc']}")
    
    print("-" * 70)
    print(f"Total unique codes found: {len(codes_seen)} out of {len(HIERARCHY_TEST)}")
    
    if len(codes_seen) == 4:
        print("✅ Conclusion: The API gives distinct codes for deep sub-categories (Level 3).")
    elif len(codes_seen) == 2:
        print("⚠️ Conclusion: The API likely groups by Level 2 (Distribution vs Control).")
    elif len(codes_seen) == 1:
        print("❌ Conclusion: The API only sees the top level category (Audio Visual).")
    else:
        print("ℹ️ Conclusion: Mixed granularity.")

if __name__ == "__main__":
    main()