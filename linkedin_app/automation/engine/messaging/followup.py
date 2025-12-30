"""
Follow-up messaging for accepted connections.
"""

from typing import List, Optional
from datetime import datetime

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Profile, Message
from .template import TemplateEngine
from .tracker import MessageTracker


# Selectors for messaging
MESSAGE_BUTTON = "button[aria-label*='Message']"
MESSAGE_OVERLAY = "div.msg-overlay-conversation-bubble"
MESSAGE_INPUT = "div.msg-form__contenteditable, div[role='textbox']"
SEND_MESSAGE_BUTTON = "button.msg-form__send-button, button[type='submit']"
CONNECTIONS_PAGE = "https://www.linkedin.com/mynetwork/invite-connect/connections/"
CONNECTION_CARD = "li.mn-connection-card"
CONNECTION_LINK = "a.mn-connection-card__link"
CONNECTION_NAME = "span.mn-connection-card__name"


class FollowUpMessenger:
    """
    Sends follow-up messages to newly accepted connections.
    """
    
    def __init__(
        self,
        browser: BrowserEngine,
        tracker: MessageTracker,
        template_engine: Optional[TemplateEngine] = None,
        daily_limit: int = 50,
    ):
        self.browser = browser
        self.tracker = tracker
        self.template_engine = template_engine or TemplateEngine()
        self.daily_limit = daily_limit
    
    def send_followup(
        self,
        profile: Profile,
        message: Optional[str] = None,
    ) -> Message:
        """
        Send a follow-up message to a connection.
        """
        logger.info(f"Sending follow-up message to {profile.name}")
        
        # if self.tracker.get_today_count() >= self.daily_limit:
        #     logger.warning("Daily message limit reached")
        #     return Message(
        #         recipient_url=profile.url,
        #         recipient_name=profile.name,
        #         content="",
        #         error="Daily message limit reached",
        #     )
        
        try:
            # Navigate to profile
            self.browser.navigate(profile.url)
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Click Message button
            if not self.browser.element_exists(MESSAGE_BUTTON):
                return Message(
                    recipient_url=profile.url,
                    recipient_name=profile.name,
                    content="",
                    error="Message button not found",
                )
            
            self.browser.click(MESSAGE_BUTTON)
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Wait for message input
            if not self.browser.wait_for_element(MESSAGE_INPUT, timeout=10000):
                return Message(
                    recipient_url=profile.url,
                    recipient_name=profile.name,
                    content="",
                    error="Message input not found",
                )
            
            # Compose message
            content = message or self.template_engine.render(profile)
            
            # Type message
            self.browser.type_text(MESSAGE_INPUT, content, human_like=True)
            self.browser.humanizer.random_delay(2000, 5000)
            
            # Send message
            self.browser.click(SEND_MESSAGE_BUTTON)
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Record message
            msg = Message(
                recipient_url=profile.url,
                recipient_name=profile.name,
                content=content,
                sent_at=datetime.now(),
            )
            self.tracker.record(msg)
            
            logger.info(f"Follow-up message sent to {profile.name}")
            return msg
            
        except Exception as e:
            logger.error(f"Failed to send follow-up message: {e}")
            return Message(
                recipient_url=profile.url,
                recipient_name=profile.name,
                content="",
                error=str(e),
            )
    
    def get_new_connections(self, limit: int = 20) -> List[Profile]:
        """
        Get newly accepted connections that haven't been messaged.
        """
        logger.info("Fetching new connections")
        
        self.browser.navigate(CONNECTIONS_PAGE)
        self.browser.humanizer.random_delay(5000, 10000)
        
        # Scroll to load connections
        for _ in range(3):
            self.browser.scroll("down", 500)
            self.browser.humanizer.random_delay(5000, 10000)
        
        profiles = []
        try:
            cards = self.browser.get_all_elements(CONNECTION_CARD)
            for card in cards[:limit * 2]:
                try:
                    link = card.query_selector(CONNECTION_LINK)
                    if not link: continue
                    url = link.get_attribute("href")
                    if not url: continue
                    if self.tracker.is_already_messaged(url): continue
                    
                    name_el = card.query_selector(CONNECTION_NAME)
                    name = name_el.text_content().strip() if name_el else ""
                    
                    profiles.append(Profile(
                        url=url,
                        name=name,
                        first_name=name.split()[0] if name else "",
                    ))
                    if len(profiles) >= limit: break
                except: continue
        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
        
        return profiles
    
    def process_new_connections(self, limit: int = 10) -> List[Message]:
        """
        Find and message new connections.
        """
        connections = self.get_new_connections(limit=limit)
        messages = []
        for profile in connections:
            # if self.tracker.get_today_count() >= self.daily_limit:
            #     break
            msg = self.send_followup(profile)
            messages.append(msg)
            if self.browser.humanizer.should_take_break(len(messages)):
                self.browser.humanizer.take_break()
        return messages
