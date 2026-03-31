import requests
import os
from datetime import datetime, timedelta
import time

# Klucze pobierane z GitHub Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") # Tu ma być ID kanału: -100...

# Lista głównych lotnisk w Polsce obsługiwanych przez Ryanair
POLISH_AIRPORTS = ["WMI", "KRK", "WRO", "GDN", "POZ", "KTW", "LUZ", "RZE", "LCJ"]

# REALISTYCZNE ŚREDNIE CENY (w jedną stronę, w PLN)
# Program automatycznie pomnoży te kwoty x2 dla lotów powrotnych.
AVERAGE_PRICES = {
    "Sweden": 140,
    "Norway": 140,
    "Denmark": 150,
    "United Kingdom": 220, 
    "Ireland": 280,
    "Italy": 320,
    "Spain": 480,
    "Greece": 450,
    "Croatia": 380,
    "Jordan": 550,
    "Cyprus": 420,
    "Malta": 400,
    "France": 280,
    "Portugal": 550,
    "Morocco": 500,
    "Albania": 350,
    "Bulgaria": 350,
    "Montenegro": 350,
    "DEFAULT": 300 
}

def send_telegram_message(text):
    """Wysyła sformatowaną wiadomość HTML na kanał Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("BŁĄD: Brak konfiguracji Telegrama w Secrets!")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("-> Sukces: Alert wysłany na kanał.")
    except Exception as e:
        print(f"-> Błąd wysyłania wiadomości: {e}")

def search_ryanair_roundtrips():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Start skanowania okazji (Roundtrip max 14 dni)...")
    
    # Okno wyszukiwania: od jutra do 4 miesięcy w przód
    date_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    deals_counter = 0

    for origin_iata in POLISH_AIRPORTS:
        print(f"Sprawdzam wyloty z: {origin_iata}...")
        base_url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
        
        # KROK 1: Szukamy tanich wylotów
        params_out = {
            "departureAirportIataCode": origin_iata,
            "language": "pl", "market": "pl-pl",
            "outboundDepartureDateFrom": date_from,
            "outboundDepartureDateTo": date_to,
            "currency": "PLN"
        }
        
        try:
            res_out = requests.get(base_url, params=params_out, headers=headers)
            if res_out.status_code != 200:
                continue
                
            for fare_out in res_out.json().get("fares", []):
                out_data = fare_out.get("outbound", {})
                out_price = float(out_data.get("price", {}).get("value", 0))
                dest_iata = out_data.get("arrivalAirport", {}).get("iataCode")
                dest_name = out_data.get("arrivalAirport", {}).get("name")
                country = out_data.get("arrivalAirport", {}).get("countryName", "DEFAULT")
                out_date = out_data.get("departureDate", "").split('T')[0]
                
                if not out_date or out_price == 0: continue
                
                # Obliczamy próg cenowy dla dwóch stron (Średnia x 2 * 0.40)
                avg_rt_price = AVERAGE_PRICES.get(country, AVERAGE_PRICES["DEFAULT"]) * 2
                max_allowed_total = avg_rt_price * 0.30
                
                # Jeśli sam wylot przekracza budżet na całość, pomijamy
                if out_price >= max_allowed_total: continue
                
                # KROK 2: Szukamy powrotu (od 1 do 14 dni po wylocie)
                ret_from = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                ret_to = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")
                
                params_in = {
                    "departureAirportIataCode": dest_iata,
                    "arrivalAirportIataCode": origin_iata,
                    "language": "pl", "market": "pl-pl",
                    "outboundDepartureDateFrom": ret_from,
                    "outboundDepartureDateTo": ret_to,
                    "currency": "PLN"
                }
                
                time.sleep(1) # Grzecznościowa pauza dla serwera
                res_in = requests.get(base_url, params=params_in, headers=headers)
                
                if res_in.status_code == 200:
                    for fare_in in res_in.json().get("fares", []):
                        in_data = fare_in.get("outbound", {})
                        in_price = float(in_data.get("price", {}).get("value", 0))
                        in_date = in_data.get("departureDate", "").split('T')[0]
                        
                        if in_price == 0: continue
                        
                        total_price = out_price + in_price
                        
                        # KROK 3: Weryfikacja Hitu Cenowego
                        if total_price <= max_allowed_total:
                            deals_counter += 1
                            discount_pct = 100 - ((total_price / avg_rt_price) * 100)
                            
                            # Generowanie profesjonalnego Deep Linku do rezerwacji
                            booking_link = (
                                f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=1&teens=0&children=0&infants=0"
                                f"&dateOut={out_date}&dateIn={in_date}&isConnectedFlight=false&isReturn=true&discount=0"
                                f"&promoCode=&originIata={origin_iata}&destinationIata={dest_iata}"
                            )
                            
                            # Budowa estetycznej wiadomości
                            msg = (
                                f"🔥 <b>HIT! {country.upper()} (-{discount_pct:.0f}%)</b>\n\n"
                                f"✈️ <b>Trasa:</b> {origin_iata} ↔️ {dest_iata} ({dest_name})\n"
                                f"🛫 <b>Wylot:</b> {out_date} (<b>{out_price:.2f} PLN</b>)\n"
                                f"🛬 <b>Powrót:</b> {in_date} (<b>{in_price:.2f} PLN</b>)\n"
                                f"💰 <b>SUMA: {total_price:.2f} PLN</b>\n"
                                f"<i>Normalna cena ok. {avg_rt_price:.2f} PLN</i>\n\n"
                                f"<a href='{booking_link}'>🔗 ZAREZERWUJ LOT (Ryanair.com)</a>"
                            )
                            send_telegram_message(msg)
                            time.sleep(1.5) # Przerwa między alertami
                            
            time.sleep(2) # Oddech między lotniskami wylotowymi
            
        except Exception as e:
            print(f"Błąd przy {origin_iata}: {e}")

    print(f"Zakończono. Znaleziono okazji: {deals_counter}")

if __name__ == "__main__":
    search_ryanair_roundtrips()
