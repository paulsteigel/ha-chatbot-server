# File: app/utils/audio_converter.py
"""
Audio Converter - Convert MP3/WAV to ESP32-compatible WAV format
"""

import io
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def convert_to_wav_16k(
    audio_bytes: bytes,
    source_format: str = "mp3"
) -> bytes:
    """
    Convert audio (MP3/WAV) to WAV 16kHz mono 16-bit for ESP32.
    
    Args:
        audio_bytes: Audio data (MP3 or WAV)
        source_format: "mp3" or "wav"
        
    Returns:
        WAV bytes (16kHz, mono, 16-bit PCM)
    """
    try:
        # Load audio
        if source_format == "mp3":
            audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        elif source_format == "wav":
            audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))
        else:
            raise ValueError(f"Unsupported format: {source_format}")
        
        # Convert to ESP32 spec: 16kHz, mono, 16-bit
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)
        audio = audio.set_sample_width(2)  # 16-bit
        
        # Export to WAV
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()
        
        logger.debug(
            f"✅ Audio conversion: {source_format.upper()} "
            f"({len(audio_bytes)} bytes) → WAV 16kHz "
            f"({len(wav_bytes)} bytes)"
        )
        
        return wav_bytes
        
    except Exception as e:
        logger.error(f"❌ Audio conversion failed: {e}")
        raise
