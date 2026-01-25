import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import os
from datetime import datetime
import config

# מיפוי: איזה עמודה ראשית מקושרת לאיזה שדה אצל הספק
LINK_MAP = {
    'Cost': 'Cost',
    'Buy Currency': 'Currency',
    'Stock': 'Stock',
    'Lead Time': 'Lead Time',
    'MOQ': 'MOQ',
    'Multiple': 'Multiple'
}

def load_or_create_db():
    if os.path.exists(config.DB_FILENAME):
        print(f"📂 Loading existing database: {config.DB_FILENAME}")
        try:
            df = pd.read_excel(config.DB_FILENAME, sheet_name='Products', dtype=str)
            df = df.replace('nan', '')
            df = df.fillna('')
            for col in config.FINAL_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception as e:
            print(f"⚠️ Error loading DB: {e}. Creating new one.")
    
    print("🆕 Creating new database...")
    return pd.DataFrame(columns=config.FINAL_COLUMNS).astype(str)

def get_col_letter(col_name):
    try:
        idx = config.FINAL_COLUMNS.index(col_name)
        return xl_col_to_name(idx)
    except ValueError:
        return None

def save_styled_db(df, rates_dict):
    print(f"💾 Saving formatted database to {config.DB_FILENAME}...")
    
    writer = pd.ExcelWriter(config.DB_FILENAME, engine='xlsxwriter')
    workbook = writer.book

    df = df[config.FINAL_COLUMNS] 
    df.to_excel(writer, index=False, sheet_name='Products', startrow=1, header=False)
    worksheet_prod = writer.sheets['Products']
    
    styles = _create_styles(workbook)
    
    # כתיבת כותרות
    for col_num, value in enumerate(config.FINAL_COLUMNS):
        worksheet_prod.write(0, col_num, value, styles['header'])
        
    int_cols = ["MOQ", "Multiple", "Stock", "Supplier 1 Stock", "Supplier 2 Stock", "Supplier 3 Stock",
                "Supplier 1 MOQ", "Supplier 2 MOQ", "Supplier 3 MOQ",
                "Supplier 1 Multiple", "Supplier 2 Multiple", "Supplier 3 Multiple", "Best Supplier Slot"]
    
    # --- הכנת האותיות לנוסחאות ---
    
    # 1. אותיות לעמודות הראשיות (לחישובי מע"מ)
    col_cost = get_col_letter("Cost")
    col_currency = get_col_letter("Buy Currency")
    col_price_no_vat = get_col_letter("Price No VAT")
    
    # 2. אותיות לעמודת ההחלטה (Best Supplier Slot)
    col_slot_decision = get_col_letter("Best Supplier Slot") # התא שקובע מי המנצח (1, 2, 3)

    for row_idx in range(len(df)):
        excel_row = row_idx + 2 
        is_even = (row_idx % 2 == 0)
        current_set = styles['white'] if is_even else styles['green']
        
        for col_idx, col_name in enumerate(config.FINAL_COLUMNS):
            val = df.iloc[row_idx, col_idx]
            
            # --- 1. עיצוב זמינות (Stock Lasts) ---
            val_str = str(val).strip().lower()
            if "Lead Time" in col_name and "stock lasts" in val_str:
                worksheet_prod.write(excel_row-1, col_idx, val, styles['red_bold'])
                continue

            # --- 2. בוליאניים ---
            if col_name in ["Hazardous", "US Stock", "Show in Website"]:
                bool_val = str(val).lower() == 'true'
                worksheet_prod.write_boolean(excel_row-1, col_idx, bool_val, current_set['base'])
                continue

            # --- 3. קישור דינמי אמיתי (Excel Logic) ---
            # הנוסחה: =IFERROR(CHOOSE($SlotCell, Sup1Cell, Sup2Cell, Sup3Cell), "")
            
            if col_name in LINK_MAP and col_slot_decision:
                suffix = LINK_MAP[col_name]
                
                # מציאת האותיות של שלושת הספקים עבור השדה הנוכחי
                sup1 = get_col_letter(f"Supplier 1 {suffix}")
                sup2 = get_col_letter(f"Supplier 2 {suffix}")
                sup3 = get_col_letter(f"Supplier 3 {suffix}")
                
                if sup1 and sup2 and sup3:
                    # בניית הנוסחה
                    # CHOOSE(Slot, Sup1, Sup2, Sup3)
                    # IFERROR עוטף את זה למקרה שהסלוט ריק או 0
                    formula = f'=IFERROR(CHOOSE({col_slot_decision}{excel_row},{sup1}{excel_row},{sup2}{excel_row},{sup3}{excel_row}),"")'
                    
                    # קביעת פורמט
                    fmt = current_set['num']
                    if col_name in ["Stock", "MOQ", "Multiple"]: fmt = current_set['int']
                    if col_name in ["Buy Currency", "Lead Time"]: fmt = current_set['base']
                    
                    worksheet_prod.write_formula(excel_row-1, col_idx, formula, fmt)
                    continue

            # --- 4. שאר הנוסחאות (עלות שקלים, מע"מ וכו') ---
            
            # עלות בשקלים לכל ספק
            if "Cost ILS" in col_name:
                prefix = col_name.replace(" Cost ILS", "") 
                sup_cost_letter = get_col_letter(f"{prefix} Cost")
                sup_curr_letter = get_col_letter(f"{prefix} Currency")
                
                if sup_cost_letter and sup_curr_letter:
                    formula = f'=IF(OR({sup_cost_letter}{excel_row}="",{sup_curr_letter}{excel_row}=""),"",{sup_cost_letter}{excel_row}*VLOOKUP({sup_curr_letter}{excel_row},\'Financial Variables\'!$A$3:$D$20,2,FALSE))'
                    worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                    continue

            # חישובים ראשיים
            elif col_name == "Real ILS Cost" and col_cost and col_currency:
                formula = f'=IF(OR({col_cost}{excel_row}="",{col_currency}{excel_row}=""),"",{col_cost}{excel_row}*VLOOKUP({col_currency}{excel_row},\'Financial Variables\'!$A$3:$D$20,2,FALSE))'
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                continue
            
            elif col_name == "Price No VAT" and col_cost and col_currency:
                formula = f'=IF(OR({col_cost}{excel_row}="",{col_currency}{excel_row}=""),"",{col_cost}{excel_row}*VLOOKUP({col_currency}{excel_row},\'Financial Variables\'!$A$3:$D$20,4,FALSE))'
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                continue

            elif col_name == "VAT" and col_price_no_vat:
                formula = f'=IF({col_price_no_vat}{excel_row}="","", {col_price_no_vat}{excel_row}*\'Financial Variables\'!$H$3)'
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                continue
                
            elif col_name == "Price With VAT" and col_price_no_vat:
                formula = f'=IF({col_price_no_vat}{excel_row}="","", {col_price_no_vat}{excel_row}*(1+\'Financial Variables\'!$H$3))'
                worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                continue

            # --- 5. כתיבה רגילה ---
            try:
                if col_name in int_cols or "Cost" in col_name:
                    if val and val != "": val = float(val)
            except: pass

            if pd.isna(val): val = ""

            if "Date" in col_name:
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

# ... (פונקציות העזר _create_styles, _set_column_widths, _create_financial_sheet נשארות ללא שינוי) ...
def _create_styles(workbook):
    base_props = {'border': 1, 'valign': 'vcenter'}
    header = workbook.add_format({'bold': True, 'fg_color': '#548235', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
    red_bold = workbook.add_format({**base_props, 'fg_color': '#FFC7CE', 'font_color': '#9C0006', 'bold': True, 'align': 'center'})
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
    worksheet.set_column(0, 5, 20)
    worksheet.set_column(6, 15, 12)
    worksheet.set_column(16, 18, 15)
    worksheet.set_column(19, 100, 14)

def _create_financial_sheet(workbook, rates_dict, styles):
    worksheet = workbook.add_worksheet('Financial Variables')
    header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
    rate_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0.0000'})
    percent_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0%'})
    date_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': 'dd/mm/yyyy'})
    worksheet.merge_range('A1:D1', 'Currencies & Multipliers Logic', header_fmt)
    headers = ['Currency', 'Rate to ILS', 'Last Update', 'Pricing Multiplier']
    for i, h in enumerate(headers): worksheet.write(1, i, h, header_fmt)
    today = datetime.now()
    row = 2
    for currency, rate in rates_dict.items():
        if currency == 'ILS': continue
        multiplier = 10 if currency == 'GBP' else 7
        worksheet.write(row, 0, currency, cell_fmt)
        worksheet.write(row, 1, rate, rate_fmt)
        worksheet.write(row, 2, today, date_fmt)
        worksheet.write(row, 3, multiplier, cell_fmt)
        row += 1
    worksheet.merge_range('G1:H1', 'Global Constants', header_fmt)
    worksheet.write('G2', 'Parameter', header_fmt)
    worksheet.write('H2', 'Value', header_fmt)
    worksheet.write('G3', 'VAT Percentage', cell_fmt)
    worksheet.write('H3', config.VAT_PERCENT, percent_fmt)
    worksheet.set_column('A:D', 18)
    worksheet.set_column('E:F', 2)
    worksheet.set_column('G:H', 20)