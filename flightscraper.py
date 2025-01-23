import asyncio
import os
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.async_api import async_playwright
import re

@dataclass
class FlightData:
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: str
    price: str
    co2_emissions: Optional[str]
    emissions_variation: Optional[str]

class FlightScraper:
    SELECTORS = {
        "airline": "div.sSHqwe.tPgKwe.ogfYpf",
        "departure_time": 'span[aria-label^="Departure time"]',
        "arrival_time": 'span[aria-label^="Arrival time"]',
        "duration": 'div[aria-label^="Total duration"]',
        "stops": "div.hF6lYb span.rGRiKd",
        "price": "div.FpEdX span",
        "co2_emissions": "div.O7CXue",
        "emissions_variation": "div.N6PNV",
    }


    def __init__(self, departure_airport, arrival_airport, date, protected_baseline):
        self.results_dir = "./results"
        os.makedirs(self.results_dir, exist_ok=True)
        self.departure_airport = departure_airport
        self.arrival_airport = arrival_airport
        self.date = date
        self.protected_baseline = protected_baseline
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    async def search_flights(self) -> List[FlightData]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            )
            page = await context.new_page()
            print("Navigating to Google Flights...")
            await page.goto("https://www.google.com/flights")

            if(self.arrival_airport != "major_airports"):
                await self._fill_search_form(page, self.departure_airport, self.arrival_airport, True)
                flights = await self._extract_flight_data(page)
                await context.close()
                await browser.close()
                return flights
            else:
                major_airports = ["ATL", "LAX", "DFW", "DEN", "ORD", "JFK", "MCO", "LAS", "CLT", "MIA", "SEA", "EWR", "SFO", "PHX", "IAH", "BOS", "FLL", "MSP", "LGA", "DTW", "PHL", "SLC", "BWI", "DCA", "SAN", "IAD", "TPA", "BNA", "AUS", "MDW", "HNL", "DAL", "PDX", "STL", "RDU", "HOU", "OGG", "PIT", "MCI", "MSY", "PHL"]
                for airport in major_airports:
                    min_first_leg = min_first_leg = float("inf")
                    min_second_leg = float("inf")
                    if(airport != self.departure_airport):
                        await self._fill_search_form(page, self.departure_airport, airport, False)
                        first_leg_flights = await self._extract_flight_data(page)
                        for i in range(min(10,len(first_leg_flights))):
                            min_first_leg = min(min_first_leg, int(first_leg_flights[i].price.replace("$", "")))
                        
                        if(min_first_leg < self.protected_baseline and airport != self.arrival_airport):
                            await self._fill_search_form(page, airport, self.arrival_airport, False)
                            second_leg_flights = await self._extract_flight_data(page)

                            for i in range(min(10,len(second_leg_flights))):
                                min_second_leg = min(min_second_leg, int(second_leg_flights[i].price.replace("$", "")))
                    
                    if(self.protected_baseline + 150 < min_first_leg + min_second_leg):
                        print(min_first_leg + min_second_leg)
                            
                            





    async def _fill_search_form(self, page, departure_airport, arrival_airport, protected) -> None:
        """
        Fill out the flight search form on Google Flights. 
        Takes screenshots before typing/selecting anything.
        """
        try:
            try:
                print("Checking for cookie consent popup...")
                consent_button = page.locator("button:has-text('Accept all')")
                if await consent_button.is_visible():
                    await consent_button.click()
                    print("Closed cookie consent popup.")
                else:
                    print("No cookie popup detected.")
            except Exception as e:
                print(f"Error while handling cookie consent popup: {e}")

            print("Changing Travel Type to One Way")
            round_trip_button = page.locator("div.VfPpkd-aPP78e").nth(0)
            await round_trip_button.wait_for(state="visible", timeout=30000)
            await round_trip_button.click()
            await asyncio.sleep(1)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")


            print("Filling departure location...")
            from_input = page.locator("input[aria-label='Where from?']").nth(0)
            await from_input.wait_for(state="visible", timeout=30000)


            await from_input.click(click_count=3)
            print("Clicked on the departure input field.")
            await asyncio.sleep(1)

            await page.keyboard.press("Backspace")
            print("Cleared the departure input field.")
            await asyncio.sleep(1)


            await page.keyboard.type(departure_airport)
            print(f"Typed departure airport: {departure_airport}")
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            print("Confirmed departure input.")

            print("Filling destination location...")

            await page.keyboard.press("Tab")
            print("Clicked on the destination input field.")
            await asyncio.sleep(1)


            await page.keyboard.press("Backspace")
            print("Cleared the destination input field.")
            await asyncio.sleep(1)


            await page.keyboard.type(arrival_airport)
            print(f"Typed destination airport: {arrival_airport}")
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            print("Confirmed destination input.")


            print("Opening calendar for departure date...")
            departure_input = page.get_by_placeholder("Departure").nth(0)
            await departure_input.wait_for(state="visible", timeout=30000)
            await departure_input.click()
            await asyncio.sleep(1)


            print("Selecting departure date...")
            await page.get_by_role("button", name=self.date).click()
            await asyncio.sleep(1)
            print("Selected departure date: Thursday, January 23,")


            await page.keyboard.press("Escape")
            print("Escaped Calendar")

            print("Searching...")
            await asyncio.sleep(1)
            await page.keyboard.press("Tab")
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            if(self.arrival_airport != "major_airports"):
                print("Loading flight results...")
                top_flights_text = page.get_by_role("heading", name = "Top flights")
                await top_flights_text.wait_for(state="visible", timeout=30000)
                close_button = page.get_by_role("button", name = "Close")
                if await close_button.is_visible():
                    await close_button.click()
                stops_button = page.locator('[aria-label="Stops, Not selected"]')
                await stops_button.wait_for(state="visible", timeout=30000)
                await stops_button.click()
                one_stop_button = page.get_by_role("radio", name = "1 stop or fewer")
                await one_stop_button.wait_for(state="visible", timeout=30000)
                await one_stop_button.click()
                await page.keyboard.press("Escape")
                cheapest_button = page.get_by_role("tab", name=re.compile(r"^Cheapest"))
                await cheapest_button.wait_for(state="visible", timeout=30000)
                await cheapest_button.click()
                await asyncio.sleep(1)
                print("Flight results loaded successfully.")
            else:
                print("Loading first leg possibilities...")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Enter")
                await page.keyboard.press("Enter")
                nonstop_button = page.get_by_role("radio", name = "Nonstop only")
                await nonstop_button.wait_for(state="visible", timeout=30000)
                await nonstop_button.click()
                await page.keyboard.press("Escape")
                print("hello")



        except Exception as e:
            print(f"Error in _fill_search_form: {e}")
            raise

    async def _load_all_flights(self, page) -> None:
        while True:
            try:
                more_button = await page.wait_for_selector(
                    'button[aria-label*="more flights"]', timeout=5000
                )
                if more_button:
                    await more_button.click()
                    print("Loaded more flights...")
                    await asyncio.sleep(2)
                else:
                    break
            except Exception as e:
                print("Error while loading more flights:", str(e))
                break

    async def _extract_flight_data(self, page) -> List[FlightData]:
        await page.wait_for_selector("li.pIav2d", timeout=30000)
        await self._load_all_flights(page)

        flights = await page.query_selector_all("li.pIav2d")
        flights_data = []

        for flight in flights:
            flight_info = {}
            for key, selector in self.SELECTORS.items():
                element = await flight.query_selector(selector)
                flight_info[key] = await self._extract_text(element) if element else None
            flights_data.append(FlightData(**flight_info))
        print(f"Extracted {len(flights_data)} flights.")
        return flights_data

    async def _extract_text(self, element) -> str:
        if element:
            return await element.inner_text()
        return ""

    def save_results(self, flights: List[FlightData]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"flight_results_{self.departure_airport}_{self.arrival_airport}_{timestamp}.json"
        )

        output_data = {
            "search_parameters": {
                "departure": self.departure_airport,
                "destination": self.arrival_airport,
                "departure_date": self.date,
                "search_timestamp": timestamp,
            },
            "flights": [vars(flight) for flight in flights],
        }

        filepath = os.path.join(self.results_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        return filepath