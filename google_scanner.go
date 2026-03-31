package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"
	"github.com/AWeirdDev/flights"
)

func main() {
	session, _ := flights.New()
	// Lotniska wylotowe
	origins := []string{"WAW", "WMI", "KRK", "WRO", "GDN", "POZ", "KTW"}
	
	var allFlights []interface{}

	for _, origin := range origins {
		fmt.Printf("Skanuję Google Flights dla: %s\n", origin)
		// Szukamy lotów "Anywhere" (wszędzie) wylatujących w ciągu najbliższych 30 dni
		args := flights.Args{
			Origin:     origin,
			Date:       time.Now().AddDate(0, 0, 7), // Za tydzień
			ReturnDate: time.Now().AddDate(0, 0, 14), // Powrót po tygodniu
			Currency:   "PLN",
		}

		res, err := session.Search(context.Background(), args)
		if err == nil {
			allFlights = append(allFlights, res)
		}
		time.Sleep(2 * time.Second)
	}

	file, _ := json.MarshalIndent(allFlights, "", "  ")
	_ = os.WriteFile("results.json", file, 0644)
	fmt.Println("Dane z Google Flights zapisane do results.json")
}
