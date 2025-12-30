"""
Connection request functionality for LinkedIn.
"""

from typing import Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile, ConnectionRequest, ConnectionStatus
from .note import NoteComposer
from .tracker import ConnectionTracker
from ..database.db import DatabaseManager


# Selectors for connection actions, scoped to the primary profile card (artdeco-card)
# Direct Connect button: button with aria-label containing "Invite" and "connect"
# We scope to section.artdeco-card to avoid clicking connect buttons in "People also viewed" or other sections
CONNECT_BUTTON = "section.artdeco-card button[aria-label*='Invite'][aria-label*='connect'], section.artdeco-card button:has(svg[data-test-icon='connect-small'])"
MORE_BUTTON = "section.artdeco-card button[aria-label='More actions'], section.artdeco-card button.artdeco-dropdown__trigger"

# Connect option in dropdown: div with aria-label containing "Invite" and "connect"
# This might be inside the card or at the end of the body depending on the dropdown implementation
# Added :has-text('Connect') to catch the specific element in the user's snippet
CONNECT_IN_DROPDOWN = (
    "div[aria-label*='Invite'][aria-label*='connect'], "
    "div.artdeco-dropdown__item:has(svg[data-test-icon='connect-medium']), "
    "div.artdeco-dropdown__item:has-text('Connect'), "
    ".artdeco-dropdown__content div[aria-label*='connect']"
)

ADD_NOTE_BUTTON = "button[aria-label='Add a note']"
NOTE_TEXTAREA = "textarea[name='message'], textarea#custom-message"
SEND_BUTTON = "button[aria-label='Send now'], button[aria-label='Send invitation']"
PENDING_BUTTON = "section.artdeco-card button[aria-label*='Pending']"
MESSAGE_BUTTON = "section.artdeco-card button[aria-label*='Message']"
# Selector for email requirement in modal
EMAIL_INPUT = "input#email, input[name='email']"
EMAIL_REQUIRED_TEXT = "text='please enter their email to connect'"


class ConnectionManager:
    """
    Manages sending connection requests on LinkedIn.
    """
    
    def __init__(
        self,
        browser: BrowserEngine,
        tracker: ConnectionTracker,
        note_composer: Optional[NoteComposer] = None,
        daily_limit: int = 25,
        database_manager: Optional[DatabaseManager] = None,
    ):
        self.browser = browser
        self.tracker = tracker
        self.note_composer = note_composer
        self.daily_limit = daily_limit
        self.database_manager = database_manager
    
    def send_connection_request(
        self,
        profile: Profile,
        note: Optional[str] = None,
    ) -> ConnectionRequest:
        """
        Send a connection request to a profile.
        """
        logger.info(f"Sending connection request to {profile.name}")
        
        try:
            # Navigate to profile
            logger.info(f"Navigating to profile: {profile.url}")
            self.browser.navigate(profile.url)
            logger.debug(f"Navigation complete, waiting for page to load...")
            self.browser.humanizer.random_delay(5000, 10000)
            logger.debug("Page load delay complete")
            
            # Check mapping status if we're already pending or connected
            if self._is_pending():
                logger.info(f"Connection pending with {profile.name}")
                if self.database_manager:
                    # NOTE: DatabaseManager is still async for now, will be wrapped or refactored
                    pass
                
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.PENDING,
                )
            
            logger.debug("Checking if already connected...")
            # Check if already connected (no Connect button and no Connect in dropdown)
            if self._is_already_connected():
                logger.info(f"Already connected with {profile.name}")
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.ACCEPTED,
                )
            
            logger.debug("Not pending and not connected, proceeding to send connection request...")
            
            # Click Connect button
            logger.debug("Attempting to click Connect button...")
            clicked = self._click_connect_button()
            if not clicked:
                logger.error("Failed to find or click Connect button")
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.ERROR,
                    error="Connect button not found",
                )
            
            logger.info("Connect button clicked successfully, waiting for modal...")
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Check if email is required
            logger.debug("Checking if email is required to connect...")
            email_input_exists = self.browser.element_exists(EMAIL_INPUT)
            email_text_exists = self.browser.page.locator(f"text='enter their email'").count() > 0 or \
                                self.browser.page.locator(f"text='email to connect'").count() > 0
            
            if email_input_exists or email_text_exists:
                logger.warning(f"Email required to connect with {profile.name}. Skipping.")
                try:
                    self.browser.page.keyboard.press("Escape")
                    self.browser.humanizer.random_delay(1000, 2000)
                except:
                    pass
                    
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.ERROR,
                    error="Email required to connect",
                )
            
            # Add note if provided
            final_note = ""
            if note or self.note_composer:
                logger.debug("Preparing to add note to connection request...")
                final_note = note or self.note_composer.compose(profile)
                logger.debug(f"Note prepared ({len(final_note)} chars), adding to form...")
                note_added = self._add_note(final_note)
                if note_added:
                    logger.debug("Note added successfully")
                else:
                    logger.warning("Failed to add note, continuing without note...")
            
            # Send the request
            logger.debug("Clicking Send button...")
            send_clicked = self._click_send()
            
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Record the connection
            request = ConnectionRequest(
                profile_url=profile.url,
                profile_name=profile.name,
                sent_at=datetime.now(),
                status=ConnectionStatus.PENDING,
                note=final_note,
            )
            
            self.tracker.record(request)
            logger.info(f"Connection request sent to {profile.name}")
            return request
            
        except Exception as e:
            logger.error(f"Failed to send connection request: {e}")
            return ConnectionRequest(
                profile_url=profile.url,
                profile_name=profile.name,
                status=ConnectionStatus.ERROR,
                error=str(e),
            )
    
    def _click_connect_button(self) -> bool:
        """Click the Connect button, handling various UI states."""
        
        # Try clicking More button then Connect
        more_exists = self.browser.element_exists(MORE_BUTTON)
        
        if more_exists:
            logger.info("Found More button, clicking to open dropdown...")
            try:
                # Get visible More button
                more_elements = self.browser.get_all_elements(MORE_BUTTON)
                visible_more = None
                for elem in more_elements:
                    try:
                        if elem.is_visible():
                            visible_more = elem
                            break
                    except: pass
                
                if visible_more:
                    visible_more.scroll_into_view_if_needed()
                    self.browser.humanizer.random_delay(200, 500)
                    visible_more.click()
                else:
                    self.browser.click(MORE_BUTTON)
                
                self.browser.humanizer.random_delay(5000, 10000)
                
                connect_in_dropdown_exists = self.browser.element_exists(CONNECT_IN_DROPDOWN)
                
                if connect_in_dropdown_exists:
                    logger.info("Found Connect option in dropdown, clicking...")
                    connect_elements = self.browser.get_all_elements(CONNECT_IN_DROPDOWN)
                    visible_connect = None
                    for elem in connect_elements:
                        try:
                            if elem.is_visible():
                                visible_connect = elem
                                break
                        except: pass
                    
                    if visible_connect:
                        visible_connect.hover()
                        self.browser.humanizer.random_delay(200, 500)
                        visible_connect.click(force=True)
                        return True
                    else:
                        self.browser.page.click(CONNECT_IN_DROPDOWN, force=True, timeout=5000)
                        return True
            except Exception as e:
                logger.error(f"Error while trying to click Connect via dropdown: {e}")
                return False
        
        # Try direct Connect button
        connect_exists = self.browser.element_exists(CONNECT_BUTTON)
        if connect_exists:
            logger.info("Found direct Connect button, checking visibility...")
            try:
                elements = self.browser.get_all_elements(CONNECT_BUTTON)
                visible_element = None
                for elem in elements:
                    try:
                        if elem.is_visible():
                            visible_element = elem
                            break
                    except: pass
                
                if visible_element:
                    visible_element.scroll_into_view_if_needed()
                    self.browser.humanizer.random_delay(5000, 10000)
                    visible_element.click()
                    return True
                else:
                    self.browser.click(CONNECT_BUTTON)
                    return True
            except Exception as e:
                logger.error(f"Failed to click direct Connect button: {e}")
                return False
        
        return False
    
    def _add_note(self, note: str) -> bool:
        """Add a personalized note to the connection request."""
        try:
            if self.browser.element_exists(ADD_NOTE_BUTTON):
                self.browser.click(ADD_NOTE_BUTTON)
                self.browser.humanizer.random_delay(5000, 10000)
            
            if self.browser.wait_for_element(NOTE_TEXTAREA, timeout=5000):
                truncated_note = note[:300] if len(note) > 300 else note
                self.browser.type_text(NOTE_TEXTAREA, truncated_note, human_like=True)
                return True
        except Exception as e:
            logger.error(f"Could not add note: {e}")
        return False
    
    def _click_send(self) -> bool:
        """Click the Send button."""
        try:
            if self.browser.element_exists(SEND_BUTTON):
                self.browser.click(SEND_BUTTON)
                return True
        except Exception as e:
            logger.error(f"Failed to click send: {e}")
        return False
    
    def _is_already_connected(self) -> bool:
        """Check if already connected with the profile."""
        has_connect_button = self.browser.element_exists(CONNECT_BUTTON)
        has_connect_in_dropdown = False
        if self.browser.element_exists(MORE_BUTTON):
            try:
                self.browser.click(MORE_BUTTON)
                self.browser.humanizer.random_delay(5000, 10000)
                has_connect_in_dropdown = self.browser.element_exists(CONNECT_IN_DROPDOWN)
                self.browser.page.keyboard.press("Escape")
                self.browser.humanizer.random_delay(200, 500)
            except: pass
        
        return not has_connect_button and not has_connect_in_dropdown
    
    def _is_pending(self) -> bool:
        """Check if connection request is pending."""
        return self.browser.element_exists(PENDING_BUTTON)
