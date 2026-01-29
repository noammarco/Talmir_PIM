import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
import re

# --- הגדרות ---
INPUT_FILENAME = 'talmir_skus_only.csv'
OUTPUT_FILENAME = 'talmir_mapped_smart.csv'
SEARCH_URL_TEMPLATE = "https://www.talmir.co.il/s?q={}"
BASE_DOMAIN = "https://www.talmir.co.il"

script_dir = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(script_dir, INPUT_FILENAME)
output_path = os.path.join(script_dir, OUTPUT_FILENAME)

def find_link_by_sku_text(soup, sku):
    """
    מוצא את האלמנט שמכיל את הטקסט של המק"ט,
    ואז מטפס למעלה בהיררכיה כדי למצוא את הקישור למוצר ששייך לו.
    """
    # 1. חיפוש כל האלמנטים שמכילים את המק"ט כטקסט
    # אנו משתמשים בביטוי רגולרי כדי למצוא את הטקסט המדויק
    target_elements = soup.find_all(string=re.compile(re.escape(str(sku))))
    
    for element in target_elements:
        # האלמנט הוא רק טקסט, צריך למצוא את התגית שעוטפת אותו
        parent = element.parent
        
        # עכשיו מטפסים למעלה (עד 5 רמות) כדי למצוא תגית <a> או קונטיינר שמחזיק <a>
        # זה מדמה "חיפוש בסביבה הקרובה" של המק"ט
        current = parent
        for _ in range(5):
            if current is None:
                break
            
            # בדיקה א': האם האלמנט עצמו הוא קישור?
            if current.name == 'a' and 'href' in current.attrs:
                return current['href']
            
            # בדיקה ב': האם יש קישור בתוך האלמנט הנוכחי? (למשל אם המק"ט הוא אח של הקישור)
            # נחפש קישור שמכיל /product/ כדי לא ליפול על כפתורי "הוסף לסל"
            link = current.find('a', href=True)
            if link and "/product/" in link['href']:
                return link['href']
                
            current = current.parent
            
    return None

def get_category_path(sku):
    sku = str(sku).strip()
    search_url = SEARCH_URL_TEMPLATE.format(sku)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    session = requests.Session()
    
    try:
        response = session.get(search_url, headers=headers, timeout=10)
        
        # אם הועברנו ישירות למוצר (Redirect)
        if "/product/" in response.url and "searchphrase" not in response.url:
             product_url = response.url
        else:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # --- השיטה החדשה: חיפוש הלינק לפי מיקום המק"ט בדף ---
            found_href = find_link_by_sku_text(soup, sku)
            
            if found_href:
                product_url = found_href if found_href.startswith("http") else BASE_DOMAIN + (found_href if found_href.startswith('/') else '/' + found_href)
            else:
                # ניסיון אחרון: אולי המק"ט לא מופיע בטקסט החיפוש, אבל יש רק תוצאה אחת רלוונטית?
                # נחפש לינק שנמצא בתוך דיב מרכזי (לרוב main או content) - אבל כרגע נחזיר שגיאה כדי לא לנחש
                return "SKU Text Not Found in Search Results", "N/A"

        # כניסה לדף המוצר ושליפת קטגוריה (כמו שעבד לנו קודם)
        prod_response = session.get(product_url, headers=headers, timeout=10)
        prod_soup = BeautifulSoup(prod_response.content, 'html.parser')
        
        breadcrumb_span = prod_soup.find('span', class_='prodBreadcrumb')
        if breadcrumb_span:
            raw_text = breadcrumb_span.get_text(" ", strip=True)
            clean_path = raw_text.replace('»', '>').replace('  ', ' ').strip()
            return clean_path, product_url
        else:
            return "Category HTML Not Found", product_url

    except Exception as e:
        return f"Error: {e}", "Error"

# --- ראשי ---
print(f"--- מתחיל מיפוי בשיטת 'איתור טקסט' ---")
try:
    df = pd.read_csv(input_path)
except:
    print("קובץ לא נמצא.")
    exit()

results = []

# הרצה על 10 ראשונים לבדיקה
for index, row in df.iterrows():
    sku = row.iloc[0]
    print(f"[{index+1}] מחפש את {sku}...", end=" ")
    
    cat_path, real_url = get_category_path(sku)
    
    print(f"-> {cat_path}")
    
    results.append({'Talmir_SKU': sku, 'Category': cat_path, 'URL': real_url})
    time.sleep(0.5)

pd.DataFrame(results).to_csv(output_path, index=False, encoding='utf-8-sig')