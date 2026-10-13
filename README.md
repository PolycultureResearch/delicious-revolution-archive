# Delicious Revolution archive

Static archive site for Delicious Revolution (2015 to 2018), served at
https://deliciousrevolution.polycultureresearch.com by GitHub Pages.
Episode audio lives in Cloudflare R2, not in this repo.

## How the pieces fit

```
Acast RSS feed ──fetch_acast.py──> archive/                  (in this repo)
                                     feed/acast-feed-*.xml    raw feed, byte for byte
                                     episodes.csv             metadata, one row per episode
                                     excluded_previews.csv    what was left out
                                     audio/<episode_id>.mp3   the episodes (gitignored)
                                     images/                  cover art
                                           │
              copy episodes.csv + cover ───┤                  upload_r2.sh
                                           ▼                        ▼
           data/episodes.csv ──build_site.py──> docs/     R2: <bucket>/delicious-revolution/<episode_id>.mp3
                                                (GitHub Pages)        (media_base_url in site.json)
```

`episode_id` is the key that ties everything together: the CSV row, the
audio file name (`audio/<episode_id>.mp3`), the R2 object name, and the
episode page URL (`/episodes/<episode_id>/`). Each row also records the
file's size and sha256, so the pairing can be verified at any time.

## 1. Download from Acast (one time)

From the repo root:

```sh
python3 scripts/fetch_acast.py
```

It saves the raw feed, writes `archive/episodes.csv`, and downloads every
episode except previews (titles containing "preview"; the skipped items are
listed in `archive/excluded_previews.csv`) into `archive/audio/`. Expect
roughly 3 GB. Re-running is safe: finished files are skipped and failed ones
retried. The feed, CSVs and artwork are committed; the MP3s are not (they
live in R2, see below).

## 2. Build the site

```sh
cp archive/episodes.csv data/episodes.csv
cp archive/images/<show cover>.jpg data/cover.jpg   # file named in archive/channel.txt
python3 scripts/build_site.py
```

Preview locally with `python3 -m http.server -d docs 8000`.

Fixes go in `data/overrides.csv` (never edit `episodes.csv` by hand, so a
re-fetch can't clobber them). Columns: `episode_id`, then any of `season`,
`number` and `kind` (`episode` to show an episode number), `title`, `hide` (yes to leave an item off the site), `notes_override`
(plain text; blank lines make paragraphs). Season names and site text live in
`site.json`.

## 3. Media storage: Cloudflare R2

1. Cloudflare dashboard → R2 → create bucket `media`.
2. Bucket → Settings → Custom Domains → connect `media.polyculture.net`.
   The `polyculture.net` zone is registered at Cloudflare, so its DNS is already there.
3. R2 → Manage API tokens → create a token with Object Read & Write on that bucket.
4. `brew install rclone`, then `rclone config`: new remote named `r2`, type `s3`,
   provider `Cloudflare`, paste the key, secret, and the account endpoint
   `https://<account_id>.r2.cloudflarestorage.com`.
5. From the repo root: `scripts/upload_r2.sh archive/audio`.
   It uploads, verifies checksums, and confirms every episode URL answers a
   byte-range request with HTTP 206.

If you change bucket, prefix, or domain, update `media_base_url` in `site.json`
and the `R2_*` variables when running the upload script.

## 4. GitHub Pages

1. Repo: `PolycultureResearch/delicious-revolution-archive`.
2. Repo → Settings → Pages → Deploy from a branch → `main`, folder `/docs`.
3. DNS: `CNAME deliciousrevolution → polycultureresearch.github.io` (if on Cloudflare, set it to "DNS only", grey cloud).
4. Back in Pages settings, confirm the custom domain and tick Enforce HTTPS once the certificate is issued.

## Podcast feed

`docs/feed.xml` is a full podcast feed pointing at the R2 audio, so the show
can be subscribed to again. Set `owner_email` in `site.json` before submitting
it to Apple Podcasts or Spotify.
