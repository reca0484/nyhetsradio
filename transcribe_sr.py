"""Transkribera senaste tillgängliga SR-sändningar lokalt utan betalt API."""
import datetime, html, json, os, re, subprocess, tempfile, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

FEEDS = {
    "Ekot": "https://public-api.sr.se/rss/ekot-nyhetssandning",
    "P1 Morgon": "https://public-api.sr.se/rss/p1-morgon",
    "Studio Ett": "https://public-api.sr.se/rss/studio-ett",
}
NOW = datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
OUTPUT = Path("sr_transcripts.json")
MAX_AGE_HOURS = 48
KEYWORDS = re.compile(r"regering|riksdag|krig|ukraina|ryssland|kina|indien|europa|usa|nato|iran|israel|gaza|ekonomi|börs|ränta|inflation|kriminalvård|fängelse|linköping|östergötland|sjukvård|skola|klimat|säkerhet|valet|budget|utredning|förhandling", re.I)

def get(url, limit=2000000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Nyhetsradio personal RSS reader", "Accept": "application/rss+xml, application/xml, */*"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return r.read(limit)

def latest(source, url):
    import email.utils
    root = ET.fromstring(get(url))
    for item in root.findall(".//item"):
        enclosure = item.find("enclosure")
        if enclosure is None or not enclosure.get("url"):
            continue
        try:
            dt = email.utils.parsedate_to_datetime(item.findtext("pubDate")).astimezone(NOW.tzinfo)
        except Exception:
            continue
        if NOW - dt > datetime.timedelta(hours=MAX_AGE_HOURS) or dt > NOW + datetime.timedelta(hours=1):
            continue
        return {"source": source, "title": html.unescape(item.findtext("title") or ""), "date": dt.isoformat(),
                "link": item.findtext("link") or "", "audio": enclosure.get("url")}
    return None

def transcribe(model, episode):
    with tempfile.TemporaryDirectory() as td:
        audio = Path(td) / "audio.wav"
        # Convert the complete programme to mono 16kHz; no arbitrary duration cut.
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-user_agent", "Mozilla/5.0", "-i", episode["audio"], "-ac", "1",
               "-ar", "16000", str(audio)]
        subprocess.run(cmd, check=True, timeout=1500)
        segments, info = model.transcribe(str(audio), language="sv", beam_size=1, vad_filter=True,
                                          condition_on_previous_text=False)
        sentences = []
        for segment in segments:
            t = re.sub(r"\\s+", " ", segment.text).strip()
            if t and len(t) > 25:
                sentences.append({"start": round(segment.start), "text": t})
        return sentences, info.language

def main():
    previous = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    result = {"updated": NOW.isoformat(), "episodes": [], "warnings": []}
    from faster_whisper import WhisperModel
    model = WhisperModel(os.getenv("WHISPER_MODEL", "tiny"), device="cpu", compute_type="int8")
    for source, url in FEEDS.items():
        try:
            episode = latest(source, url)
            if not episode:
                result["warnings"].append(source + ": inget färskt avsnitt med ljudfil i RSS")
                continue
            old = next((e for e in previous.get("episodes", []) if e.get("audio") == episode["audio"] and e.get("transcribed")), None)
            if old:
                result["episodes"].append(old)
                continue
            segments, language = transcribe(model, episode)
            matches = [s for s in segments if KEYWORDS.search(s["text"])]
            episode["language"] = language
            episode["transcribed"] = bool(segments)
            episode["segments_count"] = len(segments)
            # Representative excerpts only, not an invented editorial summary.
            episode["excerpts"] = matches[:35]
            episode.pop("audio", None)
            result["episodes"].append(episode)
        except Exception as exc:
            result["warnings"].append(source + ": " + type(exc).__name__ + ": " + str(exc)[:160])
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SR:", [(e["source"], e["segments_count"]) for e in result["episodes"]], result["warnings"])

if __name__ == "__main__":
    main()
