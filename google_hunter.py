import os
import requests
import re
import time
from datetime import datetime, timedelta

# Importy z naszej nowej biblioteki
try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
    API_V2 = True
except ImportError:
    from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter
    API_V2 = False

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# BAZA ŚREDNICH CEN (W DWIE STRONY) - PLN
GLOBAL_AVERAGES = {
    # Bliski Wschód i Europa LCC
    "AMM": 600, "AQJ": 600, "TLV": 800, "TBS": 900, "IST": 1100, "AYT": 1100, 
    "DXB": 1600, "DOH": 2600, "JED": 2200, "TFS": 1000, "FNC": 1000,
    # Azja Środkowa, Południowa i Wschodnia
    "ALA": 2200, "FRU": 2500, "ISB": 2800, "KTM": 3800, "DEL": 2600, "BOM": 2600, 
    "BLR": 2800, "NRT": 3600, "KIX": 3600, "ICN": 3300, "PEK": 2800, "PVG": 2800, 
    "CAN": 3000, "UBN": 3800,
    # Azja Południowo-Wschodnia
    "BKK": 3200, "HAN": 3600, "PNH": 4000, "VTE": 4200, "KUL": 3300, "PEN": 3500, 
    "SIN": 3500, "MNL": 3600, "CGK": 3600, "DPS": 4000, "SUB": 3800,
    # Oceania
    "SYD": 6000, "MEL": 6000, "BNE": 6200, "AKL": 6500, "CHC": 6500,
    # Afryka
    "CAI": 1400, "RAK": 800, "NBO": 2800, "ZNZ": 3200, "WDH": 3800, "JNB": 3200, 
    "CPT": 3400, "TNR": 4500, "DSS": 2600, "SEZ": 3600, "MRU": 3800,
    # Ameryki
    "JFK": 2400, "LAX": 3200, "ORD": 2600, "MIA": 2800, "SFO": 3300, "YYZ": 2600, 
    "YVR": 3400, "YUL": 2600, "CUN": 3400, "HAV": 3600, "PUJ": 3500, "SJO": 3800, 
    "PTY": 3800, "GRU": 3800, "GIG": 3800, "EZE": 4600, "SCL": 4800, "LIM": 4500, 
    "BOG": 3800, "MVD": 4600,
}

OCEANIA = {"SYD", "MEL", "BNE", "AKL", "CHC"}
AMERICAS = {"JFK", "LAX", "ORD", "MIA", "SFO", "YYZ", "YVR", "YUL", "CUN", "HAV", "PUJ", "SJO", "PTY", "GRU", "GIG", "EZE", "SCL", "LIM", "BOG", "MVD"}
SE_ASIA = {"BKK", "HAN", "PNH", "VTE", "KUL", "PEN", "SIN", "MNL", "CGK", "DPS", "SUB"}

def get_threshold(iata):
    if iata in OCEANIA: return 0.80
    if iata in AMERICAS or iata in SE_ASIA: return 0.70
    return 0.65

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload).raise_for_status()
    except Exception as e: print(f"Błąd wysyłania: {e}")

def parse_duration(duration_str):
    hours = 0
    if not isinstance(duration_str, str): return hours
    h_match = re.search(r'(\d+)\s*hr', duration_str)
    m_match = re.search(r'(\d+)\s*min', duration_str)
    if h_match: hours += int(h_match.group(1))
    if m_match: hours += int(m_match.group(1)) / 60.0
    return hours

def parse_price_to_pln(price_str):
    if not price_str or "unavailable" in str(price_str).lower() or price_str == "":
        return None
    
    clean_val = float(re.sub(r'[^\d.]', '', str(price_str)))
    
    if '$' in price_str: return clean_val * 4.03   
    if '€' in price_str: return clean_val * 4.30   
    if '£' in price_str: return clean_val * 5.05   
    return clean_val 

def scan_google_flights():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Odpalam Kolosa! (API_v2: {API_V2})")
    
    date_out = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    date_in = (datetime.now() + timedelta(days=104)).strftime("%Y-%m-%d")
    
    origins = ["WAW", "KRK"] 
    deals_found = 0

    for origin in origins:
        for dest, avg_price_pln in GLOBAL_AVERAGES.items():
            print(f"🔍 Skanuję {origin} -> {dest}...")
            
            try:
                if API_V2:
                    query = create_query(
                        flights=[FlightQuery(date=date_out, return_date=date_in, from_airport=origin, to_airport=dest)],
                        trip="round-trip", seat="economy",
                        passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0)
                    )
                    results = get_flights(query)
                else:
                    filter = create_filter(
                        flight_data=[FlightData(date=date_out, return_date=date_in, from_airport=origin, to_airport=dest)],
                        trip="round-trip", seat="economy",
                        passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
                        max_stops=2 
                    )
                    results = get_flights_from_filter(filter, mode="common")

                if not results or not hasattr(results, 'flights'):
                    continue

                for flight in results.flights:
                    price_pln = parse_price_to_pln(flight.price)
                    if not price_pln: continue
                    
                    stops = int(getattr(flight, 'stops', 99))
                    duration_hours = parse_duration(getattr(flight, 'duration', "99 hr"))
                    airlines = getattr(flight, 'name', "Nieznane")
                    
                    if stops > 2: continue
                    if duration_hours > 35.0: continue
                    
                    threshold = get_threshold(dest)
                    max_accepted_price = avg_price_pln * threshold
                    
                    if price_pln <= max_accepted_price:
                        deals_found += 1
                        discount = 100 - ((price_pln / avg_price_pln) * 100)
                        
                        stop_text = "Bez przesiadek" if stops == 0 else f"{stops} przesiadka/i"
                        
                        msg = (
                            f"🌍 <b>MEGA HIT! KIERUNEK: {dest} (-{discount:.0f}%)</b>\n\n"
                            f"✈️ <b>Trasa:</b> {origin} ↔️ {dest}\n"
                            f"🏢 <b>Lin
