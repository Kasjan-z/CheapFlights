import json
import os
import requests
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# BAZA ŚREDNICH CEN (W DWIE STRONY)
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

# GRUPY REGIONALNE DO PRZELICZNIKÓW
OCEANIA = {"SYD", "MEL", "BNE", "AKL", "CHC"}
AMERICAS = {"JFK", "LAX", "ORD", "MIA", "SFO", "YYZ", "YVR", "YUL", "CUN", "HAV", "PUJ", "SJO", "PTY", "GRU", "GIG", "EZE", "SCL", "LIM", "BOG", "MVD"}
SE_ASIA = {"BKK", "HAN", "PNH", "VTE", "KUL", "PEN", "SIN", "MNL", "CGK", "DPS", "SUB"}

def get_threshold(iata):
    """Zwraca mnożnik cenowy na podstawie regionu lotniska."""
    if iata in OCEANIA:
        return 0.80  # Max 80% średniej ceny (-20%)
    if iata in AMERICAS or iata in SE_ASIA:
        return 0.70  # Max 70% średniej ceny (-30%)
    return 0.65      # Reszta świata: Max 65% średniej ceny (-35%)

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        print(f"Błąd wysyłania: {e}")

def parse_duration_to_hours(duration_str):
    """Przetwarza ciąg znaków np. '32h 15m' na godziny jako float."""
    hours = 0
    if not isinstance(duration_str, str):
        return hours
    h_match = re.search(r'(\d+)h', duration_str)
    m_match = re.search(r'(\d+)m', duration_str)
    if h_match: hours += int(h_match.group(1))
    if m_match: hours += int(m_match.group(1)) / 60.0
    return hours

def process():
    if not os.path.exists("results.json"):
        print("Brak pliku results.json - skaner Google Flights nie zwrócił danych.")
        return

    with open("results.json", "r") as f:
        data = json.load(f)

    deals_found = 0

    # Zależnie od dokładnej struktury JSONa z Go, iterujemy po wynikach
    for search_batch in data:
        # Dodane bezpieczne sprawdzanie czy to na pewno lista lotów
        if not isinstance(search_batch, list):
            continue

        for flight in search_batch:
            dest_iata = flight.get("Destination")
            origin = flight.get("Origin")
            price = float(flight.get("Price", 99999))
            
            # FILTRY GODNOŚCI (Sanity Checks)
            stops = int(flight.get("Stops", 99))
            duration_str = str(flight.get("Duration", "99h"))
            duration_hours = parse_duration_to_hours(duration_str)

            if stops > 2: 
                continue # Odrzucamy: więcej niż 2 przesiadki
            if duration_hours > 35.0: 
                continue # Odrzucamy: ponad 35 godzin podróży

            if dest_iata not in GLOBAL_AVERAGES:
                continue # Ignorujemy lotniska spoza naszej ścisłej bazy

            # Wyliczamy próg dla danego lotniska
            threshold = get_threshold(dest_iata)
            avg_price = GLOBAL_AVERAGES[dest_iata]
            max_allowed_price = avg_price * threshold
            
            # Weryfikacja MEGA HITU
            if price <= max_allowed_price:
                deals_found += 1
                discount = 100 - ((price / avg_price) * 100)
                
                # Formatowanie czasu i przesiadek do wiadomości
                stop_text = "Bez przesiadek" if stops == 0 else f"{stops} przesiadka/i"
                
                msg = (
                    f"🌍 <b>MEGA HIT! KIERUNEK: {dest_iata} (-{discount:.0f}%)</b>\n\n"
                    f"✈️ <b>Trasa:</b> {origin} ↔️ {dest_iata}\n"
                    f"⏱ <b>Czas/Przesiadki:</b> ~{duration_hours:.1f}h | {stop_text}\n"
                    f"💸 <b>CENA: {price:.2f} PLN</b>\n"
                    f"<i>Średnia dla {dest_iata}: {avg_price:.2f} PLN</i>\n\n"
                    f"🔎 <i>Sprawdź ręcznie na Google Flights!</i>"
                )
                send_telegram_message(msg)

    print(f"Zakończono analizę. Znaleziono Mega Hitów: {deals_found}")

if __name__ == "__main__":
    process()
