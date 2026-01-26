import pandas as pd
import os
from datetime import datetime, timedelta
import config
from utils import excel_manager

class ChangeTracker:
    def __init__(self):
        self.new_logs = []
        self.existing_logs = pd.DataFrame()
        self._load_and_cleanup_old_logs()

    def _load_and_cleanup_old_logs(self):
        if not os.path.exists(config.CHANGES_LOG_FILENAME):
            return
        try:
            df = pd.read_excel(config.CHANGES_LOG_FILENAME)
            if 'Timestamp' not in df.columns:
                self.existing_logs = df
                return

            df['TempDate'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=config.LOG_RETENTION_DAYS)
            
            clean_df = df[(df['TempDate'] > cutoff_date) | (df['TempDate'].isna())].copy()
            clean_df = clean_df.drop(columns=['TempDate'])
            self.existing_logs = clean_df
            
        except Exception as e:
            print(f"⚠️ Warning: Could not cleanup old logs: {e}")

    def _normalize(self, val):
        if pd.isna(val) or val is None: return ""
        s_val = str(val).strip()
        try:
            f_val = float(s_val)
            if f_val.is_integer(): return str(int(f_val))
            return f"{f_val:.2f}" # נרמול ל-2 ספרות אחרי הנקודה להשוואת מחירים
        except:
            return s_val

    def _add_log(self, sku, field, old_val, new_val, change_type, message=""):
        self.new_logs.append({
            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'My SKU': sku,
            'Field': field,
            'Old Value': str(old_val),
            'New Value': str(new_val),
            'Change Type': change_type,
            'Details': message
        })

    def track_changes(self, sku, old_data, new_data, rates):
        # 1. New Product
        if not old_data:
            self._add_log(sku, "Product", "", "Created", "New Product", "Product added to DB")
            cost = new_data.get('Cost', '0')
            currency = new_data.get('Buy Currency', '')
            ils_rate = rates.get(currency, 1.0) if currency != 'ILS' else 1.0
            try:
                ils_val = float(cost) * ils_rate
                msg = f"{cost} {currency} (~{ils_val:.2f} ILS)"
            except: msg = f"{cost} {currency}"
            self._add_log(sku, "Cost", "", cost, "Initial Cost", msg)
            return

        # 2. Cost Change
        old_cost = self._normalize(old_data.get('Cost'))
        new_cost = self._normalize(new_data.get('Cost'))
        if old_cost != new_cost:
            currency = new_data.get('Buy Currency', 'ILS')
            ils_rate = rates.get(currency, 1.0) if currency != 'ILS' else 1.0
            diff_type = "Price Change"
            try:
                if float(new_cost) > float(old_cost): diff_type = "Cost Increase 📈"
                elif float(new_cost) < float(old_cost): diff_type = "Cost Decrease 📉"
                new_ils_val = float(new_cost) * ils_rate
                msg = f"Changed: {old_cost} -> {new_cost} {currency} (~{new_ils_val:.2f} ILS)"
            except: msg = f"Changed: {old_cost} -> {new_cost} {currency}"
            self._add_log(sku, "Cost", old_cost, new_cost, diff_type, msg)

        # 3. Selling Price (Price With VAT) - הטיפול החדש
        old_price = self._normalize(old_data.get('Price With VAT'))
        new_price = self._normalize(new_data.get('Price With VAT'))
        if old_price != new_price:
             self._add_log(sku, "Price (VAT)", old_price, new_price, "Selling Price Update")

        # 4. Winner Changed (Best Supplier Name) - הטיפול החדש
        old_winner = self._normalize(old_data.get('Best Supplier Name'))
        new_winner = self._normalize(new_data.get('Best Supplier Name'))
        if old_winner != new_winner:
            self._add_log(sku, "Best Supplier", old_winner, new_winner, "Winner Changed")

        # 5. Suppliers (Name & Status)
        for i in range(1, config.MAX_SUPPLIERS + 1):
            prefix = f"Supplier {i}"
            old_name = self._normalize(old_data.get(f"{prefix} Name"))
            new_name = self._normalize(new_data.get(f"{prefix} Name"))
            
            if old_name != new_name:
                if not old_name and new_name: self._add_log(sku, f"{prefix}", "", new_name, "Supplier Added")
                elif old_name and not new_name: self._add_log(sku, f"{prefix}", old_name, "", "Supplier Removed")
                else: self._add_log(sku, f"{prefix}", old_name, new_name, "Supplier Replaced")

            if new_name:
                old_status = self._normalize(old_data.get(f"{prefix} Status"))
                new_status = self._normalize(new_data.get(f"{prefix} Status"))
                if old_status != new_status:
                     msg = f"{new_name}: {old_status} -> {new_status}"
                     self._add_log(sku, f"{prefix} Status", old_status, new_status, "Supplier Status Change", msg)

        # 6. Simple Fields
        for field in config.TRACKED_SIMPLE_FIELDS:
            old_val = self._normalize(old_data.get(field))
            new_val = self._normalize(new_data.get(field))
            if old_val != new_val:
                self._add_log(sku, field, old_val, new_val, "Update")

        # 7. Assets (Add/Remove)
        for asset in config.TRACKED_ASSETS:
            old_val = self._normalize(old_data.get(asset))
            new_val = self._normalize(new_data.get(asset))
            if old_val != new_val:
                if not old_val and new_val:
                    self._add_log(sku, asset, "None", "Added", "Asset Added", f"New {asset}")
                elif old_val and not new_val:
                    self._add_log(sku, asset, "Exists", "Removed", "Asset Removed")

    def save_logs(self):
        if not self.new_logs:
            if not self.existing_logs.empty:
                 # משתמשים בפונקציה החדשה של המנג'ר כדי לשמור עם עיצוב גם אם אין חדשים
                 excel_manager.save_changes_log(self.existing_logs)
            return

        print(f"📝 Logging {len(self.new_logs)} changes...")
        new_df = pd.DataFrame(self.new_logs)
        
        if not self.existing_logs.empty:
            final_df = pd.concat([new_df, self.existing_logs], ignore_index=True)
        else:
            final_df = new_df
            
        # שימוש בפונקציית השמירה המעוצבת
        excel_manager.save_changes_log(final_df)