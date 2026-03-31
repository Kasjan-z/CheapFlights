import requests
from datetime import datetime, timedelta
import os
import time

# Zostawiamy tylko klucze Telegrama
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Kody IATA polskich lotnisk, z których operuje Ryanair
PL_AIRPORTS = ["WMI", "KRK", "GDN", "KTW", "WRO", "POZ", "RZE", "BZG", "LUZ", "SZZ"]

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak kluczy Telegrama.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        print(f"Błąd wysyłania na Telegram: {e}")

def get_ryanair_flights(departure_airport, date_from, date_to):
    """Pobiera najtańsze loty z danego lotniska przez nieoficjalne API Ryanaira"""
    url = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
    params = {
        "departureAirportIataCode": departure_airport,
        "outboundDepartureDateFrom": date_from,
        "outboundDepartureDateTo": date_to,
        "currency": "PLN",
        "language": "pl",
        "market": "pl",
        "offset": 0,
        "limit": 150 # Maksymalny limit jednorazowego pobrania
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json().get("fares", [])
    except Exception as e:
        print(f"Błąd pobierania danych z {departure_airport}: {e}")
        return []

def search_cheap_flights():
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Uruchamiam skaner Ryanair...")
    
    date_from = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = datetime(now.year, 12, 31).strftime("%Y-%m-%d")

    all_flights = []

    # 1. Zbieranie danych (Z umyślnym opóźnieniem, żeby nie dostać bana)
    for airport in PL_AIRPORTS:
        print(f"Pobieranie lotów z lotniska: {airport}...")
        fares = get_ryanair_flights(airport, date_from, date_to)
        all_flights.extend(fares)
        time.sleep(2) # KRYTYCZNE: 2 sekundy przerwy między zapytaniami

    if not all_flights:
        print("Nie udało się pobrać żadnych lotów z Ryanaira. Koniec.")
        return

    # 2. Obliczanie średniej ze wszystkich pobranych lotów YTD
    valid_prices = [f["outbound"]["price"]["value"] for f in all_flights if "outbound" in f and "price" in f["outbound"]]
    
    if not valid_prices:
        print("Brak poprawnych cen w danych.")
        return

    average_price_pln = sum(valid_prices) / len(valid_prices)
    print(f"\nZebrano {len(valid_prices)} lotów Ryanair z Polski.")
    print(f"Średnia rynkowa (YTD) wyliczona na: {average_price_pln:.2f} PLN")

    # 3. Szukanie anomalii (-80% od średniej)
    max_acceptable_price = average_price_pln * 0.20
    deals_found = 0

    print(f"Szukam lotów tańszych niż {max_acceptable_price:.2f} PLN...")

    for flight in all_flights:
        try:
            outbound = flight["outbound"]
            price = outbound["price"]["value"]
            
            if price <= max_acceptable_price:
                deals_found += 1
                departure_date = outbound["departureDate"].split("T")[0]
                city_from = outbound["departureAirport"]["name"]
                city_to = outbound["arrivalAirport"]["name"]
                discount = 100 - ((price / average_price_pln) * 100)
                
                message = (
                    f"🟢 <b>RYANAIR ERROR FARE! (-{discount:.0f}%)</b>\n\n"
                    f"✈️ <b>Trasa:</b> {city_from} ➡️ {city_to}\n"
                    f"📅 <b>Data:</b> {departure_date}\n"
                    f"💰 <b>Cena:</b> {price} PLN\n"
                    f"📊 <b>Średnia Ryanair:</b> {average_price_pln:.0f} PLN\n\n"
                    f"<a href='https://www.ryanair.com/pl/pl'>🔗 Zarezerwuj na Ryanair.com</a>"
                )
                
                send_telegram_message(message)
                time.sleep(1) # Zabezpieczenie przed limitem Telegrama
        except KeyError:
            continue

    if deals_found == 0:
        print("\nW tej sesji nie znaleziono lotów tańszych o 80%.")
    else:
        print(f"\nSukces! Wysłano {deals_found} ofert na Telegram.")

if __name__ == "__main__":
    search_cheap_flights()
