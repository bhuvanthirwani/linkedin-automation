"""
LinkedIn login functionality.
"""

from typing import Optional
from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.config import LinkedInConfig
from .session import SessionManager
from .checkpoint import CheckpointDetector


# LinkedIn login selectors
LOGIN_PAGE_URL = "https://www.linkedin.com/login"
USERNAME_SELECTOR = "#username"
PASSWORD_SELECTOR = "#password"
LOGIN_BUTTON_SELECTOR = "button[type='submit']"
FEED_PAGE_INDICATOR = "div.feed-identity-module"
ERROR_MESSAGE_SELECTOR = "#error-for-username, #error-for-password, div.form__label--error"


class Authenticator:
    """
    Handles LinkedIn authentication.
    """
    
    def __init__(
        self,
        browser: BrowserEngine,
        config: LinkedInConfig,
        session_manager: Optional[SessionManager] = None,
    ):
        self.browser = browser
        self.config = config
        self.session_manager = session_manager
        self.checkpoint_detector = CheckpointDetector(browser)
    
    def login(self) -> bool:
        """
        Perform the LinkedIn login process.
        
        Returns:
            True if login successful, False otherwise.
        """
        logger.info("Starting login process")
        
        # Try to restore session from cookies first
        if self.session_manager:
            if self.session_manager.restore_session():
                # Verify session is still valid
                if self.is_logged_in():
                    logger.info("Session restored from cookies")
                    return True
        
        # Navigate to login page
        self.browser.navigate(LOGIN_PAGE_URL)
        
        # Check if already logged in
        if self.is_logged_in():
            logger.info("Already logged in")
            return True
        
        # Check for security checkpoints before login
        detected, checkpoint_type = self.checkpoint_detector.detect()
        if detected:
            logger.error(f"Security checkpoint detected before login: {checkpoint_type}")
            return False
        
        # Enter username with human-like typing
        logger.debug("Entering username")
        self.browser.type_text(USERNAME_SELECTOR, self.config.email, human_like=True)
        
        # Random delay between fields
        self.browser.humanizer.random_delay(5000, 10000)
        
        # Enter password with human-like typing
        logger.debug("Entering password")
        self.browser.type_text(PASSWORD_SELECTOR, self.config.password, human_like=True)
        
        # Random delay before clicking login
        self.browser.humanizer.random_delay(300, 700)
        
        # Click login button
        logger.debug("Clicking login button")
        self.browser.click(LOGIN_BUTTON_SELECTOR)
        
        # Wait for page to load
        self.browser.humanizer.random_delay(5000, 10000)
        
        # Check for login errors
        if self._has_login_error():
            logger.error("Login failed: invalid credentials or account issue")
            return False
        
        # Check for security checkpoints after login attempt
        detected, checkpoint_type = self.checkpoint_detector.detect()
        if detected:
            logger.error(f"Security checkpoint detected after login: {checkpoint_type}")
            logger.info("Manual intervention required")
            return False
        
        # Verify successful login
        if not self.is_logged_in():
            logger.error("Login verification failed: feed page not loaded")
            return False
        
        # Save session cookies
        if self.session_manager:
            self.session_manager.save_session()
        
        logger.info("Login successful")
        return True
    
    def is_logged_in(self) -> bool:
        """Check if the user is currently logged in."""
        current_url = self.browser.get_current_url()
        
        # Check if we're on a logged-in page
        logged_in_paths = ["/feed", "/mynetwork", "/jobs", "/messaging", "/in/"]
        for path in logged_in_paths:
            if path in current_url:
                return True
        
        # Try to navigate to feed and check
        try:
            self.browser.navigate("https://www.linkedin.com/feed/")
            self.browser.humanizer.random_delay(5000, 10000)
            
            # Check if feed elements are present
            if self.browser.element_exists(FEED_PAGE_INDICATOR):
                return True
            if self.browser.element_exists("div.feed-shared-update-v2"):
                return True
        except Exception:
            pass
        
        return False
    
    def _has_login_error(self) -> bool:
        """Check if there's a login error message."""
        return self.browser.element_exists(ERROR_MESSAGE_SELECTOR)
    
    def logout(self) -> bool:
        """Log out from LinkedIn."""
        logger.info("Logging out")
        
        try:
            self.browser.navigate("https://www.linkedin.com/m/logout/")
            
            # Clear session
            if self.session_manager:
                self.session_manager.clear_session()
            
            logger.info("Logout successful")
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    def wait_for_manual_login(self, timeout_seconds: int = 300) -> bool:
        """
        Wait for the user to manually complete login (e.g., for 2FA).
        
        Args:
            timeout_seconds: Maximum time to wait in seconds.
            
        Returns:
            True if login completed, False if timeout.
        """
        import time
        
        logger.info(f"Waiting for manual login completion (timeout: {timeout_seconds}s)")
        
        start_time = time.time()
        check_interval = 5  # seconds
        
        while time.time() - start_time < timeout_seconds:
            if self.is_logged_in():
                logger.info("Manual login detected as complete")
                
                # Save session
                if self.session_manager:
                    self.session_manager.save_session()
                
                return True
            
            time.sleep(check_interval)
        
        logger.error(f"Timeout waiting for manual login after {timeout_seconds} seconds")
        return False
