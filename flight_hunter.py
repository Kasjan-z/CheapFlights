import requests
import os
from datetime import datetime, timedelta
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") # Teraz to jest ID Twojego kanału (-100...)

POLISH_AIRPORTS = ["WMI", "KRK", "WRO", "GDN", "POZ", "KTW", "LUZ", "RZE", "LCJ"]

AVERAGE_PRICES = {
    "Sweden": 120, "Norway": 120, "Denmark": 120, "United Kingdom": 200,
    "Ireland": 250, "Italy": 300, "Spain": 400, "Greece": 400,
    "Croatia": 300, "Jordan": 400, "Cyprus": 350, "Malta": 350,
    "France": 250, "Portugal": 450, "Morocco": 450, "Albania": 300,
    "Bulgaria": 300, "Montenegro": 300, "DEFAULT": 250
}

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak kluczy Telegrama.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
        print("-> Alert wysłany na kanał!")
    except Exception as e:
        print(f"Błąd wysyłania na kanał: {e}")

def search_ryanair_roundtrips():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uruchamiam skaner lotów w dwie strony dla kanału...")
    date_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    deals_found = 0

    for origin_iata in POLISH_AIRPORTS:
        print(f"Skanuję wyloty z: {origin_iata}...")
        url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
        
        params_out = {
            "departureAirportIataCode": origin_iata,
            "language": "pl", "market": "pl-pl",
            "outboundDepartureDateFrom": date_from,
            "outboundDepartureDateTo": date_to,
            "currency": "PLN"
        }
        
        try:
            res_out = requests.get(url, params_out, headers=headers)
            if res_out.status_code != 200:
                time.sleep(2)
                continue
                
            for fare_out in res_out.json().get("fares", []):
                outbound = fare_out.get("outbound", {})
                out_price = outbound.get("price", {}).get("value")
                dest_iata = outbound.get("arrivalAirport", {}).get("iataCode")
                dest_name = outbound.get("arrivalAirport", {}).get("name")
                country = outbound.get("arrivalAirport", {}).get("countryName", "DEFAULT")
                out_date_full = outbound.get("departureDate")
                
                if not out_date_full or not out_price or not dest_iata:
                    continue
                    
                out_date = out_date_full.split('T')[0]
                
                avg_price_roundtrip = AVERAGE_PRICES.get(country, AVERAGE_PRICES["DEFAULT"]) * 2
                max_accepted_roundtrip = avg_price_roundtrip * 0.40
                
                if out_price >= max_accepted_roundtrip:
                    continue
                    
                in_date_from = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                in_date_to = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")
                
                params_in = {
                    "departureAirportIataCode": dest_iata,
                    "arrivalAirportIataCode": origin_iata, 
                    "language": "pl", "market": "pl-pl",
                    "outboundDepartureDateFrom": in_date_from,
                    "outboundDepartureDateTo": in_date_to,
                    "currency": "PLN"
                }
                
                time.sleep(1)
                res_in = requests.get(url, params_in, headers=headers)
                
                if res_in.status_code == 200:
                    for fare_in in res_in.json().get("fares", []):
                        inbound = fare_in.get("outbound", {})
                        in_price = inbound.get("price", {}).get("value")
                        in_date = inbound.get("departureDate", "").split('T')[0]
                        
                        if not in_price or not in_date:
                            continue
                            
                        total_price = out_price + in_price
                        
                        if total_price <= max_accepted_roundtrip:
                            deals_found += 1
                            discount = 100 - ((total_price / avg_price_roundtrip) * 100)
                            
                            deep_link = (
                                f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=1&teens=0&children=0&infants=0"
                                f"&dateOut={out_date}&dateIn={in_date}&isConnectedFlight=false&isReturn=true&discount=0"
                                f"&promoCode=&originIata={origin_iata}&destinationIata={dest_iata}"
                            )
                            
                            msg = (
                                f"🔥 <b>HIT! {country.upper()} (w dwie strony -{discount:.0f}%)</b>\n\n"
                                f"✈️ <b>Trasa:</b> {origin_iata} ↔️ {dest_iata} ({dest_name})\n"
                                f"🛫 <b>Wylot:</b> {out_date} ({out_price} PLN)\n"
                                f"🛬 <b>Powrót:</b> {in_date} ({in_price} PLN)\n"
                                f"💰 <b>Suma: {total_price} PLN</b> <i>(Średnia: {avg_price_roundtrip} PLN)</i>\n\n"
                                f"<a href='{deep_link}'>🔗 Zarezerwuj ten lot</a>"
                            )
                            send_telegram_message(msg)
                            time.sleep(1) # Przerwa między wiadomościami
                            
            time.sleep(2) 
            
        except Exception as e:
            print(f"Błąd sieci dla {origin_iata}: {e}")

    if deals_found == 0:
        print("Nie znaleziono lotów. Kanał milczy.")

if __name__ == "__main__":
    search_ryanair_roundtrips()
