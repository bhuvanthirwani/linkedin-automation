"""
Configuration management for LinkedIn Automation.
"""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class LinkedInConfig:
    """LinkedIn-specific configuration."""
    email: str = ""
    password: str = ""
    base_url: str = "https://www.linkedin.com"

    def __post_init__(self):
        self.email = self.email or os.getenv('LINKEDIN_EMAIL', '')
        self.password = self.password or os.getenv('LINKEDIN_PASSWORD', '')


@dataclass
class BrowserConfig:
    """Browser automation configuration."""
    headless: bool = False
    timeout: int = 30000  # milliseconds
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    viewport_width: int = 1920
    viewport_height: int = 1080


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    daily_connection_limit: int = 25
    daily_message_limit: int = 50
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    page_load_delay_seconds: float = 3.0


@dataclass
class SearchConfig:
    """Search configuration."""
    max_pages: int = 10
    skip_duplicates: bool = True


@dataclass
class MessagingConfig:
    """Messaging configuration."""
    connection_note_template: str = "Hi {first_name}, I'd love to connect and learn more about your work at {company}!"
    max_note_length: int = 300
    follow_up_templates: List[str] = field(default_factory=lambda: [
        "Hi {first_name}, thanks for connecting! I'd love to learn more about your experience at {company}.",
        "Great to connect, {first_name}! Looking forward to staying in touch."
    ])


@dataclass
class PathsConfig:
    """File paths configuration."""
    cookies_dir: str = "./data/cookies"
    tracking_dir: str = "./data/tracking"


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""
    db_type: str = "postgresdb"
    host: str = ""
    port: int = 5432
    database: str = ""
    user: str = ""
    password: str = ""
    schema: str = "public"
    table_name: str = "linkedin_db_candidates"
    url_column: str = "linkedin_url"
    exclude_table: Optional[str] = None
    exclude_url_column: Optional[str] = None

    def __post_init__(self):
        # Convert port to int if it's a string from yaml or env
        if isinstance(self.port, str) and self.port.isdigit():
            self.port = int(self.port)
            
        self.host = self.host or os.getenv('DB_POSTGRESDB_HOST', '')
        self.port = self.port or int(os.getenv('DB_POSTGRESDB_PORT', '5432'))
        self.database = self.database or os.getenv('DB_POSTGRESDB_DATABASE', '')
        self.user = self.user or os.getenv('DB_POSTGRESDB_USER', '')
        self.password = self.password or os.getenv('DB_POSTGRESDB_PASSWORD', '')
        self.schema = self.schema or os.getenv('DB_POSTGRESDB_SCHEMA', 'public')


@dataclass
class Config:
    """Main configuration class."""
    linkedin: LinkedInConfig = field(default_factory=LinkedInConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    rate_limits: RateLimitConfig = field(default_factory=RateLimitConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    messaging: MessagingConfig = field(default_factory=MessagingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    def validate_credentials(self) -> bool:
        """Check if LinkedIn credentials are set."""
        return bool(self.linkedin.email and self.linkedin.password)
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        # Fix paths relative to the current working directory or define them relative to project root
        # For now, just create them as requested
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
    
    # Manually construct nested dataclasses from dict
    # This was automatic in Pydantic, but needs manual mapping in dataclasses
    
    linkedin_data = config_data.get('linkedin', {})
    browser_data = config_data.get('browser', {})
    rate_limits_data = config_data.get('rate_limits', {})
    search_data = config_data.get('search', {})
    messaging_data = config_data.get('messaging', {})
    paths_data = config_data.get('paths', {})
    database_data = config_data.get('database', {})
    
    return Config(
        linkedin=LinkedInConfig(**linkedin_data),
        browser=BrowserConfig(**browser_data),
        rate_limits=RateLimitConfig(**rate_limits_data),
        search=SearchConfig(**search_data),
        messaging=MessagingConfig(**messaging_data),
        paths=PathsConfig(**paths_data),
        database=DatabaseConfig(**database_data)
    )
