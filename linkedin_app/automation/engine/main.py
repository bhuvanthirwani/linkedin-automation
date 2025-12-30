"""
LinkedIn Automation Tool - Main Entry Point

Educational Purpose Only - Do Not Use in Production
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from .utils.config import load_config, Config
from .browser.browser import BrowserEngine
from .auth.login import Authenticator
from .auth.session import SessionManager
from .search.search import UserSearch
from .search.parser import ProfileParser
from .connection.connect import ConnectionManager
from .connection.sales_nav_connect import SalesNavConnectionManager
from .connection.note import NoteComposer
from .connection.tracker import ConnectionTracker
from .messaging.followup import FollowUpMessenger
from .messaging.template import TemplateEngine
from .messaging.tracker import MessageTracker
from .utils.models import SearchCriteria
from .messaging.tracker import MessageTracker
from .utils.models import SearchCriteria
from .database.db import DatabaseManager
from .features.network_scraper import NetworkScraper
from .features.activity_filter import ActivityFilter
from .features.request_sender import RequestSender


# Configure logging
# logger.remove()
# logger.add(
#     sys.stderr,
#     format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
#     level="INFO",
# )
# logger.add(
#     "logs/linkedin_bot_{time}.log",
#     rotation="1 day",
#     retention="7 days",
#     level="DEBUG",
# )


class LinkedInBot:
    """
    Main LinkedIn automation bot.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.browser: BrowserEngine = None
        self.authenticator: Authenticator = None
        self.session_manager: SessionManager = None
        self.searcher: UserSearch = None
        self.connection_manager: ConnectionManager = None
        self.messenger: FollowUpMessenger = None
        self.database_manager: DatabaseManager = None
        
        # Trackers
        self.connection_tracker: ConnectionTracker = None
        self.message_tracker: MessageTracker = None

        # Features
        self.network_scraper: NetworkScraper = None
        self.activity_filter: ActivityFilter = None
        self.request_sender: RequestSender = None
    
    def start(self) -> None:
        """Initialize and start the bot."""
        logger.info("Starting LinkedIn Bot initialization...")
        
        # Create browser
        self.browser = BrowserEngine(self.config.browser)
        self.browser.start()
        logger.info("Browser Engine started.")
        
        # Create database manager first
        if self.config.database.host and self.config.database.user:
            self.database_manager = DatabaseManager(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.user,
                password=self.config.database.password,
                schema=self.config.database.schema,
            )
            self.database_manager.connect()
            logger.info("Database manager connected (Sync)")

        # Create session manager
        self.session_manager = SessionManager(
            self.browser,
            self.config.paths.cookies_dir,
            self.config.linkedin.email,
        )
        
        # Create authenticator
        self.authenticator = Authenticator(
            self.browser,
            self.config.linkedin,
            self.session_manager,
        )
        
        # Create trackers (passing db manager)
        self.connection_tracker = ConnectionTracker(self.database_manager)
        self.message_tracker = MessageTracker(self.database_manager)
        
        # Create note composer
        note_composer = NoteComposer(self.config.messaging.connection_note_template)
        
        # Create connection manager
        self.connection_manager = ConnectionManager(
            self.browser,
            self.connection_tracker,
            note_composer,
            self.config.rate_limits.daily_connection_limit,
            database_manager=self.database_manager,
        )
        
        # Create template engine
        template_engine = TemplateEngine(self.config.messaging.follow_up_templates)
        
        # Create messenger
        self.messenger = FollowUpMessenger(
            self.browser,
            self.message_tracker,
            template_engine,
            self.config.rate_limits.daily_message_limit,
        )
        
        # Create searcher
        self.searcher = UserSearch(self.browser, max_pages=self.config.search.max_pages)
        
        # Initialize Features
        self.network_scraper = NetworkScraper(self.browser, self.database_manager)
        self.activity_filter = ActivityFilter(self.browser, self.database_manager, self.connection_manager)
        self.request_sender = RequestSender(self.browser, self.database_manager, self.connection_manager)
        
        logger.info("LinkedIn Bot initialized successfully")
    
    def login(self) -> bool:
        """Login to LinkedIn."""
        logger.info(f"Attempting login for {self.config.linkedin.email}...")
        success = self.authenticator.login()
        if success:
            logger.info("Login process completed successfully.")
        else:
            logger.error("Login process failed.")
        return success
    
    def search_and_connect(
        self,
        keywords: str = "",
        job_title: str = "",
        company: str = "",
        location: str = "",
        max_connections: int = 10,
    ) -> dict:
        """Search for profiles and send connection requests."""
        logger.info("Starting search and connect workflow")
        
        criteria = SearchCriteria(
            keywords=keywords,
            job_title=job_title,
            company=company,
            location=location,
            max_results=max_connections * 2,
        )
        
        result = self.searcher.search(criteria)
        logger.info(f"Found {len(result.profiles)} profiles")
        
        connections_sent = 0
        errors = 0
        
        for profile in result.profiles:
            if connections_sent >= max_connections:
                break
            
            request = self.connection_manager.send_connection_request(profile)
            if request.error:
                errors += 1
            else:
                connections_sent += 1
            
            self.browser.humanizer.random_delay(
                int(self.config.rate_limits.min_delay_seconds * 1000),
                int(self.config.rate_limits.max_delay_seconds * 1000),
            )
        
        return {
            "profiles_found": len(result.profiles),
            "connections_sent": connections_sent,
            "errors": errors,
        }
    
    def send_followups(self, max_messages: int = 10) -> dict:
        """Send follow-up messages to new connections."""
        logger.info("Starting follow-up messaging workflow")
        messages = self.messenger.process_new_connections(limit=max_messages)
        sent = sum(1 for m in messages if not m.error)
        errors = sum(1 for m in messages if m.error)
        return {
            "messages_sent": sent,
            "errors": errors,
        }
    
    def stop(self) -> None:
        """Stop the bot and cleanup."""
        logger.info("Stopping LinkedIn Bot")
        
        if self.database_manager:
            self.database_manager.close()
        
        if self.browser:
            self.browser.stop()
        
        logger.info("LinkedIn Bot stopped")

    def run_scrapping(self, keywords: str, location: str, start_page: int, pages: int, limit: int) -> None:
        """Run the Scrapping mode."""
        self.network_scraper.execute(keywords, location, start_page, pages, limit)

    def run_filtering(self, target_connections: int) -> None:
        """Run the Filtering mode."""
        self.activity_filter.execute(target_connections)

    def run_sending(self, limit: int) -> None:
        """Run the Send_Requests mode."""
        self.request_sender.execute(limit)

    def run_sales_nav_connection(self, url: str, start_page: int, end_page: int, limit: int, message: Optional[str] = None) -> None:
        """Run the Sales Navigator connection automation."""
        # Fallback to default template if no message provided
        if not message:
            message = self.config.messaging.connection_note_template
            logger.info("No message provided, using default template from config.")
            
        mgr = SalesNavConnectionManager(self.browser, self.connection_tracker, self.database_manager)
        mgr.run_automation(url, start_page, end_page, limit, message)




# Argparse logic removed. Use via library calls only.
