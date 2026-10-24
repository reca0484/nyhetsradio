"""Lokal radiotranskribering. Ingen betald API-tjänst behövs."""
import datetime
import email.utils
import html
import json
import os
import re
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

NOW = datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
OUTPUT = Path("sr_transcripts.json")
FEEDS = {
    "Ekot": "https://public-api.sr.se/rss/ekot-nyhetssandning",
    "P1 Morgon": "https://public-api.sr.se/rss/p1-morgon",
    "Studio Ett": "https://public-api.sr.se/rss/studio-ett",
}
KEYWORDS = re.compile("regering|riksdag|krig|ukraina|ryssland|kina|nato|iran|israel|gaza|ekonomi|börs|ränta|inflation|kriminalvård|fängelse|linköping|östergötland|sjukvård|skola|klimat|säkerhet|budget|utredning|förhandling", re.I)

def get(url, limit=20000000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=40) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Svar överskrider gränsen")
    return data

def rss_episodes(source, url):
    root = ET.fromstring(get(url))
    found = []
    for item in root.findall(".//item"):
        enclosure = item.find("enclosure")
        if enclosure is None or not enclosure.get("url"):
            continue
        try:
            dt = email.utils.parsedate_to_datetime(item.findtext("pubDate")).astimezone(NOW.tzinfo)
        except (ValueError, TypeError, AttributeError):
            continue
        if not datetime.timedelta(0) <= NOW - dt <= datetime.timedelta(hours=48):
            continue
        found.append({"source": source, "title": html.unescape(item.findtext("title") or ""),
                      "date": dt.isoformat(), "link": item.findtext("link") or "",
                      "audio": enclosure.get("url")})
        if len(found) >= 1:
            break
    return found

def p4_episodes():
    url = "https://api.sr.se/api/v2/news/episodes?format=json&size=200"
    data = json.loads(get(url).decode("utf-8"))
    slots = {}
    for item in data.get("episodes", []):
        program = item.get("program") or {}
        if "östergötland" not in program.get("name", "").lower():
            continue
        match = re.search(r"\\d{12,}", item.get("publishdateutc") or "")
        if not match:
            continue
        dt = datetime.datetime.fromtimestamp(int(match.group()) / 1000, tz=datetime.timezone.utc).astimezone(NOW.tzinfo)
        if not datetime.timedelta(0) <= NOW - dt <= datetime.timedelta(hours=48):
            continue
        slot = "förmiddag" if 8 <= dt.hour <= 13 else "kväll" if 15 <= dt.hour <= 21 else None
        if not slot or slot in slots:
            continue
        broadcast = item.get("broadcast") or {}
        files = broadcast.get("podfiles") or broadcast.get("broadcastfiles") or []
        if not files or not files[0].get("url"):
            continue
        slots[slot] = {"source": "P4 Östergötland", "title": item.get("title") or "Nyheter P4 Östergötland",
                       "date": dt.isoformat(), "link": "https://www.sverigesradio.se/poddar/ostergotland",
                       "audio": files[0]["url"]}
    return list(slots.values())

def transcribe(model, episode):
    with tempfile.TemporaryDirectory() as folder:
        audio = str(Path(folder) / "radio.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", episode["audio"], "-ac", "1", "-ar", "16000", audio],
                       check=True, timeout=1500)
        segments, _ = model.transcribe(audio, language="sv", beam_size=1, vad_filter=True,
                                       condition_on_previous_text=False)
        sentences = [{"start": round(s.start), "text": re.sub(r"\\s+", " ", s.text).strip()}
                     for s in segments if len(s.text.strip()) > 25]
        selected = []
        for i, sentence in enumerate(sentences):
            if KEYWORDS.search(sentence["text"]):
                for neighbor in sentences[max(0, i-1):min(len(sentences), i+2)]:
                    if neighbor not in selected:
                        selected.append(neighbor)
            if len(selected) >= 18:
                break
        return len(sentences), selected[:18]

def main():
    previous = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    result = {"updated": NOW.isoformat(), "episodes": [], "warnings": []}
    from faster_whisper import WhisperModel
    model = WhisperModel(os.getenv("WHISPER_MODEL", "tiny"), device="cpu", compute_type="int8")
    sources = [(name, lambda n=name, u=url: rss_episodes(n, u)) for name, url in FEEDS.items()]
    sources.append(("P4 Östergötland", p4_episodes))
    for source, fetcher in sources:
        try:
            episodes = fetcher()
            if not episodes:
                result["warnings"].append(source + ": inga tillgängliga färska ljudavsnitt")
            for episode in episodes:
                cached = next((e for e in previous.get("episodes", [])
                               if e.get("audio") == episode["audio"] and e.get("transcribed")), None)
                if cached:
                    result["episodes"].append(cached)
                    continue
                count, excerpts = transcribe(model, episode)
                episode.update(transcribed=count > 0, segments_count=count, excerpts=excerpts)
                result["episodes"].append(episode)
        except Exception as exc:
            result["warnings"].append(source + ": " + type(exc).__name__ + ": " + str(exc)[:160])
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SR-transkribering:", [(e["source"], e["segments_count"]) for e in result["episodes"]], result["warnings"])

if __name__ == "__main__":
    main()
