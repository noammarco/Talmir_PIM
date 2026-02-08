import requests
import hashlib
import hmac
import base64
import random
from datetime import datetime, timezone

# --- הגדרות ---
FARNELL_API_KEY = 'veeh858ufckjsqud2mgjxrcb'
FARNELL_SECRET_KEY = '8LIlamRE74mt'
FARNELL_CUSTOMER_ID = '100877201998'
FARNELL_STORE_ID = 'il.farnell.com'

# --- רשימת תחפושות (User Agents) ---
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

def get_random_headers():
    """יוצר כותרות דפדפן שנראות אמיתיות"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

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

# המק"ט לבדיקה
test_sku = "1652144"

print(f"--- מתחיל בדיקת יכולת עקיפה ---")
print(f"בודק את המק\"ט: {test_sku}")

# יצירת כותרות מזויפות
headers = get_random_headers()
print(f"מנסה להזדהות כ: {headers['User-Agent'][:60]}...")

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
    # שליחה עם ההדרים החדשים
    response = requests.get(url, params=params, headers=headers, timeout=10)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ הצלחה! הצלחנו לעקוף את החסימה בעזרת שינוי Headers.")
        print("תוכן התשובה (חלקית):", response.text[:200])
    elif response.status_code == 403:
        print("❌ עדיין חסום (403).")
        print("המסקנה: החסימה היא על ה-IP/Key ואינה ניתנת לעקיפה כרגע.")
        print("הפתרון היחיד: להפעיל את הסקריפט עם מנגנון ההמתנה הארוכה.")
    else:
        print(f"שגיאה אחרת: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"Exception: {e}")