import requests
import os
from datetime import datetime, timedelta
import time

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HISTORY_FILE = "sent_deals.txt"

WAW_AIRPORT = ["WAW"]
WMI_AIRPORT = ["WMI"]
REGIONAL_AIRPORTS = ["KRK", "WRO", "GDN", "POZ", "KTW", "LUZ", "RZE", "LCJ"]
ALL_AIRPORTS = WAW_AIRPORT + WMI_AIRPORT + REGIONAL_AIRPORTS

DEST_AVERAGES = {
    "ARN": 85, "NYO": 85, "GOT": 85, "OSL": 90, "TRF": 90, "CPH": 110, "BLL": 100, "AAR": 100,
    "BGY": 150, "TSF": 150, "VCE": 170, "CIA": 170, "FCO": 180, "NAP": 200, "PSA": 160, 
    "BLQ": 160, "BRI": 180, "PMO": 230, "CTA": 230, "TRN": 160, "SUF": 200, "CAG": 220,
    "STN": 130, "LTN": 130, "MAN": 150, "LPL": 140, "BHX": 150, "EDI": 170, "GLA": 170, 
    "DUB": 190, "SNN": 190, "ORK": 190, "BFS": 150,
    "BCN": 280, "GRO": 250, "MAD": 300, "ALC": 320, "VLC": 300, "AGP": 320, "SVQ": 320,
    "PMI": 280, "TFS": 450, "ACE": 450, "LPA": 450, "LIS": 380, "OPO": 380, "FAO": 350,
    "ATH": 300, "CHQ": 320, "CFU": 280, "RHO": 300, "PFO": 300, "LCA": 300, "MLA": 250,
    "BVA": 160, "MRS": 180, "NCE": 220, "CRL": 120, "EIN": 130, "BER": 140, "DTM": 110, "NRN": 110, "HHN": 110,
    "BUD": 130, "PRG": 140, "VIE": 130, "BTS": 110, "TIA": 220, "SKP": 180, "SOF": 160, 
    "AMM": 350, "RAK": 380, "AGA": 380, "TLV": 350, "KUT": 250,
    "DEFAULT": 250 
}

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

def search_ryanair_roundtrips():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Odpalam Snajpera Ryanair! (Pobyt min. 3 dni)")
    date_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    deals_found = 0

    for origin_iata in ALL_AIRPORTS:
        if origin_iata == "WAW": threshold = 0.40
        elif origin_iata == "WMI": threshold = 0.30
        else: threshold = 0.20
        
        base_url = "https://www.ryanair.com/api/farfnd/3/oneWayFares"
        params_out = {
            "departureAirportIataCode": origin_iata, "language": "pl", "market": "pl-pl",
            "outboundDepartureDateFrom": date_from, "outboundDepartureDateTo": date_to, "currency": "PLN"
        }
        
        try:
            res_out = requests.get(base_url, params=params_out, headers=headers)
            if res_out.status_code != 200: continue
                
            for fare_out in res_out.json().get("fares", []):
                out_data = fare_out.get("outbound", {})
                out_price = float(out_data.get("price", {}).get("value", 0))
                dest_iata = out_data.get("arrivalAirport", {}).get("iataCode")
                dest_name = out_data.get("arrivalAirport", {}).get("name", dest_iata)
                country_name = out_data.get("arrivalAirport", {}).get("countryName", "")
                out_date = out_data.get("departureDate", "").split('T')[0]
                
                if not out_date or out_price == 0: continue
                
                avg_rt_price = DEST_AVERAGES.get(dest_iata, DEST_AVERAGES["DEFAULT"]) * 2
                max_allowed_total = avg_rt_price * threshold
                
                if out_price >= max_allowed_total: continue
                
                # ZMIANA: Powrót najwcześniej po 2 dniach (np. wylot 15, powrót 17)
                ret_from = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
                ret_to = (datetime.strptime(out_date, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")
                
                params_in = {
                    "departureAirportIataCode": dest_iata, "arrivalAirportIataCode": origin_iata,
                    "language": "pl", "market": "pl-pl",
                    "outboundDepartureDateFrom": ret_from, "outboundDepartureDateTo": ret_to, "currency": "PLN"
                }
                
                time.sleep(0.8)
                res_in = requests.get(base_url, params=params_in, headers=headers)
                
                if res_in.status_code == 200:
                    for fare_in in res_in.json().get("fares", []):
                        in_data = fare_in.get("outbound", {})
                        in_price = float(in_data.get("price", {}).get("value", 0))
                        in_date = in_data.get("departureDate", "").split('T')[0]
                        total_price = out_price + in_price
                        
                        if total_price <= max_allowed_total:
                            deal_id = f"FR-{origin_iata}-{dest_iata}-{out_date}-{total_price}"
                            history = load_history()
                            if deal_id in history: continue
                            
                            deals_found += 1
                            discount_pct = 100 - ((total_price / avg_rt_price) * 100)
                            booking_link = f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=1&dateOut={out_date}&dateIn={in_date}&isConnectedFlight=false&isReturn=true&originIata={origin_iata}&destinationIata={dest_iata}"
                            
                            header = country_name if country_name else dest_name
                            msg = (
                                f"🔥 <b>HIT! {header.upper()} (-{discount_pct:.0f}%)</b>\n\n"
                                f"✈️ <b>Trasa:</b> {origin_iata} ↔️ {dest_iata} ({dest_name})\n"
                                f"🛫 <b>Wylot:</b> {out_date} | 🛬 <b>Powrót:</b> {in_date}\n"
                                f"💰 <b>SUMA: {total_price:.2f} PLN</b> (Średnia: {avg_rt_price:.0f} PLN)\n\n"
                                f"<a href='{booking_link}'>🔗 ZAREZERWUJ (Ryanair)</a>"
                            )
                            send_telegram_message(msg)
                            save_to_history(deal_id)
                            time.sleep(1)
            time.sleep(1.5)
        except Exception: pass

    if deals_found == 0:
        send_telegram_message("📡 <i>Snajper Ryanair: Brak nowych hitów (min. 3 dni pobytu). Szukam dalej...</i>")

if __name__ == "__main__":
    search_ryanair_roundtrips()
