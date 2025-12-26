"""
Anti-detection mechanisms for browser automation.
"""

from typing import List
from playwright.async_api import Page
from loguru import logger


class AntiDetect:
    """
    Anti-detection mechanisms to avoid bot detection.
    """
    
    def get_launch_args(self) -> List[str]:
        """Get browser launch arguments for stealth."""
        return [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--window-size=1920,1080",
        ]
    
    async def apply_stealth(self, page: Page) -> None:
        """Apply anti-detection scripts to the page."""
        logger.info("Applying anti-detection measures")
        
        # Override navigator.webdriver
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        
        # Add chrome object
        await page.add_init_script("""
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)
        
        # Override permissions
        await page.add_init_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        # Override plugins
        await page.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: ""},
                        description: "",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ],
            });
        """)
        
        # Override languages
        await page.add_init_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        # Override WebGL
        await page.add_init_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };
        """)
        
        # Override platform
        await page.add_init_script("""
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
            });
        """)
        
        # Override hardware concurrency
        await page.add_init_script("""
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
            });
        """)
        
        logger.info("Anti-detection measures applied successfully")
    
    async def check_for_detection(self, page: Page) -> tuple[bool, str]:
        """
        Check if automation has been detected.
        
        Returns:
            Tuple of (detected: bool, detection_type: str)
        """
        detection_signals = {
            "captcha": "div[class*='captcha'], iframe[src*='captcha'], #captcha",
            "security_check": "div[class*='security-verification'], div[class*='checkpoint']",
            "rate_limit": "div[class*='rate-limit'], div[class*='too-many-requests']",
            "account_restricted": "div[class*='restricted'], div[class*='suspended']",
        }
        
        for signal_type, selector in detection_signals.items():
            try:
                element = await page.query_selector(selector)
                if element:
                    logger.warning(f"Detection signal found: {signal_type}")
                    return True, signal_type
            except Exception:
                pass
        
        return False, ""
    
    def get_random_user_agent(self) -> str:
        """Get a random realistic user agent."""
        import random
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        
        return random.choice(user_agents)
