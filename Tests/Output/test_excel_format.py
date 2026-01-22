import pandas as pd
import xlsxwriter

# ==================== הגדרות ====================
FILENAME = 'styled_template_v3.xlsx' # גרסה 3
CURRENCY_NAME = 'GBP'
EXCHANGE_RATE = 4.2583

# רשימת העמודות הסופית (A עד T)
COLUMNS = [
    "Product Name", "SKU", "Manufacturer", "Cost", "Buy Currency", 
    "Real ILS Cost", "Price No VAT", "VAT", "Price With VAT", "Sell Currency",
    "Supplier's Name", "Supplier's SKU", "Supplier's Category", "Description",
    "Hazardous", "MOQ", "Multiple", "Supplier's Stock", "Image", "Datasheet"
]

def create_styled_excel():
    print(f"--- Creating formatted Excel V3: {FILENAME} ---")
    
    # 1. יצירת נתוני דמה (4 מוצרים לבדיקה)
    dummy_data = []
    for i in range(1, 5): 
        dummy_data.append({
            "Product Name": f"Test Product {i}",
            "SKU": f"SKU-{1000+i}",
            "Cost": 0.5 + (i * 0.01),
            "Description": "Test description for column width check",
            "Manufacturer": "TestMfg"
        })
    
    df = pd.DataFrame(dummy_data, columns=COLUMNS)
    
    # 2. יצירת המנוע
    writer = pd.ExcelWriter(FILENAME, engine='xlsxwriter')
    workbook = writer.book

    # ==================== גיליון 1: Products ====================
    df.to_excel(writer, index=False, sheet_name='Products', startrow=1, header=False)
    worksheet_prod = writer.sheets['Products']
    
    # --- הגדרת סגנונות ---
    
    # התיקון בצבע הכותרת: Green, Accent 6, Darker 25%
    header_fmt = workbook.add_format({
        'bold': True,
        'fg_color': '#548235', # <<< הצבע המתוקן והמדויק
        'font_color': 'white',
        'border': 1,
        'valign': 'vcenter',
        'text_wrap': True,
        'align': 'center'
    })
    
    row_fmt_white = workbook.add_format({
        'border': 1,
        'fg_color': 'white',
        'valign': 'vcenter'
    })
    
    row_fmt_green = workbook.add_format({
        'border': 1,
        'fg_color': '#E2EFDA', # ירוק בהיר עדין (Accent 6, Lighter 80%)
        'valign': 'vcenter'
    })

    # --- יישום העיצוב ---
    
    # 1. כותרות
    for col_num, value in enumerate(COLUMNS):
        worksheet_prod.write(0, col_num, value, header_fmt)
        
    # 2. שורות המידע (זברה)
    for row_idx in range(len(df)):
        excel_row = row_idx + 1
        
        # לוגיקה: שורה 0 (ראשונה) לבנה, שורה 1 ירוקה...
        if row_idx % 2 == 0:
            current_fmt = row_fmt_white
        else:
            current_fmt = row_fmt_green
            
        for col_idx in range(len(COLUMNS)):
            val = df.iloc[row_idx, col_idx]
            if pd.isna(val): val = ""
            worksheet_prod.write(excel_row, col_idx, val, current_fmt)

    # 3. רוחב עמודות
    worksheet_prod.set_column('A:A', 25)
    worksheet_prod.set_column('B:C', 15)
    worksheet_prod.set_column('D:J', 12)
    worksheet_prod.set_column('K:M', 15)
    worksheet_prod.set_column('N:N', 45)
    worksheet_prod.set_column('O:Q', 10)
    worksheet_prod.set_column('R:S', 12)
    worksheet_prod.set_column('T:T', 25)

    # ==================== גיליון 2: Exchange Rates ====================
    worksheet_rates = workbook.add_worksheet('Exchange Rates')
    
    rates_header_fmt = workbook.add_format({
        'bold': True,
        'fg_color': '#4F81BD',
        'font_color': 'white',
        'border': 1,
        'align': 'center'
    })
    
    rates_val_fmt = workbook.add_format({
        'border': 1,
        'align': 'center',
        'num_format': '0.0000'
    })
    
    worksheet_rates.merge_range('A1:B1', 'Exchange Rates Used', rates_header_fmt)
    worksheet_rates.write('A2', 'Currency', rates_header_fmt)
    worksheet_rates.write('B2', 'Rate to ILS', rates_header_fmt)
    
    worksheet_rates.write('A3', CURRENCY_NAME, rates_val_fmt)
    worksheet_rates.write('B3', EXCHANGE_RATE, rates_val_fmt)
    
    worksheet_rates.set_column('A:B', 20)

    writer.close()
    print(f"✅ Created: {FILENAME}")

if __name__ == "__main__":
    create_styled_excel()