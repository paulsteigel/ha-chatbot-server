import express, { Request, Response } from 'express';
import axios from 'axios';
import cors from 'cors';
import { ZingMp3 } from './zingmp3';

const app = express();
const PORT = process.env.PORT || 5001;

app.use(cors());
app.use(express.json());

// ============= API ENDPOINTS ============= //

// Health check
app.get('/health', (req: Request, res: Response) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API: Tìm kiếm bài hát
app.get('/api/search', async (req: Request, res: Response) => {
  try {
    const query = req.query.q as string;
    if (!query) {
      return res.status(400).json({ error: 'Missing query parameter' });
    }

    console.log(`[SEARCH] Query: ${query}`);
    const result = await ZingMp3.search(query);
    res.json(result);
  } catch (error: any) {
    console.error('[SEARCH ERROR]', error.message);
    res.status(500).json({ error: error.message });
  }
});

// API: Lấy link streaming (cho ESP32S3)
app.get('/api/stream/:songId', async (req: Request, res: Response) => {
  try {
    const { songId } = req.params;
    console.log(`[STREAM] Song ID: ${songId}`);
    
    const result = await ZingMp3.getSong(songId);
    
    if (result.err === 0 && result.data) {
      // Trả về URL cho ESP32S3
      const streamUrl = result.data['128'] || result.data['320'];
      res.json({
        success: true,
        songId: songId,
        streamUrl: streamUrl,
        quality: result.data['128'] ? '128kbps' : '320kbps',
        data: result.data
      });
    } else {
      res.status(404).json({ success: false, error: 'Song not found or unavailable' });
    }
  } catch (error: any) {
    console.error('[STREAM ERROR]', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// API: Lấy thông tin bài hát
app.get('/api/song/:songId', async (req: Request, res: Response) => {
  try {
    const { songId } = req.params;
    const result = await ZingMp3.getInfoSong(songId);
    res.json(result);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// API: Lấy danh sách playlist
app.get('/api/playlist/:playlistId', async (req: Request, res: Response) => {
  try {
    const { playlistId } = req.params;
    const result = await ZingMp3.getDetailPlaylist(playlistId);
    res.json(result);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// Proxy stream (để tránh CORS từ ESP32)
app.get('/proxy', async (req: Request, res: Response) => {
  try {
    const url = req.query.url as string;
    if (!url) {
      return res.status(400).json({ error: 'Missing URL parameter' });
    }

    console.log(`[PROXY] Streaming from: ${url}`);
    
    const response = await axios.get(url, {
      responseType: 'stream',
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Range': req.headers.range || ''
      }
    });

    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Accept-Ranges', 'bytes');
    
    if (response.headers['content-length']) {
      res.setHeader('Content-Length', response.headers['content-length']);
    }
    
    response.data.pipe(res);
  } catch (error: any) {
    console.error('[PROXY ERROR]', error.message);
    res.status(500).json({ error: error.message });
  }
});

// ============= WEB INTERFACE ============= //

app.get('/', (req: Request, res: Response) => {
  res.send(`
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ZingMp3-proxy - ESP32S3 Streaming</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      padding: 20px;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      background: white;
      border-radius: 20px;
      padding: 30px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }
    h1 {
      color: #667eea;
      text-align: center;
      margin-bottom: 10px;
      font-size: 2.5em;
    }
    .subtitle {
      text-align: center;
      color: #666;
      margin-bottom: 30px;
      font-size: 14px;
    }
    .api-info {
      background: #e3f2fd;
      padding: 20px;
      border-radius: 10px;
      margin-bottom: 30px;
    }
    .api-info h3 {
      color: #1976d2;
      margin-bottom: 15px;
    }
    .api-endpoint {
      background: white;
      padding: 10px;
      border-radius: 5px;
      margin-bottom: 10px;
      font-family: 'Courier New', monospace;
      font-size: 13px;
    }
    .method {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 3px;
      color: white;
      font-weight: bold;
      margin-right: 10px;
    }
    .get { background: #4caf50; }
    .search-box {
      display: flex;
      gap: 10px;
      margin-bottom: 30px;
    }
    input {
      flex: 1;
      padding: 15px;
      border: 2px solid #667eea;
      border-radius: 10px;
      font-size: 16px;
      outline: none;
    }
    button {
      padding: 15px 30px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      font-size: 16px;
      font-weight: bold;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .song-item {
      background: #f8f9fa;
      padding: 15px;
      margin-bottom: 10px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      gap: 15px;
    }
    .song-item:hover {
      background: #e9ecef;
    }
    .song-thumb {
      width: 60px;
      height: 60px;
      border-radius: 8px;
      object-fit: cover;
    }
    .song-info {
      flex: 1;
    }
    .song-title {
      font-weight: bold;
      color: #333;
      margin-bottom: 5px;
    }
    .song-artist {
      color: #666;
      font-size: 14px;
    }
    .stream-url {
      background: #263238;
      color: #aed581;
      padding: 10px;
      border-radius: 5px;
      font-family: 'Courier New', monospace;
      font-size: 11px;
      margin-top: 10px;
      word-break: break-all;
      display: none;
    }
    .stream-url.show {
      display: block;
    }
    .copy-btn {
      padding: 8px 15px;
      font-size: 13px;
      margin-left: 10px;
    }
    .player {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: white;
      padding: 20px;
      box-shadow: 0 -5px 20px rgba(0,0,0,0.1);
      display: none;
    }
    .player.active {
      display: block;
    }
    .player-content {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 20px;
    }
    .now-playing {
      display: flex;
      align-items: center;
      gap: 15px;
      flex: 1;
    }
    audio {
      width: 100%;
      max-width: 500px;
    }
    .loading {
      text-align: center;
      padding: 20px;
      color: #667eea;
    }
    .spinner {
      border: 3px solid #f3f3f3;
      border-top: 3px solid #667eea;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎵 ZingMp3-proxy</h1>
    <div class="subtitle">Streaming Server for ESP32S3 Chatbot - By Đặng Đình Ngọc</div>
    
    <div class="api-info">
      <h3>📡 API Endpoints (cho ESP32S3)</h3>
      <div class="api-endpoint">
        <span class="method get">GET</span> /api/search?q={query} - Tìm kiếm bài hát
      </div>
      <div class="api-endpoint">
        <span class="method get">GET</span> /api/stream/{songId} - Lấy link streaming
      </div>
      <div class="api-endpoint">
        <span class="method get">GET</span> /api/song/{songId} - Thông tin bài hát
      </div>
      <div class="api-endpoint">
        <span class="method get">GET</span> /proxy?url={streamUrl} - Proxy stream (tránh CORS)
      </div>
    </div>

    <div class="search-box">
      <input type="text" id="searchInput" placeholder="Nhập tên bài hát, ca sĩ..." />
      <button onclick="searchSong()">🔍 Tìm kiếm</button>
    </div>

    <div id="results"></div>
  </div>

  <div class="player" id="player">
    <div class="player-content">
      <div class="now-playing">
        <img id="playerThumb" class="song-thumb" src="" alt="">
        <div>
          <div class="song-title" id="playerTitle"></div>
          <div class="song-artist" id="playerArtist"></div>
        </div>
      </div>
      <audio id="audioPlayer" controls autoplay></audio>
    </div>
  </div>

  <script>
    let currentSongs = [];

    document.getElementById('searchInput').addEventListener('keypress', (e) => {
      if (e.key === 'Enter') searchSong();
    });

    async function searchSong() {
      const query = document.getElementById('searchInput').value.trim();
      if (!query) return;

      const resultsDiv = document.getElementById('results');
      resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Đang tìm kiếm...</div>';

      try {
        const response = await fetch('/api/search?q=' + encodeURIComponent(query));
        const data = await response.json();

        if (data.err === 0 && data.data.songs) {
          currentSongs = data.data.songs;
          displayResults(data.data.songs);
        } else {
          resultsDiv.innerHTML = '<div class="loading">❌ Không tìm thấy kết quả</div>';
        }
      } catch (error) {
        resultsDiv.innerHTML = '<div class="loading">❌ Lỗi: ' + error.message + '</div>';
      }
    }

    function displayResults(songs) {
      const resultsDiv = document.getElementById('results');
      resultsDiv.innerHTML = songs.map(song => \`
        <div class="song-item">
          <img class="song-thumb" src="\${song.thumbnail}" alt="\${song.title}">
          <div class="song-info">
            <div class="song-title">\${song.title}</div>
            <div class="song-artist">\${song.artistsNames}</div>
            <div class="stream-url" id="url-\${song.encodeId}"></div>
          </div>
          <button onclick="playSong('\${song.encodeId}')">▶ Play</button>
          <button class="copy-btn" onclick="getStreamUrl('\${song.encodeId}')">📋 Get URL</button>
        </div>
      \`).join('');
    }

    async function getStreamUrl(songId) {
      try {
        const response = await fetch('/api/stream/' + songId);
        const data = await response.json();

        if (data.success && data.streamUrl) {
          const urlDiv = document.getElementById('url-' + songId);
          urlDiv.textContent = 'Stream URL: ' + data.streamUrl;
          urlDiv.classList.add('show');
          
          // Copy to clipboard
          navigator.clipboard.writeText(data.streamUrl);
          alert('✅ Đã copy URL vào clipboard!');
        } else {
          alert('❌ Không lấy được URL');
        }
      } catch (error) {
        alert('❌ Lỗi: ' + error.message);
      }
    }

    async function playSong(songId) {
      try {
        const response = await fetch('/api/stream/' + songId);
        const data = await response.json();

        if (data.success && data.streamUrl) {
          const song = currentSongs.find(s => s.encodeId === songId);
          
          document.getElementById('playerThumb').src = song.thumbnail;
          document.getElementById('playerTitle').textContent = song.title;
          document.getElementById('playerArtist').textContent = song.artistsNames;
          document.getElementById('audioPlayer').src = data.streamUrl;
          document.getElementById('player').classList.add('active');
        } else {
          alert('❌ Không thể phát bài hát này');
        }
      } catch (error) {
        alert('❌ Lỗi: ' + error.message);
      }
    }
  </script>
</body>
</html>
  `);
});

// Start server
app.listen(PORT, () => {
  console.log('==========================================');
  console.log('🎵 ZingMp3-proxy Server');
  console.log('📅 Author: Đặng Đình Ngọc');
  console.log('🌐 Port: ' + PORT);
  console.log('🔗 Access: http://localhost:' + PORT);
  console.log('🔗 External: https://music.sfdp.net');
  console.log('==========================================');
});
