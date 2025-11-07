"""
Conversation Logger - Save conversations to MySQL
✅ UPDATED: Health check, retry logic, metrics, auto-reconnect
"""

import logging
import aiomysql
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, List


class ConversationLogger:
    """Log conversations to MySQL database with health monitoring"""
    
    def __init__(self, db_url: str):
        """Initialize logger with health monitoring"""
        self.logger = logging.getLogger('ConversationLogger')
        self.db_url = db_url
        self.pool: Optional[aiomysql.Pool] = None
        
        # Health check
        self.last_health_check = None
        self.health_check_interval = 60  # seconds
        
        # Metrics
        self.stats = {
            'total_attempts': 0,
            'successful_logs': 0,
            'failed_logs': 0,
            'last_error': None,
            'last_success': None,
            'last_error_time': None,
            'consecutive_failures': 0  # Track consecutive failures
        }
        
        # Parse connection string
        self._parse_url(db_url)
        
        self.logger.info("💾 Conversation Logger initialized")
        self.logger.info("   ✅ Health check: Enabled (every 60s)")
        self.logger.info("   ✅ Auto-retry: Enabled (3 attempts)")
        self.logger.info("   ✅ Auto-reconnect: Enabled")
    
    def _parse_url(self, url: str):
        """Parse MySQL connection URL"""
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
            self.logger.info("🔄 Creating MySQL connection pool...")
            
            self.pool = await aiomysql.create_pool(
                host=self.host,
                user=self.user,
                password=self.password,
                db=self.database,
                charset='utf8mb4',
                minsize=2,           # Increased from 1
                maxsize=20,          # Increased from 10
                autocommit=True,
                pool_recycle=3600,   # Recycle connections after 1h
                connect_timeout=10   # Connection timeout
            )
            
            self.logger.info("✅ MySQL pool created")
            self.logger.info(f"   Pool size: 2-20 connections")
            
            # Create table if not exists
            await self._create_table()
            
            # Reset failure counter on successful connect
            self.stats['consecutive_failures'] = 0
            
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
    
    async def _ensure_pool_healthy(self):
        """
        ✅ ENSURE MYSQL POOL IS HEALTHY
        - Check connection every 60s
        - Auto-reconnect if dead
        """
        now = time.time()
        
        # Skip if checked recently
        if (self.last_health_check and 
            now - self.last_health_check < self.health_check_interval):
            return
        
        try:
            if not self.pool:
                self.logger.warning("⚠️ Pool is None, reconnecting...")
                await self.connect()
                return
            
            # Test connection with timeout
            try:
                async with asyncio.timeout(5):
                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            await cursor.fetchone()
            except asyncio.TimeoutError:
                raise Exception("Health check timeout")
            
            self.last_health_check = now
            self.logger.debug("✅ MySQL pool healthy")
            
            # Log stats if there were recent failures
            if self.stats['consecutive_failures'] > 0:
                self.logger.info(
                    f"✅ MySQL recovered after {self.stats['consecutive_failures']} failures"
                )
                self.stats['consecutive_failures'] = 0
            
        except Exception as e:
            self.logger.error(f"❌ Pool health check failed: {e}")
            await self._reconnect_pool()
    
    async def _reconnect_pool(self):
        """Reconnect MySQL pool"""
        try:
            self.logger.warning("🔄 Reconnecting MySQL pool...")
            
            if self.pool:
                self.pool.close()
                await self.pool.wait_closed()
            
            await self.connect()
            self.logger.info("✅ MySQL pool reconnected")
            self.last_health_check = time.time()
            
        except Exception as e:
            self.logger.error(f"❌ Reconnect failed: {e}")
            self.stats['consecutive_failures'] += 1
    
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
        ✅ LOG CONVERSATION WITH RETRY & HEALTH CHECK
        
        Args:
            device_id: Device ID
            device_type: Device type (web-browser, esp32, etc.)
            user_message: User's question (câu hỏi)
            ai_response: AI's response (câu trả lời)
            model: AI model name
            provider: AI provider (openai, deepseek)
            response_time: Response time in seconds
        """
        self.stats['total_attempts'] += 1
        
        # ✅ CHECK POOL HEALTH FIRST
        await self._ensure_pool_healthy()
        
        if not self.pool:
            self.logger.error("❌ CRITICAL: MySQL pool not available, cannot log!")
            self.logger.error(f"   Lost message from {device_id}: '{user_message[:50]}...'")
            self.stats['failed_logs'] += 1
            self.stats['consecutive_failures'] += 1
            return
        
        insert_sql = """
        INSERT INTO conversations 
        (device_id, device_type, user_message, ai_response, model, provider, response_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # ✅ RETRY LOGIC
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # Use timeout for each attempt
                try:
                    async with asyncio.timeout(10):  # 10s timeout
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cursor:
                                await cursor.execute(
                                    insert_sql,
                                    (device_id, device_type, user_message, ai_response, 
                                     model, provider, response_time)
                                )
                except asyncio.TimeoutError:
                    raise Exception(f"Insert timeout on attempt {attempt + 1}")
                
                # ✅ SUCCESS!
                self.stats['successful_logs'] += 1
                self.stats['last_success'] = time.time()
                self.stats['consecutive_failures'] = 0
                
                self.logger.info(f"💾 Conversation saved: {device_id}")
                self.logger.debug(f"   Question: {user_message[:50]}...")
                self.logger.debug(f"   Response: {ai_response[:50]}...")
                
                # Log stats periodically
                if self.stats['successful_logs'] % 10 == 0:
                    self._log_stats()
                
                return  # ← Exit on success
                
            except Exception as e:
                self.logger.error(
                    f"❌ Log attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                
                if "pool" in str(e).lower() or "connection" in str(e).lower():
                    # Connection issue - try reconnect
                    self.logger.warning("🔄 Connection issue detected, forcing reconnect...")
                    await self._reconnect_pool()
            
            # Retry with backoff
            if attempt < max_retries - 1:
                self.logger.info(f"⏳ Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        # ❌ ALL RETRIES FAILED
        self.stats['failed_logs'] += 1
        self.stats['consecutive_failures'] += 1
        self.stats['last_error'] = f"Failed after {max_retries} attempts"
        self.stats['last_error_time'] = time.time()
        
        self.logger.error(
            f"❌ CRITICAL: Failed to log conversation from {device_id} "
            f"after {max_retries} attempts!"
        )
        self.logger.error(f"   Lost question: '{user_message[:80]}...'")
        
        # Alert if too many consecutive failures
        if self.stats['consecutive_failures'] >= 5:
            self.logger.error(
                f"🚨 ALERT: {self.stats['consecutive_failures']} consecutive failures! "
                f"MySQL may be down!"
            )
    
    def _log_stats(self):
        """Log statistics"""
        total = self.stats['total_attempts']
        success = self.stats['successful_logs']
        failed = self.stats['failed_logs']
        
        if total > 0:
            success_rate = (success / total) * 100
            self.logger.info(
                f"📊 MySQL Stats: {success}/{total} "
                f"({success_rate:.1f}% success, {failed} failed)"
            )
            
            if failed > 0:
                self.logger.warning(
                    f"   ⚠️ {failed} conversations were NOT logged!"
                )
    
    def get_stats(self) -> dict:
        """Get logging statistics"""
        stats = self.stats.copy()
        
        # Add success rate
        if stats['total_attempts'] > 0:
            stats['success_rate'] = (
                stats['successful_logs'] / stats['total_attempts'] * 100
            )
        else:
            stats['success_rate'] = 0.0
        
        # Add health status
        if not self.pool:
            stats['health'] = 'disconnected'
        elif stats['consecutive_failures'] >= 5:
            stats['health'] = 'critical'
        elif stats['consecutive_failures'] > 0:
            stats['health'] = 'degraded'
        else:
            stats['health'] = 'healthy'
        
        return stats
    
    async def get_history(
        self,
        device_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get conversation history"""
        if not self.pool:
            self.logger.warning("⚠️ Pool not available for get_history")
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
            
            # Log final stats
            self._log_stats()