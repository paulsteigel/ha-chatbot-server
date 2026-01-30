"""
Initialize MySQL configuration
Run this ONCE to populate the database with your API keys
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config_manager import ConfigManager


async def main():
    """Initialize configuration"""
    
    # Get MySQL URL from environment
    mysql_url = os.getenv('MYSQL_URL')
    if not mysql_url:
        print("❌ MYSQL_URL not set!")
        print("   Set it: export MYSQL_URL='mysql://user:pass@host/db'")
        return
    
    print("🔐 Initializing Config Manager...")
    config_manager = ConfigManager(mysql_url)
    
    try:
        await config_manager.connect()
        
        # Initialize with defaults
        await config_manager.initialize_defaults()
        
        print("\n✅ Configuration initialized!")
        print("\n📝 Next steps:")
        print("   1. Update API keys in MySQL:")
        print("      UPDATE chatbot_config SET config_value='YOUR_KEY' WHERE config_key='azure_api_key';")
        print("   2. Restart the chatbot")
        
    finally:
        await config_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
