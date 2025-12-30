"""
Message tracking and history.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict

from loguru import logger

from ..utils.models import Message, DailyStats


from ..database.db import DatabaseManager


from ..database.db import DatabaseManager


class MessageTracker:
    """
    Tracks sent messages and prevents duplicates using DatabaseManager.
    """
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
    
    def record(self, message: Message) -> None:
        """Record a sent message in the database."""
        self.db.record_message_history(
            recipient_url=message.recipient_url,
            recipient_name=message.recipient_name,
            content=message.content,
            template=message.template_used,
            error=message.error
        )
        self.db.record_daily_stat("messages_sent")
        if message.error:
            self.db.record_daily_stat("errors")
        
        logger.debug(f"Recorded message in database to: {message.recipient_url}")
    
    def is_already_messaged(self, profile_url: str) -> bool:
        """Check if we've already messaged this profile in the database."""
        return self.db.is_already_messaged(profile_url)
    
    def get_today_count(self) -> int:
        """Get the number of messages sent today from the database."""
        return self.db.get_daily_stat("messages_sent")
    
    def get_stats(self, date_str: str = None) -> Optional[DailyStats]:
        """Get stats for a specific date or today. (Note: Returns None if not directly queried from stats table)"""
        return None
