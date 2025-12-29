
import re
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger
from ..database.db import DatabaseManager
from ..browser.browser import BrowserEngine
from ..connection.connect import ConnectionManager
from ..utils.models import Profile, ConnectionStatus


# Selectors and Constants
ACTIVITY_SECTION_SELECTOR = "section.artdeco-card"
HEADER_TEXT_REGEX = re.compile(r"Activity", re.IGNORECASE)
POSTS_BUTTON_SELECTOR = "button:has(span.artdeco-pill__text:text-is('Posts'))" # Simplified playwright selector
COMMENTS_BUTTON_SELECTOR = "button:has(span.artdeco-pill__text:text-is('Comments'))"
SUB_DESCRIPTION_SELECTOR = ".update-components-actor__sub-description" 
MINI_UPDATE_SUB_DESCRIPTION_SELECTOR = ".feed-mini-update-contextual-description__text"

class ActivityFilter:
    def __init__(self, browser: BrowserEngine, db: DatabaseManager, connection_manager: ConnectionManager):
        self.browser = browser
        self.db = db
        self.connection_manager = connection_manager

    async def execute(self, target_connections: int = 10):
        """
        Execute filtering mode: visit profiles, scrape activity, and send requests.
        Continues until target_connections is reached or no more profiles are available.
        """
        logger.info(f"Starting Filtering & Sending mode. Target Requests to Send: {target_connections}")
        
        requests_sent_session = 0
        batch_size = 10
        
        while requests_sent_session < target_connections:
            # Fetch batch of unscraped profiles
            profiles = await self.db.get_profiles_for_filtering(limit=batch_size)
            
            if not profiles:
                logger.info("No more unscraped profiles found in database.")
                break
                
            logger.info(f"Fetched batch of {len(profiles)} profiles. Sent so far: {requests_sent_session}/{target_connections}")
            
            processed_in_batch = 0
            
            for profile in profiles:
                if requests_sent_session >= target_connections:
                    logger.info("Target connection requests reached mid-batch. Stopping.")
                    break

                url = profile['linkedin_url']
                logger.info(f"Checking activity for: {url}")
                
                try:
                    # 1. Navigate
                    logger.info(f"Navigating to profile: {url}")
                    await self.browser.navigate(url)
                    logger.info("Waiting after navigation...")
                    await self.browser.humanizer.random_delay(3000, 5000)
                    
                    # 2. Find Activity Section
                    logger.info("Scrolling to find activity section...")
                    await self.browser.scroll(amount=600)
                    logger.info("Waiting after scroll...")
                    await self.browser.humanizer.random_delay(1000, 2000)
                    
                    activity_section = self.browser.page.locator(ACTIVITY_SECTION_SELECTOR).filter(
                        has=self.browser.page.locator("h2", has_text=HEADER_TEXT_REGEX)
                    )
                    
                    section_count = await activity_section.count()
                    logger.info(f"Activity section found count: {section_count}")
                    
                    if section_count == 0:
                        logger.warning(f"No Activity section found for {url}")
                        await self.db.update_network_activity(url, {
                            "raw": None, "value": None, "unit": None, "minutes": None, "status": "scraped"
                        })
                        continue
                    
                    # 3. Check / Click Buttons (Posts, Comments)
                    recency_candidates = []
                    
                    posts_btn = activity_section.locator(POSTS_BUTTON_SELECTOR)
                    comments_btn = activity_section.locator(COMMENTS_BUTTON_SELECTOR)
                    
                    has_posts = await posts_btn.count() > 0
                    has_comments = await comments_btn.count() > 0
                    logger.info(f"Activity tabs present - Posts: {has_posts}, Comments: {has_comments}")
                    
                    views_to_check = []
                    if has_posts: views_to_check.append(("Posts", posts_btn))
                    if has_comments: views_to_check.append(("Comments", comments_btn))
                    
                    if not views_to_check:
                         logger.info("No Posts/Comments pills, checking default view.")
                         recency_candidates.extend(await self._scrape_current_view_times(activity_section))
                    else:
                        for label, btn in views_to_check:
                            logger.info(f"Clicking {label} filter...")
                            try:
                                await btn.first.click()
                                logger.info(f"Waiting for {label} content to load...")
                                await self.browser.humanizer.random_delay(2000, 4000)
                                timestamps = await self._scrape_current_view_times(activity_section)
                                logger.info(f"Found timestamps in {label}: {timestamps}")
                                recency_candidates.extend(timestamps)
                            except Exception as e:
                                logger.warning(f"Failed to click {label} button: {e}")

                    # 4. Determine best recency
                    logger.info(f"All recency candidates: {recency_candidates}")
                    best_recency = { "raw": None, "value": None, "unit": None, "minutes": None, "status": "scraped" }
                    valid_candidates = [r for r in recency_candidates if r.get('minutes') is not None]
                    
                    if valid_candidates:
                        valid_candidates.sort(key=lambda x: x['minutes'])
                        best_recency = valid_candidates[0]
                        best_recency["status"] = "scraped"
                    
                    recency = best_recency
                    logger.info(f"Best recency for {url}: {recency}")

                    # 5. Update DB
                    await self.db.update_network_activity(url, {
                        "raw": recency['raw'],
                        "value": recency['value'],
                        "unit": recency['unit'],
                        "minutes": recency['minutes'],
                        "status": "scraped"
                    })

                    # 6. Send Request if eligible
                    if (recency['minutes'] is not None 
                        and recency['minutes'] <= 50000 
                        and recency['status'] == 'scraped'):
                        
                        logger.info(f"Profile {url} active ({recency.get('raw')}). Sending request...")
                        
                        p_name = profile['name'] or ""
                        profile_obj = Profile(url=url, name=p_name)
                        if profile.get('first_name'): profile_obj.first_name = profile['first_name']
                        if profile.get('last_name'): profile_obj.last_name = profile['last_name']
                        
                        try:
                            logger.info(f"Initiating connection request to {url}")
                            await self.db.update_request_status(url, 'pending')
                            result = await self.connection_manager.send_connection_request(profile_obj)
                            logger.info(f"Connection request result: {result}")
                            
                            db_status = 'failed'
                            if result.error:
                                 err_msg = str(result.error).lower()
                                 if "already sent" in err_msg or "pending" in err_msg:
                                     db_status = 'already_connected'
                                 elif "email required" in err_msg:
                                     db_status = 'skipped'
                                 else:
                                     db_status = 'failed'
                            elif result.status == ConnectionStatus.PENDING:
                                 db_status = 'sent'
                            elif result.status == ConnectionStatus.ACCEPTED:
                                 db_status = 'already_connected'
                            elif result.status == ConnectionStatus.ERROR:
                                 db_status = 'failed'
                            
                            logger.info(f"Final status for {url}: {db_status}")
                            await self.db.update_request_status(url, db_status)
                            
                            if db_status == 'sent':
                                requests_sent_session += 1
                                logger.info(f"Request sent! Total session: {requests_sent_session}")
                                logger.info("Waiting after sending request...")
                                await self.browser.humanizer.random_delay(5000, 10000)
                                
                        except Exception as e:
                            logger.error(f"Error sending request to {url}: {e}")
                            await self.db.update_request_status(url, 'failed')
                    else:
                        logger.info(f"Profile {url} not eligible for connection (minutes={recency.get('minutes')})")
                    
                    processed_in_batch += 1
                    
                except Exception as e:
                    logger.error(f"Error processing activity for {url}: {e}")
                    await self.db.update_network_activity(url, { "status": "failed" })
            
            logger.info(f"Batch completed. Processed: {processed_in_batch}")
        
        logger.info(f"Filtering & Sending completed. Sent {requests_sent_session} requests.")

    async def _scrape_current_view_times(self, activity_section) -> List[Dict[str, Any]]:
        """
        Scrape all sub-description timestamp texts from the current view of the activity section.
        """
        candidates = []
        try:
            # We specifically look for the sub-description element which contains "1w • Edited" etc.
            # Using the constant selector
            # Check both standard updates and mini updates (comments)
            elements_std = activity_section.locator(SUB_DESCRIPTION_SELECTOR)
            elements_mini = activity_section.locator(MINI_UPDATE_SUB_DESCRIPTION_SELECTOR)
            
            count_std = await elements_std.count()
            count_mini = await elements_mini.count()
            
            logger.info(f"Found {count_std} standard timestamps and {count_mini} mini timestamps in current view.")
            
            # Process standard
            for i in range(count_std):
                text = await elements_std.nth(i).inner_text()
                logger.info(f"Processing standard timestamp text: '{text}'")
                parsed = self._parse_recency_from_text(text)
                if parsed['minutes'] is not None:
                    logger.info(f"Parsed valid recency: {parsed}")
                candidates.append(parsed)

            # Process mini
            for i in range(count_mini):
                text = await elements_mini.nth(i).inner_text()
                logger.info(f"Processing mini timestamp text: '{text}'")
                parsed = self._parse_recency_from_text(text)
                if parsed['minutes'] is not None:
                    logger.info(f"Parsed valid recency: {parsed}")
                candidates.append(parsed)
                
        except Exception as e:
             logger.warning(f"Error extracting times from view: {e}")
        return candidates

    def _parse_recency_from_text(self, text: str) -> Dict[str, Any]:
        """
        Parse a text string (e.g., "7mo • Edited") to extract time.
        """
        # More robust regex: (\d+)\s*(h|d|w|mo)
        # Matches "7mo", "7 mo", "1w", etc.
        # It doesn't rely on what follows, just that we have digit+unit.
        match = re.search(r'(\d+)\s*(h|d|w|mo)', text, re.IGNORECASE)
        
        if match:
            val_str, unit = match.groups()
            logger.info(f"Regex match found: value={val_str}, unit={unit}")
            
            # Normalize unit
            unit = unit.lower()
            
            try:
                val = int(val_str)
                minutes = float('inf')
                valid = False
                
                if unit == 'h':
                    if 1 <= val <= 23:
                        minutes = val * 60
                        valid = True
                elif unit == 'd':
                    if 1 <= val <= 30: # Allow up to 30 days technically (though 'mo' usually takes over)
                        minutes = val * 24 * 60
                        valid = True
                elif unit == 'w':
                    if 1 <= val <= 4:
                        minutes = val * 7 * 24 * 60
                        valid = True
                elif unit == 'mo':
                    # Allow multi-month parsing if needed, but user constraints said "mo: 1 only" usually for filtering
                    # But for parsing we should be accurate.
                    # Constraints: "mo: 1 only" was for VALIDITY check maybe?
                    # I will accept whatever, but the *filtering* logic decides cutoff (50000 mins).
                    minutes = val * 30 * 24 * 60
                    valid = True
                
                if valid:
                     return {
                        "raw": f"{val}{unit}",
                        "value": val,
                        "unit": unit,
                        "minutes": minutes
                    }
            except ValueError:
                pass
        
        return { "raw": None, "value": None, "unit": None, "minutes": None }
