# voice_assistant/youtube_utils.py
import os
import urllib.parse
from typing import Tuple

try:
    import yt_dlp as ytdlp
    YTDLP_AVAILABLE = True
except Exception:
    YTDLP_AVAILABLE = False

def yt_search_top_url(query: str) -> str:
    if YTDLP_AVAILABLE:
        try:
            with ytdlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entries = info.get("entries") if isinstance(info, dict) else None
                if entries:
                    video = entries[0]
                    return f"https://www.youtube.com/watch?v={video['id']}"
        except Exception:
            pass
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"

def yt_download(query_or_url: str, dest_folder: str = ".") -> Tuple[int, str, str]:
    if not YTDLP_AVAILABLE:
        return -1, "", "yt-dlp not installed."
    ydl_opts = {
        "outtmpl": os.path.join(dest_folder, "%(title).100s-%(id)s.%(ext)s"),
        "format": "bestaudio+bv*+ba/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query_or_url, download=True)
            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]
            try:
                filename = ydl.prepare_filename(info)
            except Exception:
                filename = ""
            return 0, filename, ""
    except Exception as ex:
        return -1, "", f"yt-dlp error: {ex}"
