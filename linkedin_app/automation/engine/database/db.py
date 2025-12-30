"""
PostgreSQL database connection and query management.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
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
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        self.conn = None
    
    def connect(self) -> None:
        """Create database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            self.conn.autocommit = True
            logger.info("Database connection established successfully")
            
            # Initialize schema for network data
            self.create_network_data_table()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def fetch_linkedin_urls(
        self,
        table_name: str = "linkedin_db_candidates",
        url_column: str = "linkedin_url",
        limit: Optional[int] = None,
        where_clause: Optional[str] = None,
        additional_columns: Optional[List[str]] = None,
        exclude_table: Optional[str] = None,
        exclude_url_column: Optional[str] = None,
    ) -> List[Profile]:
        """Fetch LinkedIn URLs from the database and create Profile objects."""
        if not self.conn:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        profiles = []
        try:
            main_alias = "t"
            effective_columns = [f'{main_alias}."{url_column}"']
            if additional_columns:
                effective_columns.extend([f'{main_alias}."{col}"' for col in additional_columns])
            
            effective_schema = 'public'
            schema_quoted = f'"{effective_schema}"'
            table_quoted = f'"{table_name}"'
            
            query = f'SELECT {", ".join(effective_columns)} FROM {schema_quoted}.{table_quoted} {main_alias}'
            
            if exclude_table:
                if exclude_table == "connection_requests" and not "linkedin_db_" in exclude_table:
                    exclude_table = "linkedin_db_connection_requests"
                
                exclude_table_quoted = f'"{exclude_table}"'
                exclude_url_col = exclude_url_column or url_column
                query += f' LEFT JOIN {schema_quoted}.{exclude_table_quoted} e '
                query += f'ON {main_alias}."{url_column}" = e."{exclude_url_col}"'
                
                where_conditions = [f'e."{exclude_url_col}" IS NULL']
                if where_clause:
                    clean_where = where_clause.strip()
                    if clean_where.upper().startswith("WHERE "):
                        clean_where = clean_where[6:].strip()
                    if clean_where:
                        where_conditions.append(f"({clean_where})")
                
                query += f" WHERE {' AND '.join(where_conditions)}"
            else:
                if where_clause:
                    clean_where = where_clause.strip()
                    if clean_where.upper().startswith("WHERE "):
                        clean_where = clean_where[6:].strip()
                    if clean_where:
                        query += f" WHERE {clean_where}"
            
            query += f' ORDER BY {main_alias}."{url_column}"'
            if limit:
                query += f" LIMIT {limit}"
            
            logger.debug(f"Executing query: {query}")
            
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
            
            logger.info(f"Fetched {len(rows)} LinkedIn URLs from database")
            
            column_mapping = {
                'name': 'name',
                'full_name': 'name',
                'snippet': 'headline',
                'job_title': 'title',
            }
            
            for row in rows:
                try:
                    url = row[url_column]
                    if not url: continue
                    url = url.strip()
                    profile_data = {"url": url}
                    
                    if additional_columns:
                        for col in additional_columns:
                            if col in row and row[col] is not None:
                                field_name = column_mapping.get(col, col)
                                profile_data[field_name] = str(row[col]).strip()
                    
                    profiles.append(Profile(**profile_data))
                except Exception as e:
                    logger.warning(f"Failed to create profile from row: {e}")
            
            return profiles
        except Exception as e:
            logger.error(f"Failed to fetch LinkedIn URLs: {e}")
            raise

    def record_connection_request(self, url: str, status: str, sent_at: Optional[datetime] = None) -> bool:
        """Record a connection request in the database."""
        if not self.conn: return False
        try:
            table_name = "linkedin_db_connection_requests"
            query = f'INSERT INTO "public"."{table_name}" ("linkedin_url", "status", "sent_at") VALUES (%s, %s, %s) ON CONFLICT DO NOTHING'
            with self.conn.cursor() as cur:
                cur.execute(query, (url, status, sent_at))
            return True
        except Exception as e:
            logger.error(f"Failed to record connection request: {e}")
            return False

    def create_network_data_table(self) -> None:
        """Create the linkedin_db_network_data table if it doesn't exist."""
        if not self.conn: return
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
            recent_activity_unit TEXT,
            recent_activity_minutes INTEGER,
            scrape_status TEXT DEFAULT 'not_scraped',
            request_status TEXT DEFAULT 'not_sent',
            scraped_at TIMESTAMPTZ,
            request_sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS linkedin_db_network_data_linkedin_url_idx 
        ON public.linkedin_db_network_data (linkedin_url);
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
            logger.info("Ensured linkedin_db_network_data table exists")
        except Exception as e:
            logger.error(f"Failed to create network data table: {e}")

    def upsert_network_profile(self, profile_data: Dict[str, Any]) -> bool:
        """Insert or update a profile in network data table."""
        if not self.conn: return False
        query = """
        INSERT INTO public.linkedin_db_network_data (
            linkedin_url, name, first_name, last_name, keywords, location
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (linkedin_url) DO UPDATE SET
            name = EXCLUDED.name,
            updated_at = NOW()
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    profile_data.get('linkedin_url'),
                    profile_data.get('name'),
                    profile_data.get('first_name'),
                    profile_data.get('last_name'),
                    profile_data.get('keywords', []),
                    profile_data.get('location')
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to upsert network profile: {e}")
            return False

    def get_profiles_for_filtering(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch profiles that need activity scraping."""
        if not self.conn: return []
        query = "SELECT linkedin_url, name FROM public.linkedin_db_network_data WHERE scrape_status IN ('not_scraped', 'failed') LIMIT %s"
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch profiles for filtering: {e}")
            return []

    def update_network_activity(self, url: str, activity_data: Dict[str, Any]) -> bool:
        """Update activity data for a profile."""
        if not self.conn: return False
        query = """
        UPDATE public.linkedin_db_network_data
        SET recent_activity_raw = %s, recent_activity_value = %s, recent_activity_unit = %s, 
            recent_activity_minutes = %s, scrape_status = %s, scraped_at = NOW(), updated_at = NOW()
        WHERE linkedin_url = %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    activity_data.get('raw'),
                    activity_data.get('value'),
                    activity_data.get('unit'),
                    activity_data.get('minutes'),
                    activity_data.get('status', 'scraped'),
                    url
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to update activity: {e}")
            return False

    def get_profiles_for_sending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch profiles eligible for requests."""
        if not self.conn: return []
        query = "SELECT linkedin_url, name, first_name, last_name FROM public.linkedin_db_network_data WHERE scrape_status = 'scraped' AND request_status = 'not_sent' LIMIT %s"
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch profiles for sending: {e}")
            return []

    def update_request_status(self, url: str, status: str) -> bool:
        """Update request status."""
        if not self.conn: return False
        query = "UPDATE public.linkedin_db_network_data SET request_status = %s, updated_at = NOW() WHERE linkedin_url = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (status, url))
            return True
        except Exception as e:
            logger.error(f"Failed to update request status: {e}")
            return False

    def delete_from_raw_ingest(self, url: str) -> bool:
        """Delete from raw_linkedin_ingest."""
        if not self.conn: return False
        query = 'DELETE FROM "public"."linkedin_db_raw_linkedin_ingest" WHERE "linkedin_url" = %s'
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (url,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete from raw_ingest: {e}")
            return False

