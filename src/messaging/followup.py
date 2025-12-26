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
    
    async def send_followup(
        self,
        profile: Profile,
        message: Optional[str] = None,
    ) -> Message:
        """
        Send a follow-up message to a connection.
        
        Args:
            profile: The profile to message.
            message: Optional message content. Uses template if not provided.
            
        Returns:
            Message with the result.
        """
        logger.info(f"Sending follow-up message to {profile.name}")
        
        # Check daily limit
        if self.tracker.get_today_count() >= self.daily_limit:
            logger.warning("Daily message limit reached")
            return Message(
                recipient_url=profile.url,
                recipient_name=profile.name,
                content="",
                error="Daily message limit reached",
            )
        
        # Check if already messaged
        if self.tracker.is_already_messaged(profile.url):
            logger.info(f"Already messaged {profile.name}")
            return Message(
                recipient_url=profile.url,
                recipient_name=profile.name,
                content="",
                error="Already messaged",
            )
        
        try:
            # Navigate to profile
            await self.browser.navigate(profile.url)
            await self.browser.humanizer.random_delay(5000, 10000)
            
            # Click Message button
            if not await self.browser.element_exists(MESSAGE_BUTTON):
                return Message(
                    recipient_url=profile.url,
                    recipient_name=profile.name,
                    content="",
                    error="Message button not found - may not be connected",
                )
            
            await self.browser.click(MESSAGE_BUTTON)
            await self.browser.humanizer.random_delay(5000, 10000)
            
            # Wait for message input
            if not await self.browser.wait_for_element(MESSAGE_INPUT, timeout=10000):
                return Message(
                    recipient_url=profile.url,
                    recipient_name=profile.name,
                    content="",
                    error="Message input not found",
                )
            
            # Compose message
            content = message or self.template_engine.render(profile)
            template_used = "" if message else self.template_engine.current_template
            
            # Type message
            await self.browser.type_text(MESSAGE_INPUT, content, human_like=True)
            await self.browser.humanizer.random_delay(2000, 5000)
            
            # Send message
            await self.browser.click(SEND_MESSAGE_BUTTON)
            await self.browser.humanizer.random_delay(5000, 10000)
            
            # Record message
            msg = Message(
                recipient_url=profile.url,
                recipient_name=profile.name,
                content=content,
                sent_at=datetime.now(),
                template_used=template_used,
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
    
    async def get_new_connections(self, limit: int = 20) -> List[Profile]:
        """
        Get newly accepted connections that haven't been messaged.
        
        Args:
            limit: Maximum number of connections to return.
            
        Returns:
            List of Profile objects.
        """
        logger.info("Fetching new connections")
        
        await self.browser.navigate(CONNECTIONS_PAGE)
        await self.browser.humanizer.random_delay(5000, 10000)
        
        # Scroll to load connections
        for _ in range(3):
            await self.browser.scroll("down", 500)
            await self.browser.humanizer.random_delay(5000, 10000)
        
        profiles = []
        
        try:
            cards = await self.browser.get_all_elements(CONNECTION_CARD)
            
            for card in cards[:limit * 2]:  # Get extra to account for filtering
                try:
                    # Get profile link
                    link = await card.query_selector(CONNECTION_LINK)
                    if not link:
                        continue
                    
                    url = await link.get_attribute("href")
                    if not url:
                        continue
                    
                    # Skip if already messaged
                    if self.tracker.is_already_messaged(url):
                        continue
                    
                    # Get name
                    name_el = await card.query_selector(CONNECTION_NAME)
                    name = ""
                    if name_el:
                        name = await name_el.text_content() or ""
                        name = name.strip()
                    
                    profiles.append(Profile(
                        url=url,
                        name=name,
                        first_name=name.split()[0] if name else "",
                    ))
                    
                    if len(profiles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to parse connection card: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
        
        logger.info(f"Found {len(profiles)} new connections to message")
        return profiles
    
    async def process_new_connections(self, limit: int = 10) -> List[Message]:
        """
        Find and message new connections.
        
        Args:
            limit: Maximum number of messages to send.
            
        Returns:
            List of Message objects for sent messages.
        """
        # Get new connections
        connections = await self.get_new_connections(limit=limit)
        
        messages = []
        for profile in connections:
            # Check daily limit
            if self.tracker.get_today_count() >= self.daily_limit:
                logger.warning("Daily message limit reached, stopping")
                break
            
            msg = await self.send_followup(profile)
            messages.append(msg)
            
            # Take break between messages
            if self.browser.humanizer.should_take_break(len(messages)):
                logger.info("Taking a break...")
                await self.browser.humanizer.take_break()
        
        return messages
