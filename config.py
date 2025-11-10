# voice_assistant/config.py
import os

# config.py
WAKE_PATTERNS = [
    r"hey dj", r"hey deejay", r"hey d j", r"hey d\.j", r"hey assistant",
    r"ok dj", r"yo dj", r"dj",r"yo"
]
WAKE_WORDS = "(" + "|".join(WAKE_PATTERNS) + ")"


ALLOWED_COMMANDS = {
    "ipconfig": {"accepts_args": True},
    "ping": {"accepts_args": True},
    "tracert": {"accepts_args": True},
    "nslookup": {"accepts_args": True},
    "systeminfo": {"accepts_args": False},
    "whoami": {"accepts_args": False},
    "tasklist": {"accepts_args": False},
    "calc": {"accepts_args": False},
    "shutdown": {"accepts_args": True},
    "lock": {"accepts_args": False},
    "music": {"accepts_args": False},
}

MAX_ARGS_LEN = 120
FORBIDDEN_CHARS = set("&|;><$`")

COMMANDS_LOG = "commands.log"
DOWNLOADS_LOG = "downloads.log"
ARBITRARY_LOG = "arbitrary_commands.log"

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
