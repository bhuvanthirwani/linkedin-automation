"""
Configuration management for LinkedIn Automation.
"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LinkedInConfig(BaseModel):
    """LinkedIn-specific configuration."""
    email: str = ""
    password: str = ""
    base_url: str = "https://www.linkedin.com"
    
    @field_validator('email', mode='before')
    @classmethod
    def get_email(cls, v):
        return v or os.getenv('LINKEDIN_EMAIL', '')
    
    @field_validator('password', mode='before')
    @classmethod
    def get_password(cls, v):
        return v or os.getenv('LINKEDIN_PASSWORD', '')


class BrowserConfig(BaseModel):
    """Browser automation configuration."""
    headless: bool = False
    timeout: int = 30000  # milliseconds
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    viewport_width: int = 1920
    viewport_height: int = 1080


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    daily_connection_limit: int = 25
    daily_message_limit: int = 50
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    page_load_delay_seconds: float = 3.0


class SearchConfig(BaseModel):
    """Search configuration."""
    max_pages: int = 10
    skip_duplicates: bool = True


class MessagingConfig(BaseModel):
    """Messaging configuration."""
    connection_note_template: str = "Hi {first_name}, I'd love to connect and learn more about your work at {company}!"
    max_note_length: int = 300
    follow_up_templates: List[str] = Field(default_factory=lambda: [
        "Hi {first_name}, thanks for connecting! I'd love to learn more about your experience at {company}.",
        "Great to connect, {first_name}! Looking forward to staying in touch."
    ])


class PathsConfig(BaseModel):
    """File paths configuration."""
    cookies_dir: str = "./data/cookies"
    tracking_dir: str = "./data/tracking"


class Config(BaseModel):
    """Main configuration class."""
    linkedin: LinkedInConfig = Field(default_factory=LinkedInConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    
    def validate_credentials(self) -> bool:
        """Check if LinkedIn credentials are set."""
        return bool(self.linkedin.email and self.linkedin.password)
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        Path(self.paths.cookies_dir).mkdir(parents=True, exist_ok=True)
        Path(self.paths.tracking_dir).mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file and environment variables.
    
    Args:
        config_path: Path to the YAML configuration file.
        
    Returns:
        Config object with all settings.
    """
    config_data = {}
    
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
    
    # Create config with defaults and overrides
    config = Config(**config_data)
    
    # Ensure directories exist
    config.ensure_directories()
    
    return config
