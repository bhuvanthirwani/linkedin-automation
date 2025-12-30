"""
LinkedIn user search functionality.
"""

import re
import urllib.parse
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile, SearchCriteria, SearchResult
from .parser import ProfileParser
from .pagination import PaginationHandler


class UserSearch:
    """
    Search for LinkedIn users based on criteria.
    """
    
    BASE_SEARCH_URL = "https://www.linkedin.com/search/results/people/"
    
    def __init__(self, browser: BrowserEngine, max_pages: int = 30):
        self.browser = browser
        self.max_pages = max_pages
        self.parser = ProfileParser(browser)
        self.pagination = PaginationHandler(browser)
        self._seen_urls: set = set()
    
    from typing import List, Optional, Callable

    def search(self, criteria: SearchCriteria, on_page_scraped: Optional[Callable[[List[Profile]], None]] = None) -> SearchResult:
        """
        Search for profiles matching the given criteria.
        
        Args:
            criteria: Search criteria to use.
            on_page_scraped: Optional callback to invoke with new profiles from each page.
            
        Returns:
            SearchResult with found profiles.
        """
        start_time = datetime.now()
        logger.info(f"Starting user search with criteria: {criteria}")
        
        profiles: List[Profile] = []
        pages_scraped = 0
        
        # Build search URL
        search_url = self._build_search_url(criteria)
        logger.debug(f"Search URL: {search_url}")
        
        # Navigate to search results
        self.browser.navigate(search_url)
        self.browser.humanizer.random_delay(5000, 10000)
        
        # Process pages
        while pages_scraped < self.max_pages:
            pages_scraped += 1
            current_page_num = criteria.page + pages_scraped - 1
            logger.info(f"Processing page {current_page_num} (Iteration {pages_scraped})")
            
            # Scroll to load all results on the page
            self._scroll_to_load_results()
            
            # Parse profiles from current page
            page_profiles = self.parser.parse_search_results()
            
            # Filter duplicates
            new_profiles = []
            for profile in page_profiles:
                if profile.url not in self._seen_urls:
                    self._seen_urls.add(profile.url)
                    new_profiles.append(profile)
            
            profiles.extend(new_profiles)
            logger.info(f"Found {len(new_profiles)} new profiles on page {pages_scraped}")
            
            if on_page_scraped and new_profiles:
                on_page_scraped(new_profiles)
            
            # Check if we've reached max results
            if criteria.max_results and len(profiles) >= criteria.max_results:
                profiles = profiles[:criteria.max_results]
                break
            
            # Check for next page
            has_next = self.pagination.has_next_page()
            if not has_next:
                logger.info("No more pages available")
                break
            
            # Go to next page
            self.pagination.go_to_next_page()
            self.browser.humanizer.random_delay(500, 1000)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result = SearchResult(
            criteria=criteria,
            profiles=profiles,
            total_found=len(profiles),
            pages_scraped=pages_scraped,
            searched_at=datetime.now(),
            duration_seconds=duration,
        )
        
        logger.info(f"Search completed: {len(profiles)} profiles found in {duration:.2f}s")
        return result
    
    def _build_search_url(self, criteria: SearchCriteria) -> str:
        """Build the LinkedIn search URL from criteria."""
        params = {}
        
        if criteria.keywords:
            params["keywords"] = criteria.keywords

        params["network"] = criteria.network
        params["page"] = criteria.page
        # LinkedIn uses specific filter parameters
        filters = []
        
        if criteria.job_title:
            filters.append(f"currentFunction->title:{criteria.job_title}")
        
        if criteria.company:
            filters.append(f"currentCompany:{criteria.company}")
        
        if criteria.location:
            params["geoUrn"] = criteria.location
        
        if criteria.industry:
            filters.append(f"industry:{criteria.industry}")
        
        if filters:
            params["filters"] = ",".join(filters)
        
        # Build URL
        query_string = urllib.parse.urlencode(params)
        return f"{self.BASE_SEARCH_URL}?{query_string}"
    
    def _scroll_to_load_results(self) -> None:
        """Scroll through the page to load all lazy-loaded results."""
        scroll_count = 0
        max_scrolls = 5
        
        while scroll_count < max_scrolls:
            self.browser.scroll("down", 400)
            self.browser.humanizer.random_delay(5000, 10000)
            scroll_count += 1
        
        # Scroll back to top
        self.browser.page.evaluate("window.scrollTo(0, 0)")
        self.browser.humanizer.random_delay(5000, 10000)
    
    def clear_seen_profiles(self) -> None:
        """Clear the set of seen profile URLs."""
        self._seen_urls.clear()


def search_by_keywords(
    browser: BrowserEngine,
    keywords: str,
    location: str = "",
    max_results: int = 100,
) -> SearchResult:
    """
    Convenience function to search by keywords.
    
    Args:
        browser: Browser engine to use.
        keywords: Search keywords.
        location: Optional location filter.
        max_results: Maximum number of results.
        
    Returns:
        SearchResult with found profiles.
    """
    criteria = SearchCriteria(
        keywords=keywords,
        location=location,
        max_results=max_results,
    )
    
    searcher = UserSearch(browser)
    return searcher.search(criteria)
