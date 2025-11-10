# voice_assistant/main.py
import argparse
from .wake import WakeAssistant
from . import tts, logger
from .config import WAKE_WORDS

def get_weather(city: str, api_key: str = None):
    import requests
    key = api_key
    if not key:
        return False, "OpenWeatherMap API key not set. Set OPENWEATHER_API_KEY env var or pass --openweather-key."
    url = f"http://api.openweathermap.org/data/2.5/weather?q={requests.utils.requote_uri(city)}&appid={key}&units=metric"
    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return False, f"Weather API error: {r.status_code} {r.text[:200]}"
        j = r.json()
        name = j.get("name")
        main = j.get("weather", [{}])[0].get("main", "")
        desc = j.get("weather", [{}])[0].get("description", "")
        temp = j.get("main", {}).get("temp")
        feels = j.get("main", {}).get("feels_like")
        humidity = j.get("main", {}).get("humidity")
        return True, f"{name}: {main} ({desc}). Temperature {temp}°C, feels like {feels}°C. Humidity {humidity}%."
    except Exception as ex:
        return False, f"Weather lookup failed: {ex}"

def parse_args():
    p = argparse.ArgumentParser(description="VoiceAssistant (Hey DJ)")
    p.add_argument("--allow-download", action="store_true", help="Allow YouTube downloads.")
    p.add_argument("--allow-arbitrary", action="store_true", help="Allow arbitrary system commands (use with caution).")
    p.add_argument("--openweather-key", default=None, help="OpenWeatherMap API key (or set OPENWEATHER_API_KEY env var).")
    return p.parse_args()

def main():
    args = parse_args()
    if args.allow_download:
        print("Downloads ENABLED for this session.")
    if args.allow_arbitrary:
        print("Arbitrary commands ENABLED for this session.")
    try:
        assistant = WakeAssistant(WAKE_WORDS, allow_download=args.allow_download, allow_arbitrary=args.allow_arbitrary, openweather_key=args.openweather_key)
    except Exception as e:
        print("Failed to initialize assistant:", e)
        tts.speak("Microphone or audio initialization failed.")
        return
    assistant.start()

if __name__ == "__main__":
    main()
