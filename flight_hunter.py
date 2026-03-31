import requests
import os
from datetime import datetime, timedelta
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

POLISH_AIRPORTS = ["WMI", "KRK", "WRO", "GDN", "POZ", "KTW", "LUZ", "RZE", "LCJ"]

# Średnie normalne ceny lotów (w jedną stronę) dla popularnych krajów Ryanaira w PLN.
# Możesz swobodnie edytować te wartości, aby dostosować czułość bota.
AVERAGE_PRICES = {
    "Sweden": 120,
    "Norway": 120,
    "Denmark": 120,
    "United Kingdom": 200,
    "Ireland": 250,
    "Italy": 300,
    "Spain": 400,
    "Greece": 400,
    "Croatia": 300,
    "Jordan": 400,
    "Cyprus": 350,
    "Malta": 350,
    "France": 250,
    "Portugal": 450,
    "Morocco": 450,
    "Albania": 300,
    "Bulgaria": 300,
    "Montenegro": 300,
    "DEFAULT": 250 # Cena domyślna, jeśli kraju nie ma na liście
}

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak kluczy Telegrama.")
        return
    
    # Rozdzielamy numery ID po przecinku i tworzymy z nich listę
    chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',')]
    
    for chat_id in chat_ids:
        if not chat_id: # Zabezpieczenie, gdybyś przypadkiem postawił gdzieś dwa przecinki
            continue
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        
        try:
            requests.post(url, json=payload).raise_for_status()
            print(f"Wysłano ofertę do użytkownika: {chat_id}")
        except Exception as e:
            print(f"Błąd wysyłania do {chat_id}: {e}")
            
        # BARDZO WAŻNE: Telegram blokuje boty, które wysyłają za dużo wiadomości w jednej sekundzie.
        # Dajemy mu pół sekundy oddechu przed wysłaniem wiadomości do kolejnej osoby.
        time.sleep(0.5)

def search_ryanair():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uruchamiam skaner Ryanair...")
    date_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    deals_found = 0

    for airport in POLISH_AIRPORTS:
        print(f"Skanuję lotnisko: {airport}...")
        url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
        
        # Pobieramy najtańsze loty z danego lotniska do 500 PLN, aby mieć z czego filtrować
        params = {
            "departureAirportIataCode": airport,
            "language": "pl", "market": "pl-pl",
            "outboundDepartureDateFrom": date_from,
            "outboundDepartureDateTo": date_to,
            "priceValueTo": 500.0, 
            "currency": "PLN"
        }
        
        try:
            res = requests.get(url, params=params, headers=headers)
            if res.status_code == 200:
                for fare in res.json().get("fares", []):
                    outbound = fare.get("outbound", {})
                    price = outbound.get("price", {}).get("value")
                    country = outbound.get("arrivalAirport", {}).get("countryName", "DEFAULT")
                    
                    # Ustalamy średnią cenę dla tego kraju
                    avg_price = AVERAGE_PRICES.get(country, AVERAGE_PRICES["DEFAULT"])
                    
                    # LOGIKA: Szukamy lotów tańszych o 60% od średniej (czyli cena to maks 40% średniej)
                    max_accepted_price = avg_price * 0.40
                    
                    if price and price <= max_accepted_price:
                        deals_found += 1
                        discount = 100 - ((price / avg_price) * 100)
                        dest_name = outbound['arrivalAirport']['name']
                        dest_iata = outbound['arrivalAirport']['iataCode']
                        dep_date = outbound['departureDate'].split('T')[0]
                        
                        msg = (
                            f"🔥 <b>HIT! {country.upper()} -{discount:.0f}%</b>\n\n"
                            f"✈️ <b>Trasa:</b> {outbound['departureAirport']['name']} ➡️ {dest_name} ({dest_iata})\n"
                            f"📅 <b>Data:</b> {dep_date}\n"
                            f"💰 <b>Cena: {price} PLN</b> <i>(Średnia: {avg_price} PLN)</i>\n\n"
                            f"<a href='https://www.ryanair.com/pl/pl'>🔗 Zarezerwuj na Ryanair</a>"
                        )
                        send_telegram_message(msg)
                        time.sleep(1) # Przerwa dla API Telegrama
            else:
                print(f"-> Błąd {res.status_code} dla lotniska {airport}")
                
            time.sleep(3) # Oddech dla serwerów Ryanaira
            
        except Exception as e:
            print(f"Błąd sieci dla {airport}: {e}")

    if deals_found == 0:
        print("Nie znaleziono lotów tańszych o 60% od średniej.")

if __name__ == "__main__":
    search_ryanair()
