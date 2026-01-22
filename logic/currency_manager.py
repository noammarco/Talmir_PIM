# logic/currency_manager.py
import requests

def get_rate(currency_code):
    """מושך שער יציג עבור מטבע נתון מול השקל"""
    # אם זה כבר שקל, השער הוא 1
    if currency_code == 'ILS':
        return 1.0

    print(f"💱 Fetching live {currency_code} to ILS rate...")
    try:
        url = f'https://api.frankfurter.app/latest?from={currency_code}&to=ILS'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            rate = response.json()['rates']['ILS']
            print(f"✅ Current Rate: 1 {currency_code} = {rate} ILS")
            return rate
    except Exception as e:
        print(f"⚠️ Failed to fetch {currency_code} rate ({e}).")
    
    # ערכי גיבוי
    fallback_rates = {'GBP': 4.3, 'USD': 3.7, 'EUR': 4.0}
    return fallback_rates.get(currency_code, 1.0)