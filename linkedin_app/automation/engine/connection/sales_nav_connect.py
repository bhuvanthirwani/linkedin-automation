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


# Selectors for Sales Navigator connection actions (Updated)
THREE_DOTS_BUTTON = "button[aria-label^='See more actions for']"
CONNECT_OPTION = "div[data-control-name='connect']"
MODAL_SEND_BUTTON = "button.connect-cta-form__send"
MODAL_MESSAGE_TEXTAREA = "textarea#connect-cta-form__invitation"
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
    
    def run_automation(self, base_url: str, start_page: int, end_page: int, limit: int, message: Optional[str] = None) -> None:
        """
        Main loop for Sales Navigator connection automation.
        """
        logger.info(f"Starting Sales Navigator connection automation. Start: {start_page}, End: {end_page}, Limit: {limit}")
        
        sent_count = 0
        current_page = start_page
        
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

            # Parse profiles on current page with lazy loading handling
            try:
                from ..search.sales_nav_parser import SEARCH_RESULT_ITEM, RESULTS_CONTAINER
                
                # Wait for results container to appear
                logger.info(f"Waiting for search results on page {current_page}...")
                if self.browser.wait_for_element(RESULTS_CONTAINER, timeout=15000):
                    logger.info("Found results container.")
                else:
                    logger.warning(f"Results container {RESULTS_CONTAINER} not found. Attempting scroll...")
                
                # Initial wait
                self.browser.humanizer.random_delay(2000, 4000)
                
                # Scroll gradually to trigger lazy loading
                logger.info(f"Scrolling page {current_page} to load all profiles...")
                for _ in range(3):
                    self.browser.scroll(amount=800)
                    self.browser.humanizer.random_delay(1500, 2500)
                
                # Scroll back to top to start processing
                self.browser.page.evaluate("window.scrollTo(0, 0)")
                self.browser.humanizer.random_delay(1500, 3000)
                
                # Get all elements - using the container if possible
                selector = f"{RESULTS_CONTAINER} {SEARCH_RESULT_ITEM}"
                items = self.browser.get_all_elements(selector)
                
                if not items:
                    logger.warning(f"No items found with specific selector. Trying broader selector: {SEARCH_RESULT_ITEM}")
                    items = self.browser.get_all_elements(SEARCH_RESULT_ITEM)
            except Exception as e:
                logger.warning(f"Error during profile detection on page {current_page}: {e}")
                items = []

            logger.info(f"Detected {len(items)} potential items on page {current_page}")
            
            processed_on_page = 0
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
                    
                    # Format message if it's a template
                    final_message = message
                    if final_message and "{" in final_message and "}" in final_message:
                        try:
                            final_message = final_message.format(
                                first_name=profile.first_name,
                                last_name=profile.last_name,
                                company=profile.company or "your company",
                                title=profile.title or "your role"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to format message template: {e}")
                    
                    success = self._send_connection(item, final_message)
                    
                    if success:
                        sent_count += 1
                        
                        # Record in tracker
                        request = ConnectionRequest(
                            profile_url=profile.url,
                            profile_name=profile.name,
                            sent_at=datetime.now(),
                            status=ConnectionStatus.PENDING,
                            note=final_message or "",
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
                                note=final_message or ""
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
                direct_connect = item.query_selector("button:has-text('Connect')")
                if direct_connect:
                    direct_connect.click()
                else:
                    return False
            else:
                three_dots.click()
                self.browser.humanizer.random_delay(1500, 3000)
                
                # 2. Click Connect option in dropdown
                connect_selectors = [
                    CONNECT_OPTION,
                    "div.artdeco-dropdown__item:has-text('Connect')",
                    "li:has-text('Connect')",
                    "div[data-control-name='connect']"
                ]
                
                clicked_connect = False
                for sel in connect_selectors:
                    option = self.browser.page.locator(sel).first
                    if option.is_visible():
                        option.click()
                        clicked_connect = True
                        break
                
                if not clicked_connect:
                    logger.warning("Connect option not found in dropdown.")
                    self.browser.page.keyboard.press("Escape")
                    return False
            
            # 3. Handle modal
            if not self.browser.wait_for_element("div.artdeco-modal", timeout=10000):
                logger.warning("Connection modal did not appear.")
                return False
            
            # Add message if provided (or use a default if user wants)
            # Use the provided message or a generic one if you want to ensure a note is sent
            if message:
                # Wait for the modal content to settle
                self.browser.humanizer.random_delay(1000, 2000)
                
                textarea = self.browser.page.locator(MODAL_MESSAGE_TEXTAREA)
                if not textarea.is_visible():
                    # Check for "Add a note" button
                    add_note = self.browser.page.locator(MODAL_ADD_NOTE_BUTTON)
                    if add_note.is_visible():
                        add_note.click()
                        # Wait for textarea to appear after click
                        textarea.wait_for(state="visible", timeout=5000)
                
                if textarea.is_visible():
                    logger.info("Typing connection message...")
                    # Clear existing text if any (sometimes there's placeholder text)
                    textarea.fill("") 
                    self.browser.type_text(MODAL_MESSAGE_TEXTAREA, message, human_like=True)
                    self.browser.humanizer.random_delay(1000, 2000)
                    
                    # Verify text was entered
                    val = textarea.input_value()
                    if not val:
                        logger.warning("Message textarea seems empty after typing. Retrying...")
                        textarea.fill(message)
                else:
                    logger.warning("Message textarea not visible even after clicking 'Add a note'.")
            
            # 4. Click Send invitation
            send_btn = self.browser.page.locator(MODAL_SEND_BUTTON)
            if send_btn.is_visible() and send_btn.is_enabled():
                send_btn.click()
                logger.info("Connection request sent.")
                self.browser.humanizer.random_delay(2000, 4000)
                return True
            else:
                logger.warning("Send invitation button not clickable.")
                self.browser.page.keyboard.press("Escape")
                return False
                
        except Exception as e:
            logger.error(f"Failed connection flow: {e}")
            try:
                self.browser.page.keyboard.press("Escape")
            except:
                pass
            return False

    def _get_page_url(self, url: str, page_num: int) -> str:
        """Construct the URL for a specific page number."""
        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query['page'] = str(page_num)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)
