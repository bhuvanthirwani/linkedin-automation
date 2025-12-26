"""
Data models for LinkedIn Automation.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class ConnectionStatus(str, Enum):
    """Status of a connection request."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    ERROR = "error"


class Profile(BaseModel):
    """LinkedIn user profile."""
    url: str
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    headline: str = ""
    company: str = ""
    location: str = ""
    title: str = ""
    scraped_at: datetime = Field(default_factory=datetime.now)
    
    def get_template_vars(self) -> Dict[str, str]:
        """Get variables for template substitution."""
        return {
            "first_name": self.first_name or self.name.split()[0] if self.name else "",
            "last_name": self.last_name or (self.name.split()[-1] if len(self.name.split()) > 1 else ""),
            "name": self.name,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "headline": self.headline,
        }


class ConnectionRequest(BaseModel):
    """A connection request sent to a profile."""
    profile_url: str
    profile_name: str = ""
    sent_at: datetime = Field(default_factory=datetime.now)
    status: ConnectionStatus = ConnectionStatus.PENDING
    note: str = ""
    error: Optional[str] = None


class Message(BaseModel):
    """A message sent to a connection."""
    recipient_url: str
    recipient_name: str = ""
    content: str
    sent_at: datetime = Field(default_factory=datetime.now)
    template_used: str = ""
    error: Optional[str] = None


class SearchCriteria(BaseModel):
    """Search criteria for finding profiles."""
    keywords: str = ""
    job_title: str = ""
    company: str = ""
    location: str = ""
    industry: str = ""
    school: str = ""
    network: str = "\"S\""
    max_results: int = 100


class SearchResult(BaseModel):
    """Result of a profile search."""
    criteria: SearchCriteria
    profiles: List[Profile] = Field(default_factory=list)
    total_found: int = 0
    pages_scraped: int = 0
    searched_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0


class Cookie(BaseModel):
    """Browser cookie."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[float] = None
    secure: bool = False
    http_only: bool = False


class Session(BaseModel):
    """Browser session with cookies."""
    email: str
    cookies: List[Cookie] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    valid: bool = True


class DailyStats(BaseModel):
    """Daily usage statistics."""
    date: str
    connections_sent: int = 0
    connections_accepted: int = 0
    messages_sent: int = 0
    profiles_searched: int = 0
    errors: int = 0


class ActionLog(BaseModel):
    """Log entry for an automation action."""
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str
    target: str = ""
    success: bool = True
    duration_ms: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
