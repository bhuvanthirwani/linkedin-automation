"""
Browser automation engine using Playwright.
"""

from typing import Optional, List, Dict, Any

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from loguru import logger

from ..utils.config import BrowserConfig
from .antidetect import AntiDetect
from .humanize import Humanizer


class BrowserEngine:
    """
    Browser automation engine with anti-detection and human-like behavior.
    """
    
    def __init__(self, config: BrowserConfig):
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.humanizer = Humanizer()
        self.antidetect = AntiDetect()
        
    def start(self) -> None:
        """Start the browser."""
        logger.info("Starting browser engine (Sync)")
        
        self._playwright = sync_playwright().start()
        
        # Launch browser with anti-detection settings
        launch_args = self.antidetect.get_launch_args()
        
        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            args=launch_args,
        )
        
        # Create context with fingerprint protection
        self._context = self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            user_agent=self.config.user_agent,
            locale="en-US",
            timezone_id="America/New_York",
        )
        
        # Create page
        self._page = self._context.new_page()
        
        # Apply anti-detection scripts
        self.antidetect.apply_stealth(self._page)
        
        logger.info("Browser engine started successfully")
    
    def stop(self) -> None:
        """Stop the browser and cleanup."""
        logger.info("Stopping browser engine")
        
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
            
        logger.info("Browser engine stopped")
    
    @property
    def page(self) -> Page:
        """Get the current page."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page
    
    @property
    def context(self) -> BrowserContext:
        """Get the browser context."""
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._context
    
    def navigate(self, url: str) -> None:
        """Navigate to a URL with human-like behavior."""
        logger.info(f"Navigating to {url}")
        
        # Random delay before navigation
        self.humanizer.random_delay(5000, 15000)
        
        self.page.goto(url, wait_until="domcontentloaded")
        
        # Wait for page to stabilize
        self.humanizer.random_delay(5000, 10000)
        
    def click(self, selector: str, timeout: int = 10000) -> None:
        """Click an element with human-like behavior."""
        logger.debug(f"Clicking element: {selector}")
        
        # Wait for element
        self.page.wait_for_selector(selector, timeout=timeout)
        
        # Human-like delay before click
        self.humanizer.random_delay(200, 500)
        
        # Get element position for human-like mouse movement
        element = self.page.query_selector(selector)
        if element:
            box = element.bounding_box()
            if box:
                # Move mouse to element with human-like path
                target_x = box["x"] + box["width"] / 2
                target_y = box["y"] + box["height"] / 2
                self.humanizer.human_mouse_move(self.page, target_x, target_y)
        
        self.page.click(selector)
        
    def type_text(self, selector: str, text: str, human_like: bool = True) -> None:
        """Type text with human-like speed."""
        logger.debug(f"Typing text in: {selector}")
        
        self.page.wait_for_selector(selector)
        self.page.focus(selector)
        
        # Clear existing content
        self.page.fill(selector, "")
        
        if human_like:
            # Type character by character with random delays
            for char in text:
                self.page.type(selector, char, delay=self.humanizer.typing_delay())
        else:
            self.page.fill(selector, text)
    
    def scroll(self, direction: str = "down", amount: int = 300) -> None:
        """Scroll the page with human-like behavior."""
        scroll_y = amount if direction == "down" else -amount
        
        self.page.evaluate(f"window.scrollBy({{top: {scroll_y}, behavior: 'smooth'}})")
        
        # Wait after scrolling
        self.humanizer.random_delay(5000, 10000)
    
    def wait_for_element(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for an element to be visible."""
        try:
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            return True
        except Exception:
            return False
    
    def element_exists(self, selector: str) -> bool:
        """Check if an element exists on the page."""
        try:
            element = self.page.query_selector(selector)
            return element is not None
        except Exception:
            return False
    
    def get_text(self, selector: str) -> str:
        """Get text content of an element."""
        try:
            element = self.page.query_selector(selector)
            if element:
                return element.text_content() or ""
        except Exception:
            pass
        return ""
    
    def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get an attribute value from an element."""
        try:
            element = self.page.query_selector(selector)
            if element:
                return element.get_attribute(attribute)
        except Exception:
            pass
        return None
    
    def get_all_elements(self, selector: str) -> List[Any]:
        """Get all elements matching a selector."""
        return self.page.query_selector_all(selector)
    
    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url
    
    def screenshot(self, path: str) -> None:
        """Take a screenshot of the current page."""
        self.page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved to {path}")
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Get all cookies from the browser context."""
        return self._context.cookies()
    
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """Set cookies in the browser context."""
        self._context.add_cookies(cookies)
    
    def clear_cookies(self) -> None:
        """Clear all cookies from the browser context."""
        self._context.clear_cookies()
    
    def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the page context."""
        return self.page.evaluate(script)
