import asyncio
import os
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.async_api import async_playwright

@dataclass
class SearchParameters:
    departure: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    ticket_type: str = "One way"

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

    def __init__(self):
        self.results_dir = "./results"
        os.makedirs(self.results_dir, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    async def search_flights(self, params: SearchParameters) -> List[FlightData]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()
            print("Navigating to Google Flights...")
            await page.goto("https://www.google.com/flights")

            await self._fill_search_form(page, params)

            flights = await self._extract_flight_data(page)

            await browser.close()
            return flights

    async def _fill_search_form(self, page, params: SearchParameters) -> None:
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

            print("Filling departure location...")
            from_input = page.locator("input[aria-label='Where from?']").nth(0)
            await from_input.wait_for(state="visible", timeout=30000)
            await from_input.click()
            print("Clicked on the departure input field.")
            await asyncio.sleep(5)

            await from_input.fill("")
            print("Cleared the departure input field.")
            await asyncio.sleep(5)
            await page.keyboard.type(params.departure)
            print(f"Typed departure airport: {params.departure}")
            await asyncio.sleep(5)
            await page.keyboard.press("Enter")
            print("Confirmed departure input.")

            print("Filling destination location...")
            to_input = page.locator("input[aria-label='Where to?']")
            print("Checking visibility of 'Where to?' input field...")
            if not await to_input.nth(1).is_visible():
                print("'Where to?' input field (nth(1)) is not visible. Falling back to nth(0).")
                to_input = to_input.nth(0)

            await to_input.wait_for(state="visible", timeout=30000)
            await to_input.click()
            print("Clicked on the destination input field.")
            await asyncio.sleep(5)

            await to_input.fill("")
            print("Cleared the destination input field.")
            await asyncio.sleep(5)
            await page.keyboard.type(params.destination)
            print(f"Typed destination airport: {params.destination}")
            await asyncio.sleep(5)
            await page.keyboard.press("Enter")
            print("Confirmed destination input.")

            print("Opening calendar for departure date...")
            departure_input = page.get_by_placeholder("Departure").nth(0)
            await departure_input.wait_for(state="visible", timeout=30000)
            await departure_input.click()
            await asyncio.sleep(5)

            print("Selecting departure date...")
            await page.get_by_role("button", name="Tuesday, December 31,").click()
            await asyncio.sleep(5)
            print("Selected departure date: Tuesday, December 31,")

            if params.return_date:
                print("Selecting return date...")
                return_input = page.get_by_placeholder("Return").nth(0)
                await return_input.wait_for(state="visible", timeout=30000)
                await return_input.click()
                await asyncio.sleep(5)
                await page.get_by_role("button", name="Monday, January 6,").click()
                await asyncio.sleep(5)
                print("Selected return date: Monday, January 6,")

            print("Waiting for flight results to load...")
            await page.wait_for_selector("div[aria-label='Flight options']", timeout=30000)
            print("Flight results loaded successfully.")
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
                    await asyncio.sleep(5)
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

    def save_results(self, flights: List[FlightData], params: SearchParameters) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"flight_results_{params.departure}_{params.destination}_{timestamp}.json"
        )

        output_data = {
            "search_parameters": {
                "departure": params.departure,
                "destination": params.destination,
                "departure_date": params.departure_date,
                "return_date": params.return_date,
                "search_timestamp": timestamp,
            },
            "flights": [vars(flight) for flight in flights],
        }

        filepath = os.path.join(self.results_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        return filepath

async def main():
    scraper = FlightScraper()
    params = SearchParameters(
        departure="MIA",
        destination="SEA",
        departure_date="2024-12-31",
        # return_date="2025-01-06",
        ticket_type="One way",
    )

    try:
        flights = await scraper.search_flights(params)
        if flights:
            print(f"Successfully found {len(flights)} flights")
            scraper.save_results(flights, params)
        else:
            print("No flights found.")
    except Exception as e:
        print(f"Error during flight search: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())