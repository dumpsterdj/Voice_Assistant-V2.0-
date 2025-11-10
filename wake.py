# voice_assistant/wake.py
"""
Improved background wake-word detector with debounce and non-blocking recognition.

Notes:
- Prints recognized text for debugging (no TTS calls).
- Uses overlapping recording windows (half-overlap) to reduce misses.
- Recognition runs in worker threads so background loop is non-blocking.
- Debounce prevents immediate retrigger/looping when wake is spoken repeatedly.
- Pause/resume background listener during active listening to avoid overlap.
- Tune CHUNK_SECONDS and DEBOUNCE_SECONDS if needed.
"""

import io
import re
import threading
import time
import urllib.parse
import webbrowser
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr

from . import config, logger  # assumes config.py exists in package
from .nlp_engine import NLPEngine
from .commands import run_command, run_raw_command
from .youtube_utils import yt_search_top_url, yt_download

# ------------------- TUNABLES -------------------
SAMPLE_RATE = 16000
CHANNELS = 1

# background chunk length (seconds). shorter -> lower latency, but may cut phrases.
# use 1.2 - 1.6 normally. If you still miss wake, increase slightly.
CHUNK_SECONDS = 3.5

# overlap between successive recordings. 0.5 = half-overlap (good default)
OVERLAP_FACTOR = 0.5

# after a wake is handled or detected, ignore further wake events for this many seconds
DEBOUNCE_SECONDS = 3.0

# max phrase_time_limit used when actively listening for a command
ACTIVE_LISTEN_SECONDS = 10

# ------------------- helpers -------------------
def _record_chunk(seconds: float = CHUNK_SECONDS, samplerate: int = SAMPLE_RATE):
    """Record raw float32 numpy array for given seconds."""
    try:
        data = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=CHANNELS, dtype="float32")
        sd.wait()
        return np.squeeze(data)
    except Exception as e:
        print("sounddevice record error:", e)
        return None


def _np_to_wav_bytes(data: np.ndarray, samplerate: int = SAMPLE_RATE):
    """Convert numpy audio (float32) into wav bytes (16-bit PCM)."""
    if data is None:
        return None
    try:
        # clamp to -1..1 then convert to int16
        clipped = np.clip(data, -1.0, 1.0)
        int16 = (clipped * 32767).astype("int16")
        buf = io.BytesIO()
        sf.write(buf, int16, samplerate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf
    except Exception as e:
        print("error converting audio to wav bytes:", e)
        return None


# ------------------- WakeAssistant -------------------
class WakeAssistant:
    def __init__(self, wake_regex: str, allow_download=False, allow_arbitrary=False, openweather_key=None):
        # compiled wake regex (from config)
        self.wake_re = re.compile(wake_regex, flags=re.IGNORECASE)
        self.allow_download = allow_download
        self.allow_arbitrary = allow_arbitrary
        self.openweather_key = openweather_key

        # state
        self.running = False
        self._bg_paused = False               # NEW: pause flag for the background loop
        self.busy_lock = threading.Lock()
        self.last_wake_time = 0.0

        # components
        self.nlp = NLPEngine()
        self.recognizer = sr.Recognizer()

        # device sanity: you can set sd.default.device = (input_index, output_index) here if needed
        # sd.default.device = None

        # pre-warm microphone / recognizer (brief, avoid long blocking)
        try:
            # a short, non-blocking check to ensure device is accessible
            sd.check_input_settings(samplerate=SAMPLE_RATE, channels=CHANNELS)
        except Exception as e:
            print("Warning: sounddevice input check failed:", e)

    # ---------- lifecycle ----------
    def start(self):
        self.running = True
        print("[System] Assistant starting. Say 'hey DJ' to wake me.")
        threading.Thread(target=self._background_loop, daemon=True).start()
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        print("[System] Assistant shutting down.")
        time.sleep(0.2)

    # ---------- background control ----------
    def _pause_background(self):
        """Pause background recognition without killing the background thread."""
        if not self._bg_paused:
            self._bg_paused = True
            print("[System] Background listener paused.")

    def _resume_background(self):
        """Resume background recognition."""
        if self._bg_paused:
            self._bg_paused = False
            print("[System] Background listener resumed.")

    # ---------- background loop ----------
    def _background_loop(self):
        """Continuously record short overlapping chunks and process them asynchronously."""
        print("Background loop started (sounddevice). CHUNK_SECONDS=", CHUNK_SECONDS)
        hop = CHUNK_SECONDS * (1.0 - OVERLAP_FACTOR)
        if hop <= 0:
            hop = CHUNK_SECONDS * 0.5

        while self.running:
            # if paused, sleep briefly and continue (keeps thread alive)
            if self._bg_paused:
                time.sleep(0.1)
                continue

            start_time = time.time()
            data = _record_chunk(seconds=CHUNK_SECONDS)
            if data is None:
                # short sleep on failure to avoid tight loop
                time.sleep(0.2)
                continue

            wav_buf = _np_to_wav_bytes(data)
            if wav_buf is None:
                time.sleep(0.05)
                continue

            # hand off to worker thread for recognition (so loop continues quickly)
            self._process_bg_audio_async(wav_buf)

            # sleep until next hop (overlap)
            elapsed = time.time() - start_time
            to_sleep = max(0.0, hop - elapsed)
            time.sleep(to_sleep)

    def _process_bg_audio_async(self, wav_buf):
        """Spawn a worker to run recognition on the buffer and check for wake phrase."""
        def job():
            try:
                with sr.AudioFile(wav_buf) as source:
                    audio = self.recognizer.record(source)
                    try:
                        txt = self.recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        return
                    except sr.RequestError as e:
                        # network / API error - print and return
                        print("Speech recognition RequestError (bg):", e)
                        return
                    txt = txt.strip()
                    if not txt:
                        return
                    # debug: always print what was heard
                    print("[bg] Heard:", txt)

                    # check debounce and busy state before triggering
                    now = time.time()
                    if now - self.last_wake_time < DEBOUNCE_SECONDS:
                        # recently triggered - ignore
                        # but still useful to print
                        print(f"[bg] Ignored wake (debounced). {now - self.last_wake_time:.2f}s since last.")
                        return

                    if self.wake_re.search(txt):
                        print("[Wake] Wake phrase detected in:", txt)
                        self.last_wake_time = now

                        # if busy, skip handling and note it
                        if self.busy_lock.locked():
                            print("[Wake] Assistant busy; skipping trigger.")
                            return

                        # spawn handler thread (non-blocking)
                        threading.Thread(target=self._handle_command_flow, daemon=True).start()
            except Exception as e:
                print("bg recognition thread error:", e)
        threading.Thread(target=job, daemon=True).start()

    # ---------- active listen & command handling ----------
    def _listen_command(self, timeout: int = 6, phrase_time_limit: int = ACTIVE_LISTEN_SECONDS) -> Optional[str]:
        """
        Active listen: record a chunk intended to contain the user's command and return recognized text.
        Uses the same record -> wav_bytes -> SpeechRecognition pipeline.
        """
        print("[Listen] Active listening for command...")
        data = _record_chunk(seconds=phrase_time_limit)
        if data is None:
            print("[Listen] No audio captured.")
            return None
        wav_buf = _np_to_wav_bytes(data)
        if wav_buf is None:
            return None
        try:
            with sr.AudioFile(wav_buf) as source:
                audio = self.recognizer.record(source)
                try:
                    txt = self.recognizer.recognize_google(audio)
                    txt = txt.strip()
                    print("[command] Recognized:", txt)
                    return txt
                except sr.UnknownValueError:
                    print("[Listen] Could not understand command.")
                    return None
                except sr.RequestError as e:
                    print("Recognition error (active):", e)
                    return None
        except Exception as e:
            print("Active listen audio error:", e)
            return None

    def _handle_command_flow(self):
        """Handles a single wake -> command interaction. Uses busy_lock to prevent concurrent handling."""
        if not self.busy_lock.acquire(blocking=False):
            print("[Handle] Could not acquire busy lock; another handler is running.")
            return

        # Pause background audio to avoid overlap / false triggers during active listening
        self._pause_background()

        try:
            print("[Handle] Ready for command. Say it now.")
            utter = self._listen_command(timeout=6, phrase_time_limit=ACTIVE_LISTEN_SECONDS)
            if not utter:
                print("[Handle] No command heard; returning to background.")
                return

            # For debugging we print what it heard (no TTS)
            print(f"[Handle] I heard: {utter}")

            # map to intent/command
            mapped = self._map_intent_or_command(utter)
            if mapped[0] is None:
                reason = mapped[1]
                print(f"[Handle] Couldn't map that: {reason}")
                if not self.allow_arbitrary:
                    print("[Handle] Arbitrary commands disabled. Restart with --allow-arbitrary to enable.")
                    return

                # confirm arbitrary execution
                print(f"[Confirm] Do you want me to run the exact command: {utter}? Say 'run command' to confirm.")
                reply = self._listen_command(timeout=8, phrase_time_limit=6)
                reply = (reply or "").lower()
                print("[Confirm] reply:", reply)
                if reply not in ("run command", "run", "execute", "yes"):
                    print("[Confirm] Cancelled by user.")
                    logger.log_arbitrary(utter, confirmed=False, note="user declined")
                    return

                rc, out, err = run_raw_command(utter)
                logger.log_arbitrary(utter, confirmed=True, rc=rc, stdout=out, stderr=err)
                print("[Arbitrary] RC:", rc)
                if rc == 0:
                    if out:
                        print("[Arbitrary] Output:", out[:1000])
                    else:
                        print("[Arbitrary] Command executed.")
                else:
                    print("[Arbitrary] Error:", err)
                return

            base_cmd, args = mapped

            # HIGH-LEVEL: weather
            if base_cmd == "__weather__":
                city = args[0] if args else None
                if not city:
                    print("[Weather] Which city?")
                    city = self._listen_command(timeout=8, phrase_time_limit=6)
                if not city:
                    print("[Weather] No city given. Cancelling.")
                    return
                # lazy-import weather function in main to avoid cycles
                from .main import get_weather
                ok, msg = get_weather(city, api_key=self.openweather_key if hasattr(self, "openweather_key") else None)
                print("[Weather] Result:", msg)
                logger.log_command(utter, "WEATHER", "weather", [city], 0 if ok else -1, msg if ok else "", "" if ok else msg)
                return

            # HIGH-LEVEL: youtube play
            if base_cmd == "__youtube_play__":
                query = args[0]
                print(f"[YouTube] Searching for: {query}")
                url = yt_search_top_url(query)
                print("[YouTube] Opening:", url)
                webbrowser.open(url)
                logger.log_command(utter, "YOUTUBE_PLAY", "youtube_play", [query], 0, url, "")
                return

            # HIGH-LEVEL: youtube download
            if base_cmd == "__youtube_download__":
                user_phrase = args[0] if args else ""
                query = self._clean_download_query(user_phrase)
                is_url = bool(re.match(r"https?://", query))
                yt_target = query if is_url else f"ytsearch1:{query}"
                if not self.allow_download:
                    print("[Download] Downloads disabled. Restart with --allow-download to enable.")
                    logger.log_download(user_phrase, query, "", -1, "downloads_disabled")
                    return
                print(f"[Download] You asked to download: {query}. Say 'download this' to confirm.")
                reply = self._listen_command(timeout=8, phrase_time_limit=6)
                reply = (reply or "").lower()
                print("[Download] reply:", reply)
                if reply not in ("download this", "download", "confirm", "yes"):
                    print("[Download] Cancelled.")
                    logger.log_download(user_phrase, query, "", -1, "user_cancelled")
                    return
                print("[Download] Starting download (yt-dlp)...")
                rc, fname, err = yt_download(yt_target, dest_folder=".")
                logger.log_download(user_phrase, query, fname or "", rc, err or "")
                if rc == 0:
                    print("[Download] Finished. Saved as:", fname)
                else:
                    print("[Download] Download failed:", err)
                return

            # HIGH-LEVEL: web search
            if base_cmd == "__web_search__":
                q = args[0]
                url = f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}"
                print("[WebSearch] Opening:", url)
                webbrowser.open(url)
                logger.log_command(utter, "WEB_SEARCH", "web_search", [q], 0, url, "")
                return

            # sanitize and run whitelisted commands
            ok, reason = self._sanitize_and_validate(base_cmd, args)
            if not ok:
                print("[Handle] Sanitize failed:", reason)
                return

            # confirmations for network or sensitive commands
            if args and base_cmd in ("ping", "tracert", "nslookup"):
                print(f"[Confirm] Will run {base_cmd} {' '.join(args)}. Say 'yes' to confirm.")
                reply = self._listen_command(timeout=6, phrase_time_limit=4)
                if (reply or "").lower() not in ("yes", "confirm", "sure"):
                    print("[Confirm] Cancelled.")
                    return

            if base_cmd == "shutdown":
                print("[Confirm] This will shutdown your PC. Say 'yes' to confirm.")
                reply = self._listen_command(timeout=6, phrase_time_limit=4)
                if (reply or "").lower() not in ("yes", "confirm", "shutdown"):
                    print("[Confirm] Shutdown cancelled.")
                    return

            print(f"[Run] Running: {base_cmd} {' '.join(args)}")
            rc, out, err = run_command(base_cmd, args)
            logger.log_command(utter, "WHITELIST", base_cmd, args, rc, out, err)
            if rc == 0:
                if out:
                    print("[Run] Output:", out[:1000])
                else:
                    print("[Run] Command completed successfully.")
            else:
                print("[Run] Error:", err)
                return

        finally:
            if self.busy_lock.locked():
                self.busy_lock.release()
                print("[Handle] Released busy lock.")
            # Resume background recognition in all cases
            self._resume_background()

    # ---------- mapping & helpers ----------
    def _map_intent_or_command(self, utterance: str):
        """Map text -> (command, args) or (None, reason)."""
        if not utterance or not utterance.strip():
            return None, "No speech detected."
        if re.search(r"\b(exit|quit|stop|shutdown assistant)\b", utterance.lower()):
            return ("EXIT", [])

        low = utterance.lower()
        if "download" in low and ("youtube" in low or "video" in low):
            return ("__youtube_download__", [utterance.strip()])

        intent, score, best = self.nlp.predict_intent(utterance)
        if not intent:
            import shlex
            try:
                tokens = shlex.split(utterance.lower())
                if tokens and tokens[0] in config.ALLOWED_COMMANDS:
                    return (tokens[0], tokens[1:])
            except Exception:
                pass
            return None, f"No intent match (best score {score} for '{best}')."

        info = self.nlp.intents[intent]
        cmd = info["cmd"]
        slots = self.nlp.extract_slot(intent, utterance)

        if cmd in config.ALLOWED_COMMANDS:
            if cmd == "ipconfig":
                return ("ipconfig", [])
            if cmd == "systeminfo":
                return ("systeminfo", [])
            if cmd == "whoami":
                return ("whoami", [])
            if cmd == "tasklist":
                return ("tasklist", [])
            if cmd == "calc":
                return ("calc", [])
            if cmd == "lock":
                return ("lock", [])
            if cmd == "music":
                return ("music", [])
            if cmd == "ping":
                target = slots.get("target") or "8.8.8.8"
                if any(ch in config.FORBIDDEN_CHARS for ch in target):
                    return None, "Illegal characters in ping target."
                return ("ping", ["-n", "1", target.replace(" ", ".")])
            if cmd == "tracert":
                target = slots.get("target")
                if not target:
                    return ("tracert", [])
                return ("tracert", [target.replace(" ", ".")])
            if cmd == "nslookup":
                target = slots.get("target")
                if not target:
                    return ("nslookup", [])
                return ("nslookup", [target.replace(" ", ".")])

        if cmd == "weather":
            city = slots.get("city") or re.sub(r".* in ", "", utterance, flags=re.IGNORECASE).strip()
            return ("__weather__", [city])
        if cmd == "youtube_play":
            q = None
            if "play " in utterance.lower():
                q = re.sub(r"(?i)play\s+", "", utterance, count=1).strip()
                q = re.sub(r"(?i)\s+on youtube$", "", q).strip()
            q = q or slots.get("query") or utterance
            return ("__youtube_play__", [q])
        if cmd == "youtube_download":
            q = utterance.strip()
            return ("__youtube_download__", [q])
        if cmd == "web_search":
            q = None
            if "search " in utterance.lower():
                q = re.sub(r"(?i)search (?:web |google |for )?", "", utterance, count=1).strip()
            q = q or slots.get("query") or utterance
            return ("__web_search__", [q])

        return None, "Intent recognized but no mapping available."

    def _sanitize_and_validate(self, base, args):
        if base not in config.ALLOWED_COMMANDS and not base.startswith("__"):
            return False, f"Command '{base}' not allowed."
        if base in config.ALLOWED_COMMANDS:
            if not config.ALLOWED_COMMANDS[base]["accepts_args"] and args:
                return False, f"Command '{base}' does not accept arguments."
            if " ".join(args) and len(" ".join(args)) > config.MAX_ARGS_LEN:
                return False, "Arguments too long."
            if any(ch in config.FORBIDDEN_CHARS for ch in " ".join(args)):
                return False, "Illegal characters in arguments."
        return True, None

    def _clean_download_query(self, utterance: str) -> str:
        u = utterance.lower().strip()
        u = re.sub(r"\b(download( the video| the| this)?)\b", " ", u)
        u = re.sub(r"\bfrom youtube\b", " ", u)
        u = re.sub(r"\bon youtube\b", " ", u)
        u = re.sub(r"\bplease\b", " ", u)
        u = re.sub(r"[^A-Za-z0-9 \-._]", " ", u)
        u = re.sub(r"\s+", " ", u).strip()
        return u or utterance.strip()
