"""
Message tracking and history.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict

from loguru import logger

from ..utils.models import Message, DailyStats


class MessageTracker:
    """
    Tracks sent messages and prevents duplicates.
    """
    
    def __init__(self, tracking_dir: str):
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        
        self._messages_file = self.tracking_dir / "messages.json"
        self._stats_file = self.tracking_dir / "message_stats.json"
        
        self._messages: List[Message] = []
        self._daily_stats: Dict[str, DailyStats] = {}
        
        self._load()
    
    def record(self, message: Message) -> None:
        """Record a sent message."""
        self._messages.append(message)
        
        # Update daily stats
        today = date.today().isoformat()
        if today not in self._daily_stats:
            self._daily_stats[today] = DailyStats(date=today)
        
        self._daily_stats[today].messages_sent += 1
        
        if message.error:
            self._daily_stats[today].errors += 1
        
        self._save()
        
        logger.debug(f"Recorded message to: {message.recipient_url}")
    
    def is_already_messaged(self, profile_url: str) -> bool:
        """Check if we've already messaged this profile."""
        for msg in self._messages:
            if msg.recipient_url == profile_url and not msg.error:
                return True
        return False
    
    def get_today_count(self) -> int:
        """Get the number of messages sent today."""
        today = date.today().isoformat()
        if today in self._daily_stats:
            return self._daily_stats[today].messages_sent
        return 0
    
    def get_messages_to(self, profile_url: str) -> List[Message]:
        """Get all messages sent to a profile."""
        return [m for m in self._messages if m.recipient_url == profile_url]
    
    def get_recent_messages(self, limit: int = 50) -> List[Message]:
        """Get the most recent messages."""
        return sorted(self._messages, key=lambda m: m.sent_at, reverse=True)[:limit]
    
    def get_stats(self, date_str: str = None) -> Optional[DailyStats]:
        """Get stats for a specific date or today."""
        date_str = date_str or date.today().isoformat()
        return self._daily_stats.get(date_str)
    
    def _load(self) -> None:
        """Load data from files."""
        if self._messages_file.exists():
            try:
                with open(self._messages_file, "r") as f:
                    data = json.load(f)
                    self._messages = [Message(**m) for m in data]
            except Exception as e:
                logger.warning(f"Failed to load messages: {e}")
                self._messages = []
        
        if self._stats_file.exists():
            try:
                with open(self._stats_file, "r") as f:
                    data = json.load(f)
                    self._daily_stats = {k: DailyStats(**v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load message stats: {e}")
                self._daily_stats = {}
    
    def _save(self) -> None:
        """Save data to files."""
        try:
            with open(self._messages_file, "w") as f:
                data = [m.model_dump() for m in self._messages]
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save messages: {e}")
        
        try:
            with open(self._stats_file, "w") as f:
                data = {k: v.model_dump() for k, v in self._daily_stats.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save message stats: {e}")
