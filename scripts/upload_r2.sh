#!/usr/bin/env bash
# Upload the episode MP3s to Cloudflare R2 and check that they serve correctly.
#
# One-time setup (see README): `brew install rclone`, then `rclone config` to add
# an S3 remote named "r2" (provider Cloudflare) using an R2 API token.
#
# Usage:  scripts/upload_r2.sh "/path/to/Acast Archive/audio"
set -euo pipefail

AUDIO_DIR="${1:?give the folder that holds the <episode_id>.mp3 files}"
REMOTE="${R2_REMOTE:-r2}"
BUCKET="${R2_BUCKET:-media}"
PREFIX="${R2_PREFIX:-delicious-revolution}"
MEDIA_BASE="$(python3 -c 'import json;print(json.load(open("site.json"))["media_base_url"].rstrip("/"))')"

echo "Uploading $(ls "$AUDIO_DIR"/*.mp3 | wc -l | tr -d ' ') files to $REMOTE:$BUCKET/$PREFIX"
rclone copy "$AUDIO_DIR" "$REMOTE:$BUCKET/$PREFIX" \
  --include "*.mp3" \
  --header-upload "Content-Type: audio/mpeg" \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" \
  --s3-no-check-bucket --transfers 4 --progress

echo "Comparing local files with the bucket (size + checksum)..."
rclone check "$AUDIO_DIR" "$REMOTE:$BUCKET/$PREFIX" --include "*.mp3" --one-way

# Every episode in the CSV should be reachable at the URL the site uses,
# and must answer a byte-range request with 206 (podcast apps and Safari need this).
echo "Checking public URLs and range requests..."
fail=0
while IFS= read -r id; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -r 0-1023 "$MEDIA_BASE/$id.mp3")
  if [ "$code" != "206" ]; then echo "  $id.mp3 -> HTTP $code"; fail=1; fi
done < <(python3 -c 'import csv;[print(r["episode_id"]) for r in csv.DictReader(open("data/episodes.csv", encoding="utf-8"))]')
[ $fail = 0 ] && echo "All episodes serve with range support." || { echo "Some episodes failed (above)."; exit 1; }
