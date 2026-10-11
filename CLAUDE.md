# Delicious Revolution archive: handoff notes

Static archive site for Delicious Revolution, the food radio show and podcast
Devon Sampson and Chelsea Wills produced 2015 to 2018. Goal: get every published
episode back online with its show notes.

- Site: https://deliciousrevolution.polycultureresearch.com (GitHub Pages, served from `docs/`)
- Repo: PolycultureResearch/delicious-revolution-archive
- Audio: Cloudflare R2 bucket `media`, public via the custom domain `media.polyculture.net`
  (`polyculture.net` is registered at Cloudflare); `media_base_url` in `site.json` is
  `https://media.polyculture.net/delicious-revolution`
- Source of truth for episodes: the old Acast RSS feed
  `https://feeds.acast.com/public/shows/5bd8a109e7394b07090e2d66`
  (Apple Podcasts lists 64 episodes, 2015 to 2018)

README.md has the full pipeline and setup steps. Read it first.

## Current state (2026-10-10)

- Fetched from the real feed: 64 items, 59 kept, 5 previews excluded, no failed downloads.
- All 59 MP3s are in R2 (checksums match, every URL answers a range request with 206).
- Site restyled to the Polyculture Research design system and built into `docs/`.
- DNS: `deliciousrevolution` CNAME to `polycultureresearch.github.io` is set at Namecheap.
- Still to do: enable GitHub Pages from `main` / `docs` with the custom domain, then steps 4, 5
  and 8 below.

## The one rule: episode_id is the key

`episode_id` (`<date>_<slug of title>`) ties together the CSV row, `archive/audio/<episode_id>.mp3`,
the R2 object `<prefix>/<episode_id>.mp3`, and the page `/episodes/<episode_id>/`. Don't rename
files or change the id scheme once audio is uploaded. Each row also has `audio_bytes` and `audio_sha256`.

## Next steps

Steps 1 to 3, 6 (commit and push) and 7 are done; they stay here as a record of the pipeline.

1. Check the fetch: `archive/fetch_log.txt` for failures (re-running retries them), row count in
   `archive/episodes.csv` (expect about 60+), and `archive/excluded_previews.csv`. Only titles
   containing "preview" are excluded; specials, the season recap and "Announcing Season 6" are
   kept on purpose. Confirm that split with Devon.
2. `cp archive/episodes.csv data/` and copy the show cover from `archive/images/` (named in
   `archive/channel.txt`) to `data/cover.jpg`, then `python3 scripts/build_site.py`.
3. Preview: `python3 -m http.server -d docs 8000`. Check every season, an episode page, mobile width,
   and the search box.
4. Check season grouping. `build_site.py` assigns seasons by episode number
   (`SEASONS_BY_NUMBER`: 1-11, 12-20, 21-29, 30-42, 43-50, 51+) and falls back to air date
   (`SEASONS_BY_DATE`) for specials and announcements. Fix individual items with `data/overrides.csv`,
   never by editing `data/episodes.csv`.
5. Fill thin show notes. Some feed items have only a title line (seen: #50, #45, #40). Better text
   exists in Devon's local archive (below); put it in `data/overrides.csv` `notes_override`.
6. Commit (including `docs/`, `archive/feed/`, `archive/*.csv`, `archive/images/`; MP3s are gitignored),
   push, then enable Pages from `main` / `docs`. DNS: CNAME `deliciousrevolution` to
   `polycultureresearch.github.io` (DNS only if on Cloudflare).
7. R2: bucket plus custom domain (the domain's zone must be on Cloudflare), rclone remote
   named `r2`, then `scripts/upload_r2.sh archive/audio`. It verifies checksums and that every URL
   returns 206 to a range request.
8. Set `owner_email` in `site.json` before anyone submits `docs/feed.xml` to Apple or Spotify.

## Known quirks

- Numbering: Season 6 reused #51 (Elizabeth Mpofu). A planned Season 5 #51 (Jocelyn Boreta) appears in
  local notes but likely never aired. Severine von Tscharner Fleming (#47 by schedule) has no number in
  her feed title, so she shows with no "No." label; add the number via an override title if wanted.
- Some feed enclosures declare `length="0"`; the site feed uses the downloaded `audio_bytes` instead.
- Season names in `site.json`: 4 "California Food Systems", 5 "Migrations", 6 "The Movement Builders".
  Seasons 1 to 3 had no names in the notes.
- Claude cloud sessions could not reach acast.com (org egress policy). Local runs are fine.

## Devon's local archive (reference only, don't modify)

`~/Library/Mobile Documents/com~apple~CloudDocs/from dropbox/Delicious Revolution/`
Show notes by season (most are Apple Pages files; the text is inside `Index/Document.iwa`, snappy-compressed):
- S1: `Delicious Revolution-KOWS/EpisodeDescriptionsnodates.docx`
- S2: `Season 2/Season 2 Documents/Season 2 Bios and Titles.pages`
- S3: `Season 3/Season 3 episode descriptions - show notes.pages`
- S4: `Season 4/Season 4 Show Titles and Notes.pages`
- S5: `Season 5/Titles and Bios - season 5.pages`
- S6: `Season 6/Titles and Show Notes.pages`
Guest photos are in each season's images folder and `Images/`, if episode artwork is wanted later.

## Style

Devon dislikes em dashes in written copy; use commas, colons or new sentences.
Design follows the Polyculture Research design system (https://claude.ai/artifact/3rENc1dDrGU8pZWfgmh2fQ),
Cream theme: Figtree headings, Source Serif 4 body, slate and cream grounds, fuchsia and blue accents at
display size only. Token names in `static/assets/style.css` match the system's. One shared player, plain search.
