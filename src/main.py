"""
LinkedIn Automation Tool - Main Entry Point

Educational Purpose Only - Do Not Use in Production
"""

import asyncio
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
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/linkedin_bot_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)


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
    
    async def start(self) -> None:
        """Initialize and start the bot."""
        logger.info("Starting LinkedIn Bot")
        
        # Create browser
        self.browser = BrowserEngine(self.config.browser)
        await self.browser.start()
        
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
        
        # Create trackers
        self.connection_tracker = ConnectionTracker(self.config.paths.tracking_dir)
        self.message_tracker = MessageTracker(self.config.paths.tracking_dir)
        
        # Create database manager if database config is provided
        if self.config.database.host and self.config.database.user:
            self.database_manager = DatabaseManager(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.user,
                password=self.config.database.password,
                schema=self.config.database.schema,
            )
            await self.database_manager.connect()
            logger.info("Database manager initialized")
        
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
        self.searcher = UserSearch(
            self.browser,
            self.config.search.max_pages,
        )

        # Initialize Features
        self.network_scraper = NetworkScraper(self.browser, self.database_manager)
        self.activity_filter = ActivityFilter(self.browser, self.database_manager, self.connection_manager)
        # RequestSender needs connection_manager
        self.request_sender = RequestSender(self.browser, self.database_manager, self.connection_manager)
        
        logger.info("LinkedIn Bot started successfully")
    
    async def login(self) -> bool:
        """Login to LinkedIn."""
        return await self.authenticator.login()
    
    async def search_and_connect(
        self,
        keywords: str = "",
        job_title: str = "",
        company: str = "",
        location: str = "",
        max_connections: int = 10,
    ) -> dict:
        """
        Search for profiles and send connection requests.
        
        Returns:
            Summary of actions taken.
        """
        logger.info("Starting search and connect workflow")
        
        # Build search criteria
        criteria = SearchCriteria(
            keywords=keywords,
            job_title=job_title,
            company=company,
            location=location,
            max_results=max_connections * 2,  # Get extra to account for failures
        )
        
        # Search for profiles
        result = await self.searcher.search(criteria)
        logger.info(f"Found {len(result.profiles)} profiles")
        
        # Send connection requests
        connections_sent = 0
        errors = 0
        
        for profile in result.profiles:
            if connections_sent >= max_connections:
                break
            
            # Check daily limit
            # if self.connection_tracker.get_today_count() >= self.config.rate_limits.daily_connection_limit:
            #     logger.warning("Daily connection limit reached")
            #     break
            
            # Send connection request
            request = await self.connection_manager.send_connection_request(profile)
            
            if request.error:
                errors += 1
            else:
                connections_sent += 1
            
            # Random delay between connections
            await self.browser.humanizer.random_delay(
                int(self.config.rate_limits.min_delay_seconds * 1000),
                int(self.config.rate_limits.max_delay_seconds * 1000),
            )
        
        return {
            "profiles_found": len(result.profiles),
            "connections_sent": connections_sent,
            "errors": errors,
        }
    
    async def connect_from_database(
        self,
        max_connections: int = 10,
        table_name: Optional[str] = None,
        where_clause: Optional[str] = None,
    ) -> dict:
        """
        Fetch LinkedIn URLs from database and send connection requests.
        
        Args:
            max_connections: Maximum number of connection requests to send
            table_name: Optional table name (defaults to config value)
            where_clause: Optional WHERE clause for filtering
        
        Returns:
            Summary of actions taken.
        """
        if not self.database_manager:
            raise RuntimeError("Database manager not initialized. Check database configuration.")
        
        logger.info("Starting database-driven connection workflow")
        
        # Use table name from config or parameter
        table = table_name or self.config.database.table_name
        
        # If fetching from raw_linkedin_ingest, use the special method that excludes connection_requests
        if table in ["raw_linkedin_ingest", "linkedin_db_raw_linkedin_ingest"]:
            logger.info("Fetching from raw_linkedin_ingest, excluding existing connection requests")
            profiles = await self.database_manager.fetch_urls_from_raw_ingest(
                limit=max_connections * 5,  # Get extra to account for failures
                exclude_connection_requests=True,
            )
        else:
            # Fetch profiles from database
            exclude_table = self.config.database.exclude_table
            exclude_url_column = self.config.database.exclude_url_column
            
            # Determine appropriate columns based on table name
            if table in ["candidates", "linkedin_db_candidates"]:
                additional_columns = ['full_name', 'headline']
            elif table in ["raw_linkedin_ingest", "linkedin_db_raw_linkedin_ingest"]:
                additional_columns = ['name', 'title', 'snippet']
            else:
                # Default: try common columns, but handle missing ones gracefully
                additional_columns = ['name', 'title', 'headline', 'full_name']
            
            profiles = await self.database_manager.fetch_linkedin_urls(
                table_name=table,
                url_column=self.config.database.url_column,
                limit=max_connections * 2,  # Get extra to account for failures
                where_clause=where_clause,
                additional_columns=additional_columns,
                exclude_table=exclude_table,
                exclude_url_column=exclude_url_column,
            )
        
        logger.info(f"Fetched {len(profiles)} profiles from database")
        
        # Send connection requests
        connections_sent = 0
        errors = 0
        
        for profile in profiles:
            if connections_sent >= max_connections:
                break
            
            # Check daily limit
            # if self.connection_tracker.get_today_count() >= self.config.rate_limits.daily_connection_limit:
            #     logger.warning("Daily connection limit reached")
            #     break
            
            # Send connection request
            request = await self.connection_manager.send_connection_request(profile)
            
            if request.error:
                errors += 1
            else:
                connections_sent += 1
            
            # Random delay between connections
            await self.browser.humanizer.random_delay(
                int(self.config.rate_limits.min_delay_seconds * 1000),
                int(self.config.rate_limits.max_delay_seconds * 1000),
            )
        
        return {
            "profiles_found": len(profiles),
            "connections_sent": connections_sent,
            "errors": errors,
        }
    
    async def send_followups(self, max_messages: int = 10) -> dict:
        """
        Send follow-up messages to new connections.
        
        Returns:
            Summary of messages sent.
        """
        logger.info("Starting follow-up messaging workflow")
        
        messages = await self.messenger.process_new_connections(limit=max_messages)
        
        sent = sum(1 for m in messages if not m.error)
        errors = sum(1 for m in messages if m.error)
        
        return {
            "messages_sent": sent,
            "errors": errors,
        }
    
    async def stop(self) -> None:
        """Stop the bot and cleanup."""
        logger.info("Stopping LinkedIn Bot")
        
        if self.database_manager:
            await self.database_manager.close()
        
        if self.browser:
            await self.browser.stop()
        
        logger.info("LinkedIn Bot stopped")

    async def run_scrapping(self, keywords: str, location: str, start_page: int, pages: int, limit: int) -> None:
        """Run the Scrapping mode."""
        if not self.network_scraper:
            raise RuntimeError("NetworkScraper not initialized")
        await self.network_scraper.execute(keywords, location, start_page, pages, limit)

    async def run_filtering(self, target_connections: int) -> None:
        """Run the Filtering mode (which includes sending)."""
        if not self.activity_filter:
            raise RuntimeError("ActivityFilter not initialized")
        await self.activity_filter.execute(target_connections)

    async def run_sending(self, limit: int) -> None:
        """Run the Send_Requests mode."""
        if not self.request_sender:
            raise RuntimeError("RequestSender not initialized")
        await self.request_sender.execute(limit)




async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LinkedIn Automation Tool (Educational Purpose Only)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["search", "followup", "both", "database", "Scrapping", "Filtering", "Send_Requests"],
        default="both",
        help="Operation mode (search, followup, both, database, Scrapping, Filtering, Send_Requests)",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="Database table name (for database mode)",
    )
    parser.add_argument(
        "--where",
        type=str,
        default=None,
        help="WHERE clause for database query (for database mode)",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        help="Search keywords",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Job title filter",
    )
    parser.add_argument(
        "--company",
        type=str,
        default="",
        help="Company filter",
    )
    parser.add_argument(
        "--location",
        type=str,
        default="",
        help="Location filter",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=10,
        help="Maximum connections to send",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=10,
        help="Maximum follow-up messages to send",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual actions)",

    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="Start page for LinkedIn search results (Scrapping mode)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=10,
        help="Number of pages to scrape (Scrapping mode)",
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Validate credentials
    if not config.validate_credentials():
        logger.error("LinkedIn credentials not configured. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
        sys.exit(1)
    
    # Create and start bot
    bot = LinkedInBot(config)
    
    try:
        await bot.start()
        
        # Login
        if not await bot.login():
            logger.error("Login failed")
            sys.exit(1)
        
        # Execute based on mode
        if args.mode == "database":
            if args.dry_run:
                logger.info("[DRY RUN] Would fetch URLs from database and connect")
            else:
                if not bot.database_manager:
                    logger.error("Database manager not initialized. Check database configuration.")
                    sys.exit(1)
                result = await bot.connect_from_database(
                    max_connections=args.max_connections,
                    table_name=args.table,
                    where_clause=args.where,
                )
                logger.info(f"Database Connect Results: {result}")
        
        elif args.mode == "Scrapping":
            if args.dry_run:
                logger.info("[DRY RUN] Would run Scrapping")
            else:
                # Scrapping uses page counts AND profile limits
                await bot.run_scrapping(args.keywords, args.location, args.start_page, args.pages, args.max_connections)
        
        elif args.mode == "Filtering":
            if args.dry_run:
                logger.info("[DRY RUN] Would run Filtering")
            else:
                # Filtering runs until max_connections requests are sent (or explicit limit)
                await bot.run_filtering(args.max_connections)
        
        elif args.mode == "Send_Requests":
            if args.dry_run:
                logger.info("[DRY RUN] Would run Send_Requests")
            else:
                await bot.run_sending(args.max_connections)

        elif args.mode in ["search", "both"]:
            if args.dry_run:
                logger.info("[DRY RUN] Would search and connect")
            else:
                result = await bot.search_and_connect(
                    keywords=args.keywords,
                    job_title=args.title,
                    company=args.company,
                    location=args.location,
                    max_connections=args.max_connections,
                )
                logger.info(f"Search & Connect Results: {result}")
        
        if args.mode in ["followup", "both"]:
            if args.dry_run:
                logger.info("[DRY RUN] Would send follow-up messages")
            else:
                result = await bot.send_followups(max_messages=args.max_messages)
                logger.info(f"Follow-up Results: {result}")
        
        logger.info("Automation completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Error during automation: {e}")
    finally:
        await bot.stop()


def run():
    """Entry point for the package."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
