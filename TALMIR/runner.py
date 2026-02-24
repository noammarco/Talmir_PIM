import subprocess
import time
from datetime import datetime, timedelta

# הגדרות
SCRIPT_TO_RUN = "talmir_farnell_unified_pipeline.py"
WAIT_HOURS_ON_BLOCK = 24

print("======================================================")
print(f"  מנהל משימות חכם (Runner) עבור: {SCRIPT_TO_RUN}  ")
print("======================================================\n")

while True:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] מפעיל את הסקריפט הראשי...")
    
    # הרצת הסקריפט והמתנה עד שיסיים (או יקרוס)
    result = subprocess.run(["python", SCRIPT_TO_RUN])
    
    # בדיקת קוד היציאה (sys.exit)
    if result.returncode == 0:
        print("\n✅ הסקריפט הראשי סיים לעבור על כל המק\"טים בהצלחה! מנהל המשימות עוצר.")
        break
        
    elif result.returncode == 2:
        # חסימת API - ממתינים 24 שעות
        next_run = datetime.now() + timedelta(hours=WAIT_HOURS_ON_BLOCK)
        print(f"\n🛑 זוהתה חסימת API (קוד 2).")
        print(f"💤 נכנס למצב שינה של {WAIT_HOURS_ON_BLOCK} שעות.")
        print(f"⏰ הריצה הבאה תתחיל אוטומטית ב: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # ממתין את הזמן המוגדר בשניות
        time.sleep(WAIT_HOURS_ON_BLOCK * 3600)
        print("\nההמתנה הסתיימה. מתניע מחדש...")
        
    else:
        # שגיאה אחרת (למשל קובץ לא נמצא, או קריסה של פייתון)
        print(f"\n⚠️ הסקריפט עצר עקב שגיאה לא צפויה (קוד יציאה: {result.returncode}).")
        print("ממתין 5 דקות ומנסה שוב ליתר ביטחון...")
        time.sleep(300)