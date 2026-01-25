import datetime
import config

# --- שערי המרה (זמני/קבוע) ---
EXCHANGE_RATES = {
    'GBP': 4.85, 
    'USD': 3.65, 
    'EUR': 4.00, 
    'ILS': 1.00  
}

def get_ils_price(cost, currency):
    """ממיר מחיר לשקלים לצורך השוואה בלבד"""
    try:
        cost = float(cost)
        currency = str(currency).upper().strip()
        rate = EXCHANGE_RATES.get(currency, 1.0) 
        return cost * rate
    except:
        return 999999.0 

def select_winner(candidates):
    """
    בוחר את הספק המנצח.
    1. עדיפות לפארנל.
    2. מחיר זול.
    3. מלאי גבוה.
    """
    if not candidates:
        return None

    # 1. בדיקת עדיפות לפארנל (Farnell First)
    for cand in candidates:
        if 'FARNELL' in cand['name'].upper():
            return cand

    # 2. מיון לפי מחיר ומלאי
    candidates.sort(key=lambda x: x['stock'], reverse=True) # עדיפות למלאי גבוה
    candidates.sort(key=lambda x: x['ils_cost'])            # עדיפות למחיר נמוך

    return candidates[0]


def recalculate_row(row):
    """
    הפונקציה הראשית: עוברת על השורה, בוחרת מנצח ומעדכנת את הראשיים.
    """
    valid_candidates = []

    # --- עדכון מטבע מכירה (קבוע גלובלי) ---
    row['Sell Currency'] = 'ILS' # <--- התיקון שלך: תמיד שקלים

    # --- שלב א: איסוף מועמדים ---
    for i in range(1, config.MAX_SUPPLIERS + 1):
        prefix = f"Supplier {i}"
        
        name = row.get(f"{prefix} Name")
        status = row.get(f"{prefix} Status")
        
        if not name: continue 

        # משתמשים בסטטוס שכבר נקבע ע"י slot_manager
        if status == config.STATUS_VALID:
            try:
                cost = float(row.get(f"{prefix} Cost", 0))
                currency = row.get(f"{prefix} Currency", 'ILS')
                stock = int(row.get(f"{prefix} Stock", 0))
                
                valid_candidates.append({
                    'index': i,
                    'prefix': prefix,
                    'name': name,
                    'cost': cost,
                    'currency': currency,
                    'ils_cost': get_ils_price(cost, currency),
                    'stock': stock
                })
            except Exception as e:
                print(f"⚠️ Error parsing supplier {i} data: {e}")
                continue

    # --- שלב ב: קבלת החלטות ---
    winner = select_winner(valid_candidates)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")

    if winner:
        # יש מנצח!
        prefix = winner['prefix']
        
        # עדכון נתוני המנצח
        row['Best Supplier Name'] = winner['name']
        row['Cost'] = row.get(f"{prefix} Cost")
        row['Buy Currency'] = row.get(f"{prefix} Currency")
        row['Stock'] = row.get(f"{prefix} Stock")
        row['Lead Time'] = row.get(f"{prefix} Lead Time")
        row['MOQ'] = row.get(f"{prefix} MOQ")
        row['Multiple'] = row.get(f"{prefix} Multiple")
        
        row['Show in Website'] = True
        row['Drop Date'] = None 
        row['Date Updated'] = current_time

    else:
        # אין אף ספק תקין
        row['Best Supplier Name'] = "None"
        
        # ניהול Drop Date
        current_show_status = row.get('Show in Website')
        
        # אם זה היה פעיל ועכשיו לא -> נעדכן תאריך הסרה
        if current_show_status is True or str(current_show_status).upper() == 'TRUE': 
             row['Drop Date'] = current_time
        elif not row.get('Drop Date'): 
             row['Drop Date'] = current_time

        row['Show in Website'] = False
        row['Stock'] = 0

    return row