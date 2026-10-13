#!/usr/bin/env python3
"""Build the Delicious Revolution archive site from data/episodes.csv.

    python3 scripts/build_site.py

Reads:   data/episodes.csv     (made by fetch_acast.py; one row per episode)
         data/overrides.csv    (optional; edit by hand to fix seasons, titles, notes)
         site.json             (site settings: domain, media URL, show text)
Writes:  docs/                 (what GitHub Pages serves)

Audio is NOT in the repo. Each episode plays from
    <media_base_url>/<episode_id>.mp3
so the files uploaded to object storage must keep the names in episodes.csv.
Standard library only.
"""
import csv
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import shutil
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
ACAST_FOOTER_RE = re.compile(r"Hosted on Acast\. See acast\.com/privacy for more information\.?", re.I)

# Season boundaries by air date (first day of the following season's window).
# Numbered episodes are placed by number first; dates catch specials and announcements.
SEASONS_BY_NUMBER = [(1, 11, 1), (12, 20, 2), (21, 29, 3), (30, 42, 4), (43, 50, 5), (51, 99, 6)]
SEASONS_BY_DATE = [("2016-02-15", 1), ("2016-06-15", 2), ("2016-12-01", 3),
                   ("2017-07-10", 4), ("2018-01-01", 5), ("9999-12-31", 6)]


# ---------- data ----------

def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def season_for(ep):
    if ep.get("season"):
        return int(ep["season"])
    if ep.get("kind") == "episode" and ep.get("number", "").isdigit():
        n = int(ep["number"])
        for lo, hi, s in SEASONS_BY_NUMBER:
            if lo <= n <= hi:
                return s
    for cutoff, s in SEASONS_BY_DATE:
        if (ep.get("date") or "9999") < cutoff:
            return s
    return 6


def split_title(title):
    """'#34 Kristyn Leach of Namu Farm on finding roots...' -> (guest, topic)."""
    t = re.sub(r"^\s*(?:DR\s+)?(?:Special\s*)?#?\s*\d{1,3}\s*[:.\-]?\s*", "", title, flags=re.I).strip()
    m = re.match(r"(.+?)\s+on\s+(.+)", t)
    if m and len(m.group(1)) < 90:
        return m.group(1).strip(), m.group(2).strip()
    return t, ""


def label_for(ep):
    if ep.get("kind") == "special":
        return f"Special {ep['number'].lstrip('S')}"
    if ep.get("kind") == "episode":
        return f"No. {ep['number']}"
    return ""


def fmt_date(iso):
    try:
        d = dt.date.fromisoformat(iso)
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    except Exception:
        return iso


def fmt_duration(s):
    secs = 0
    for p in (s or "").split(":"):
        if p.isdigit():
            secs = secs * 60 + int(p)
    if secs <= 0:
        return ""
    return f"{secs // 3600} hr {secs % 3600 // 60} min" if secs >= 3600 else f"{secs // 60} min"


class _Clean(HTMLParser):
    """Keep simple formatting and links from Acast show notes; drop everything else."""
    KEEP = {"p", "br", "a", "strong", "b", "em", "i", "ul", "ol", "li", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.KEEP:
            return
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith(("http://", "https://", "mailto:")):
                self.out.append(f'<a href="{html.escape(href)}" rel="noopener">')
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{'strong' if tag == 'b' else 'em' if tag == 'i' else tag}>")

    def handle_endtag(self, tag):
        if tag in self.KEEP and tag != "br":
            self.out.append(f"</{'strong' if tag == 'b' else 'em' if tag == 'i' else tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(data))


def clean_notes(raw_html, plain):
    if raw_html and "<" in raw_html:
        p = _Clean()
        p.feed(ACAST_FOOTER_RE.sub("", raw_html))
        out = "".join(p.out)
        out = re.sub(r"<p>\s*Hosted on Acast\..*?</p>", "", out, flags=re.I | re.S)  # footer with a link inside
        out = re.sub(r"<p>\s*</p>", "", out).strip()
        if out:
            return out if out.startswith("<") else f"<p>{out}</p>"
    text = ACAST_FOOTER_RE.sub("", plain or raw_html or "").strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    linkify = lambda s: re.sub(r"(https?://[^\s)]+)", r'<a href="\1" rel="noopener">\1</a>', s)
    return "".join(f"<p>{linkify(html.escape(p)).replace(chr(10), '<br>')}</p>" for p in paras)


def plain_summary(notes_html, n=180):
    text = re.sub(r"<[^>]+>", " ", notes_html)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def load_episodes():
    rows = load_csv(os.path.join(ROOT, "data", "episodes.csv"))
    overrides = {r["episode_id"]: r for r in load_csv(os.path.join(ROOT, "data", "overrides.csv"))}
    eps = []
    for r in rows:
        o = overrides.get(r["episode_id"], {})
        if o.get("hide", "").strip().lower() in ("1", "yes", "true"):
            continue
        for k, v in o.items():
            if k not in ("episode_id", "hide", "notes_override") and v:
                r[k] = v
        if o.get("notes_override"):
            r["notes_html"], r["notes_text"] = "", o["notes_override"]
        r["season"] = season_for(r)
        r["guest"], r["topic"] = split_title(r["title"])
        r["label"] = label_for(r)
        r["notes"] = clean_notes(r.get("notes_html", ""), r.get("notes_text", ""))
        r["summary"] = plain_summary(r["notes"])
        eps.append(r)
    eps.sort(key=lambda e: (e["date"], e["title"]))
    return eps


# ---------- html ----------

def asset_version(name):
    """Short content hash, so browsers refetch an asset when it changes."""
    with open(os.path.join(ROOT, "static", "assets", name), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:8]


def page(cfg, title, body, description="", path="", extra_head=""):
    url = cfg["site_url"].rstrip("/") + "/" + path
    desc = html.escape(description or cfg["tagline"])
    full_title = html.escape(title + (" | " + cfg["title"] if title != cfg["title"] else ""))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{full_title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{full_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{cfg['site_url'].rstrip('/')}/assets/cover.jpg">
<link rel="alternate" type="application/rss+xml" title="{html.escape(cfg['title'])}" href="/feed.xml">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400;1,500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400;1,8..60,500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css?v={asset_version('style.css')}">
{extra_head}
</head>
<body>
{body}
<script src="/assets/app.js?v={asset_version('app.js')}" defer></script>
</body>
</html>
"""


def media_url(cfg, ep):
    return cfg["media_base_url"].rstrip("/") + "/" + ep["episode_id"] + ".mp3"


def episode_row(cfg, ep):
    e = html.escape
    dur = fmt_duration(ep.get("duration"))
    meta = e(fmt_date(ep["date"])) + (f"<span>{e(dur)}</span>" if dur else "")
    topic = f'<span class="topic">on {e(ep["topic"])}</span>' if ep["topic"] else ""
    label = f'<p class="ep-label">{e(ep["label"])}</p>\n    ' if ep["label"] else ""
    return f"""<li class="ep" data-search="{e((ep['title'] + ' ' + ep['summary']).lower())}">
  <button class="play" type="button" data-src="{e(media_url(cfg, ep))}" data-title="{e(ep['title'])}" aria-label="Play {e(ep['guest'])}"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="i-play" d="M8 5v14l11-7z"/><path class="i-pause" d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg></button>
  <div class="ep-body">
    {label}<h3><a href="/episodes/{e(ep['episode_id'])}/"><span class="guest">{e(ep['guest'])}</span> {topic}</a></h3>
    <p class="ep-meta">{meta}</p>
  </div>
</li>"""


def site_nav(cfg):
    return f"""<header class="header">
  <nav class="nav" aria-label="Site">
    <a class="nav__logo" href="/">{html.escape(cfg['title'])}</a>
    <ul class="nav__menu">
      <li><a class="nav__link" href="/#archive">Episodes</a></li>
      <li><a class="nav__link" href="/#about">About</a></li>
      <li><a class="nav__link" href="/#subscribe">Subscribe</a></li>
    </ul>
  </nav>
</header>"""


def site_footer(cfg):
    credit = html.escape(cfg["footer"]).replace(
        "Polyculture Research", '<a href="https://polycultureresearch.com">Polyculture Research</a>')
    return f"""<footer class="footer">
  <nav class="footer__nav" aria-label="Footer"><a href="/#archive">Episodes</a><a href="/feed.xml">Podcast feed</a><a href="https://polycultureresearch.com">Polyculture Research</a></nav>
  <p class="footer__copyright">{credit}</p>
</footer>"""


def build_index(cfg, eps, seasons):
    e = html.escape
    jump = "".join(f'<a href="#season-{s}" aria-label="Season {s}">{s}</a>' for s in sorted(seasons))
    sections = []
    for s in sorted(seasons):
        info = seasons[s]
        name = f"Season {s}" + (f": {info['name']}" if info.get("name") else "")
        items = "\n".join(episode_row(cfg, ep) for ep in info["eps"])
        blurb = f'<p class="season-blurb">{e(info["blurb"])}</p>' if info.get("blurb") else ""
        if info.get("credit"):
            blurb += f'<p class="season-blurb season-credit">{info["credit"]}</p>'
        count = f"{len(info['eps'])} episode{'' if len(info['eps']) == 1 else 's'}"
        sections.append(f"""<section class="season" id="season-{s}" aria-labelledby="h-season-{s}">
  <header class="season-head"><p class="eyebrow">{e(info['years'])} · {count}</p><h2 class="accent-heading" id="h-season-{s}">{e(name)}</h2>{blurb}</header>
  <ol class="eps">
{items}
  </ol>
</section>""")

    # Hero title: the whole show name takes the accent colour.
    title = f'<span class="hero__accent">{e(cfg["title"])}</span>'
    site = cfg["site_url"].rstrip("/")
    lead = [e(" ".join(cfg["about"][:-1])), e(cfg["about"][-1] + " " + cfg["hosts_line"] + ".")]
    if cfg.get("hosts_now"):  # trusted HTML from site.json, may carry a link
        lead[-1] += " " + cfg["hosts_now"]
    lead = "\n      ".join(f'<p class="intro__lead">{p}</p>' for p in lead)
    body = f"""<a class="skip" href="#archive">Skip to episodes</a>
{site_nav(cfg)}
<section class="hero">
  <div class="hero__background"><img src="/assets/hero.jpg" alt="{e(cfg.get('hero_alt', ''))}"><div class="hero__overlay"></div></div>
  <div class="hero__content">
    <h1 class="hero__title">{title}</h1>
    <p class="hero__subtitle">{e(cfg['tagline'])}</p>
  </div>
</section>
<main>
  <section class="band intro" id="about">
    <div class="band__inner">
      {lead}
    </div>
  </section>
  <div class="archive" id="archive">
    <div class="find">
      <label for="q">Find an episode</label>
      <div class="find__row">
        <input id="q" type="search" placeholder="Try seeds, fermentation, Oakland…" autocomplete="off">
        <nav class="jump" aria-label="Seasons"><span>Season</span>{jump}</nav>
      </div>
      <p class="find-status" id="find-status" aria-live="polite"></p>
    </div>
    {''.join(sections)}
  </div>
  <section class="cta-band" id="subscribe">
    <h2>Listen in your podcast app</h2>
    <p>Add the archive feed to any podcast app to get every episode.</p>
    <a class="button button--primary" href="/feed.xml">Open the podcast feed</a>
    <p class="feed-url">{e(site)}/feed.xml</p>
  </section>
</main>
{site_footer(cfg)}
<div class="player" id="player" hidden>
  <p class="now" id="now"></p>
  <audio id="audio" controls preload="none"></audio>
</div>"""
    return page(cfg, cfg["title"], body, cfg["tagline"])


def build_episode(cfg, ep, prev_ep, next_ep):
    e = html.escape
    src = media_url(cfg, ep)
    topic = f'<p class="lead">On {e(ep["topic"])}</p>' if ep["topic"] else ""
    nav = []
    if prev_ep:
        nav.append(f'<a class="prev" href="/episodes/{e(prev_ep["episode_id"])}/"><span>Earlier</span>{e(prev_ep["guest"])}</a>')
    if next_ep:
        nav.append(f'<a class="next" href="/episodes/{e(next_ep["episode_id"])}/"><span>Later</span>{e(next_ep["guest"])}</a>')
    dur = fmt_duration(ep.get("duration"))
    kicker = f"Season {ep['season']}" + (f" · {ep['label']}" if ep["label"] else "")
    body = f"""<a class="skip" href="#episode">Skip to episode</a>
{site_nav(cfg)}
<main id="episode" class="page">
  <a class="eyebrow" href="/#season-{ep['season']}">{e(kicker)}</a>
  <h1>{e(ep['guest'])}</h1>
  {topic}
  <p class="ep-meta">{e(fmt_date(ep['date']))}{('<span>' + e(dur) + '</span>') if dur else ''}</p>
  <audio class="ep-audio" controls preload="metadata" src="{e(src)}"></audio>
  <p class="download"><a class="button button--secondary" href="{e(src)}" download>Download MP3</a></p>
  <div class="notes">{ep['notes'] or '<p>No show notes for this episode.</p>'}</div>
  <nav class="pager" aria-label="More episodes">{''.join(nav)}</nav>
</main>
{site_footer(cfg)}"""
    return page(cfg, ep["title"], body, ep["summary"], f"episodes/{ep['episode_id']}/")


def build_feed(cfg, eps):
    """A podcast RSS feed pointing at our own media host, so podcast apps can subscribe again."""
    e = html.escape
    site = cfg["site_url"].rstrip("/")
    items = []
    for ep in sorted(eps, key=lambda x: x["date"], reverse=True):
        try:
            d = dt.datetime.fromisoformat(ep["date"]).replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        length = ep.get("audio_bytes") or ep.get("enclosure_length") or "0"
        ep_type = "bonus" if ep["kind"] in ("special", "other") else "full"
        num = f"<itunes:episode>{e(ep['number'])}</itunes:episode>" if ep["number"].isdigit() else ""
        items.append(f"""<item>
<title>{e(ep['title'])}</title>
<link>{site}/episodes/{e(ep['episode_id'])}/</link>
<guid isPermaLink="false">{e(ep.get('guid') or ep['episode_id'])}</guid>
<pubDate>{email.utils.format_datetime(d)}</pubDate>
<description><![CDATA[{ep['notes'].replace(']]>', ']]&gt;')}]]></description>
<enclosure url="{e(media_url(cfg, ep))}" length="{e(length)}" type="audio/mpeg"/>
<itunes:duration>{e(ep.get('duration', ''))}</itunes:duration>
<itunes:season>{ep['season']}</itunes:season>{num}
<itunes:episodeType>{ep_type}</itunes:episodeType>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{e(cfg['title'])}</title>
<link>{site}/</link>
<atom:link href="{site}/feed.xml" rel="self" type="application/rss+xml"/>
<language>en-us</language>
<description>{e(cfg['tagline'] + ' ' + ' '.join(cfg['about']))}</description>
<itunes:author>{e(cfg['author'])}</itunes:author>
<itunes:owner><itunes:name>{e(cfg['author'])}</itunes:name><itunes:email>{e(cfg['owner_email'])}</itunes:email></itunes:owner>
<itunes:image href="{site}/assets/cover.jpg"/>
<itunes:category text="Arts"><itunes:category text="Food"/></itunes:category>
<itunes:explicit>false</itunes:explicit>
<itunes:type>episodic</itunes:type>
<itunes:complete>Yes</itunes:complete>
{''.join(items)}
</channel>
</rss>
"""


def main():
    cfg = json.load(open(os.path.join(ROOT, "site.json"), encoding="utf-8"))
    eps = load_episodes()
    if not eps:
        raise SystemExit("data/episodes.csv is empty or missing; run fetch_acast.py first.")

    seasons = {}
    for ep in eps:
        seasons.setdefault(ep["season"], {"eps": []})["eps"].append(ep)
    for s, info in seasons.items():
        years = sorted({ep["date"][:4] for ep in info["eps"] if ep["date"]})
        info["years"] = years[0] if len(years) == 1 else f"{years[0]}–{years[-1][2:]}"
        info.update(cfg.get("seasons", {}).get(str(s), {}))

    # Clean rebuild of docs/, keeping hand-managed files.
    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    shutil.copytree(os.path.join(ROOT, "static"), DOCS)
    with open(os.path.join(DOCS, "CNAME"), "w") as f:
        f.write(cfg["domain"] + "\n")
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    for ext in (".jpg", ".jpeg"):
        cover = os.path.join(ROOT, "data", "cover" + ext)
        if os.path.exists(cover):
            shutil.copy(cover, os.path.join(DOCS, "assets", "cover.jpg"))

    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(cfg, eps, seasons))
    for i, ep in enumerate(eps):
        d = os.path.join(DOCS, "episodes", ep["episode_id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_episode(cfg, ep, eps[i - 1] if i else None, eps[i + 1] if i + 1 < len(eps) else None))
    with open(os.path.join(DOCS, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(build_feed(cfg, eps))
    with open(os.path.join(DOCS, "404.html"), "w", encoding="utf-8") as f:
        f.write(page(cfg, "Not found", site_nav(cfg) + '<main class="page"><h1>That page isn’t in the archive.</h1><p><a href="/#archive">Browse all episodes</a></p></main>' + site_footer(cfg)))
    print(f"built {len(eps)} episodes across {len(seasons)} seasons into {DOCS}")


if __name__ == "__main__":
    main()
