"""
Profile parsing from LinkedIn Sales Navigator search results.
"""

import re
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile


# Selectors for Sales Navigator search results (Updated based on user HTML)
RESULTS_CONTAINER = "ol.artdeco-list"
SEARCH_RESULT_ITEM = "li.artdeco-list__item"
PROFILE_LINK = "a[data-control-name='view_lead_panel_via_search_lead_name']"
PROFILE_NAME = "span[data-anonymize='person-name']"
PROFILE_HEADLINE = "span[data-anonymize='title']"
PROFILE_LOCATION = "span[data-anonymize='location']"
PROFILE_COMPANY = "a[data-anonymize='company-name']"
LEAD_INDICATOR = "div[data-x-search-result='LEAD']"


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
            # First, verify if this is actually a lead result
            if not item.query_selector(LEAD_INDICATOR):
                logger.debug("Item does not have a lead indicator, skipping.")
                return None

            # Get profile URL
            link_element = item.query_selector(PROFILE_LINK)
            if not link_element:
                return None
            
            url = link_element.get_attribute("href") or ""
            if not url:
                return None
            
            # Clean URL
            url = self._clean_profile_url(url)
            
            # Get name - usually inside the link in a span
            name_element = link_element.query_selector(PROFILE_NAME)
            if name_element:
                name = name_element.text_content() or ""
            else:
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
            
            # Get company
            company = ""
            company_element = item.query_selector(PROFILE_COMPANY)
            if company_element:
                company = company_element.text_content() or ""
                company = company.strip()
            
            # Extract first name
            first_name, last_name = self._split_name(name)
            
            # If headline is missing, use title if available
            title = headline
            
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
