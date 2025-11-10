# voice_assistant/logger.py
import datetime
import threading
from . import config

_lock = threading.Lock()

def ts():
    return datetime.datetime.now().isoformat(sep=" ", timespec="seconds")

def _write_log(filename: str, line: str):
    with _lock:
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

def truncate(s, n=800):
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else s[:n] + " ...[truncated]"

def log_command(utterance, mode, base_cmd, args, rc, stdout, stderr, note=""):
    entry = f"{ts()}\tMODE={mode}\tUTTERANCE={utterance}\tCMD={base_cmd}\tARGS={' '.join(args) if args else ''}\tRC={rc}\tSTDOUT={truncate(stdout,400)}\tSTDERR={truncate(stderr,400)}\tNOTE={note}"
    _write_log(config.COMMANDS_LOG, entry)

def log_download(utterance, query_or_url, filename, rc, note=""):
    entry = f"{ts()}\tUTTERANCE={utterance}\tQUERY_OR_URL={query_or_url}\tSAVED_AS={filename}\tRC={rc}\tNOTE={note}"
    _write_log(config.DOWNLOADS_LOG, entry)

def log_arbitrary(utterance, confirmed, rc=None, stdout=None, stderr=None, note=""):
    entry = f"{ts()}\tUTTERANCE={utterance}\tCONFIRMED={confirmed}\tRC={rc}\tSTDOUT={truncate(stdout,200)}\tSTDERR={truncate(stderr,200)}\tNOTE={note}"
    _write_log(config.ARBITRARY_LOG, entry)
    _write_log(config.COMMANDS_LOG, "ARBITRARY " + entry)
