import pandas as pd
import xlsxwriter
import os
from datetime import datetime
import config

def load_or_create_db():
    if os.path.exists(config.DB_FILENAME):
        print(f"📂 Loading existing database: {config.DB_FILENAME}")
        try:
            df = pd.read_excel(config.DB_FILENAME, sheet_name='Products', dtype=str)
            df = df.replace('nan', '')
            df = df.fillna('')
            
            for col in config.FINAL_COLUMNS:
                if col not in df.columns:
                    print(f"✨ Adding new column: {col}")
                    df[col] = ""
            return df
        except Exception as e:
            print(f"⚠️ Error loading DB: {e}. Creating new one.")
    
    print("🆕 Creating new database...")
    return pd.DataFrame(columns=config.FINAL_COLUMNS).astype(str)

def save_styled_db(df, rates_dict):
    print(f"💾 Saving formatted database to {config.DB_FILENAME}...")
    
    writer = pd.ExcelWriter(config.DB_FILENAME, engine='xlsxwriter')
    workbook = writer.book

    # סידור העמודות לפי ה-CONFIG הסופי
    df = df[config.FINAL_COLUMNS] 
    df.to_excel(writer, index=False, sheet_name='Products', startrow=1, header=False)
    worksheet_prod = writer.sheets['Products']
    
    styles = _create_styles(workbook)
    
    # כתיבת כותרות
    for col_num, value in enumerate(config.FINAL_COLUMNS):
        worksheet_prod.write(0, col_num, value, styles['header'])
        
    int_cols = ["MOQ", "Multiple", "Supplier 1 Stock", "Supplier 2 Stock", "Supplier 3 Stock"]
    price_cols = ["Cost", "Supplier 1 Cost", "Supplier 2 Cost", "Supplier 3 Cost"]

    for row_idx in range(len(df)):
        excel_row = row_idx + 2 
        is_even = (row_idx % 2 == 0)
        current_set = styles['white'] if is_even else styles['green']
            
        for col_idx, col_name in enumerate(config.FINAL_COLUMNS):
            val = df.iloc[row_idx, col_idx]
            
            # --- 1. הדגשה מיוחדת לזמינות מוגבלת (התיקון כאן!) ---
            val_str = str(val).strip().lower()
            
            # השינוי: בודקים אם "Lead Time" נמצא בתוך שם העמודה (למשל Supplier 1 Lead Time)
            if "Lead Time" in col_name and "stock lasts" in val_str:
                worksheet_prod.write(excel_row-1, col_idx, val, styles['red_bold'])
                continue

            # --- 2. טיפול בשדות בוליאניים (Hazardous + US Stock) ---
            if col_name == "Hazardous" or col_name == "US Stock":
                bool_val = str(val).lower() == 'true'
                worksheet_prod.write_boolean(excel_row-1, col_idx, bool_val, current_set['base'])
                continue

            # --- 3. המרות למספרים ---
            if col_name in int_cols or col_name in price_cols or col_name == "Cost":
                try:
                    if val and val != "":
                        val = float(val)
                except:
                    pass
            
            if pd.isna(val): val = ""
            
            # --- 4. נוסחאות ---
            # הערה: וודא שהפניות התאים (G, A, H וכו') תואמות למיקום העמודות החדש ב-FINAL_COLUMNS שלך
            # בנוסחאות כאן הנחתי שהמיקומים היחסיים לא השתנו דרמטית, אך ייתכן שתצטרך להתאים את האותיות
            # אם הוספת עמודות באמצע. כרגע השארתי את זה גנרי.
            
            if col_name == "Real ILS Cost":
                # שים לב: זה מחפש את Buy Currency. אם שינית מיקום עמודות, צריך לוודא ש-G זה עדיין Buy Currency
                # בקונפיג שלך Buy Currency הוא עמודה 7 (אינדקס 6) -> שזה G באקסל. אז זה תקין.
                formula = f"=F{excel_row}*VLOOKUP(G{excel_row},'Financial Variables'!$A$3:$D$20,2,FALSE)"
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
            
            elif col_name == "Price No VAT":
                formula = f"=F{excel_row}*VLOOKUP(G{excel_row},'Financial Variables'!$A$3:$D$20,4,FALSE)"
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])

            elif col_name == "VAT":
                # I זה Real ILS Cost (עמודה 9) -> לא, בקונפיג שלך זה עמודה 9 (I). תקין.
                formula = f"=I{excel_row}*'Financial Variables'!$H$3"
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                
            elif col_name == "Price With VAT":
                formula = f"=I{excel_row}+J{excel_row}" # J זה Price No VAT. (עמודה 10). תקין.
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                
            # --- 5. כתיבה לפי סוג ---
            elif col_name == "Date Updated":
                worksheet_prod.write(excel_row-1, col_idx, val, current_set['date'])
            elif col_name in int_cols and isinstance(val, (int, float)):
                worksheet_prod.write(excel_row-1, col_idx, val, current_set['int'])
            elif isinstance(val, (int, float)):
                worksheet_prod.write(excel_row-1, col_idx, val, current_set['num'])
            else:
                worksheet_prod.write(excel_row-1, col_idx, val, current_set['base'])

    _set_column_widths(worksheet_prod)
    _create_financial_sheet(workbook, rates_dict, styles)

    writer.close()
    print("✅ Database saved successfully.")

def _create_styles(workbook):
    base_props = {'border': 1, 'valign': 'vcenter'}
    header = workbook.add_format({'bold': True, 'fg_color': '#548235', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
    
    # סגנון אדום מודגש
    red_bold = workbook.add_format({
        **base_props, 
        'fg_color': '#FFC7CE', 
        'font_color': '#9C0006', 
        'bold': True, 
        'align': 'center'
    })

    white = {
        'base': workbook.add_format({**base_props, 'fg_color': 'white'}),
        'date': workbook.add_format({**base_props, 'fg_color': 'white', 'num_format': 'dd/mm/yyyy'}), 
        'num':  workbook.add_format({**base_props, 'fg_color': 'white', 'num_format': '0.0000'}),
        'int':  workbook.add_format({**base_props, 'fg_color': 'white', 'num_format': '0'})
    }
    green = {
        'base': workbook.add_format({**base_props, 'fg_color': '#E2EFDA'}),
        'date': workbook.add_format({**base_props, 'fg_color': '#E2EFDA', 'num_format': 'dd/mm/yyyy'}),
        'num':  workbook.add_format({**base_props, 'fg_color': '#E2EFDA', 'num_format': '0.0000'}),
        'int':  workbook.add_format({**base_props, 'fg_color': '#E2EFDA', 'num_format': '0'})
    }
    return {'header': header, 'white': white, 'green': green, 'red_bold': red_bold}

def _set_column_widths(worksheet):
    worksheet.set_column('A:A', 25) 
    worksheet.set_column('B:D', 18) 
    worksheet.set_column('E:E', 30) 
    worksheet.set_column('F:L', 12) 
    worksheet.set_column('M:O', 10) 
    worksheet.set_column('P:T', 15) 
    worksheet.set_column('U:X', 15) 
    worksheet.set_column('Y:AB', 15) 
    worksheet.set_column('AC:AD', 20)

def _create_financial_sheet(workbook, rates_dict, styles):
    worksheet = workbook.add_worksheet('Financial Variables')
    header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
    rate_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0.0000'})
    percent_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0%'})
    date_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': 'dd/mm/yyyy'})

    worksheet.merge_range('A1:D1', 'Currencies & Multipliers Logic', header_fmt)
    headers = ['Currency', 'Rate to ILS', 'Last Update', 'Pricing Multiplier']
    for i, h in enumerate(headers):
        worksheet.write(1, i, h, header_fmt)
    
    today = datetime.now()
    
    worksheet.write('A3', 'GBP', cell_fmt)
    worksheet.write('B3', rates_dict.get('GBP', 0), rate_fmt)
    worksheet.write('C3', today, date_fmt)
    worksheet.write('D3', 10, cell_fmt)
    
    worksheet.write('A4', 'USD', cell_fmt)
    worksheet.write('B4', rates_dict.get('USD', 0), rate_fmt)
    worksheet.write('C4', today, date_fmt)
    worksheet.write('D4', 7, cell_fmt)
    
    worksheet.merge_range('G1:H1', 'Global Constants', header_fmt)
    worksheet.write('G2', 'Parameter', header_fmt)
    worksheet.write('H2', 'Value', header_fmt)
    worksheet.write('G3', 'VAT Percentage', cell_fmt)
    worksheet.write('H3', config.VAT_PERCENT, percent_fmt)

    worksheet.set_column('A:D', 18)
    worksheet.set_column('E:F', 2)
    worksheet.set_column('G:H', 20)