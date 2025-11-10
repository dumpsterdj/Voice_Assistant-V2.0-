# voice_assistant/commands.py
import os
import shlex
import subprocess
from typing import Tuple

def run_command(base_cmd, args_list) -> Tuple[int, str, str]:
    try:
        if base_cmd == "calc":
            subprocess.Popen(["calc.exe"])
            return 0, "Opened Calculator.", ""
        if base_cmd == "lock":
            r = subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True, text=True, shell=False, timeout=10)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        if base_cmd == "music":
            path = os.path.expanduser(os.path.join("~", "Music"))
            subprocess.Popen(["explorer", path])
            return 0, f"Opened music folder {path}", ""
        if base_cmd == "shutdown":
            r = subprocess.run(["shutdown"] + args_list, capture_output=True, text=True, shell=False, timeout=10)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        r = subprocess.run([base_cmd] + args_list, capture_output=True, text=True, shell=False, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as ex:
        return -1, "", f"Error running {base_cmd}: {ex}"

def run_raw_command(command_text) -> Tuple[int, str, str]:
    try:
        argv = shlex.split(command_text)
        if not argv:
            return -1, "", "Empty command."
        r = subprocess.run(argv, capture_output=True, text=True, shell=False, timeout=60)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as ex:
        return -1, "", f"Error running raw command: {ex}"
