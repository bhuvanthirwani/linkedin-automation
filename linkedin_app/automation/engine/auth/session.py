"""
Session management for LinkedIn automation.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger

from ..browser.browser import BrowserEngine
from ..utils.models import Session, Cookie


class SessionManager:
    """
    Manages browser session persistence and restoration.
    """
    
    def __init__(self, browser: BrowserEngine, cookies_dir: str, email: str):
        self.browser = browser
        self.cookies_dir = Path(cookies_dir)
        self.email = email
        
        # Ensure cookies directory exists
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
    
    def save_session(self) -> bool:
        """
        Save the current browser session cookies to disk.
        
        Returns:
            True if saved successfully, False otherwise.
        """
        logger.info("Saving session cookies")
        
        try:
            # Get cookies from browser
            cookies = self.browser.get_cookies()
            
            # Create session object
            session = Session(
                email=self.email,
                cookies=[
                    Cookie(
                        name=c.get("name", ""),
                        value=c.get("value", ""),
                        domain=c.get("domain", ""),
                        path=c.get("path", "/"),
                        expires=c.get("expires"),
                        secure=c.get("secure", False),
                        http_only=c.get("httpOnly", False),
                    )
                    for c in cookies
                ],
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=7),
                valid=True,
            )
            
            # Save to file
            from dataclasses import asdict
            cookie_file = self._get_cookie_file_path()
            with open(cookie_file, "w") as f:
                json.dump(asdict(session), f, default=str, indent=2)
            
            logger.info(f"Session saved successfully ({len(cookies)} cookies)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    def restore_session(self) -> bool:
        """
        Restore a saved session from disk.
        
        Returns:
            True if restored successfully, False otherwise.
        """
        logger.info("Attempting to restore session")
        
        cookie_file = self._get_cookie_file_path()
        
        if not cookie_file.exists():
            logger.info("No saved session found")
            return False
        
        try:
            # Read session file
            with open(cookie_file, "r") as f:
                session_data = json.load(f)
            
            # Reconstruct session from dict (since it's a dataclass)
            cookies_data = session_data.get('cookies', [])
            session_data['cookies'] = [Cookie(**c) for c in cookies_data]
            
            # Handle datetime strings
            if session_data.get('created_at'):
                session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
            if session_data.get('expires_at'):
                session_data['expires_at'] = datetime.fromisoformat(session_data['expires_at'])
                
            session = Session(**session_data)
            
            # Check if session is expired
            if session.expires_at and datetime.now() > session.expires_at:
                logger.warning("Session has expired")
                return False
            
            # Navigate to LinkedIn first
            self.browser.navigate("https://www.linkedin.com")
            
            # Convert to browser cookie format
            browser_cookies = [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "secure": c.secure,
                    "httpOnly": c.http_only,
                }
                for c in session.cookies
            ]
            
            # Set cookies in browser
            self.browser.set_cookies(browser_cookies)
            
            logger.info(f"Session restored successfully ({len(browser_cookies)} cookies)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore session: {e}")
            return False
    
    def clear_session(self) -> bool:
        """
        Remove the saved session.
        
        Returns:
            True if cleared successfully, False otherwise.
        """
        cookie_file = self._get_cookie_file_path()
        
        try:
            if cookie_file.exists():
                cookie_file.unlink()
            
            self.browser.clear_cookies()
            
            logger.info("Session cleared")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return False
    
    def is_session_valid(self) -> bool:
        """Check if a valid saved session exists."""
        cookie_file = self._get_cookie_file_path()
        
        if not cookie_file.exists():
            return False
        
        try:
            with open(cookie_file, "r") as f:
                session_data = json.load(f)
            
            session = Session(**session_data)
            
            # Check expiration
            if session.expires_at and datetime.now() > session.expires_at:
                return False
            
            # Check for essential LinkedIn cookies
            essential_cookies = {"li_at", "JSESSIONID"}
            found_cookies = {c.name for c in session.cookies}
            
            return essential_cookies.issubset(found_cookies)
            
        except Exception:
            return False
    
    def get_session_info(self) -> Optional[Session]:
        """Get information about the current saved session."""
        cookie_file = self._get_cookie_file_path()
        
        if not cookie_file.exists():
            return None
        
        try:
            with open(cookie_file, "r") as f:
                session_data = json.load(f)
            return Session(**session_data)
        except Exception:
            return None
    
    def _get_cookie_file_path(self) -> Path:
        """Get the path for the session cookie file."""
        # Create a safe filename from the email
        safe_email = self._sanitize_filename(self.email)
        return self.cookies_dir / f"session_{safe_email}.json"
    
    def _sanitize_filename(self, s: str) -> str:
        """Remove or replace invalid filename characters."""
        result = []
        for c in s:
            if c.isalnum() or c in "-_":
                result.append(c)
            elif c in "@.":
                result.append("_")
        return "".join(result)
