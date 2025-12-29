
import asyncio
from typing import Optional, List
from loguru import logger
from ..database.db import DatabaseManager
from ..browser.browser import BrowserEngine
from ..search.search import UserSearch
from ..utils.models import SearchCriteria

class NetworkScraper:
    def __init__(self, browser: BrowserEngine, db: DatabaseManager):
        self.browser = browser
        self.db = db
        # Set max pages to a reasonable default or pass via config
        self.searcher = UserSearch(browser, max_pages=30)

    async def execute(self, keywords: str, location: str = "", start_page: int = 1, max_pages: int = 10, limit: int = 100):
        """
        Execute scraping of profiles based on search criteria.
        Populates the linkedin_db_network_data table.
        """
        logger.info(f"Starting Scrapping mode with keywords='{keywords}' location='{location}' start_page={start_page} pages={max_pages} limit={limit}")
        
        # If no keywords, we can't search easily. User might mean "My Network" but that's harder to scrape properly without API.
        # We'll assume search.
        search_kw = keywords or "" 
        
        criteria = SearchCriteria(
            keywords=search_kw,
            locations=[location] if location else [],  # Ensure list for locations
            page=start_page,
            max_results=limit
        )
        
        # update searcher max_pages
        self.searcher.max_pages = max_pages
        
        # Perform search (this navigates and scrolls)
        results = await self.searcher.search(criteria)
        
        logger.info(f"Found {len(results.profiles)} profiles. Saving to database...")
        
        saved_count = 0
        for profile in results.profiles:
            try:
                # Basic name parsing
                parts = profile.name.strip().split(' ') if profile.name else []
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                
                data = {
                    "linkedin_url": profile.url,
                    "name": profile.name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "keywords": [search_kw] if search_kw else [],
                    "location": location if location else profile.location
                }
                
                if await self.db.upsert_network_profile(data):
                    saved_count += 1
            except Exception as e:
                logger.error(f"Error saving profile {profile.url}: {e}")
                
        logger.info(f"Successfully saved {saved_count} profiles to network data.")
        return saved_count
