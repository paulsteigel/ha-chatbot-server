# app/music_service.py
"""
Music Service - Interface with YouTube Audio Streaming Server
"""
import logging
import httpx
from typing import Optional, Dict, List

logger = logging.getLogger('MusicService')

class MusicService:
    """Service to search and stream music from YouTube"""
    
    def __init__(self, music_server_url: str = "https://music.sfdp.net"):
        """
        Initialize Music Service
        
        Args:
            music_server_url: Base URL of YouTube streaming server
        """
        self.base_url = music_server_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"🎵 Music Service initialized: {self.base_url}")
    
    async def search_music(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search for music on YouTube
        
        Args:
            query: Search query (e.g., "the tempest piano")
            max_results: Maximum number of results
            
        Returns:
            List of search results with id, title, artist, duration, audio_url
        """
        try:
            logger.info(f"🔍 Searching music: '{query}' (max: {max_results})")
            
            response = await self.client.get(
                f"{self.base_url}/search",
                params={
                    'q': query,
                    'max_results': max_results
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and data.get('results'):
                    results = data['results']
                    
                    # Add full audio_url to each result
                    for result in results:
                        result['audio_url'] = f"{self.base_url}/stream?video_id={result['id']}"
                    
                    logger.info(f"✅ Found {len(results)} results")
                    return results
                else:
                    logger.warning("❌ No results found")
                    return []
            else:
                logger.error(f"❌ Search failed: HTTP {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"❌ Music search error: {e}")
            return []
    
    async def get_first_result(self, query: str) -> Optional[Dict]:
        """
        Get first search result (convenience method)
        
        Returns:
            Dict with id, title, artist, audio_url or None
        """
        results = await self.search_music(query, max_results=1)
        return results[0] if results else None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("🛑 Music Service closed")
