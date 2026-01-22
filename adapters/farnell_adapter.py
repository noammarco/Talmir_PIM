import requests
import hashlib
import hmac
import base64
import math
from datetime import datetime, timezone
import config

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Connection': 'keep-alive'
}

session = requests.Session()
session.headers.update(HEADERS)

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

def extract_price_for_qty1(prices_list):
    if not prices_list: return 0.0
    for p in prices_list:
        try:
            qty_from = int(p.get('from', 0))
            qty_to = int(p.get('to', 999999999))
            if qty_from <= 1 <= qty_to:
                return float(p.get('cost', 0.0))
        except: continue
    if prices_list: return float(prices_list[0].get('cost', 0.0))
    return 0.0

def check_hazardous(attributes_list):
    if not attributes_list: return False
    for item in attributes_list:
        if item.get('attributeLabel', '').lower() == 'hazardous':
            val = str(item.get('attributeValue', '')).lower()
            return val == 'true'
    return False

def check_direct_ship(raw_data):
    status = raw_data.get('productStatus', '').upper()
    if 'DIRECT' in status: return True
    stock_data = raw_data.get('stock', {})
    if stock_data and 'breakdown' in stock_data:
        for wh in stock_data['breakdown']:
            if 'DIRECT' in wh.get('warehouse', '').upper():
                return True
    return False

def fetch_product_data(sku):
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
        response = session.get(base_url, params=params, timeout=10)
        
        # --- דיבאג במקרה של כישלון ---
        if response.status_code != 200:
            print(f"⚠️ API Error {response.status_code} for {sku}: {response.text[:100]}...") # מדפיס את 100 התווים הראשונים של השגיאה
            return None
        
        data = response.json()
        if data.get('premierFarnellPartNumberReturn', {}).get('numberOfResults', 0) == 0:
            print(f"⚠️ Zero results for {sku}")
            return None
            
        raw = data['premierFarnellPartNumberReturn']['products'][0]
        
        cost_gbp = extract_price_for_qty1(raw.get('prices', []))
        original_sku = str(raw.get('sku'))
        my_sku = original_sku[::-1]
        product_name = raw.get('translatedManufacturerPartNumber') or raw.get('displayName')
        short_desc = raw.get('displayName')
        mpn = raw.get('manufacturerPartNumber')
        if not mpn: mpn = raw.get('translatedManufacturerPartNumber', '')
        
        stock_val = int(raw.get('inv', 0))
        product_status = raw.get('productStatus', 'Unknown')
        is_direct_ship = check_direct_ship(raw)
        
        warehouse_region = "UK"
        stock_data = raw.get('stock', {})
        
        # לוגיקה מעודכנת לאיתור מלאי ארה"ב
        if stock_data and 'breakdown' in stock_data:
            for wh in stock_data['breakdown']:
                inv = int(wh.get('inv', 0))
                region = wh.get('region', 'UK').upper()
                warehouse_name = wh.get('warehouse', '').upper()
                if inv > 0:
                    if region in ['US', 'USA'] or 'US' in warehouse_name:
                        warehouse_region = 'USA'
                        break 
        
        # חישוב US STOCK
        is_us_stock = (warehouse_region == 'USA')

        lead_time_str = "Unknown"
        lead_days = stock_data.get('leastLeadTime')
        
        bad_statuses = ['NO_LONGER_STOCKED', 'NO_LONGER_MANUFACTURED', 'NLS', 'NLM', 'OBSOLETE']
        if product_status.upper() in bad_statuses and stock_val > 0:
            lead_time_str = "Available until stock lasts"
        elif lead_days is not None:
            weeks = math.ceil(lead_days / 7)
            lead_time_str = f"{weeks} Weeks"
        
        image_url = ''
        if raw.get('image'):
             base_name = raw['image'].get('baseName', '')
             if base_name:
                 if base_name.startswith('http'):
                     image_url = base_name
                 else:
                     if warehouse_region == 'USA':
                         image_url = f"https://www.newark.com/productimages/standard/en_US{base_name}"
                     else:
                         image_url = f"https://uk.farnell.com/productimages/standard/en_GB{base_name}"

        datasheet = ''
        if raw.get('datasheets'):
            datasheet = raw['datasheets'][0].get('url', '')

        moq = raw.get('translatedMinimumOrderQuality', 1)
        
        return {
            '1_Product_Name': product_name,
            '2_My_SKU': my_sku,
            '3_Category_Farnell': raw.get('commodityClassCode', 'Needs Mapping'),
            '4_Manufacturer': raw.get('brandName'),
            '4a_MPN': mpn,
            '5_Cost_Buy': cost_gbp,
            '5_Currency_Buy': 'GBP',
            '8_Supplier_Name': 'FARNELL',
            '8_Supplier_SKU': original_sku,
            'Lead_Time': lead_time_str,
            '9_Short_Description': short_desc,
            '11_MOQ': moq,
            '12_Order_Multiple': moq,
            'Extra_Stock': stock_val,
            'Extra_Image': image_url,
            'Extra_Datasheet': datasheet,
            'Hazardous': check_hazardous(raw.get('attributes', [])),
            'is_us_stock': is_us_stock, 
            '_status': product_status,
            '_warehouse': warehouse_region,
            '_is_direct_ship': is_direct_ship
        }

    except Exception as e:
        print(f"❌ Exception for {sku}: {e}")
        return None