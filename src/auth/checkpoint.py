"""
Security checkpoint detection for LinkedIn.
"""

from typing import Tuple, Optional
from dataclasses import dataclass

from loguru import logger

from ..browser.browser import BrowserEngine


# Checkpoint types
CHECKPOINT_2FA = "2fa"
CHECKPOINT_CAPTCHA = "captcha"
CHECKPOINT_PHONE_VERIFY = "phone_verification"
CHECKPOINT_EMAIL_VERIFY = "email_verification"
CHECKPOINT_SECURITY_CHECK = "security_check"
CHECKPOINT_UNKNOWN = "unknown"

# Checkpoint selectors
SELECTOR_2FA_INPUT = "input#input__phone_verification_pin, input#input__email_verification_pin"
SELECTOR_CAPTCHA = "iframe[src*='captcha'], div[class*='captcha'], #captcha"
SELECTOR_PHONE_VERIFY = "input#input__phone_verification_pin, div[class*='phone-verification']"
SELECTOR_EMAIL_VERIFY = "input#input__email_verification_pin, div[class*='email-verification']"
SELECTOR_SECURITY_CHECK = "div[class*='security-verification'], div[class*='checkpoint']"
SELECTOR_CHALLENGE = "div[class*='challenge'], main[id*='challenge']"


@dataclass
class CheckpointInfo:
    """Information about a detected checkpoint."""
    checkpoint_type: str
    message: str
    url: str


class CheckpointDetector:
    """
    Detects security checkpoints during LinkedIn automation.
    """
    
    def __init__(self, browser: BrowserEngine):
        self.browser = browser
    
    async def detect(self) -> Tuple[bool, str]:
        """
        Check for any security checkpoints.
        
        Returns:
            Tuple of (detected: bool, checkpoint_type: str)
        """
        logger.debug("Checking for security checkpoints")
        
        # Check for 2FA
        if await self.browser.element_exists(SELECTOR_2FA_INPUT):
            logger.warning("2FA checkpoint detected")
            return True, CHECKPOINT_2FA
        
        # Check for CAPTCHA
        if await self.browser.element_exists(SELECTOR_CAPTCHA):
            logger.warning("CAPTCHA checkpoint detected")
            return True, CHECKPOINT_CAPTCHA
        
        # Check for phone verification
        if await self.browser.element_exists(SELECTOR_PHONE_VERIFY):
            logger.warning("Phone verification checkpoint detected")
            return True, CHECKPOINT_PHONE_VERIFY
        
        # Check for email verification
        if await self.browser.element_exists(SELECTOR_EMAIL_VERIFY):
            logger.warning("Email verification checkpoint detected")
            return True, CHECKPOINT_EMAIL_VERIFY
        
        # Check for general security check
        if await self.browser.element_exists(SELECTOR_SECURITY_CHECK):
            logger.warning("Security check checkpoint detected")
            return True, CHECKPOINT_SECURITY_CHECK
        
        if await self.browser.element_exists(SELECTOR_CHALLENGE):
            logger.warning("Challenge checkpoint detected")
            return True, CHECKPOINT_SECURITY_CHECK
        
        # Check URL for checkpoint indicators
        current_url = await self.browser.get_current_url()
        if self._is_checkpoint_url(current_url):
            logger.warning(f"Checkpoint detected in URL: {current_url}")
            return True, CHECKPOINT_UNKNOWN
        
        return False, ""
    
    async def is_2fa(self) -> bool:
        """Check specifically for 2FA."""
        return await self.browser.element_exists(SELECTOR_2FA_INPUT)
    
    async def is_captcha(self) -> bool:
        """Check specifically for CAPTCHA."""
        return await self.browser.element_exists(SELECTOR_CAPTCHA)
    
    async def get_checkpoint_message(self) -> str:
        """Try to get any error/instruction message from the checkpoint."""
        message_selectors = [
            "div[class*='error'] p",
            "div[class*='message'] p",
            "div[class*='instruction'] p",
            "p[class*='error']",
            "span[class*='error-message']",
        ]
        
        for selector in message_selectors:
            text = await self.browser.get_text(selector)
            if text:
                return text.strip()
        
        return ""
    
    async def get_checkpoint_info(self) -> Optional[CheckpointInfo]:
        """Get detailed information about the current checkpoint."""
        detected, checkpoint_type = await self.detect()
        
        if not detected:
            return None
        
        url = await self.browser.get_current_url()
        message = await self.get_checkpoint_message()
        
        return CheckpointInfo(
            checkpoint_type=checkpoint_type,
            message=message,
            url=url,
        )
    
    def _is_checkpoint_url(self, url: str) -> bool:
        """Check if the URL indicates a checkpoint."""
        checkpoint_patterns = [
            "/checkpoint/",
            "/challenge/",
            "/security-verification",
            "/add-phone",
            "/add-email",
            "/uas/",
        ]
        
        return any(pattern in url for pattern in checkpoint_patterns)
