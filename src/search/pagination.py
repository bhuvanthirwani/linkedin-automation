"""
Pagination handling for LinkedIn search results.
"""

from loguru import logger

from ..browser.browser import BrowserEngine


# Pagination selectors
NEXT_BUTTON = "button[aria-label='Next'], button.artdeco-pagination__button--next"
PREV_BUTTON = "button[aria-label='Previous'], button.artdeco-pagination__button--previous"
PAGE_BUTTONS = "button.artdeco-pagination__indicator"
CURRENT_PAGE = "button.artdeco-pagination__indicator--number.active"
PAGINATION_CONTAINER = "div.artdeco-pagination"


class PaginationHandler:
    """
    Handles pagination for LinkedIn search results.
    """
    
    def __init__(self, browser: BrowserEngine):
        self.browser = browser
    
    async def has_next_page(self) -> bool:
        """Check if there's a next page of results."""
        try:
            # Check if next button exists and is enabled
            next_button = await self.browser.page.query_selector(NEXT_BUTTON)
            if not next_button:
                return False
            
            # Check if button is disabled
            is_disabled = await next_button.get_attribute("disabled")
            if is_disabled:
                return False
            
            # Check aria-disabled
            aria_disabled = await next_button.get_attribute("aria-disabled")
            if aria_disabled == "true":
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking for next page: {e}")
            return False
    
    async def has_previous_page(self) -> bool:
        """Check if there's a previous page of results."""
        try:
            prev_button = await self.browser.page.query_selector(PREV_BUTTON)
            if not prev_button:
                return False
            
            is_disabled = await prev_button.get_attribute("disabled")
            if is_disabled:
                return False
            
            aria_disabled = await prev_button.get_attribute("aria-disabled")
            if aria_disabled == "true":
                return False
            
            return True
            
        except Exception:
            return False
    
    async def go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        logger.debug("Navigating to next page")
        
        try:
            if not await self.has_next_page():
                return False
            
            # Scroll to pagination
            await self._scroll_to_pagination()
            
            # Click next button
            await self.browser.click(NEXT_BUTTON)
            
            # Wait for page to load
            await self.browser.humanizer.random_delay(5000, 10000)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to go to next page: {e}")
            return False
    
    async def go_to_previous_page(self) -> bool:
        """Navigate to the previous page of results."""
        logger.debug("Navigating to previous page")
        
        try:
            if not await self.has_previous_page():
                return False
            
            await self._scroll_to_pagination()
            await self.browser.click(PREV_BUTTON)
            await self.browser.humanizer.random_delay(5000, 10000)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to go to previous page: {e}")
            return False
    
    async def go_to_page(self, page_number: int) -> bool:
        """
        Navigate to a specific page number.
        
        Args:
            page_number: The page number to navigate to (1-indexed).
            
        Returns:
            True if navigation successful, False otherwise.
        """
        logger.debug(f"Navigating to page {page_number}")
        
        try:
            await self._scroll_to_pagination()
            
            # Find the page button
            page_buttons = await self.browser.get_all_elements(PAGE_BUTTONS)
            
            for button in page_buttons:
                text = await button.text_content()
                if text and text.strip() == str(page_number):
                    await button.click()
                    await self.browser.humanizer.random_delay(5000, 10000)
                    return True
            
            logger.warning(f"Page {page_number} button not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to go to page {page_number}: {e}")
            return False
    
    async def get_current_page(self) -> int:
        """Get the current page number."""
        try:
            current = await self.browser.page.query_selector(CURRENT_PAGE)
            if current:
                text = await current.text_content()
                if text:
                    return int(text.strip())
        except Exception:
            pass
        
        return 1
    
    async def get_total_pages(self) -> int:
        """Get the total number of pages (if available)."""
        try:
            page_buttons = await self.browser.get_all_elements(PAGE_BUTTONS)
            
            max_page = 1
            for button in page_buttons:
                text = await button.text_content()
                if text and text.strip().isdigit():
                    page_num = int(text.strip())
                    max_page = max(max_page, page_num)
            
            return max_page
            
        except Exception:
            return 1
    
    async def _scroll_to_pagination(self) -> None:
        """Scroll to make pagination visible."""
        try:
            # Scroll to bottom where pagination usually is
            await self.browser.page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await self.browser.humanizer.random_delay(5000, 10000)
        except Exception:
            pass
