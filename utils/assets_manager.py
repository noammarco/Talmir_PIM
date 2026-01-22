import os
import requests
import config

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def ensure_directories():
    """יוצר את מבנה התיקיות לנכסים אם הוא לא קיים"""
    assets_dir = os.path.join(config.DATA_DIR, 'assets')
    images_dir = os.path.join(assets_dir, 'images')
    datasheets_dir = os.path.join(assets_dir, 'datasheets')
    
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(datasheets_dir, exist_ok=True)
    
    return images_dir, datasheets_dir

def download_image(url, my_sku):
    """מוריד תמונה ושומר אותה תחת {my_sku}.jpg"""
    if not url: return ""
    
    images_dir, _ = ensure_directories()
    filename = f"{my_sku}.jpg"
    full_path = os.path.join(images_dir, filename)
    relative_path = os.path.join('assets', 'images', filename)

    if os.path.exists(full_path):
        return relative_path

    print(f"  🖼️ Downloading image for {my_sku}...")
    return _download_file(url, full_path, relative_path)

def download_datasheet(url, my_sku):
    """מוריד דף נתונים ושומר אותו תחת {my_sku}.pdf"""
    if not url: return ""
    
    _, datasheets_dir = ensure_directories()
    # הנחה: רוב דפי הנתונים הם PDF
    filename = f"{my_sku}.pdf"
    full_path = os.path.join(datasheets_dir, filename)
    relative_path = os.path.join('assets', 'datasheets', filename)

    if os.path.exists(full_path):
        return relative_path

    print(f"  📄 Downloading datasheet for {my_sku}...")
    return _download_file(url, full_path, relative_path)

def _download_file(url, full_path, relative_path):
    """פונקציית עזר פנימית לביצוע ההורדה בפועל"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            with open(full_path, 'wb') as f:
                f.write(response.content)
            return relative_path
        else:
            print(f"  ⚠️ Failed download (Status: {response.status_code})")
            return ""
    except Exception as e:
        print(f"  ⚠️ Error downloading: {e}")
        return ""