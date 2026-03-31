import sys

# Próbujemy zaimportować bibliotekę w zależności od jej wersji
try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
    API_V2 = True
except ImportError:
    from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter
    API_V2 = False

def run_probe():
    print(f"Startuję sondę Google Flights! Wykryto nowe API: {API_V2}")
    
    if API_V2:
        # Nowsza wersja biblioteki
        query = create_query(
            flights=[FlightQuery(date="2026-06-15", from_airport="WAW", to_airport="JFK")],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0)
        )
        try:
            result = get_flights(query)
            print("🚀 SUKCES! Oto dane z Google Flights:")
            print(result)
        except Exception as e:
            print(f"❌ Błąd przy pobieraniu: {e}")
            
    else:
        # Starsza wersja biblioteki
        filter = create_filter(
            flight_data=[FlightData(date="2026-06-15", from_airport="WAW", to_airport="JFK")],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
            max_stops=2
        )
        try:
            result = get_flights_from_filter(filter, mode="common")
            print("🚀 SUKCES! Oto dane z Google Flights:")
            print(result)
        except Exception as e:
            print(f"❌ Błąd przy pobieraniu: {e}")

if __name__ == "__main__":
    run_probe()
