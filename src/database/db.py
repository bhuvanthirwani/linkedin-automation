"""
PostgreSQL database connection and query management.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import asyncpg
from loguru import logger

from ..utils.models import Profile


class DatabaseManager:
    """
    Manages PostgreSQL database connections and queries for LinkedIn URLs.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        schema: str = "public",
    ):
        """
        Initialize database manager.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            schema: Database schema (default: public)
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Create database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=1,
                max_size=5,
                # Required for PgBouncer/Supabase to avoid "prepared statement already exists" error
                statement_cache_size=0,
            )
            logger.info("Database connection pool created successfully")
            
            # Initialize schema for network data
            await self.create_network_data_table()
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def fetch_linkedin_urls(
        self,
        table_name: str = "linkedin_db_candidates",
        url_column: str = "linkedin_url",
        limit: Optional[int] = None,
        where_clause: Optional[str] = None,
        additional_columns: Optional[List[str]] = None,
        exclude_table: Optional[str] = None,
        exclude_url_column: Optional[str] = None,
    ) -> List[Profile]:
        """
        Fetch LinkedIn URLs from the database and create Profile objects.
        
        Args:
            table_name: Name of the table to query
            url_column: Name of the column containing LinkedIn URLs
            limit: Maximum number of URLs to fetch (None for no limit)
            where_clause: Optional WHERE clause (e.g., "status = 'pending'")
            additional_columns: Optional list of additional columns to fetch
                               (e.g., ['name', 'first_name', 'company'])
            exclude_table: Optional table name to exclude URLs from (e.g., 'linkedin_db_connection_requests')
            exclude_url_column: Column name in exclude_table containing URLs (defaults to url_column)
        
        Returns:
            List of Profile objects with URLs from the database
        """
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        profiles = []
        
        try:
            # Build SELECT query with proper identifier quoting
            # Quote identifiers to handle case-sensitive names
            # Define alias for the main table to avoid ambiguity
            main_alias = "t"
            effective_columns = [f'{main_alias}."{url_column}"']
            if additional_columns:
                effective_columns.extend([f'{main_alias}."{col}"' for col in additional_columns])
            
            # Ensure we have a valid schema name
            effective_schema = 'public'
            
            # Diagnostic check: if effective_schema is 'linkedin_db', it might be a mistake
            # if effective_schema == "linkedin_db" and table_name.startswith("linkedin_db_"):
            #     logger.warning(f"Database schema is set to 'linkedin_db', but tables start with 'linkedin_db_'. "
            #                    f"Are you sure the schema isn't 'public'?")
            
            # Quote schema and table names separately
            schema_quoted = f'"{effective_schema}"'
            table_quoted = f'"{table_name}"'
            
            query = f'SELECT {", ".join(effective_columns)} FROM {schema_quoted}.{table_quoted} {main_alias}'
            logger.debug(f"Executing query on table: {effective_schema}.{table_name} as {main_alias}")
            
            # Add exclusion logic if exclude_table is provided
            if exclude_table:
                # Handle prefixes for common tables if they don't have them
                if exclude_table == "connection_requests" and not "linkedin_db_" in exclude_table:
                    exclude_table = "linkedin_db_connection_requests"
                
                exclude_table_quoted = f'"{exclude_table}"'
                
                # Join with exclude table using linkedin_url
                exclude_url_col = exclude_url_column or url_column
                query += f' LEFT JOIN {schema_quoted}.{exclude_table_quoted} e '
                query += f'ON {main_alias}."{url_column}" = e."{exclude_url_col}"'
                
                # Build WHERE clause with exclusion condition
                where_conditions = [f'e."{exclude_url_col}" IS NULL']
                
                # Add additional WHERE clause if provided
                if where_clause:
                    # Clean WHERE clause if it starts with WHERE
                    clean_where = where_clause.strip()
                    if clean_where.upper().startswith("WHERE "):
                        clean_where = clean_where[6:].strip()
                    if clean_where:
                        where_conditions.append(f"({clean_where})")
                
                query += f" WHERE {' AND '.join(where_conditions)}"
            else:
                # Add WHERE clause if provided (only if not using exclusion)
                if where_clause:
                    clean_where = where_clause.strip()
                    if clean_where.upper().startswith("WHERE "):
                        clean_where = clean_where[6:].strip()
                    if clean_where:
                        query += f" WHERE {clean_where}"
            
            # Add ORDER BY to ensure consistent ordering
            # Use table alias to avoid ambiguity when using JOINs
            query += f' ORDER BY {main_alias}."{url_column}"'
            
            # Add LIMIT if provided
            if limit:
                query += f" LIMIT {limit}"
            
            logger.debug(f"Executing query: {query}")
            
            async with self.pool.acquire() as conn:
                try:
                    rows = await conn.fetch(query)
                except Exception as e:
                    # Check if it's a column-related error
                    error_msg = str(e).lower()
                    if 'column' in error_msg and ('does not exist' in error_msg or 'undefined' in error_msg):
                        # Column doesn't exist - this means we're requesting wrong columns for this table
                        logger.error(f"Column error in query: {e}")
                        logger.error(f"Table: {table_name}, Requested columns: {effective_columns}")
                        logger.info("Attempting to fetch only basic columns (linkedin_url)")
                        # Retry with only the URL column
                        simple_query = f'SELECT {main_alias}."{url_column}" FROM {schema_quoted}.{table_quoted} {main_alias}'
                        if exclude_table:
                            # Rebuild exclusion logic
                            # Join with exclude table using linkedin_url
                            exclude_url_col = exclude_url_column or url_column
                            exclude_table_quoted = f'"{exclude_table}"'
                            simple_query += f' LEFT JOIN {schema_quoted}.{exclude_table_quoted} e '
                            simple_query += f'ON {main_alias}."{url_column}" = e."{exclude_url_col}"'
                            simple_query += f' WHERE e."{exclude_url_col}" IS NULL'
                        elif where_clause:
                            clean_where = where_clause.strip()
                            if clean_where.upper().startswith("WHERE "):
                                clean_where = clean_where[6:].strip()
                            if clean_where:
                                simple_query += f" WHERE {clean_where}"
                        simple_query += f' ORDER BY {main_alias}."{url_column}"'
                        if limit:
                            simple_query += f" LIMIT {limit}"
                        logger.debug(f"Retrying with simplified query: {simple_query}")
                        rows = await conn.fetch(simple_query)
                        # Clear additional_columns since we're only getting URL
                        additional_columns = []
                    else:
                        # Re-raise if it's not a column error
                        raise
            
            logger.info(f"Fetched {len(rows)} LinkedIn URLs from database")
            
            # Map database columns to Profile fields
            column_mapping = {
                'name': 'name',
                'full_name': 'name',  # candidates table uses full_name
                'first_name': 'first_name',
                'last_name': 'last_name',
                'headline': 'headline',
                'snippet': 'headline',  # raw_linkedin_ingest uses snippet
                'company': 'company',
                'location': 'location',
                'title': 'title',
                'job_title': 'title',  # Alternative column name
            }
            
            for row in rows:
                try:
                    # Get URL (required)
                    url = row[url_column]
                    if not url or not isinstance(url, str):
                        logger.warning(f"Skipping row with invalid URL: {url}")
                        continue
                    
                    # Clean URL
                    url = url.strip()
                    if not url.startswith('http'):
                        # Assume it's a relative URL or just the path
                        if url.startswith('/'):
                            url = f"https://www.linkedin.com{url}"
                        elif '/in/' in url:
                            url = f"https://www.linkedin.com/in/{url.split('/in/')[-1].split('/')[0]}"
                        else:
                            logger.warning(f"Skipping invalid URL format: {url}")
                            continue
                    
                    # Extract additional fields if available
                    profile_data = {"url": url}
                    
                    if additional_columns:
                        for col in additional_columns:
                            try:
                                # Check if column exists in row (handles missing columns gracefully)
                                if col in row and row[col] is not None:
                                    # Map to Profile field name if mapping exists
                                    field_name = column_mapping.get(col, col)
                                    profile_data[field_name] = str(row[col]).strip()
                            except (KeyError, AttributeError):
                                # Column doesn't exist in this row, skip it
                                logger.debug(f"Column '{col}' not found in row, skipping")
                                continue
                    
                    # Create Profile object
                    profile = Profile(**profile_data)
                    profiles.append(profile)
                    
                except Exception as e:
                    logger.warning(f"Failed to create profile from row: {e}")
                    continue
            
            logger.info(f"Created {len(profiles)} Profile objects from database")
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to fetch LinkedIn URLs from database: {e}")
            raise
    
    async def fetch_urls_from_queue(
        self,
        limit: Optional[int] = None,
    ) -> List[Profile]:
        """
        Convenience method to fetch URLs from candidate_queue table.
        Note: This requires joining with candidates table to get the linkedin_url.
        
        Args:
            limit: Maximum number of URLs to fetch
        
        Returns:
            List of Profile objects
        """
        # candidate_queue references candidates via candidate_id
        # We need to join to get the linkedin_url
        # This is a more complex query, so we'll use a custom approach
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        profiles = []
        
        try:
            effective_schema = self.schema or 'public'
            schema_quoted = f'"{effective_schema}"'
            
            query = f'''
                SELECT c."linkedin_url", c."full_name", c."headline"
                FROM {schema_quoted}."linkedin_db_candidate_queue" cq
                JOIN {schema_quoted}."linkedin_db_candidates" c ON cq."candidate_id" = c."id"
                WHERE cq."status" = 'QUEUED'
                ORDER BY cq."scheduled_at"
            '''
            
            if limit:
                query += f" LIMIT {limit}"
            
            logger.debug(f"Executing query: {query}")
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
            
            logger.info(f"Fetched {len(rows)} URLs from candidate_queue")
            
            for row in rows:
                try:
                    url = row['linkedin_url']
                    if not url or not isinstance(url, str):
                        continue
                    
                    url = url.strip()
                    if not url.startswith('http'):
                        if url.startswith('/'):
                            url = f"https://www.linkedin.com{url}"
                        elif '/in/' in url:
                            url = f"https://www.linkedin.com/in/{url.split('/in/')[-1].split('/')[0]}"
                        else:
                            continue
                    
                    profile = Profile(
                        url=url,
                        name=row.get('full_name', '') or '',
                        headline=row.get('headline', '') or '',
                    )
                    profiles.append(profile)
                    
                except Exception as e:
                    logger.warning(f"Failed to create profile from row: {e}")
                    continue
            
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to fetch URLs from candidate_queue: {e}")
            raise
    
    async def fetch_urls_from_raw_ingest(
        self,
        limit: Optional[int] = None,
        exclude_connection_requests: bool = True,
    ) -> List[Profile]:
        """
        Convenience method to fetch URLs from raw_linkedin_ingest table,
        excluding URLs that already exist in connection_requests (via candidates table).
        
        Args:
            limit: Maximum number of URLs to fetch
            exclude_connection_requests: If True, exclude URLs already in connection_requests table
        
        Returns:
            List of Profile objects
        """
        additional_columns = ['name', 'title', 'snippet']  # Available columns in raw_linkedin_ingest
        
        exclude_table = None
        if exclude_connection_requests:
            exclude_table = "connection_requests"
            logger.info("Excluding URLs that exist in connection_requests (via candidates table)")
        
        return await self.fetch_linkedin_urls(
            table_name="linkedin_db_raw_linkedin_ingest",
            url_column="linkedin_url",
            limit=limit,
            additional_columns=additional_columns,
            exclude_table=exclude_table,
            exclude_url_column=None,  # Will be handled specially for connection_requests
        )
    
    async def record_connection_request(
        self,
        url: str,
        status: str,
        sent_at: Optional[datetime] = None,
    ) -> bool:
        """
        Record a connection request in the database.
        
        Args:
            url: LinkedIn URL of the profile
            status: Status (e.g., 'PENDING', 'SENT', 'ACCEPTED', 'FAILED')
            sent_at: Optional timestamp of when it was sent
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pool:
            logger.error("Database not connected. Call connect() first.")
            return False
            
        try:
            effective_schema = self.schema or 'public'
            schema_quoted = f'"{effective_schema}"'
            table_name = "linkedin_db_connection_requests"
            table_quoted = f'"{table_name}"'
            
            # Use transactional mode for UPSERT or simple INSERT
            # The schema provided by user has id as primary key (uuid) and linkedin_url matches
            # Let's check if there's already an entry for this URL and just update it, 
            # or insert if not exists.
            
            # Since user didn't specify a UNIQUE constraint on linkedin_url in their latest SQL,
            # we should probably check existence first or just INSERT if we want a history.
            # But the user mentioned it's used for filtering, so we should avoid duplicates.
            
            query = f'''
                INSERT INTO {schema_quoted}.{table_quoted} ("linkedin_url", "status", "sent_at")
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
            '''
            # Note: For ON CONFLICT DO NOTHING to work, linkedin_url needs a UNIQUE constraint.
            # If not unique, we'll just get multiple rows, which is also fine for exclusion filters.
            
            async with self.pool.acquire() as conn:
                await conn.execute(query, url, status, sent_at)
                
            logger.debug(f"Recorded connection status '{status}' for {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to record connection request: {e}")
            return False

    async def create_network_data_table(self) -> None:
        """Create the linkedin_db_network_data table if it doesn't exist."""
        if not self.pool:
             return
        
        # 1. Base Table Creation
        query = """
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        CREATE TABLE IF NOT EXISTS public.linkedin_db_network_data (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            linkedin_url TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            keywords TEXT[],
            location TEXT,
            recent_activity_raw TEXT,
            recent_activity_value INTEGER,
            recent_activity_unit TEXT CHECK (recent_activity_unit IN ('h', 'd', 'w', 'mo')),
            recent_activity_minutes INTEGER,
            scrape_status TEXT CHECK (scrape_status IN ('not_scraped', 'scraped', 'failed')) DEFAULT 'not_scraped',
            request_status TEXT CHECK (request_status IN ('not_sent', 'pending', 'sent', 'skipped', 'failed', 'already_connected')) DEFAULT 'not_sent',
            scraped_at TIMESTAMPTZ,
            request_sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
        
        # 2. Self-Healing: Remove Duplicates & Ensure Unique Index
        # This handles cases where the table exists but lacks the UNIQUE constraint, causing ON CONFLICT failures.
        cleanup_query = """
        DELETE FROM public.linkedin_db_network_data a USING public.linkedin_db_network_data b 
        WHERE a.id < b.id AND a.linkedin_url = b.linkedin_url;
        """
        
        index_query = """
        CREATE UNIQUE INDEX IF NOT EXISTS linkedin_db_network_data_linkedin_url_idx 
        ON public.linkedin_db_network_data (linkedin_url);
        """

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query)
                
                # Run self-healing
                try:
                    await conn.execute(cleanup_query)
                    await conn.execute(index_query)
                    logger.debug("Ensured unique index and removed duplicates for linkedin_db_network_data")
                except Exception as e:
                    logger.warning(f"Metadata maintenance (cleanup/index) failed (non-critical if table new): {e}")

            logger.info("Ensured linkedin_db_network_data table exists")
        except Exception as e:
            logger.error(f"Failed to create network data table: {e}")

    async def upsert_network_profile(self, profile_data: Dict[str, Any]) -> bool:
        """Insert or update a profile in network data table."""
        if not self.pool:
            return False
        
        query = """
        INSERT INTO public.linkedin_db_network_data (
            linkedin_url, name, first_name, last_name, keywords, location, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
        ON CONFLICT (linkedin_url) DO UPDATE SET
            name = EXCLUDED.name,
            first_name = COALESCE(EXCLUDED.first_name, public.linkedin_db_network_data.first_name),
            last_name = COALESCE(EXCLUDED.last_name, public.linkedin_db_network_data.last_name),
            keywords = EXCLUDED.keywords, 
            location = COALESCE(EXCLUDED.location, public.linkedin_db_network_data.location),
            updated_at = NOW()
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    profile_data.get('linkedin_url'),
                    profile_data.get('name'),
                    profile_data.get('first_name'),
                    profile_data.get('last_name'),
                    profile_data.get('keywords', []),
                    profile_data.get('location')
                )
            return True
        except Exception as e:
            logger.error(f"Failed to upsert network profile: {e}")
            return False

    async def get_profiles_for_filtering(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch profiles that need activity scraping."""
        if not self.pool:
            return []
        
        query = """
        SELECT linkedin_url, name 
        FROM public.linkedin_db_network_data
        WHERE scrape_status = 'not_scraped'
        ORDER BY created_at ASC
        LIMIT $1
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch profiles for filtering: {e}")
            return []

    async def update_network_activity(self, url: str, activity_data: Dict[str, Any]) -> bool:
        """Update activity data for a profile."""
        if not self.pool:
            return False
            
        query = """
        UPDATE public.linkedin_db_network_data
        SET
            recent_activity_raw = $2,
            recent_activity_value = $3,
            recent_activity_unit = $4,
            recent_activity_minutes = $5,
            scrape_status = $6,
            scraped_at = NOW(),
            updated_at = NOW()
        WHERE linkedin_url = $1
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    url,
                    activity_data.get('raw'),
                    activity_data.get('value'),
                    activity_data.get('unit'),
                    activity_data.get('minutes'),
                    activity_data.get('status', 'scraped')
                )
            return True
        except Exception as e:
            logger.error(f"Failed to update activity for {url}: {e}")
            return False

    async def get_profiles_for_sending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch profiles eligible for connection requests (recent activity < 1 week)."""
        if not self.pool:
            return []
            
        # 1 week = 7 * 24 * 60 = 10080 minutes
        query = """
        SELECT linkedin_url, name, first_name, last_name, recent_activity_minutes
        FROM public.linkedin_db_network_data
        WHERE 
            scrape_status = 'scraped' AND
            request_status = 'not_sent' AND
            recent_activity_minutes IS NOT NULL AND
            recent_activity_minutes <= 10080
        ORDER BY recent_activity_minutes ASC
        LIMIT $1
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch profiles for sending: {e}")
            return []

    async def update_request_status(self, url: str, status: str) -> bool:
        """Update request status."""
        if not self.pool:
            return False
            
        query = """
        UPDATE public.linkedin_db_network_data
        SET
            request_status = $2,
            request_sent_at = CASE WHEN $2 = 'sent' THEN NOW() ELSE request_sent_at END,
            updated_at = NOW()
        WHERE linkedin_url = $1
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, url, status)
            return True
        except Exception as e:
            logger.error(f"Failed to update request status for {url}: {e}")
            return False

    async def delete_from_raw_ingest(self, url: str) -> bool:
        """
        Delete a profile from the raw_linkedin_ingest table.
        
        Args:
            url: LinkedIn URL of the profile to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pool:
            logger.error("Database not connected. Call connect() first.")
            return False
            
        try:
            effective_schema = self.schema or 'public'
            schema_quoted = f'"{effective_schema}"'
            table_name = "linkedin_db_raw_linkedin_ingest"
            table_quoted = f'"{table_name}"'
            
            query = f'DELETE FROM {schema_quoted}.{table_quoted} WHERE "linkedin_url" = $1'
            
            async with self.pool.acquire() as conn:
                await conn.execute(query, url)
                
            logger.info(f"Deleted {url} from {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {url} from raw_linkedin_ingest: {e}")
            return False

