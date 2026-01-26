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
    'Multiple': 'Multiple',
    'Best Supplier Name': 'Name' 
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

# --- פונקציה לשמירת ה-DB הראשי ---
def save_styled_db(df, rates_dict):
    print(f"💾 Saving formatted database to {config.DB_FILENAME}...")
    
    try:
        writer = pd.ExcelWriter(config.DB_FILENAME, engine='xlsxwriter')
        workbook = writer.book

        df = df[config.FINAL_COLUMNS] 
        df.to_excel(writer, index=False, sheet_name='Products', startrow=1, header=False)
        worksheet_prod = writer.sheets['Products']
        
        # יצירת הסגנונות (ללא text_wrap)
        styles = _create_styles(workbook)
        
        # --- כתיבת כותרות ---
        for col_num, value in enumerate(config.FINAL_COLUMNS):
            style_to_use = styles['header']
            
            if "Supplier 1" in value:
                style_to_use = styles['header_sup1']
            elif "Supplier 2" in value:
                style_to_use = styles['header_sup2']
            elif "Supplier 3" in value:
                style_to_use = styles['header_sup3']
            
            worksheet_prod.write(0, col_num, value, style_to_use)
            
        int_cols = ["MOQ", "Multiple", "Stock", "Supplier 1 Stock", "Supplier 2 Stock", "Supplier 3 Stock",
                    "Supplier 1 MOQ", "Supplier 2 MOQ", "Supplier 3 MOQ",
                    "Supplier 1 Multiple", "Supplier 2 Multiple", "Supplier 3 Multiple", "Best Supplier Slot"]
        
        col_cost = get_col_letter("Cost")
        col_currency = get_col_letter("Buy Currency")
        col_price_no_vat = get_col_letter("Price No VAT")
        col_slot_decision = get_col_letter("Best Supplier Slot")

        for row_idx in range(len(df)):
            excel_row = row_idx + 2 
            is_even = (row_idx % 2 == 0)
            
            # --- קיבוע גובה שורה ל-20 (כפי שביקשת) ---
            worksheet_prod.set_row(excel_row-1, 20)

            for col_idx, col_name in enumerate(config.FINAL_COLUMNS):
                val = df.iloc[row_idx, col_idx]
                
                # --- בחירת ערכת נושא ---
                if "Supplier 1" in col_name:
                    current_set = styles['sup1_even'] if is_even else styles['sup1_odd']
                elif "Supplier 2" in col_name:
                    current_set = styles['sup2_even'] if is_even else styles['sup2_odd']
                elif "Supplier 3" in col_name:
                    current_set = styles['sup3_even'] if is_even else styles['sup3_odd']
                else:
                    current_set = styles['main_even'] if is_even else styles['main_odd']

                cell_format = current_set['base']
                
                try:
                    if col_name in int_cols or "Cost" in col_name:
                        if val and val != "": 
                            val = float(val)
                except: pass

                if pd.isna(val): val = ""

                if "Date" in col_name:
                     cell_format = current_set['date']
                elif col_name in int_cols and isinstance(val, (int, float)):
                    cell_format = current_set['int']
                elif isinstance(val, (int, float)):
                    cell_format = current_set['num']

                # --- גבולות עבים ---
                if col_name in ["Supplier 1 Name", "Supplier 2 Name", "Supplier 3 Name"]:
                    cell_format = current_set['base_left_thick'] 
                elif col_name == "Supplier 3 Last Check":
                     cell_format = current_set['base_right_thick']

                # --- כתיבת הנתונים ---

                # 1. Lead Time Red
                val_str = str(val).strip().lower()
                if "Lead Time" in col_name and "stock lasts" in val_str:
                    worksheet_prod.write(excel_row-1, col_idx, val, current_set['red_text'])
                    continue

                # 2. Booleans
                if col_name in ["Hazardous", "US Stock", "Show in Website"]:
                    bool_val = str(val).lower() == 'true'
                    worksheet_prod.write_boolean(excel_row-1, col_idx, bool_val, cell_format)
                    continue

                # 3. Dynamic Linking
                if col_name in LINK_MAP and col_slot_decision:
                    suffix = LINK_MAP[col_name]
                    sup1 = get_col_letter(f"Supplier 1 {suffix}")
                    sup2 = get_col_letter(f"Supplier 2 {suffix}")
                    sup3 = get_col_letter(f"Supplier 3 {suffix}")
                    
                    if sup1 and sup2 and sup3:
                        formula = f'=IFERROR(CHOOSE({col_slot_decision}{excel_row},{sup1}{excel_row},{sup2}{excel_row},{sup3}{excel_row}),"")'
                        worksheet_prod.write_formula(excel_row-1, col_idx, formula, cell_format)
                        continue

                # 4. Supplier Cost ILS
                if "Cost ILS" in col_name:
                    prefix = col_name.replace(" Cost ILS", "") 
                    sup_cost_letter = get_col_letter(f"{prefix} Cost")
                    sup_curr_letter = get_col_letter(f"{prefix} Currency")
                    if sup_cost_letter and sup_curr_letter:
                        formula = f'=IF(OR({sup_cost_letter}{excel_row}="",{sup_curr_letter}{excel_row}=""),"",{sup_cost_letter}{excel_row}*VLOOKUP({sup_curr_letter}{excel_row},\'Financial Variables\'!$A$3:$D$20,2,FALSE))'
                        worksheet_prod.write_formula(excel_row-1, col_idx, formula, current_set['num'])
                        continue

                # 5. Main Calcs
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

                # 6. Regular Values
                worksheet_prod.write(excel_row-1, col_idx, val, cell_format)

        _set_column_widths(worksheet_prod)
        _create_financial_sheet(workbook, rates_dict, styles)
        writer.close()
        print("✅ Database saved successfully.")
    except Exception as e:
        print(f"❌ Error saving DB: {e}")

# --- הפונקציה החדשה לשמירת לוג השינויים המעוצב ---
def save_changes_log(df):
    print(f"💾 Saving changes log to {config.CHANGES_LOG_FILENAME}...")
    try:
        writer = pd.ExcelWriter(config.CHANGES_LOG_FILENAME, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Changes')
        
        workbook = writer.book
        worksheet = writer.sheets['Changes']
        
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': False, 'valign': 'top',
            'fg_color': '#D7E4BC', 'border': 1
        })
        
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)
            
        worksheet.set_column('A:A', 18)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 18)
        worksheet.set_column('D:E', 25)
        worksheet.set_column('F:F', 22)
        worksheet.set_column('G:G', 50)
        
        red_text = workbook.add_format({'font_color': '#9C0006', 'bold': True})
        green_text = workbook.add_format({'font_color': '#006100', 'bold': True})
        
        worksheet.set_column('D:D', 25, red_text)
        worksheet.set_column('E:E', 25, green_text)
        
        worksheet.write(0, 3, "Old Value", header_format)
        worksheet.write(0, 4, "New Value", header_format)

        if len(df) > 0:
            for change_text, hex_color in config.LOG_COLORS.items():
                format_obj = workbook.add_format({'bg_color': hex_color, 'border': 1})
                worksheet.conditional_format(1, 5, len(df), 5, {
                    'type':     'text',
                    'criteria': 'containing',
                    'value':    change_text,
                    'format':   format_obj
                })

        writer.close()
        print("✅ Log saved successfully.")
        
    except Exception as e:
        print(f"❌ Error saving Log: {e}")

# --- פונקציות עזר פנימיות ---
def _create_styles(workbook):
    # הסרתי את text_wrap=True
    base_props = {'border': 1, 'valign': 'vcenter'} 
    
    # Headers
    header = workbook.add_format({'bold': True, 'fg_color': '#548235', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
    header_sup1 = workbook.add_format({'bold': True, 'fg_color': '#4472C4', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
    header_sup2 = workbook.add_format({'bold': True, 'fg_color': '#FF66CC', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
    header_sup3 = workbook.add_format({'bold': True, 'fg_color': '#7030A0', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})

    props_thick_left = base_props.copy()
    props_thick_left['left'] = 2 
    props_thick_right = base_props.copy()
    props_thick_right['right'] = 2

    red_text_props = {'font_color': '#9C0006', 'bold': True, 'align': 'center'}

    def create_color_set(bg_color):
        return {
            'base': workbook.add_format({**base_props, 'fg_color': bg_color}),
            'date': workbook.add_format({**base_props, 'fg_color': bg_color, 'num_format': 'dd/mm/yyyy'}), 
            'num':  workbook.add_format({**base_props, 'fg_color': bg_color, 'num_format': '0.0000'}),
            'int':  workbook.add_format({**base_props, 'fg_color': bg_color, 'num_format': '0'}),
            'base_left_thick': workbook.add_format({**props_thick_left, 'fg_color': bg_color}),
            'base_right_thick': workbook.add_format({**props_thick_right, 'fg_color': bg_color}),
            'red_text': workbook.add_format({**base_props, 'fg_color': bg_color, **red_text_props})
        }

    # צבעים
    main_even_col = "#E7F0E2"
    main_odd_col = "#CDE6BE" 

    sup1_even_col = '#D9E1F2' 
    sup1_odd_col = '#B4C6E7'  

    sup2_even_col = '#FFE6F7' 
    sup2_odd_col = '#FFCCF2'  

    sup3_even_col = '#F2E6FF' 
    sup3_odd_col = '#E5CCFF'  

    return {
        'header': header, 
        'header_sup1': header_sup1, 
        'header_sup2': header_sup2, 
        'header_sup3': header_sup3,
        
        'main_even': create_color_set(main_even_col),
        'main_odd': create_color_set(main_odd_col),
        
        'sup1_even': create_color_set(sup1_even_col),
        'sup1_odd': create_color_set(sup1_odd_col),
        
        'sup2_even': create_color_set(sup2_even_col),
        'sup2_odd': create_color_set(sup2_odd_col),
        
        'sup3_even': create_color_set(sup3_even_col),
        'sup3_odd': create_color_set(sup3_odd_col),
    }

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