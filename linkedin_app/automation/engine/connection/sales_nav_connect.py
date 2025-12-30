"""
Connection manager for LinkedIn Sales Navigator.
"""

from typing import Optional, List
from datetime import datetime
import time
import urllib.parse as urlparse
from urllib.parse import urlencode

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile, ConnectionRequest, ConnectionStatus
from .tracker import ConnectionTracker
from ..database.db import DatabaseManager
from ..search.sales_nav_parser import SalesNavParser


# Selectors for Sales Navigator connection actions
THREE_DOTS_BUTTON = "button.artdeco-dropdown__trigger[aria-label*='actions']"
CONNECT_OPTION = "div[data-control-name='connect']"
MODAL_SEND_BUTTON = "button.artdeco-button--primary:has-text('Send invitation')"
MODAL_MESSAGE_TEXTAREA = "textarea#connect-message-content"
MODAL_ADD_NOTE_BUTTON = "button:has-text('Add a note')"

# Pagination
NEXT_PAGE_BUTTON = "button.search-results__pagination-next-button"


class SalesNavConnectionManager:
    """
    Manages sending connection requests on LinkedIn Sales Navigator.
    """
    
    def __init__(
        self,
        browser: BrowserEngine,
        tracker: ConnectionTracker,
        database_manager: Optional[DatabaseManager] = None,
    ):
        self.browser = browser
        self.tracker = tracker
        self.database_manager = database_manager
        self.parser = SalesNavParser(browser)
    
    def run_automation(
        self,
        base_url: str,
        end_page: int,
        limit: int,
        message: Optional[str] = None
    ):
        """
        Main loop for Sales Navigator connection automation.
        """
        logger.info(f"Starting Sales Navigator connection automation. Limit: {limit}, End Page: {end_page}")
        
        sent_count = 0
        current_page = 1
        
        while current_page <= end_page and sent_count < limit:
            # Construct page URL
            target_url = self._get_page_url(base_url, current_page)
            logger.info(f"Navigating to page {current_page}: {target_url}")
            self.browser.navigate(target_url)
            
            # Ensure page is stable
            try:
                self.browser.page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass

            # Double check for redirect or modal
            if "contract-chooser" in self.browser.page.url:
                logger.warning("Redirected to contract chooser. Please select a contract manually. Waiting 30s...")
                self.browser.humanizer.random_delay(30000, 40000)
                if "contract-chooser" in self.browser.page.url:
                    logger.error("Still on contract-chooser. Skipping automation.")
                    break

            # Parse profiles on current page
            try:
                items = self.browser.get_all_elements("li.search-results__result-item")
            except Exception as e:
                logger.warning(f"Context may have been destroyed, retrying: {e}")
                self.browser.humanizer.random_delay(5000, 10000)
                items = self.browser.get_all_elements("li.search-results__result-item")

            logger.info(f"Found {len(items)} profiles on page {current_page}")
            
            if not items:
                logger.warning(f"No profiles found on page {current_page}. Scrolling to check for lazy loading...")
                self.browser.scroll(amount=1000)
                items = self.browser.get_all_elements("li.search-results__result-item")
                if not items:
                    logger.warning("Still no profiles found. Moving to next page or finishing.")
            
            for item in items:
                if sent_count >= limit:
                    logger.info(f"Reached connection limit: {limit}")
                    return

                try:
                    # Scroll item into view
                    item.scroll_into_view_if_needed()
                    self.browser.humanizer.random_delay(1000, 2000)
                    
                    profile = self.parser._parse_result_item(item)
                    if not profile:
                        continue

                    # Check if already sent in this session or DB
                    if self.database_manager and self.database_manager.is_connection_sent(profile.url):
                        logger.info(f"Connection already sent to {profile.name} ({profile.url}). Skipping.")
                        continue

                    logger.info(f"Attempting to connect with {profile.name}")
                    
                    success = self._send_connection(item, message)
                    
                    if success:
                        sent_count += 1
                        
                        # Record in tracker
                        request = ConnectionRequest(
                            profile_url=profile.url,
                            profile_name=profile.name,
                            sent_at=datetime.now(),
                            status=ConnectionStatus.PENDING,
                            note=message or "",
                        )
                        # Record in local tracker
                        self.tracker.record(request)
                        
                        # Update database
                        if self.database_manager:
                            self.database_manager.record_daily_stat("connections_sent")
                            self.database_manager.record_connection_history(
                                profile_url=profile.url,
                                profile_name=profile.name,
                                status="pending",
                                note=message or ""
                            )
                        
                        logger.info(f"Successfully sent invitation to {profile.name}. Total: {sent_count}")
                    
                        # Random delay between connections (User requested 20-30s)
                        logger.info("Waiting 20-30 seconds before next connection...")
                        self.browser.humanizer.random_delay(20000, 30000)
                    else:
                        # Small delay after failure
                        self.browser.humanizer.random_delay(5000, 10000)
                    
                except Exception as e:
                    logger.error(f"Error processing profile: {e}")
                    continue
            
            # After finishing all items on the page, move to next page
            current_page += 1
                
        logger.info(f"Sales Navigator automation complete. Sent {sent_count} invitations.")
    
    def _send_connection(self, item, message: Optional[str] = None) -> bool:
        """Execute the 3 dots -> Connect -> Send flow for a single item."""
        try:
            # 1. Click 3 dots button
            three_dots = item.query_selector(THREE_DOTS_BUTTON)
            if not three_dots:
                logger.warning("Could not find 3 dots button for this profile. Checking direct connect...")
                # Sometimes there's a direct connect button even in Sales Nav
                direct_connect = item.query_selector("button:has-text('Connect')")
                if direct_connect:
                    direct_connect.click()
                    self.browser.humanizer.random_delay(2000, 4000)
                else:
                    return False
            else:
                three_dots.click()
                self.browser.humanizer.random_delay(2000, 4000)
                
                # 2. Click Connect option in dropdown
                connect_option = self.browser.page.locator(CONNECT_OPTION).first
                if not connect_option.is_visible():
                    logger.warning("Connect option not visible in dropdown.")
                    # Try clicking outside to close dropdown
                    self.browser.page.keyboard.press("Escape")
                    return False
                
                connect_option.click()
                self.browser.humanizer.random_delay(3000, 5000)
            
            # 3. Handle modal
            if not self.browser.wait_for_element("div.artdeco-modal", timeout=10000):
                logger.warning("Connection modal did not appear.")
                return False
            
            # Add message if provided
            if message:
                add_note = self.browser.page.locator(MODAL_ADD_NOTE_BUTTON)
                if add_note.is_visible():
                    add_note.click()
                    self.browser.humanizer.random_delay(1000, 2000)
                
                textarea = self.browser.page.locator(MODAL_MESSAGE_TEXTAREA)
                if textarea.is_visible():
                    self.browser.type_text(MODAL_MESSAGE_TEXTAREA, message, human_like=True)
                    self.browser.humanizer.random_delay(1000, 2000)
            
            # 4. Click Send invitation
            send_btn = self.browser.page.locator(MODAL_SEND_BUTTON)
            if send_btn.is_visible():
                send_btn.click()
                self.browser.humanizer.random_delay(3000, 5000)
                
                # Check for success or error toast
                # Usually Sales Nav shows a toast. We'll just assume success if button becomes hidden/modal closes
                return True
            else:
                logger.warning("Send invitation button not found in modal.")
                self.browser.page.keyboard.press("Escape")
                return False
                
        except Exception as e:
            logger.error(f"Failed connection flow: {e}")
            self.browser.page.keyboard.press("Escape")
            return False

    def _get_page_url(self, url: str, page_num: int) -> str:
        """Construct the URL for a specific page number."""
        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query['page'] = str(page_num)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)
