"""
Profile parsing from LinkedIn Sales Navigator search results.
"""

import re
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile


# Selectors for Sales Navigator search results
SEARCH_RESULT_ITEM = "li.search-results__result-item"
PROFILE_LINK = "a.result-lockup__full-name-link"
PROFILE_NAME = "a.result-lockup__full-name-link"
PROFILE_HEADLINE = "div.result-lockup__headline"
PROFILE_LOCATION = "p.result-lockup__address"


class SalesNavParser:
    """
    Parses profile information from LinkedIn Sales Navigator pages.
    """
    
    def __init__(self, browser: BrowserEngine):
        self.browser = browser
    
    def parse_search_results(self) -> List[Profile]:
        """
        Parse profiles from the current Sales Navigator search results page.
        
        Returns:
            List of Profile objects.
        """
        profiles = []
        
        try:
            # Wait for search results to load
            self.browser.wait_for_element(SEARCH_RESULT_ITEM, timeout=20000)
            
            # Get all search result items
            items = self.browser.get_all_elements(SEARCH_RESULT_ITEM)
            logger.debug(f"Found {len(items)} Sales Navigator search result items")
            
            for i, item in enumerate(items):
                try:
                    profile = self._parse_result_item(item)
                    if profile:
                        profiles.append(profile)
                except Exception as e:
                    logger.debug(f"Failed to parse Sales Nav result item {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to parse Sales Nav search results: {e}")
        
        return profiles
    
    def _parse_result_item(self, item) -> Optional[Profile]:
        """Parse a single Sales Navigator search result item."""
        try:
            # Get profile URL
            link_element = item.query_selector(PROFILE_LINK)
            if not link_element:
                return None
            
            url = link_element.get_attribute("href") or ""
            if not url:
                return None
            
            # Clean URL
            url = self._clean_profile_url(url)
            
            # Get name
            name = link_element.text_content() or ""
            name = name.strip()
            
            # Get headline
            headline = ""
            headline_element = item.query_selector(PROFILE_HEADLINE)
            if headline_element:
                headline = headline_element.text_content() or ""
                headline = headline.strip()
            
            # Get location
            location = ""
            location_element = item.query_selector(PROFILE_LOCATION)
            if location_element:
                location = location_element.text_content() or ""
                location = location.strip()
            
            # Extract first name and company from headline
            first_name, last_name = self._split_name(name)
            company = self._extract_company(headline)
            title = self._extract_title(headline)
            
            return Profile(
                url=url,
                name=name,
                first_name=first_name,
                last_name=last_name,
                headline=headline,
                company=company,
                location=location,
                title=title,
                scraped_at=datetime.now(),
            )
            
        except Exception as e:
            logger.debug(f"Error parsing Sales Nav result item: {e}")
            return None
    
    def _clean_profile_url(self, url: str) -> str:
        """Clean a profile URL."""
        if "?" in url:
            url = url.split("?")[0]
        return url.rstrip("/")
    
    def _split_name(self, full_name: str) -> tuple:
        """Split full name into first and last name."""
        parts = full_name.strip().split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        elif len(parts) == 1:
            return parts[0], ""
        return "", ""
    
    def _extract_company(self, headline: str) -> str:
        """Extract company name from headline."""
        patterns = [
            r" at (.+?)(?:\s*[|·•]|$)",
            r" @ (.+?)(?:\s*[|·•]|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, headline, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_title(self, headline: str) -> str:
        """Extract job title from headline."""
        patterns = [
            r"^(.+?)\s+(?:at|@)\s+",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, headline, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return headline.split("|")[0].strip() if headline else ""
