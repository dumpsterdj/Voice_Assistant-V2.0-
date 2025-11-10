# Voice_Assistant(V2.0) — “Hey DJ”

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A local-first voice assistant for Windows that listens for a wake phrase ("hey DJ"), maps simple natural-language requests to whitelisted system commands, and performs safe actions such as opening YouTube results, downloading videos (optional), and running common network utilities. Designed to be easy to run locally with minimal native build tools required.

---

# Key features

* Continuous wake-word listening ("hey DJ")
* Lightweight NLP intent mapper for common commands
* Whitelisted system commands: `ipconfig`, `ping`, `systeminfo`, `tasklist`, `whoami`, `calc`, `lock`, `music`, and others
* YouTube helpers: open top search result or download using `yt-dlp` (optional and gated)
* Active command listening after wake phrase
* Console-based feedback by default (prints everything it hears)
* Logs commands, downloads, and arbitrary runs to local files
* Runs without PyAudio by using `sounddevice` and `soundfile`

---

# Repository tree

Copy this into the Project Structure section of the repo or use it to verify files.

```
VoiceAssistant/
├─ .venv/                     # Virtual environment (not committed)
├─ voice_assistant/           # Python package
│  ├─ __init__.py
│  ├─ config.py               # Configuration and constants
│  ├─ logger.py               # Logging utilities
│  ├─ tts.py                  # Text feedback (prints) or TTS wrapper
│  ├─ commands.py             # Command execution helpers
│  ├─ nlp_engine.py           # Lightweight NLP intent engine
│  ├─ youtube_utils.py        # YouTube search & download helpers
│  ├─ wake.py                 # Wake-word listener and main logic
│  └─ main.py                 # Entry point
├─ requirements.txt
├─ start_voice_assistant.bat   # Optional: Windows startup helper
├─ README.md
└─ LICENSE
```

---

# Quick start

1. Clone the repo and change directory

```powershell
git clone https://github.com/dumpsterdj/VoiceAssistant.git
cd VoiceAssistant
```

2. Create and activate a virtual environment (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
```

3. Install dependencies

```powershell
pip install -r requirements.txt
```

4. Run the assistant

```powershell
python -m voice_assistant.main
```

Optional flags

```text
--allow-download      Enable YouTube downloads (requires spoken confirmation)
--allow-arbitrary     Allow arbitrary shell commands (dangerous; use only in trusted environment)
--openweather-key    Supply OpenWeatherMap API key (or set OPENWEATHER_API_KEY env var)
```

Example:

```powershell
python -m voice_assistant.main --allow-download --allow-arbitrary --openweather-key YOUR_KEY
```

---

# Requirements

Save as `requirements.txt` and keep it up to date.

```
SpeechRecognition>=3.8.1
rapidfuzz>=2.13.7
requests>=2.31.0
yt-dlp>=2024.10.19

# audio input without PyAudio
sounddevice>=0.4.8
soundfile>=0.12.1
numpy>=1.26.0
```

Optional (only if you want voice-auth or advanced features):

```
PyAudio
webrtcvad
resemblyzer
torch
vosk
```

Notes

* `sounddevice` and `soundfile` are used to avoid PyAudio wheels and build tool issues.
* `yt-dlp` is optional. If installed, downloads will use it and may require `ffmpeg` for format merging.
* `recognize_google()` uses the Google Web Speech API. It requires network access. Consider an offline recognizer (Vosk) if you want zero network dependency.

---

# How to use

1. Start the assistant.
2. Say the wake phrase: `hey DJ`, `hey deejay`, `ok dj`, or `dj`.
3. When prompted (console shows active listen), speak a command, for example:

   * "show my ip"
   * "ping google.com"
   * "what is my system info"
   * "open calculator"
   * "play despacito on YouTube"
   * "download this video" (requires `--allow-download` and confirmation)
   * "what's the weather in London" (requires OpenWeather API key)

Logging

* `commands.log` records whitelisted command activity
* `downloads.log` records download attempts
* `arbitrary_commands.log` records arbitrary-run confirmations

---

# Safety and security

* Arbitrary command execution is disabled by default. Do not run `--allow-arbitrary` unless you trust the device and environment.
* Downloads are disabled by default. Use `--allow-download` only when you understand legal obligations.
* The assistant runs local commands with your user permissions. Treat the project as you would any local automation tool.
* Consider configuring voice authentication or OS-level access control before enabling destructive actions like `shutdown`.

---

# Troubleshooting

Wake phrase not detected

* Open `voice_assistant/config.py` and ensure `WAKE_PATTERNS` contains common variants like `"hey dj"`, `"hey deejay"`, `"dj"`.
* Tune `CHUNK_SECONDS` in `voice_assistant/wake.py`. Lower reduces latency but may clip phrases. Typical values 1.2 to 1.6 seconds.
* If you hear "debounced" messages, increase `DEBOUNCE_SECONDS` or wait a bit longer between wake attempts.
* Print debug output appears as `[bg] Heard:`. Add the printed phrase to `WAKE_PATTERNS` if recognizer rewrites your phrase.

Recognition is slow

* The assistant uses `recognize_google()` which is a network call. Use offline recognizer (Vosk) for lower latency.
* TTS was changed to printing for speed. If you re-enable TTS make it non-blocking or use the queue-based worker version in `tts.py`.

Audio device errors

* If `sounddevice` errors out, run `python -c "import sounddevice as sd; print(sd.query_devices())"` to list devices and set `sd.default.device`.
* On Windows, ensure microphone permissions are granted and drivers are installed.

yt-dlp / ffmpeg errors

* If you see errors about `ffmpeg` when downloading, install ffmpeg and add it to PATH.

Windows startup

* To run the assistant at login, add `start_voice_assistant.bat` or a shortcut to the Windows Startup folder:

  * Press `Win+R`, type `shell:startup`, paste a shortcut to `start_voice_assistant.bat`.

---

# Development

Project layout is intentionally modular to make testing and improvements easy.

* `nlp_engine.py` contains intents and examples. Add more examples to improve matching.
* `wake.py` contains the audio capture, background worker, debounce logic, and command flow. Tune constants here.
* `youtube_utils.py` is lazy about importing `yt-dlp`. It falls back to opening the search results in a browser if yt-dlp is not installed.
* `tts.py` prints by default. Swap `print` to `pyttsx3` calls if you want audible feedback. Prefer the non-blocking queue version of TTS.

Run tests (add tests as you build them)

```
pytest -q
```

Linting

```
flake8 voice_assistant
```

---

# Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch `git checkout -b feat/something`
3. Commit changes and push
4. Open a pull request with a clear description and screenshots if applicable

Please add tests for new functionality and keep PRs focused.

---

# Roadmap ideas

* Add offline wake-word detection using VAD + small keyword model (Vosk)
* Add local voice authentication (voice profile + similarity check)
* Build a Windows tray icon with start/stop and logs
* Add a web UI for configuring intents and command mappings
* Ship a pip-installable package and a Windows installer

---

# License

MIT License. See `LICENSE` in this repository.

---

# Contact

If you use or extend this project, please open an issue or PR. If you want help tuning for your mic or environment, paste a few `[bg] Heard:` lines from the console and I will suggest concrete `WAKE_PATTERNS` and timing changes.

---
