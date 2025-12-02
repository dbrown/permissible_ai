"""
SQLite-based query execution service for collaboration sessions.
Each collaboration session gets its own isolated SQLite database.
"""
import os
import sqlite3
import csv
import io
import hashlib
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Executes SQL queries against isolated SQLite databases.
    Each collaboration session has its own database with loaded datasets.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the query executor.
        
        Args:
            data_dir: Directory to store SQLite databases. Defaults to /opt/tee-data
        """
        if data_dir is None:
            data_dir = '/opt/tee-data'
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # Restricted permissions
        logger.info(f"Query executor initialized with data directory: {self.data_dir}")
    
    def _get_db_path(self, session_id: int) -> Path:
        """Get the SQLite database path for a session."""
        return self.data_dir / f"session_{session_id}.db"
    
    def _sanitize_table_name(self, name: str) -> str:
        """
        Sanitize a name to be used as a table name.
        Converts to lowercase, replaces non-alphanumeric with underscore.
        """
        import re
        sanitized = re.sub(r'[^a-z0-9_]', '_', name.lower())
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'table_' + sanitized
        return sanitized or 'table_unnamed'
    
    def create_session_database(self, session_id: int) -> None:
        """
        Create a new SQLite database for a collaboration session.
        
        Args:
            session_id: The collaboration session ID
        """
        db_path = self._get_db_path(session_id)
        
        if db_path.exists():
            logger.warning(f"Database already exists for session {session_id}")
            return
        
        # Create the database
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Create metadata table to track datasets
        conn.execute("""
            CREATE TABLE _session_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        conn.execute("""
            INSERT INTO _session_metadata (key, value) VALUES (?, ?)
        """, ('session_id', str(session_id)))
        
        conn.execute("""
            INSERT INTO _session_metadata (key, value) VALUES (?, ?)
        """, ('created_at', datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Set restrictive permissions
        os.chmod(db_path, 0o600)
        logger.info(f"Created database for session {session_id} at {db_path}")
    
    def load_dataset(
        self,
        session_id: int,
        dataset_id: int,
        dataset_name: str,
        csv_content: str
    ) -> Dict[str, Any]:
        """
        Load a CSV dataset into the session's SQLite database.
        
        Args:
            session_id: The collaboration session ID
            dataset_id: The dataset ID
            dataset_name: Name for the dataset (will be sanitized for table name)
            csv_content: CSV file content as string (must have header row)
        
        Returns:
            Dictionary with load results including table_name, row_count, columns
        """
        db_path = self._get_db_path(session_id)
        
        if not db_path.exists():
            self.create_session_database(session_id)
        
        # Parse CSV
        csv_reader = csv.reader(io.StringIO(csv_content))
        
        try:
            # Read header
            headers = next(csv_reader)
            if not headers:
                raise ValueError("CSV file is empty or has no header")
            
            # Sanitize column names
            sanitized_columns = [self._sanitize_table_name(col) for col in headers]
            
            # Check for duplicate column names
            if len(sanitized_columns) != len(set(sanitized_columns)):
                raise ValueError("CSV contains duplicate column names after sanitization")
            
            # Sanitize table name
            table_name = f"dataset_{dataset_id}_{self._sanitize_table_name(dataset_name)}"
            
            # Read all rows
            rows = list(csv_reader)
            
            if not rows:
                raise ValueError("CSV file contains no data rows")
            
            # Connect to database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if table already exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if cursor.fetchone():
                raise ValueError(f"Table {table_name} already exists in session database")
            
            # Create table - all columns as TEXT for simplicity
            # SQLite will handle type affinity automatically
            columns_def = ', '.join([f'"{col}" TEXT' for col in sanitized_columns])
            create_sql = f'CREATE TABLE "{table_name}" ({columns_def})'
            cursor.execute(create_sql)
            
            # Insert data
            placeholders = ', '.join(['?' for _ in sanitized_columns])
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
            
            cursor.executemany(insert_sql, rows)
            
            # Store metadata about the dataset
            cursor.execute("""
                INSERT INTO _session_metadata (key, value) VALUES (?, ?)
            """, (f'dataset_{dataset_id}_table', table_name))
            
            cursor.execute("""
                INSERT INTO _session_metadata (key, value) VALUES (?, ?)
            """, (f'dataset_{dataset_id}_loaded_at', datetime.utcnow().isoformat()))
            
            conn.commit()
            
            row_count = len(rows)
            
            logger.info(
                f"Loaded dataset {dataset_id} into session {session_id}: "
                f"{table_name} with {row_count} rows, {len(sanitized_columns)} columns"
            )
            
            conn.close()
            
            return {
                'table_name': table_name,
                'row_count': row_count,
                'columns': list(zip(headers, sanitized_columns)),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_id}: {e}")
            raise
    
    def execute_query(
        self,
        session_id: int,
        query_text: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute a SQL query against the session's database.
        
        Args:
            session_id: The collaboration session ID
            query_text: SQL query to execute
            timeout: Query timeout in seconds
        
        Returns:
            Dictionary with query results including columns, rows, row_count
        """
        db_path = self._get_db_path(session_id)
        
        if not db_path.exists():
            raise ValueError(f"No database found for session {session_id}")
        
        # Security: Only allow SELECT statements
        query_upper = query_text.strip().upper()
        if not query_upper.startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        # Additional security checks
        dangerous_keywords = ['ATTACH', 'DETACH', 'PRAGMA', 'VACUUM', 'REINDEX']
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")
        
        start_time = datetime.utcnow()
        
        try:
            conn = sqlite3.connect(str(db_path), timeout=timeout)
            conn.set_trace_callback(None)  # Disable tracing for security
            
            # Set timeout and read-only mode
            conn.execute("PRAGMA query_only = ON")
            
            cursor = conn.cursor()
            cursor.execute(query_text)
            
            # Fetch results
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            conn.close()
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                'success': True,
                'columns': columns,
                'rows': rows,
                'row_count': len(rows),
                'execution_time': execution_time
            }
            
            logger.info(
                f"Query executed for session {session_id}: "
                f"{len(rows)} rows, {execution_time:.3f}s"
            )
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"Query execution failed for session {session_id}: {e}")
            raise ValueError(f"Query execution failed: {str(e)}")
    
    def get_session_schema(self, session_id: int) -> Dict[str, Any]:
        """
        Get schema information for all tables in a session's database.
        
        Args:
            session_id: The collaboration session ID
        
        Returns:
            Dictionary with table names and their schemas
        """
        db_path = self._get_db_path(session_id)
        
        if not db_path.exists():
            return {'tables': []}
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all tables except metadata
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE '_%'
            ORDER BY name
        """)
        
        tables = []
        for (table_name,) in cursor.fetchall():
            # Get table schema
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = [
                {'name': row[1], 'type': row[2]}
                for row in cursor.fetchall()
            ]
            
            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]
            
            tables.append({
                'name': table_name,
                'columns': columns,
                'row_count': row_count
            })
        
        conn.close()
        
        return {'tables': tables}
    
    def delete_session_database(self, session_id: int) -> bool:
        """
        Delete the SQLite database for a session.
        
        Args:
            session_id: The collaboration session ID
        
        Returns:
            True if database was deleted, False if it didn't exist
        """
        db_path = self._get_db_path(session_id)
        
        if db_path.exists():
            db_path.unlink()
            logger.info(f"Deleted database for session {session_id}")
            return True
        
        return False
