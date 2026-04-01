import os
import requests
import re
import time
from datetime import datetime, timedelta

try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
    API_V2 = True
except ImportError:
    from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter
    API_V2 = False

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HISTORY_FILE = "sent_deals.txt"

# WYSELEKCJONOWANA BAZA ŚREDNICH CEN (PLN)
GLOBAL_AVERAGES = {
    "AGA": 1000, "TNG": 1200, "RAK": 800, "RBA": 1000, "CMN": 1200, 
    "DEL": 2800, "BOM": 2800, "GOI": 3200, "COK": 2600, "TRV": 3500, "CMB": 3000, 
    "BKK": 3100, "HKT": 3100, "KBV": 3200, "USM": 4300, 
    "HAN": 3400, "SGN": 3600, "DAD": 3100, "CXR": 5000, "SAI": 4000,
    "KUL": 2900, "PEN": 3600, "LGK": 3600, "SIN": 3000, 
    "CGK": 3300, "DPS": 3500, "MNL": 4300, "CEB": 4000, "PPS": 5300, "MPH": 6000,
    "NRT": 4200, "HND": 4200, "KIX": 3600, "CTS": 5300, "OKA": 3300, "NGO": 3600, "FUK": 4000, 
    "ICN": 3200, "PEK": 2600, "PVG": 2700, 
    "SYD": 4900, "MEL": 5500, "BNE": 5000, "ADL": 6700, "PER": 5400, 
    "JNB": 3000, "CPT": 3300, "DUR": 3600, "NBO": 2800, "MBA": 3000, 
    "DAR": 3500, "ZNZ": 2900, "JRO": 3900, 
    "YYZ": 2800, "YVR": 3100, "YYC": 3400, 
    "MEX": 3600, "CUN": 3700, "TUQ": 4100, "PVR": 4400, "SJD": 4500, 
    "SJO": 3000, "LIR": 3900, "PTY": 3300, "HAV": 3600, "PUJ": 3500, 
    "GRU": 3800, "GIG": 4000, "SSA": 4300, "FOR": 4000, 
    "EZE": 4400, "SCL": 5000, "LIM": 4500, "CUZ": 6000, 
    "BOG": 3300, "MDE": 4100, "CTG": 4000, "CLO": 4300, "UIO": 4400, "GYE": 5000, 
    "MVD": 5400, "LPB": 7000, "FNC": 1200, "TFS": 1000,
    "AMM": 600, "AQJ": 600, "TLV": 800, "TBS": 900, "IST": 1100, "AYT": 1100, 
    "DXB": 1600, "DOH": 2600, "JED": 2200
}

OCEANIA_SOUTH_AM = {"SYD", "MEL", "BNE", "ADL", "PER", "SCL", "EZE", "MVD", "LPB"}
LCC_ZONE = {"AMM", "AQJ", "TLV", "TBS", "IST", "AYT", "DXB", "DOH", "JED", "TFS", "FNC", "AGA", "TNG", "RAK", "RBA", "CMN"}

def get_threshold(iata):
    if iata in OCEANIA_SOUTH_AM: return 0.65  # -35% 
    if iata in LCC_ZONE: return 0.40          # -60% 
    return 0.55                               # -45% 

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f: return set(f.read().splitlines())
    return set()

def save_to_history(deal_id):
    with open(HISTORY_FILE, "a") as f: f.write(f"{deal_id}\n")

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload)
    except Exception: pass

def parse_duration(duration_str):
    hours = 0
    if not isinstance(duration_str, str): return hours
    h_match = re.search(r'(\d+)\s*hr', duration_str)
    m_match = re.search(r'(\d+)\s*min', duration_str)
    if h_match: hours += int(h_match.group(1))
    if m_match: hours += int(m_match.group(1)) / 60.0
    return hours

def parse_price_to_pln(price_str):
    if not price_str or "unavailable" in str(price_str).lower() or price_str == "": return None
    clean_val = float(re.sub(r'[^\d.]', '', str(price_str)))
    if '$' in price_str: return clean_val * 4.03   
    if '€' in price_str: return clean_val * 4.30   
    if '£' in price_str: return clean_val * 5.05   
    return clean_val 

def scan_google_flights():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Odpalam Kolosa! (Z anty-spamem)")
    date_out = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    date_in = (datetime.now() + timedelta(days=104)).strftime("%Y-%m-%d")
    
    origins = ["WAW", "KRK"] 
    deals_found = 0

    for origin in origins:
        for dest, avg_price_pln in GLOBAL_AVERAGES.items():
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

                if not results or not hasattr(results, 'flights'): continue

                for flight in results.flights:
                    price_pln = parse_price_to_pln(flight.price)
                    if not price_pln: continue
                    
                    stops = int(getattr(flight, 'stops', 99))
                    duration_hours = parse_duration(getattr(flight, 'duration', "99 hr"))
                    airlines = getattr(flight, 'name', "Nieznane")
                    
                    if stops > 2 or duration_hours > 35.0: continue
                    
                    threshold = get_threshold(dest)
                    max_accepted_price = avg_price_pln * threshold
                    
                    if price_pln <= max_accepted_price:
                        deal_id = f"GF-{origin}-{dest}-{date_out}-{price_pln}"
                        history = load_history()
                        
                        if deal_id in history:
                            print(f"Pominięto {dest} - już to dzisiaj wysyłałem!")
                            continue
                            
                        deals_found += 1
                        discount = 100 - ((price_pln / avg_price_pln) * 100)
                        stop_text = "Bez przesiadek" if stops == 0 else f"{stops} przesiadka/i"
                        
                        msg = (
                            f"🌍 <b>LEGENDARNY HIT! {dest} (-{discount:.0f}%)</b>\n\n"
                            f"✈️ <b>Trasa:</b> {origin} ↔️ {dest}\n"
                            f"🏢 <b>Linie:</b> {airlines}\n"
                            f"⏱ <b>Czas/Przesiadki:</b> ~{duration_hours:.1f}h | {stop_text}\n"
                            f"💸 <b>CENA: ~{price_pln:.0f} PLN</b>\n"
                            f"<i>(Normalnie: {avg_price_pln} PLN | Termin za 3 m-ce)</i>\n\n"
                            f"🔎 <i>Szukaj ręcznie na Google Flights!</i>"
                        )
                        send_telegram_message(msg)
                        save_to_history(deal_id)
                        time.sleep(1)
                        break 
            except Exception: pass
            time.sleep(1.5) 

    if deals_found == 0:
        send_telegram_message("📡 <i>Aktualnie brak legendarnych okazji długodystansowych. Szukam dalej...</i>")

if __name__ == "__main__":
    scan_google_flights()
