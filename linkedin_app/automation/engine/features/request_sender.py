
from typing import Optional
from loguru import logger
from ..database.db import DatabaseManager
from ..browser.browser import BrowserEngine
from ..connection.connect import ConnectionManager
from ..utils.models import Profile, ConnectionStatus

class RequestSender:
    def __init__(self, browser: BrowserEngine, db: DatabaseManager, connection_manager: ConnectionManager):
        self.browser = browser
        self.db = db
        self.connection_manager = connection_manager

    def execute(self, limit: int = 10):
        """
        Execute Send_Requests mode: send connection requests to profiles with recent activity.
        """
        logger.info(f"Starting Send_Requests mode. Limit={limit}")
        
        profiles_data = self.db.get_profiles_for_sending(limit)
        
        if not profiles_data:
            logger.info("No profiles found matching criteria (Active < 1 week, Not Sent).")
            return
            
        logger.info(f"Found {len(profiles_data)} candidates for connection requests.")
        
        sent_count = 0
        for p_data in profiles_data:
            url = p_data['linkedin_url']
            name = p_data['name']
            
            profile = Profile(url=url, name=name)
            if p_data.get('first_name'):
                profile.first_name = p_data['first_name']
            if p_data.get('last_name'):
                profile.last_name = p_data['last_name']
                
            logger.info(f"Processing candidate: {name} (Activity: {p_data.get('recent_activity_minutes')}m)")
            
            try:
                self.db.update_request_status(url, 'pending')
                result = self.connection_manager.send_connection_request(profile)
                
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
                
                self.db.update_request_status(url, db_status)
                
                if db_status == 'sent':
                    sent_count += 1
                    self.browser.humanizer.random_delay(10000, 20000)
                
            except Exception as e:
                logger.error(f"Error sending request to {url}: {e}")
                self.db.update_request_status(url, 'failed')

        logger.info(f"Send_Requests completed. Sent: {sent_count}")
