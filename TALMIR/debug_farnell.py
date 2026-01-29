import requests
import hashlib
import hmac
import base64
from datetime import datetime, timezone

# --- הגדרות ---
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

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

# המק"ט הבעייתי (ההפוך של 4412561)
test_sku = "1652144"

print(f"בודק את המק\"ט: {test_sku}...")

timestamp = get_timestamp()
op_name = 'searchByPremierFarnellPartNumber'
signature = generate_signature(op_name, timestamp)

url = "https://api.element14.com/catalog/products"
params = {
    'term': f'id:{test_sku}',
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
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Success! Data received.")
        print(response.text[:200]) # מדפיס את תחילת התשובה
    else:
        print("Error Response:")
        print(response.text) # מדפיס את סיבת השגיאה
        
except Exception as e:
    print(f"Exception: {e}")