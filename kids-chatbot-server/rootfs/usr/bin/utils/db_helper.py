# rootfs/usr/bin/utils/db_helper.py

import mysql.connector
from mysql.connector import pooling
import json
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class DatabaseHelper:
    """Helper class for MySQL database operations"""
    
    _pool = None
    
    @classmethod
    def initialize(cls, db_config):
        """Initialize database connection pool"""
        try:
            cls._pool = pooling.MySQLConnectionPool(
                pool_name="chatbot_pool",
                pool_size=5,
                pool_reset_session=True,
                **db_config
            )
            logger.info("✅ MySQL connection pool initialized")
            
            # Tạo bảng nếu chưa tồn tại
            cls._create_tables()
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    @classmethod
    def _create_tables(cls):
        """Tạo các bảng cần thiết"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        
        try:
            # Bảng sessions: Lưu thông tin session
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    language VARCHAR(10) NOT NULL DEFAULT 'vi',
                    voice VARCHAR(20) NOT NULL DEFAULT 'alloy',
                    voice_override BOOLEAN DEFAULT FALSE,
                    title VARCHAR(255),
                    created_at DATETIME NOT NULL,
                    last_activity DATETIME NOT NULL,
                    message_count INT DEFAULT 0,
                    metadata JSON,
                    INDEX idx_last_activity (last_activity),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Bảng messages: Lưu từng tin nhắn
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    role ENUM('system', 'user', 'assistant') NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    tokens_used INT DEFAULT 0,
                    metadata JSON,
                    INDEX idx_session (session_id),
                    INDEX idx_timestamp (timestamp),
                    FOREIGN KEY (session_id) REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE,
                    FULLTEXT INDEX ft_content (content)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Bảng summaries: Lưu tóm tắt conversation (cho tương lai)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_summaries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    summary TEXT NOT NULL,
                    message_range VARCHAR(50),
                    created_at DATETIME NOT NULL,
                    tokens_saved INT DEFAULT 0,
                    INDEX idx_session (session_id),
                    FOREIGN KEY (session_id) REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            conn.commit()
            logger.info("✅ Database tables verified/created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            conn.rollback()
            raise
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def save_session(cls, session_id, session_data):
        """Lưu hoặc cập nhật session"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO chatbot_sessions 
                (session_id, language, voice, voice_override, title, created_at, last_activity, message_count, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    language = VALUES(language),
                    voice = VALUES(voice),
                    voice_override = VALUES(voice_override),
                    last_activity = VALUES(last_activity),
                    message_count = VALUES(message_count),
                    metadata = VALUES(metadata)
            """, (
                session_id,
                session_data.get('language', 'vi'),
                session_data.get('voice', 'alloy'),
                session_data.get('voice_override', False),
                session_data.get('metadata', {}).get('title', f"Conversation {session_id[:8]}"),
                session_data['created_at'],
                session_data['last_activity'],
                len(session_data['messages']) - 1,  # -1 để không đếm system message
                json.dumps(session_data.get('metadata', {}))
            ))
            
            conn.commit()
            logger.debug(f"💾 Saved session {session_id} to database")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save session {session_id}: {e}")
            conn.rollback()
            return False
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def save_message(cls, session_id, role, content, tokens_used=0):
        """Lưu tin nhắn"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO chatbot_messages 
                (session_id, role, content, timestamp, tokens_used)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session_id,
                role,
                content,
                datetime.now(),
                tokens_used
            ))
            
            conn.commit()
            logger.debug(f"💬 Saved {role} message to database")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save message: {e}")
            conn.rollback()
            return False
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def load_session(cls, session_id):
        """Load session từ database"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Load session info
            cursor.execute("""
                SELECT * FROM chatbot_sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            session = cursor.fetchone()
            
            if not session:
                return None
            
            # Load messages
            cursor.execute("""
                SELECT role, content, timestamp 
                FROM chatbot_messages 
                WHERE session_id = %s 
                ORDER BY timestamp ASC
            """, (session_id,))
            
            messages = [
                {
                    'role': msg['role'],
                    'content': msg['content']
                }
                for msg in cursor.fetchall()
            ]
            
            # Reconstruct session data
            session_data = {
                'messages': messages,
                'language': session['language'],
                'voice': session['voice'],
                'voice_override': bool(session['voice_override']),
                'created_at': session['created_at'],
                'last_activity': session['last_activity'],
                'metadata': json.loads(session['metadata']) if session['metadata'] else {}
            }
            
            logger.info(f"📂 Loaded session {session_id} from database ({len(messages)} messages)")
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load session {session_id}: {e}")
            return None
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def delete_session(cls, session_id):
        """Xóa session (cascade sẽ xóa messages)"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM chatbot_sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            conn.commit()
            logger.info(f"🗑️ Deleted session {session_id} from database")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete session {session_id}: {e}")
            conn.rollback()
            return False
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def cleanup_old_sessions(cls, timeout_minutes=30):
        """Xóa sessions cũ"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM chatbot_sessions 
                WHERE last_activity < DATE_SUB(NOW(), INTERVAL %s MINUTE)
            """, (timeout_minutes,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"⏰ Cleaned up {deleted_count} expired sessions")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup sessions: {e}")
            conn.rollback()
            return 0
        
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def get_session_stats(cls):
        """Lấy thống kê"""
        conn = cls._pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(message_count) as total_messages,
                    AVG(message_count) as avg_messages_per_session
                FROM chatbot_sessions
            """)
            
            stats = cursor.fetchone()
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}
        
        finally:
            cursor.close()
            conn.close()
