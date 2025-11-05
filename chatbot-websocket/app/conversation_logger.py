"""
Conversation Logger - Save conversations to MySQL
"""

import logging
import aiomysql
from datetime import datetime
from typing import Optional, Dict, List


class ConversationLogger:
    """Log conversations to MySQL database"""
    
    def __init__(self, db_url: str):
        """
        Initialize logger
        
        Args:
            db_url: MySQL connection URL
                   Format: mysql://user:pass@host/database?charset=utf8mb4
        """
        self.logger = logging.getLogger('ConversationLogger')
        self.db_url = db_url
        self.pool: Optional[aiomysql.Pool] = None
        
        # Parse connection string
        self._parse_url(db_url)
        
        self.logger.info("💾 Conversation Logger initialized")
    
    def _parse_url(self, url: str):
        """Parse MySQL connection URL"""
        # mysql://paulsteigel:D1ndh1sk@192.168.100.251/homeassistant?charset=utf8mb4
        import re
        
        pattern = r'mysql://([^:]+):([^@]+)@([^/]+)/([^?]+)'
        match = re.match(pattern, url)
        
        if not match:
            raise ValueError(f"Invalid MySQL URL: {url}")
        
        self.user = match.group(1)
        self.password = match.group(2)
        self.host = match.group(3)
        self.database = match.group(4)
        
        self.logger.info(f"   Host: {self.host}")
        self.logger.info(f"   Database: {self.database}")
        self.logger.info(f"   User: {self.user}")
    
    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                user=self.user,
                password=self.password,
                db=self.database,
                charset='utf8mb4',
                minsize=1,
                maxsize=10,
                autocommit=True
            )
            
            self.logger.info("✅ MySQL pool created")
            
            # Create table if not exists
            await self._create_table()
            
        except Exception as e:
            self.logger.error(f"❌ MySQL connection error: {e}")
            raise
    
    async def _create_table(self):
        """Create conversations table if not exists"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(100) NOT NULL,
            device_type VARCHAR(50),
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            model VARCHAR(50),
            provider VARCHAR(50),
            response_time FLOAT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_device (device_id),
            INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(create_sql)
                    self.logger.info("✅ Table 'conversations' ready")
        
        except Exception as e:
            self.logger.error(f"❌ Create table error: {e}")
    
    async def log_conversation(
        self,
        device_id: str,
        device_type: str,
        user_message: str,
        ai_response: str,
        model: str,
        provider: str,
        response_time: float
    ):
        """
        Log a conversation to database
        
        Args:
            device_id: Device ID
            device_type: Device type (web-browser, esp32, etc.)
            user_message: User's message
            ai_response: AI's response
            model: AI model name
            provider: AI provider (openai, deepseek)
            response_time: Response time in seconds
        """
        if not self.pool:
            self.logger.warning("⚠️ MySQL pool not initialized, skipping log")
            return
        
        insert_sql = """
        INSERT INTO conversations 
        (device_id, device_type, user_message, ai_response, model, provider, response_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        insert_sql,
                        (device_id, device_type, user_message, ai_response, 
                         model, provider, response_time)
                    )
                    
            self.logger.info(f"💾 Conversation saved: {device_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Log conversation error: {e}")
    
    async def get_history(
        self,
        device_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get conversation history
        
        Args:
            device_id: Optional device ID filter
            limit: Max records to return
        
        Returns:
            List of conversation records
        """
        if not self.pool:
            return []
        
        if device_id:
            sql = """
            SELECT * FROM conversations 
            WHERE device_id = %s 
            ORDER BY timestamp DESC 
            LIMIT %s
            """
            params = (device_id, limit)
        else:
            sql = """
            SELECT * FROM conversations 
            ORDER BY timestamp DESC 
            LIMIT %s
            """
            params = (limit,)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, params)
                    rows = await cursor.fetchall()
                    return rows
        
        except Exception as e:
            self.logger.error(f"❌ Get history error: {e}")
            return []
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.logger.info("💾 MySQL pool closed")
