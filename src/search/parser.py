"""
Profile parsing from LinkedIn search results.
"""

import re
from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile


# Selectors for search results
# Using more stable selectors that work with LinkedIn's obfuscated class names
# Select divs with data-chameleon-result-urn attribute (each result item contains one)
SEARCH_RESULT_ITEM = "div[data-chameleon-result-urn]"
PROFILE_LINK = "a[data-test-app-aware-link][href*='/in/']"
PROFILE_NAME = "a[data-test-app-aware-link][href*='/in/'] span[aria-hidden='true']"
# Headline: div with t-14, t-black, t-normal classes (appears after name section)
PROFILE_HEADLINE = "div.t-14.t-black.t-normal"
# Location: div with t-14, t-normal classes that comes after headline (typically contains city, state)
PROFILE_LOCATION = "div.t-14.t-normal"


class ProfileParser:
    """
    Parses profile information from LinkedIn pages.
    """
    
    def __init__(self, browser: BrowserEngine):
        self.browser = browser
    
    async def parse_search_results(self) -> List[Profile]:
        """
        Parse profiles from the current search results page.
        
        Returns:
            List of Profile objects.
        """
        profiles = []
        
        try:
            # Get all search result items
            items = await self.browser.get_all_elements(SEARCH_RESULT_ITEM)
            logger.debug(f"Found {len(items)} search result items")
            
            for i, item in enumerate(items):
                try:
                    profile = await self._parse_result_item(item)
                    if profile:
                        profiles.append(profile)
                except Exception as e:
                    logger.debug(f"Failed to parse result item {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to parse search results: {e}")
        
        return profiles
    
    async def _parse_result_item(self, item) -> Optional[Profile]:
        """Parse a single search result item."""
        try:
            # Get profile URL - look for the main profile link (not mutual connections links)
            # Use query_selector_all on the item (ElementHandle)
            link_elements = await item.query_selector_all(PROFILE_LINK)
            link_element = None
            url = None
            
            # Find the main profile link (usually the first one with /in/ in href)
            for link in link_elements:
                href = await link.get_attribute("href") or ""
                if "/in/" in href and "miniProfileUrn" in href:
                    link_element = link
                    url = href
                    break
            
            if not link_element or not url:
                return None
            
            # Clean URL (remove query parameters)
            url = self._clean_profile_url(url)
            
            # Get name - look for span with aria-hidden='true' within the profile link
            name = ""
            name_element = await link_element.query_selector("span[aria-hidden='true']")
            if name_element:
                name = await name_element.text_content() or ""
                name = name.strip()
            
            # Get headline - find div with t-14 t-black t-normal classes
            # This appears in the result item, typically after the name section
            headline = ""
            headline_elements = await item.query_selector_all(PROFILE_HEADLINE)
            # Usually the first one is the headline (others might be badges or other text)
            if headline_elements:
                headline = await headline_elements[0].text_content() or ""
                headline = headline.strip()
            
            # Get location - find div with t-14 t-normal that comes after headline
            # Look for the one that contains location-like text (has comma or city/state pattern)
            location = ""
            location_elements = await item.query_selector_all(PROFILE_LOCATION)
            for loc_elem in location_elements:
                loc_text = await loc_elem.text_content() or ""
                loc_text = loc_text.strip()
                # Location typically contains commas or looks like "City, State" or "City, Country"
                if loc_text and ("," in loc_text or len(loc_text.split()) <= 3):
                    location = loc_text
                    break
            
            # Extract first name and company from headline
            first_name, last_name = self._split_name(name)
            company = self._extract_company(headline)
            if company == "" or "Engineer" in company:
                company = "your company"
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
            logger.debug(f"Error parsing result item: {e}")
            return None
    
    async def parse_profile_page(self) -> Optional[Profile]:
        """
        Parse profile information from a profile page.
        
        Returns:
            Profile object if successful, None otherwise.
        """
        try:
            url = await self.browser.get_current_url()
            
            # Get name from the profile page
            name = await self.browser.get_text("h1.text-heading-xlarge")
            
            # Get headline
            headline = await self.browser.get_text("div.text-body-medium")
            
            # Get location
            location = await self.browser.get_text("span.text-body-small:has-text('•')")
            
            first_name, last_name = self._split_name(name)
            company = self._extract_company(headline)
            if company == "" or "Engineer" in company:
                company = "your company"
            title = self._extract_title(headline)
            
            return Profile(
                url=self._clean_profile_url(url),
                name=name.strip(),
                first_name=first_name,
                last_name=last_name,
                headline=headline.strip(),
                company=company,
                location=location.strip(),
                title=title,
                scraped_at=datetime.now(),
            )
            
        except Exception as e:
            logger.error(f"Failed to parse profile page: {e}")
            return None
    
    def _clean_profile_url(self, url: str) -> str:
        """Clean a profile URL by removing query parameters."""
        # Remove query parameters
        if "?" in url:
            url = url.split("?")[0]
        
        # Ensure it ends without trailing slash
        url = url.rstrip("/")
        
        return url
    
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
        # Common patterns: "Title at Company", "Title @ Company"
        patterns = [
            r" at (.+?)(?:\s*[|·•]|$)",
            r" @ (.+?)(?:\s*[|·•]|$)",
            r"(?:^|\|)\s*(.+?)(?:\s*[|·•]|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, headline, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_title(self, headline: str) -> str:
        """Extract job title from headline."""
        # Common patterns: "Title at Company"
        patterns = [
            r"^(.+?)\s+(?:at|@)\s+",
            r"^(.+?)(?:\s*[|·•])",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, headline, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no pattern matches, return the whole headline as title
        return headline.split("|")[0].strip() if headline else ""
