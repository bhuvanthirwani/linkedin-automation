"""
PostgreSQL database connection and query management.
"""

from datetime import datetime, date
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

    def record_connection_status(self, url: str, status: str) -> bool:
        """Update connection status in network data table."""
        if not self.conn: return False
        query = "UPDATE public.linkedin_db_network_data SET request_status = %s, request_sent_at = NOW(), updated_at = NOW() WHERE linkedin_url = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (status, url))
            return True
        except Exception as e:
            logger.error(f"Failed to update connection status: {e}")
            return False

    def record_daily_stat(self, category: str, count: int = 1) -> bool:
        """Increment daily statistic for a specific category."""
        if not self.conn: return False
        today = date.today().isoformat()
        
        # Mapping categories to column names
        column_map = {
            "connections_sent": "connections_sent",
            "connections_accepted": "connections_accepted",
            "messages_sent": "messages_sent",
            "profiles_searched": "profiles_searched",
            "errors": "errors"
        }
        
        column = column_map.get(category)
        if not column:
            logger.error(f"Invalid stat category: {category}")
            return False
            
        query = f"""
        INSERT INTO public.automation_dailystats (
            date, connections_sent, connections_accepted, 
            messages_sent, profiles_searched, errors
        )
        VALUES (%s, %s, 0, 0, 0, 0)
        ON CONFLICT (date) DO UPDATE SET
            {column} = public.automation_dailystats.{column} + EXCLUDED.{column}
        """
        
        # Prepare value: if we are incrementing, EXCLUDED.{column} will be count.
        # But for the initial INSERT, we need to put the count in the correct column.
        
        # Actually, let's make it even simpler and more robust:
        # Use a dynamic query that sets the target column to 'count' and others to 0 on INSERT.
        
        cols = ["connections_sent", "connections_accepted", "messages_sent", "profiles_searched", "errors"]
        vals = [0] * len(cols)
        if category in column_map:
            col_idx = cols.index(column_map[category])
            vals[col_idx] = count
            
        col_str = ", ".join(cols)
        val_placeholders = ", ".join(["%s"] * len(vals))
        
        query = f"""
        INSERT INTO public.automation_dailystats (date, {col_str})
        VALUES (%s, {val_placeholders})
        ON CONFLICT (date) DO UPDATE SET
            {column} = public.automation_dailystats.{column} + EXCLUDED.{column}
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, [today] + vals)
            return True
        except Exception as e:
            logger.error(f"Failed to record daily stat: {e}")
            return False

    def get_daily_stat(self, category: str, date_str: Optional[str] = None) -> int:
        """Get statistic for a specific category and date."""
        if not self.conn: return 0
        date_val = date_str or date.today().isoformat()
        
        column_map = {
            "connections_sent": "connections_sent",
            "messages_sent": "messages_sent",
            "errors": "errors"
        }
        column = column_map.get(category)
        if not column: return 0
        
        query = f"SELECT {column} FROM public.automation_dailystats WHERE date = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (date_val,))
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to get daily stat: {e}")
            return 0

    def record_connection_history(self, profile_url: str, profile_name: str, status: str, note: str = "", error: str = None) -> bool:
        """Record connection request in history table."""
        if not self.conn: return False
        query = """
        INSERT INTO public.automation_connectiontracking (profile_url, profile_name, sent_at, status, note, error)
        VALUES (%s, %s, NOW(), %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (profile_url, profile_name, status, note, error))
            return True
        except Exception as e:
            logger.error(f"Failed to record connection history: {e}")
            return False

    def is_connection_sent(self, profile_url: str) -> bool:
        """Check if connection was already sent to this URL."""
        if not self.conn: return False
        query = "SELECT 1 FROM public.automation_connectiontracking WHERE profile_url = %s LIMIT 1"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (profile_url,))
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check connection history: {e}")
            return False

    def record_message_history(self, recipient_url: str, recipient_name: str, content: str, template: str = "", error: str = None) -> bool:
        """Record message in history table."""
        if not self.conn: return False
        query = """
        INSERT INTO public.automation_messagetracking (recipient_url, recipient_name, content, sent_at, template_used, error)
        VALUES (%s, %s, %s, NOW(), %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (recipient_url, recipient_name, content, template, error))
            return True
        except Exception as e:
            logger.error(f"Failed to record message history: {e}")
            return False

    def is_already_messaged(self, profile_url: str) -> bool:
        """Check if profile was already messaged successfully."""
        if not self.conn: return False
        query = "SELECT 1 FROM public.automation_messagetracking WHERE recipient_url = %s AND error IS NULL LIMIT 1"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (profile_url,))
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check message history: {e}")
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

