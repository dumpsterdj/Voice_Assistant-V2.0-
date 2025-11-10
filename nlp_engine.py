# voice_assistant/nlp_engine.py
import re
from rapidfuzz import process, fuzz

class NLPEngine:
    def __init__(self):
        self.intents = {
            "ip_show": {"cmd": "ipconfig", "examples": ["show my ip", "what is my ip", "ipconfig"], "slots": {}},
            "ping": {"cmd": "ping", "examples": ["ping google", "ping 8.8.8.8", "check connectivity"], "slots": {"target": {"pattern": r"(\b\d{1,3}(?:[ .]\d{1,3}){3}\b)|([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"}}},
            "tracert": {"cmd": "tracert", "examples": ["traceroute google", "tracert example.com"], "slots": {"target": {"pattern": r"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})|(\b\d{1,3}(?:[ .]\d{1,3}){3}\b)"}}},
            "nslookup": {"cmd": "nslookup", "examples": ["dns lookup google", "nslookup example.com"], "slots": {"target": {"pattern": r"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"}}},
            "systeminfo": {"cmd": "systeminfo", "examples": ["system info", "system information"], "slots": {}},
            "whoami": {"cmd": "whoami", "examples": ["who am i", "current user"], "slots": {}},
            "tasklist": {"cmd": "tasklist", "examples": ["list processes", "tasklist"], "slots": {}},
            "calc": {"cmd": "calc", "examples": ["open calculator", "launch calc"], "slots": {}},
            "lock": {"cmd": "lock", "examples": ["lock computer", "lock pc"], "slots": {}},
            "music": {"cmd": "music", "examples": ["open music folder", "play music"], "slots": {}},
            "weather": {"cmd": "weather", "examples": ["what's the weather in london", "weather new york"], "slots": {"city": {"pattern": r"in ([A-Za-z .]+)$", "required": False}}},
            "youtube_play": {"cmd": "youtube_play", "examples": ["play despacito on youtube", "play blinding lights"], "slots": {"query": {"pattern": r"play (.+) on youtube|play (.+)$", "required": True}}},
            "youtube_download": {"cmd": "youtube_download", "examples": ["download this song", "download video", "download youtube video"], "slots": {"url_or_query": {"pattern": r"(https?://\S+)|(.+)", "required": True}}},
            "web_search": {"cmd": "web_search", "examples": ["search web for best lasagna recipe", "search for how to tie a tie"], "slots": {"query": {"pattern": r"(?:search (?:web|google|for) )(.+)", "required": True}}}
        }
        self.example_map = {}
        self.examples = []
        for intent, info in self.intents.items():
            for ex in info["examples"]:
                norm = self._normalize(ex)
                self.example_map[norm] = intent
                self.examples.append(norm)

    def _normalize(self, t: str) -> str:
        t = t.lower().strip()
        t = re.sub(r'\bdot\b', '.', t)
        nums = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9"}
        toks = t.split()
        toks = [nums.get(x,x) for x in toks]
        t = " ".join(toks)
        t = re.sub(r"\bplease\b", "", t)
        t = re.sub(r"\bcan you\b", "", t)
        t = re.sub(r"\bwhat('?s| is)\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def predict_intent(self, utterance: str, score_cutoff: int = 60):
        u = self._normalize(utterance)
        match = process.extractOne(u, self.examples, scorer=fuzz.ratio)
        if not match:
            return None, 0, None
        matched_text, score, _ = match
        if score < score_cutoff:
            return None, score, matched_text
        return self.example_map.get(matched_text), score, matched_text

    def extract_slot(self, intent_name: str, utterance: str):
        info = self.intents[intent_name]
        slots = {}
        u = utterance.strip()
        for slot_name, meta in info.get("slots", {}).items():
            pat = meta.get("pattern")
            if not pat:
                continue
            m = re.search(pat, u, flags=re.IGNORECASE)
            if m:
                groups = [g for g in m.groups() if g]
                if groups:
                    val = groups[-1].strip()
                    slots[slot_name] = val
                else:
                    slots[slot_name] = m.group(0).strip()
        return slots
