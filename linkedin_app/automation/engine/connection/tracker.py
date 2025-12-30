"""
Connection request tracking and daily limits.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict

from loguru import logger

from ..utils.models import ConnectionRequest, ConnectionStatus, DailyStats


class ConnectionTracker:
    """
    Tracks sent connection requests and enforces daily limits.
    """
    
    def __init__(self, tracking_dir: str):
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        
        self._connections_file = self.tracking_dir / "connections.json"
        self._stats_file = self.tracking_dir / "daily_stats.json"
        
        self._connections: List[ConnectionRequest] = []
        self._daily_stats: Dict[str, DailyStats] = {}
        
        self._load()
    
    def record(self, request: ConnectionRequest) -> None:
        """Record a connection request."""
        self._connections.append(request)
        
        # Update daily stats
        today = date.today().isoformat()
        if today not in self._daily_stats:
            self._daily_stats[today] = DailyStats(date=today)
        
        self._daily_stats[today].connections_sent += 1
        
        if request.status == ConnectionStatus.ERROR:
            self._daily_stats[today].errors += 1
        
        self._save()
        
        logger.debug(f"Recorded connection request: {request.profile_url}")
    
    def is_already_sent(self, profile_url: str) -> bool:
        """Check if a connection request was already sent to this profile."""
        for conn in self._connections:
            if conn.profile_url == profile_url:
                return True
        return False
    
    def get_today_count(self) -> int:
        """Get the number of connections sent today."""
        today = date.today().isoformat()
        if today in self._daily_stats:
            return self._daily_stats[today].connections_sent
        return 0
    
    def get_pending_connections(self) -> List[ConnectionRequest]:
        """Get all pending connection requests."""
        return [c for c in self._connections if c.status == ConnectionStatus.PENDING]
    
    def get_accepted_connections(self) -> List[ConnectionRequest]:
        """Get all accepted connection requests."""
        return [c for c in self._connections if c.status == ConnectionStatus.ACCEPTED]
    
    def update_status(self, profile_url: str, status: ConnectionStatus) -> None:
        """Update the status of a connection request."""
        for conn in self._connections:
            if conn.profile_url == profile_url:
                conn.status = status
                self._save()
                
                if status == ConnectionStatus.ACCEPTED:
                    today = date.today().isoformat()
                    if today in self._daily_stats:
                        self._daily_stats[today].connections_accepted += 1
                    self._save()
                
                logger.info(f"Updated connection status: {profile_url} -> {status}")
                return
    
    def get_stats(self, date_str: str = None) -> Optional[DailyStats]:
        """Get stats for a specific date or today."""
        date_str = date_str or date.today().isoformat()
        return self._daily_stats.get(date_str)
    
    def get_all_stats(self) -> List[DailyStats]:
        """Get all daily stats."""
        return list(self._daily_stats.values())
    
    def _load(self) -> None:
        """Load data from files."""
        # Load connections
        if self._connections_file.exists():
            try:
                with open(self._connections_file, "r") as f:
                    data = json.load(f)
                    self._connections = [ConnectionRequest(**c) for c in data]
            except Exception as e:
                logger.warning(f"Failed to load connections: {e}")
                self._connections = []
        
        # Load stats
        if self._stats_file.exists():
            try:
                with open(self._stats_file, "r") as f:
                    data = json.load(f)
                    self._daily_stats = {k: DailyStats(**v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load stats: {e}")
                self._daily_stats = {}
    
    def _save(self) -> None:
        """Save data to files."""
        # Save connections
        try:
            with open(self._connections_file, "w") as f:
                data = [c.model_dump() for c in self._connections]
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save connections: {e}")
        
        # Save stats
        try:
            with open(self._stats_file, "w") as f:
                data = {k: v.model_dump() for k, v in self._daily_stats.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def clear_old_data(self, days_to_keep: int = 30) -> None:
        """Clear data older than specified days."""
        from datetime import timedelta
        
        cutoff = date.today() - timedelta(days=days_to_keep)
        cutoff_str = cutoff.isoformat()
        
        # Filter connections
        self._connections = [
            c for c in self._connections 
            if c.sent_at.date().isoformat() >= cutoff_str
        ]
        
        # Filter stats
        self._daily_stats = {
            k: v for k, v in self._daily_stats.items()
            if k >= cutoff_str
        }
        
        self._save()
        logger.info(f"Cleared data older than {days_to_keep} days")
