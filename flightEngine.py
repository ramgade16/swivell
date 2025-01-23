import flightScraper
import asyncio

class FlightEngine:

    def __init__(self):
        print("Hello! I hope you're ready to book some flights!")

    def askUserForFlightDetails(self):
        self.ticket_type = input("Will you be flying One-Way or Round-Trip? (Answer with an \"O\" or \"R\") --> ")
        self.departure_airport = input("Which airport will you be flying from today? Please enter the airport's 3-letter code (e.g. \"LAX\") --> ")
        self.arrival_airport = input("Which airport will you be flying to today?  Please enter the airport's 3-letter code (e.g. \"ORD\") -->  ")
        self.departure_date = input("What is your departure date? Please enter in this format: \"Thursday, January 23,\" --> ")
        if(self.ticket_type == "R"):
            self.arrival_date = input("What is your arrival date? Please enter in this format: \"Sunday, January 26,\" --> ")
        self.checked_bag = input("Will you be flying with a checked bag today? (Answer with an \"Y\" or \"N\") --> ")




async def main():
    engine = FlightEngine()
    engine.askUserForFlightDetails()
    direct_scraper = flightScraper.FlightScraper(engine.departure_airport, engine.arrival_airport, engine.departure_date)
    protected_baseline = 0
    try:
        flights = await direct_scraper.search_flights()
        for i in range(min(10,len(flights))):
            protected_baseline = max(protected_baseline, int(flights[i].price.replace("$", "")))
        print(protected_baseline)
        if flights:
            print(f"Successfully found {len(flights)} flights")
            direct_scraper.save_results(flights)
        else:
            print("No flights found.")
    except Exception as e:
        print(f"Error during flight search: {str(e)}")
    
    # connecting_scraper = flightScraper.FlightScraper(engine.departure_airport, "major_airports", engine.departure_date)
    # try:
    #     flights = await connecting_scraper.search_flights()
    #     if flights:
    #         print(f"Successfully found {len(flights)} flights")
    #         direct_scraper.save_results(flights)
    #     else:
    #         print("No flights found.")
    # except Exception as e:
    #     print(f"Error during flight search: {str(e)}")
    
    # connecting_scraper = flightScraper.FlightScraper(engine.departure_airport, "Anywhere", engine.departure_date, True)

if __name__ == "__main__":
    asyncio.run(main())


# Goal: 
# Display top 5 best options(protected by interline agreements) --> remember to check if checked bags/carry-on are allowed. If not, they must be booked.
# and
# Display top 5 best connecting options(not protected by interline agreements) --> min 1.5-2 hours connecting and no checked bags. If checked bags, leave 2-3 hours time. Remember to check if checked bags/carry-on are allowed. If not, they must be booked.
# and 
# Display "SWIVELL's" choice