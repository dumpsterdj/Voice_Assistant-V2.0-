# voice_assistant/tts.py
"""
Text-only TTS stub — replaces speech output with printed feedback.

Every call to speak(text) just prints it on the console instead of speaking.
"""

import threading

_lock = threading.Lock()

def speak(text: str):
    """Print assistant feedback to console instead of speaking aloud."""
    with _lock:
        if text:
            print(f"[Assistant]: {text}")
