import requests
import os
from datetime import datetime, timedelta
import time

# Klucze pobierane z GitHub Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Podział lotnisk dla różnych progów cenowych
WAW_AIRPORT = ["WAW"]
WMI_AIRPORT = ["WMI"]
REGIONAL_AIRPORTS = ["KRK", "WRO", "GDN", "POZ", "KTW", "LUZ", "RZE", "LCJ"]
ALL_AIRPORTS = WAW_AIRPORT + WMI_AIRPORT + REGIONAL_AIRPORTS

# REALISTYCZNE ŚREDNIE CENY (w jedną stronę, w PLN)
AVERAGE_PRICES = {
    "Sweden": 100, "Norway": 100, "Denmark": 150, "United Kingdom": 220, 
    "Ireland": 280, "Italy": 220, "Spain": 480, "Greece": 450,
    "Croatia": 380, "Jordan": 550, "Cyprus": 420, "Malta": 400,
    "France": 280, "Portugal": 550, "Morocco": 500, "Albania": 200,
    "Bulgaria": 350, "Montenegro": 350, "DEFAULT": 300 
}

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("BŁĄD: Brak konfiguracji Telegrama.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        print(f"Błąd wysyłania: {e}")

def search_ryanair_roundtrips():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Start skanowania (WAW:0.4 | WMI:0.3 | Regiony:0.15)...")
    date_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    deals_counter = 0

    for origin_iata in ALL_AIRPORTS:
        print(f"Skanuję: {origin_iata}...")
        base_url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
        
        # Nowa logika progów (Thresholds)
        if origin_iata in WAW_AIRPORT:
            threshold = 0.40
        elif origin_iata in WMI_AIRPORT:
            threshold = 0.30
        else:
            threshold = 0.15
        
        params_out = {
            "departureAirportIataCode": origin_iata,
            "language": "pl", "market": "pl-pl",
            "outboundDepartureDateFrom": date_from,
            "outboundDepartureDateTo": date_to,
            "currency": "PLN"
        }
        
        try:
            res_out = requests.get(base_url, params=params_out, headers=headers)
            if res_out.status_code != 200: continue
                
            for fare_out in res_out.json().get("fares", []):
                out_data = fare_out.get("outbound", {})
                out_price = float(out_data.get("price", {}).get("value", 0))
                dest_iata = out_data.get("arrivalAirport", {}).get("iataCode")
                dest_name = out_data.get("arrivalAirport", {}).get("name")
                country = out_data.get("arrivalAirport", {}).get("countryName", "DEFAULT")
                out_date = out_data.get("departureDate", "").split('T')[0]
                
                if not out_date or out_price == 0: continue
                
                avg_rt_price = AVERAGE_PRICES.get(country, AVERAGE_PRICES["DEFAULT"]) * 1.85
                max_allowed_total = avg_rt_price * threshold
                
                if out_price >= max_allowed_total: continue
                
                # Szukamy powrotu (1-14 dni)
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
                
                time.sleep(1)
                res_in = requests.get(base_url, params=params_in, headers=headers)
                
                if res_in.status_code == 200:
                    for fare_in in res_in.json().get("fares", []):
                        in_data = fare_in.get("outbound", {})
                        in_price = float(in_data.get("price", {}).get("value", 0))
                        in_date = in_data.get("departureDate", "").split('T')[0]
                        
                        total_price = out_price + in_price
                        
                        if total_price <= max_allowed_total:
                            deals_counter += 1
                            discount_pct = 100 - ((total_price / avg_rt_price) * 100)
                            
                            booking_link = (
                                f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=1"
                                f"&dateOut={out_date}&dateIn={in_date}&isConnectedFlight=false&isReturn=true"
                                f"&originIata={origin_iata}&destinationIata={dest_iata}"
                            )
                            
                            # Przywrócone formatowanie: HIT! [KRAJ]
                            msg = (
                                f"🔥 <b>HIT! {country.upper()} (-{discount_pct:.0f}%)</b>\n\n"
                                f"✈️ <b>Trasa:</b> {origin_iata} ↔️ {dest_iata} ({dest_name})\n"
                                f"🛫 <b>Wylot:</b> {out_date} (<b>{out_price:.2f} PLN</b>)\n"
                                f"🛬 <b>Powrót:</b> {in_date} (<b>{in_price:.2f} PLN</b>)\n"
                                f"💰 <b>SUMA: {total_price:.2f} PLN</b>\n"
                                f"<i>Średnia dla {country}: {avg_rt_price:.2f} PLN</i>\n\n"
                                f"<a href='{booking_link}'>🔗 ZAREZERWUJ (Ryanair.com)</a>"
                            )
                            send_telegram_message(msg)
                            time.sleep(1)
                            
            time.sleep(2)
            
        except Exception as e:
            print(f"Błąd przy {origin_iata}: {e}")

    print(f"Zakończono. Znaleziono okazji: {deals_counter}")

if __name__ == "__main__":
    search_ryanair_roundtrips()
