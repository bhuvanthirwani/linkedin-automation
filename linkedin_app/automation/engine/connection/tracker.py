"""
Connection request tracking and daily limits.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict

from loguru import logger

from ..utils.models import ConnectionRequest, ConnectionStatus, DailyStats


from ..database.db import DatabaseManager


from ..database.db import DatabaseManager


class ConnectionTracker:
    """
    Tracks sent connection requests and enforces daily limits using DatabaseManager.
    """
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
    
    def record(self, request: ConnectionRequest) -> None:
        """Record a connection request in the database."""
        self.db.record_connection_history(
            profile_url=request.profile_url,
            profile_name=request.profile_name,
            status=request.status.value,
            note=request.note,
            error=request.error
        )
        self.db.record_daily_stat("connections_sent")
        if request.status == ConnectionStatus.ERROR:
            self.db.record_daily_stat("errors")
        
        logger.debug(f"Recorded connection request in database: {request.profile_url}")
    
    def is_already_sent(self, profile_url: str) -> bool:
        """Check if a connection request was already sent to this profile."""
        return self.db.is_connection_sent(profile_url)
    
    def get_today_count(self) -> int:
        """Get the number of connections sent today."""
        return self.db.get_daily_stat("connections_sent")
    
    def update_status(self, profile_url: str, status: ConnectionStatus) -> None:
        """Update the status of a connection request in the database."""
        self.db.record_connection_status(profile_url, status.value)
        if status == ConnectionStatus.ACCEPTED:
            self.db.record_daily_stat("connections_accepted")
        
        logger.info(f"Updated connection status in database: {profile_url} -> {status}")
    
    def get_stats(self, date_str: str = None) -> Optional[DailyStats]:
        """Get stats for a specific date or today. (Note: Returns None if not directly queried from stats table)"""
        # In a fully DB-only mode, we could query the DailyStats table if needed.
        return None
