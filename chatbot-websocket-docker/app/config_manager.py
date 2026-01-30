"""
Config Manager - Load configuration from MySQL
✅ Secure: No API keys in code or .env
✅ Dynamic: Update config without restart
✅ Fallback: Use environment variables if DB unavailable
"""

import logging
import aiomysql
import json
from typing import Optional, Dict, Any
from datetime import datetime


class ConfigManager:
    """Manage configuration from MySQL database"""
    
    def __init__(self, db_url: str):
        """Initialize config manager"""
        self.logger = logging.getLogger('ConfigManager')
        self.db_url = db_url
        self.pool: Optional[aiomysql.Pool] = None
        self.config_cache: Dict[str, Any] = {}
        self.cache_time: Optional[datetime] = None
        self.cache_ttl = 300  # 5 minutes
        # Parse connection string
        self._parse_url(db_url)
        
        self.logger.info("🔐 Config Manager initialized")
        self.logger.info("   ✅ Source: MySQL database")
        self.logger.info("   ✅ Cache TTL: 5 minutes")
    
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
                minsize=1,
                maxsize=5,
                autocommit=True,
                pool_recycle=3600,
                connect_timeout=10
            )
            
            self.logger.info("✅ MySQL pool created")
            
            # Create config table if not exists
            await self._create_table()
            
            # Load initial config
            await self.load_config()
            
        except Exception as e:
            self.logger.error(f"❌ MySQL connection error: {e}")
            raise
    
    async def _create_table(self):
        """Create config table if not exists"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS chatbot_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT,
            category VARCHAR(50),
            description TEXT,
            is_secret BOOLEAN DEFAULT FALSE,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_category (category),
            INDEX idx_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(create_sql)
                    self.logger.info("✅ Table 'chatbot_config' ready")
        
        except Exception as e:
            self.logger.error(f"❌ Create table error: {e}")
    
    async def load_config(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Load configuration from MySQL
        
        Args:
            force_refresh: Force reload from database (ignore cache)
        
        Returns:
            Dict of configuration key-value pairs
        """
        # Check cache
        if not force_refresh and self.config_cache and self.cache_time:
            age = (datetime.now() - self.cache_time).total_seconds()
            if age < self.cache_ttl:
                self.logger.debug(f"✅ Using cached config (age: {age:.0f}s)")
                return self.config_cache
        
        if not self.pool:
            self.logger.warning("⚠️ Pool not available, using empty config")
            return {}
        
        try:
            self.logger.info("🔄 Loading config from MySQL...")
            
            sql = "SELECT config_key, config_value, is_secret FROM chatbot_config"
            
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql)
                    rows = await cursor.fetchall()
            
            # Build config dict
            config = {}
            secret_count = 0
            
            for row in rows:
                key = row['config_key']
                value = row['config_value']
                is_secret = row['is_secret']
                
                # Parse JSON values
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string
                
                config[key] = value
                
                if is_secret:
                    secret_count += 1
            
            # Update cache
            self.config_cache = config
            self.cache_time = datetime.now()
            
            self.logger.info(f"✅ Loaded {len(config)} config items")
            self.logger.info(f"   🔐 Secrets: {secret_count}")
            self.logger.info(f"   📦 Regular: {len(config) - secret_count}")
            
            return config
        
        except Exception as e:
            self.logger.error(f"❌ Load config error: {e}")
            return self.config_cache or {}
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if not self.config_cache:
            await self.load_config()
        
        return self.config_cache.get(key, default)
    
    async def set(self, key: str, value: Any, category: str = None, 
                  description: str = None, is_secret: bool = False):
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
            category: Category (azure, tts, stt, etc.)
            description: Human-readable description
            is_secret: Whether this is a secret (API key, password)
        """
        if not self.pool:
            raise Exception("MySQL pool not available")
        
        # Convert value to JSON if needed
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        sql = """
        INSERT INTO chatbot_config 
        (config_key, config_value, category, description, is_secret)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            config_value = VALUES(config_value),
            category = VALUES(category),
            description = VALUES(description),
            is_secret = VALUES(is_secret),
            updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        sql,
                        (key, value_str, category, description, is_secret)
                    )
            
            # Update cache
            self.config_cache[key] = value
            
            log_value = "***" if is_secret else value_str[:50]
            self.logger.info(f"✅ Config updated: {key} = {log_value}")
        
        except Exception as e:
            self.logger.error(f"❌ Set config error: {e}")
            raise
    
    async def initialize_defaults(self):
        """
        Initialize database with default configuration
        (Run this once to populate the database)
        """
        self.logger.info("🔄 Initializing default configuration...")
        
        defaults = [
            # Azure OpenAI
            ("azure_api_key", "YOUR_KEY_HERE", "azure", "Azure OpenAI API Key", True),
            ("azure_endpoint", "https://admin-mkz8dkfn-eastus2.openai.azure.com/openai/v1/", "azure", "Azure OpenAI Endpoint", False),
            ("azure_deployment", "DeepSeek-V3.2", "azure", "Azure Deployment Name", False),
            ("azure_api_version", "2024-12-01-preview", "azure", "Azure API Version", False),
            ("ai_model", "deepseek-chat", "azure", "AI Model Name", False),
            ("ai_provider", "azure", "azure", "AI Provider", False),
            
            # Azure Speech
            ("azure_speech_key", "YOUR_KEY_HERE", "tts", "Azure Speech API Key", True),
            ("azure_speech_region", "eastus", "tts", "Azure Speech Region", False),
            ("tts_provider", "azure_speech", "tts", "TTS Provider", False),
            ("tts_voice_vi", "en-US-Ava:DragonHDLatestNeural", "tts", "Vietnamese TTS Voice", False),
            ("tts_voice_en", "en-US-AvaMultilingualNeural", "tts", "English TTS Voice", False),
            
            # STT
            ("stt_provider", "azure_speech", "stt", "STT Provider", False),
            ("groq_api_key", "YOUR_KEY_HERE", "stt", "Groq API Key (fallback)", True),
            
            # Fallback providers
            ("openai_api_key", "", "fallback", "OpenAI API Key", True),
            ("openai_base_url", "https://api.openai.com/v1", "fallback", "OpenAI Base URL", False),
            ("deepseek_api_key", "", "fallback", "DeepSeek API Key", True),
            
            # Piper
            ("piper_host", "addon_core_piper", "piper", "Piper Host", False),
            ("piper_port", "10200", "piper", "Piper Port", False),
            ("piper_voice_vi", "vi_VN-vais1000-medium", "piper", "Piper Vietnamese Voice", False),
            ("piper_voice_en", "en_US-lessac-medium", "piper", "Piper English Voice", False),
            
            # Music
            ("music_service_url", "http://music.sfdp.net", "music", "Music Service URL", False),
            ("enable_music_playback", "true", "music", "Enable Music Playback", False),
            
            # Chat settings
            ("temperature", "0.7", "chat", "AI Temperature", False),
            ("max_tokens", "500", "chat", "Max Tokens", False),
            ("max_context", "10", "chat", "Max Context Messages", False),
            
            # TTS settings
            ("tts_remove_emoji", "true", "tts", "Remove Emoji from TTS", False),
            ("tts_remove_markdown", "true", "tts", "Remove Markdown from TTS", False),
            
            # System
            ("log_level", "INFO", "system", "Log Level", False),
        ]
        
        for key, value, category, description, is_secret in defaults:
            try:
                await self.set(key, value, category, description, is_secret)
            except Exception as e:
                self.logger.error(f"❌ Failed to set {key}: {e}")
        
        self.logger.info(f"✅ Initialized {len(defaults)} default config items")
    
    async def get_all_by_category(self, category: str = None) -> Dict[str, Any]:
        """Get all config items, optionally filtered by category"""
        if not self.pool:
            return {}
        
        if category:
            sql = """
            SELECT config_key, config_value, category, description, is_secret, updated_at
            FROM chatbot_config
            WHERE category = %s
            ORDER BY config_key
            """
            params = (category,)
        else:
            sql = """
            SELECT config_key, config_value, category, description, is_secret, updated_at
            FROM chatbot_config
            ORDER BY category, config_key
            """
            params = ()
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, params)
                    rows = await cursor.fetchall()
            
            # Mask secrets
            for row in rows:
                if row['is_secret'] and row['config_value']:
                    row['config_value'] = "***HIDDEN***"
            
            return rows
        
        except Exception as e:
            self.logger.error(f"❌ Get all config error: {e}")
            return {}
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.logger.info("🔐 Config Manager closed")
