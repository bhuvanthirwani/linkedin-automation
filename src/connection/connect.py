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
    
    async def send_connection_request(
        self,
        profile: Profile,
        note: Optional[str] = None,
    ) -> ConnectionRequest:
        """
        Send a connection request to a profile.
        
        Args:
            profile: The profile to connect with.
            note: Optional personalized note (max 300 chars).
            
        Returns:
            ConnectionRequest with the result.
        """
        logger.info(f"Sending connection request to {profile.name}")
        
        # Check daily limit
        # if self.tracker.get_today_count() >= self.daily_limit:
        #     logger.warning("Daily connection limit reached")
        #     return ConnectionRequest(
        #         profile_url=profile.url,
        #         profile_name=profile.name,
        #         status=ConnectionStatus.ERROR,
        #         error="Daily connection limit reached",
        #     )
        
        # Check if already sent
        if self.tracker.is_already_sent(profile.url):
            logger.info(f"Connection already sent to {profile.name}")
            return ConnectionRequest(
                profile_url=profile.url,
                profile_name=profile.name,
                status=ConnectionStatus.PENDING,
                error="Connection already sent",
            )
        
        try:
            # Navigate to profile
            logger.info(f"Navigating to profile: {profile.url}")
            await self.browser.navigate(profile.url)
            logger.debug(f"Navigation complete, waiting for page to load...")
            await self.browser.humanizer.random_delay(5000, 10000)
            logger.debug("Page load delay complete")
            
            # Check mapping status if we're already pending or connected
            if await self._is_pending():
                logger.info(f"Connection pending with {profile.name}")
                # Log to database for future exclusion
                if self.database_manager:
                    await self.database_manager.record_connection_request(profile.url, "PENDING")
                
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.PENDING,
                )
            
            logger.debug("Checking if already connected...")
            # Check if already connected (no Connect button and no Connect in dropdown)
            if await self._is_already_connected():
                logger.info(f"Already connected with {profile.name}")
                # Log to database for future exclusion
                if self.database_manager:
                    await self.database_manager.record_connection_request(profile.url, "ACCEPTED")
                
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.ACCEPTED,
                )
            
            logger.debug("Not pending and not connected, proceeding to send connection request...")
            
            # Click Connect button
            logger.debug("Attempting to click Connect button...")
            clicked = await self._click_connect_button()
            if not clicked:
                logger.error("Failed to find or click Connect button")
                return ConnectionRequest(
                    profile_url=profile.url,
                    profile_name=profile.name,
                    status=ConnectionStatus.ERROR,
                    error="Connect button not found",
                )
            
            logger.info("Connect button clicked successfully, waiting for modal...")
            await self.browser.humanizer.random_delay(5000, 10000)
            
            # Check if email is required
            logger.debug("Checking if email is required to connect...")
            email_input_exists = await self.browser.element_exists(EMAIL_INPUT)
            # Use text search for the specific message mentioned by user
            email_text_exists = await self.browser.page.locator(f"text='enter their email'").count() > 0 or \
                                await self.browser.page.locator(f"text='email to connect'").count() > 0
            
            if email_input_exists or email_text_exists:
                logger.warning(f"Email required to connect with {profile.name}. Skipping and deleting.")
                # Record as BLOCKED in database
                if self.database_manager:
                    await self.database_manager.record_connection_request(profile.url, "BLOCKED")
                    # Delete from raw_linkedin_ingest as requested
                    await self.database_manager.delete_from_raw_ingest(profile.url)
                
                # Close modal if it's open (usually by clicking Escape or the close button)
                try:
                    await self.browser.page.keyboard.press("Escape")
                    await self.browser.humanizer.random_delay(1000, 2000)
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
                note_added = await self._add_note(final_note)
                if note_added:
                    logger.debug("Note added successfully")
                else:
                    logger.warning("Failed to add note, continuing without note...")
            
            # Send the request
            logger.debug("Clicking Send button...")
            send_clicked = await self._click_send()
            if send_clicked:
                logger.debug("Send button clicked successfully")
            else:
                logger.warning("Send button may not have been clicked")
            
            await self.browser.humanizer.random_delay(5000, 10000)
            
            # Record the connection
            request = ConnectionRequest(
                profile_url=profile.url,
                profile_name=profile.name,
                sent_at=datetime.now(),
                status=ConnectionStatus.PENDING,
                note=final_note,
            )
            
            self.tracker.record(request)
            
            # Log to database for future exclusion
            if self.database_manager:
                await self.database_manager.record_connection_request(profile.url, "SENT", sent_at=request.sent_at)
            
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
    
    async def _click_connect_button(self) -> bool:
        """Click the Connect button, handling various UI states."""
        
        # Try clicking More button then Connect
        logger.debug(f"Checking for More button: {MORE_BUTTON}")
        more_exists = await self.browser.element_exists(MORE_BUTTON)
        logger.debug(f"More button exists: {more_exists}")
        
        if more_exists:
            logger.info("Found More button, clicking to open dropdown...")
            try:
                # Get visible More button
                more_elements = await self.browser.get_all_elements(MORE_BUTTON)
                logger.debug(f"Found {len(more_elements)} More button elements")
                
                visible_more = None
                for i, elem in enumerate(more_elements):
                    try:
                        if await elem.is_visible():
                            visible_more = elem
                            logger.info(f"Found visible More button at index {i}")
                            break
                    except Exception:
                        pass
                
                if visible_more:
                    await visible_more.scroll_into_view_if_needed()
                    await self.browser.humanizer.random_delay(200, 500)
                    await visible_more.click()
                else:
                    await self.browser.click(MORE_BUTTON)
                
                logger.debug("More button clicked, waiting for dropdown to open...")
                await self.browser.humanizer.random_delay(5000, 10000)
                
                # Wait for Connect option in dropdown to be visible
                logger.debug(f"Looking for Connect in dropdown with selector: {CONNECT_IN_DROPDOWN}")
                try:
                    await self.browser.wait_for_element(CONNECT_IN_DROPDOWN, timeout=3000)
                    logger.debug("Connect option found in dropdown")
                except Exception as e:
                    logger.warning(f"Timeout waiting for Connect in dropdown: {e}, checking anyway...")
                    await self.browser.humanizer.random_delay(300, 500)
                
                connect_in_dropdown_exists = await self.browser.element_exists(CONNECT_IN_DROPDOWN)
                logger.debug(f"Connect in dropdown exists: {connect_in_dropdown_exists}")
                
                if connect_in_dropdown_exists:
                    logger.info("Found Connect option in dropdown, clicking...")
                    # Get visible Connect in dropdown
                    connect_elements = await self.browser.get_all_elements(CONNECT_IN_DROPDOWN)
                    logger.debug(f"Found {len(connect_elements)} Connect in dropdown elements")
                    
                    visible_connect = None
                    for i, elem in enumerate(connect_elements):
                        try:
                            if await elem.is_visible():
                                visible_connect = elem
                                logger.info(f"Found visible Connect in dropdown at index {i}")
                                break
                        except Exception:
                            pass
                    
                    if visible_connect:
                        logger.debug("Visible Connect option found, clicking...")
                        await visible_connect.hover()
                        await self.browser.humanizer.random_delay(200, 500)
                        # Use force click to bypass any interception by the dropdown overlay
                        await visible_connect.click(force=True)
                        logger.info("Connect in dropdown clicked successfully (visible element)")
                        return True
                    else:
                        # Fallback: try clicking the first matching element directly via page
                        logger.debug("No visible element found, trying direct selector click...")
                        await self.browser.page.click(CONNECT_IN_DROPDOWN, force=True, timeout=5000)
                        logger.info("Connect in dropdown clicked (selector fallback)")
                        return True
                else:
                    logger.warning("Connect option not found in dropdown after opening")
            except Exception as e:
                logger.error(f"Error while trying to click Connect via dropdown: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return False
        
        logger.debug(f"Looking for Connect button with selector: {CONNECT_BUTTON}")
        
        # Try direct Connect button first
        connect_exists = await self.browser.element_exists(CONNECT_BUTTON)
        logger.debug(f"Direct Connect button exists: {connect_exists}")
        
        if connect_exists:
            logger.info("Found direct Connect button, checking visibility...")
            try:
                # Get all matching elements to find a visible one
                elements = await self.browser.get_all_elements(CONNECT_BUTTON)
                logger.debug(f"Found {len(elements)} Connect button elements")
                
                # Try to find a visible element
                visible_element = None
                for i, elem in enumerate(elements):
                    try:
                        is_visible = await elem.is_visible()
                        logger.debug(f"Connect button element {i} is visible: {is_visible}")
                        if is_visible:
                            visible_element = elem
                            logger.info(f"Found visible Connect button at index {i}")
                            break
                    except Exception as e:
                        logger.debug(f"Error checking visibility of element {i}: {e}")
                
                if visible_element:
                    # Scroll to element if needed
                    try:
                        await visible_element.scroll_into_view_if_needed()
                        await self.browser.humanizer.random_delay(5000, 10000)
                    except Exception as e:
                        logger.debug(f"Error scrolling to element: {e}")
                    
                    # Click the visible element directly
                    await visible_element.click()
                    logger.info("Direct Connect button clicked successfully")
                    return True
                else:
                    logger.warning("No visible Connect button found, trying to click first element anyway...")
                    # Fallback: try clicking the first element
                    await self.browser.click(CONNECT_BUTTON)
                    logger.info("Connect button clicked (fallback)")
                    return True
            except Exception as e:
                logger.error(f"Failed to click direct Connect button: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return False
        
        logger.warning("Connect button not found on profile (neither direct nor in dropdown)")
        return False
    
    async def _add_note(self, note: str) -> bool:
        """Add a personalized note to the connection request."""
        try:
            logger.debug(f"Attempting to add note ({len(note)} chars)...")
            
            # Check if Add Note button exists
            add_note_exists = await self.browser.element_exists(ADD_NOTE_BUTTON)
            logger.debug(f"Add Note button exists: {add_note_exists}")
            
            if add_note_exists:
                logger.debug("Clicking Add Note button...")
                await self.browser.click(ADD_NOTE_BUTTON)
                await self.browser.humanizer.random_delay(5000, 10000)
                logger.debug("Add Note button clicked, waiting for textarea...")
            
            # Wait for textarea
            logger.debug(f"Waiting for note textarea with selector: {NOTE_TEXTAREA}")
            textarea_ready = await self.browser.wait_for_element(NOTE_TEXTAREA, timeout=5000)
            logger.debug(f"Textarea ready: {textarea_ready}")
            
            if textarea_ready:
                # Truncate note to 300 chars
                truncated_note = note[:300] if len(note) > 300 else note
                if len(note) > 300:
                    logger.debug(f"Note truncated from {len(note)} to {len(truncated_note)} chars")
                
                logger.debug("Typing note into textarea...")
                await self.browser.type_text(NOTE_TEXTAREA, truncated_note, human_like=True)
                logger.debug("Note typed successfully")
                return True
            else:
                logger.warning("Textarea not found or not ready")
            
        except Exception as e:
            logger.error(f"Could not add note: {e}")
        
        return False
    
    async def _click_send(self) -> bool:
        """Click the Send button."""
        try:
            logger.debug(f"Looking for Send button with selector: {SEND_BUTTON}")
            send_exists = await self.browser.element_exists(SEND_BUTTON)
            logger.debug(f"Send button exists: {send_exists}")
            
            if send_exists:
                logger.info("Found Send button, clicking...")
                await self.browser.click(SEND_BUTTON)
                logger.debug("Send button clicked successfully")
                return True
            else:
                logger.warning("Send button not found")
        except Exception as e:
            logger.error(f"Failed to click send: {e}")
        
        return False
    
    async def _is_already_connected(self) -> bool:
        """
        Check if already connected with the profile.
        
        Returns True if:
        - There is NO Connect button visible
        - There is NO Connect option in the dropdown menu
        
        This means the user is already connected (or connection was accepted).
        """
        logger.debug("Checking if already connected...")
        
        # Check if Connect button exists
        logger.debug(f"Checking for Connect button: {CONNECT_BUTTON}")
        has_connect_button = await self.browser.element_exists(CONNECT_BUTTON)
        logger.debug(f"Connect button exists: {has_connect_button}")
        
        # Check if Connect exists in dropdown
        has_connect_in_dropdown = False
        more_exists = await self.browser.element_exists(MORE_BUTTON)
        logger.debug(f"More button exists: {more_exists}")
        
        if more_exists:
            logger.debug("Opening More dropdown to check for Connect option...")
            try:
                # Click More button to open dropdown
                await self.browser.click(MORE_BUTTON)
                await self.browser.humanizer.random_delay(5000, 10000)
                logger.debug("More button clicked, waiting for dropdown...")
                
                # Wait for Connect option in dropdown to be visible (or check if it doesn't exist)
                try:
                    # Wait a bit for dropdown to open, then check
                    await self.browser.humanizer.random_delay(300, 500)
                    # Check if Connect option exists in dropdown
                    logger.debug(f"Checking for Connect in dropdown: {CONNECT_IN_DROPDOWN}")
                    has_connect_in_dropdown = await self.browser.element_exists(CONNECT_IN_DROPDOWN)
                    logger.debug(f"Connect in dropdown exists: {has_connect_in_dropdown}")
                except Exception as e:
                    logger.warning(f"Error checking for Connect in dropdown: {e}")
                    # If check fails, assume it doesn't exist
                    has_connect_in_dropdown = False
                
                # Close dropdown by pressing Escape
                try:
                    logger.debug("Closing dropdown...")
                    await self.browser.page.keyboard.press("Escape")
                    await self.browser.humanizer.random_delay(200, 500)
                except Exception as e:
                    logger.debug(f"Error closing dropdown: {e}")
            except Exception as e:
                logger.error(f"Error while checking dropdown: {e}")
        
        # Already connected if neither Connect button nor Connect in dropdown exists
        is_connected = not has_connect_button and not has_connect_in_dropdown
        logger.debug(f"Already connected check result: {is_connected} (has_connect_button={has_connect_button}, has_connect_in_dropdown={has_connect_in_dropdown})")
        return is_connected
    
    async def _is_pending(self) -> bool:
        """Check if connection request is pending."""
        logger.debug(f"Checking if connection is pending with selector: {PENDING_BUTTON}")
        is_pending = await self.browser.element_exists(PENDING_BUTTON)
        logger.debug(f"Pending button exists: {is_pending}")
        return is_pending
