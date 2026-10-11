#!/usr/bin/env python3
"""Archive the Delicious Revolution podcast from its Acast RSS feed.

Run on a Mac (or any machine with python3 and curl):

    python3 scripts/fetch_acast.py              # from the repo root; writes into archive/
    python3 scripts/fetch_acast.py --out DIR    # or somewhere else
    python3 scripts/fetch_acast.py --no-audio   # feed + CSV only

What it produces (inside the output folder):

    feed/acast-feed-YYYYMMDD-HHMMSS.xml   the feed exactly as served (raw bytes)
    episodes.csv                          one row per episode (previews excluded)
    excluded_previews.csv                 the items that were left out, and why
    audio/<episode_id>.mp3                one file per row of episodes.csv
    fetch_log.txt                         what happened on each run

The link between metadata and audio: every row has an `episode_id`, and the
audio file is always `audio/<episode_id>.mp3` (also written out in the
`audio_file` column), with its byte size and sha256 recorded so the pairing
can be verified later. Re-running is safe: finished files are skipped.

Only the Python standard library and the system `curl` are used.
"""
import argparse
import csv
import datetime as dt
import email.utils
import hashlib
import html
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

FEED_URL = "https://feeds.acast.com/public/shows/5bd8a109e7394b07090e2d66"
UA = "Mozilla/5.0 (Delicious Revolution archive fetch)"
NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "acast": "https://schema.acast.com/1.0/",
}
PREVIEW_RE = re.compile(r"\bpreview\b", re.I)
ACAST_FOOTER_RE = re.compile(r"\s*Hosted on Acast\. See acast\.com/privacy for more information\.?\s*$", re.I)

CSV_FIELDS = [
    "episode_id", "number", "kind", "title", "date", "pub_date_raw",
    "duration", "itunes_season", "itunes_episode", "itunes_episode_type",
    "audio_url", "audio_file", "audio_bytes", "audio_sha256", "enclosure_length",
    "image_url", "image_file", "link", "guid", "notes_text", "notes_html",
]


def log(msg, fh=None):
    line = f"{dt.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


def curl(url, dest, retries=3):
    """Download url to dest with curl (follows redirects, uses system certs)."""
    part = dest + ".part"
    for attempt in range(1, retries + 1):
        r = subprocess.run(
            ["curl", "-fL", "--silent", "--show-error", "--retry", "3", "--retry-delay", "5",
             "-A", UA, "-o", part, url],
            capture_output=True, text=True)
        if r.returncode == 0 and os.path.getsize(part) > 0:
            os.replace(part, dest)
            return
        err = r.stderr.strip()
    if os.path.exists(part):
        os.remove(part)
    raise RuntimeError(f"curl failed for {url}: {err}")


class _Text(HTMLParser):
    """Turn show-note HTML into readable plain text, keeping links visible."""
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self):
        super().__init__()
        self.out, self.href = [], None

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "li":
            self.out.append("- ")
        if tag == "a":
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            text_so_far = "".join(self.out)
            if not text_so_far.rstrip().endswith(self.href):
                self.out.append(f" ({self.href})")
            self.href = None
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        self.out.append(data)

    def text(self):
        t = html.unescape("".join(self.out))
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
        return t.strip()


def html_to_text(s):
    p = _Text()
    p.feed(s or "")
    return ACAST_FOOTER_RE.sub("", p.text()).strip()


def slugify(s, maxlen=60):
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s or "episode"


def classify(title):
    m = re.search(r"special\s*#?\s*(\d+)", title, re.I)
    if m:
        return "special", f"S{m.group(1)}"
    m = re.match(r"\s*#?\s*(\d{1,3})\b", title)
    if m:
        return "episode", m.group(1)
    return "other", ""


def text_of(el, path):
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    items = []
    for it in channel.findall("item"):
        title = text_of(it, "title")
        enc = it.find("enclosure")
        pub_raw = text_of(it, "pubDate")
        try:
            date = email.utils.parsedate_to_datetime(pub_raw).date().isoformat()
        except Exception:
            date = ""
        notes_html = text_of(it, "content:encoded") or text_of(it, "description") or text_of(it, "itunes:summary")
        img = it.find("itunes:image", NS)
        kind, number = classify(title)
        items.append({
            "title": title,
            "date": date,
            "pub_date_raw": pub_raw,
            "duration": text_of(it, "itunes:duration"),
            "itunes_season": text_of(it, "itunes:season"),
            "itunes_episode": text_of(it, "itunes:episode"),
            "itunes_episode_type": text_of(it, "itunes:episodeType"),
            "audio_url": enc.get("url", "") if enc is not None else "",
            "enclosure_length": enc.get("length", "") if enc is not None else "",
            "image_url": img.get("href", "") if img is not None else "",
            "link": text_of(it, "link"),
            "guid": text_of(it, "guid"),
            "notes_html": notes_html,
            "notes_text": html_to_text(notes_html),
            "kind": kind,
            "number": number,
        })
    channel_info = {
        "title": text_of(channel, "title"),
        "description": text_of(channel, "description"),
        "image": (channel.find("itunes:image", NS).get("href", "")
                  if channel.find("itunes:image", NS) is not None else ""),
    }
    return channel_info, items


def assign_ids(items):
    """episode_id = <date>_<slug of title>; unique and stable across re-runs."""
    seen = {}
    for e in sorted(items, key=lambda e: (e["date"], e["title"])):
        base = f"{e['date'] or 'undated'}_{slugify(e['title'])}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        e["episode_id"] = base if n == 0 else f"{base}-{n + 1}"
        e["audio_file"] = f"audio/{e['episode_id']}.mp3"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "archive"))
    ap.add_argument("--feed-url", default=FEED_URL)
    ap.add_argument("--feed-file", help="parse an already-saved feed instead of downloading one")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    os.makedirs(os.path.join(out, "feed"), exist_ok=True)
    os.makedirs(os.path.join(out, "audio"), exist_ok=True)
    logfh = open(os.path.join(out, "fetch_log.txt"), "a", encoding="utf-8")
    log(f"--- run started, output: {out}", logfh)

    # 1. Raw feed, saved byte-for-byte.
    if a.feed_file:
        feed_path = os.path.abspath(a.feed_file)
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        feed_path = os.path.join(out, "feed", f"acast-feed-{stamp}.xml")
        curl(a.feed_url, feed_path)
    raw = open(feed_path, "rb").read()
    log(f"feed: {feed_path} ({len(raw):,} bytes)", logfh)

    # 2. Parse, split out previews.
    channel, items = parse_feed(raw)
    keep, excluded = [], []
    for e in items:
        if PREVIEW_RE.search(e["title"]):
            e["excluded_reason"] = "title contains 'preview'"
            excluded.append(e)
        elif not e["audio_url"]:
            e["excluded_reason"] = "no audio enclosure"
            excluded.append(e)
        else:
            keep.append(e)
    assign_ids(keep)
    keep.sort(key=lambda e: (e["date"], e["title"]))
    log(f"items in feed: {len(items)}; keeping {len(keep)}; excluded {len(excluded)}", logfh)

    # Carry over hashes from a previous run so finished files are not re-hashed.
    csv_path = os.path.join(out, "episodes.csv")
    previous = {}
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                previous[r["episode_id"]] = r

    # 3. Audio.
    failures = []
    for i, e in enumerate(keep, 1):
        dest = os.path.join(out, e["audio_file"])
        prev = previous.get(e["episode_id"], {})
        if os.path.exists(dest) and prev.get("audio_sha256") and str(os.path.getsize(dest)) == prev.get("audio_bytes"):
            e["audio_bytes"], e["audio_sha256"] = prev["audio_bytes"], prev["audio_sha256"]
            log(f"[{i}/{len(keep)}] already have {e['audio_file']}", logfh)
            continue
        if a.no_audio:
            e["audio_bytes"] = e["audio_sha256"] = ""
            continue
        try:
            log(f"[{i}/{len(keep)}] downloading {e['title']}", logfh)
            curl(e["audio_url"], dest)
            e["audio_bytes"] = str(os.path.getsize(dest))
            e["audio_sha256"] = sha256(dest)
            log(f"    -> {e['audio_file']} ({int(e['audio_bytes']) / 1e6:.1f} MB)", logfh)
        except Exception as ex:
            e["audio_bytes"] = e["audio_sha256"] = ""
            failures.append((e["title"], str(ex)))
            log(f"    !! FAILED: {ex}", logfh)

    # 4. Artwork: show cover + any per-episode images (deduplicated by URL).
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    urls = [channel["image"]] + [e["image_url"] for e in keep]
    for url in dict.fromkeys(u for u in urls if u):
        ext = os.path.splitext(url.split("?")[0])[1].lower()
        ext = ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
        name = "images/" + hashlib.sha1(url.encode()).hexdigest()[:12] + ext
        dest = os.path.join(out, name)
        try:
            if not os.path.exists(dest):
                curl(url, dest)
        except Exception as ex:
            log(f"    !! image failed: {url}: {ex}", logfh)
            name = ""
        if url == channel["image"]:
            channel["image_file"] = name
        for e in keep:
            if e["image_url"] == url:
                e["image_file"] = name

    # 5. Spreadsheets.
    write_csv(csv_path, keep, CSV_FIELDS)
    write_csv(os.path.join(out, "excluded_previews.csv"), excluded,
              ["title", "date", "excluded_reason", "audio_url", "guid"])
    with open(os.path.join(out, "channel.txt"), "w", encoding="utf-8") as f:
        f.write(f"title: {channel['title']}\nimage: {channel['image']}\nimage_file: {channel.get('image_file', '')}\n\n{html_to_text(channel['description'])}\n")

    total = sum(int(e["audio_bytes"]) for e in keep if e.get("audio_bytes"))
    log(f"done: {len(keep)} episodes in episodes.csv, {total / 1e9:.2f} GB of audio, "
        f"{len(failures)} failed downloads", logfh)
    for t, err in failures:
        log(f"   failed: {t}: {err}", logfh)
    if failures:
        log("Re-run the script to retry the failed downloads.", logfh)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
