import datetime
import config

# --- אין יותר HARDCODED RATES ---
# השערים יתקבלו כארגומנט מה-Main

def get_ils_price(cost, currency, rates):
    """
    ממיר מחיר לשקלים לצורך השוואה בלבד, בהתבסס על שערים חיים.
    """
    try:
        cost = float(cost)
        currency = str(currency).upper().strip()
        
        # אם המטבע הוא שקל, השער הוא 1. אחרת, מושכים מהמילון שהתקבל.
        if currency == 'ILS':
            rate = 1.0
        else:
            rate = rates.get(currency, 1.0) # ברירת מחדל 1.0 אם לא נמצא
            
        return cost * rate
    except:
        return 999999.0 # מחיר עתק כדי שלא ייבחר בטעות

def select_winner(candidates):
    """
    בוחר את הספק המנצח.
    1. עדיפות לפארנל.
    2. מחיר זול (בשקלים, לפי השערים החיים).
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
    candidates.sort(key=lambda x: x['ils_cost'])            # עדיפות למחיר נמוך (גובר על הקודם)

    return candidates[0]


def recalculate_row(row, rates):
    """
    הפונקציה הראשית: מקבלת שורה + מילון שערים מעודכן.
    בוחרת מנצח ומעדכנת את ה-Slot Index (מצביע).
    """
    valid_candidates = []
    
    # עדכון מטבע מכירה קבוע
    row['Sell Currency'] = 'ILS'

    # --- איסוף מועמדים ---
    for i in range(1, config.MAX_SUPPLIERS + 1):
        prefix = f"Supplier {i}"
        
        name = row.get(f"{prefix} Name")
        status = row.get(f"{prefix} Status")
        
        if not name: continue 

        if status == config.STATUS_VALID:
            try:
                cost = float(row.get(f"{prefix} Cost", 0))
                currency = row.get(f"{prefix} Currency", 'ILS')
                stock = int(row.get(f"{prefix} Stock", 0))
                
                # כאן השינוי: מעבירים את rates לפונקציית העזר
                ils_price = get_ils_price(cost, currency, rates)
                
                valid_candidates.append({
                    'index': i,
                    'prefix': prefix,
                    'name': name,
                    'cost': cost,
                    'currency': currency,
                    'ils_cost': ils_price,
                    'stock': stock
                })
            except Exception as e:
                print(f"⚠️ Error parsing supplier {i} data: {e}")
                continue

    # --- בחירת מנצח ---
    winner = select_winner(valid_candidates)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")

    if winner:
        # יש מנצח! שומרים רק את ה-Index שלו לקישור דינמי
        row['Best Supplier Name'] = winner['name']
        row['Best Supplier Slot'] = winner['index']
        
        row['Show in Website'] = True
        row['Drop Date'] = None 
        row['Date Updated'] = current_time

    else:
        # אין מנצח
        row['Best Supplier Name'] = "None"
        row['Best Supplier Slot'] = ""
        
        current_show_status = row.get('Show in Website')
        if current_show_status is True or str(current_show_status).upper() == 'TRUE': 
             row['Drop Date'] = current_time
        elif not row.get('Drop Date'): 
             row['Drop Date'] = current_time

        row['Show in Website'] = False
        row['Stock'] = 0

    return row