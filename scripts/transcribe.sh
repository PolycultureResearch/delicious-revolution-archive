#!/usr/bin/env bash
# Transcribe episode MP3s locally with whisper.cpp (machine transcript, no speaker labels).
#
# One-time setup: `brew install whisper-cpp`, then download into ~/.cache/whisper.cpp/
#   ggml-large-v3-turbo.bin  from https://huggingface.co/ggerganov/whisper.cpp
#   ggml-silero-v5.1.2.bin   from https://huggingface.co/ggml-org/whisper-vad
#
# Usage:  scripts/transcribe.sh <episode_id> [<episode_id> ...]
# Writes transcripts/raw/<episode_id>.{txt,vtt,json}; skips episodes already done.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUDIO_DIR="${AUDIO_DIR:-$ROOT/archive/audio}"
OUT_DIR="${OUT_DIR:-$ROOT/transcripts/raw}"
MODEL="${WHISPER_MODEL:-$HOME/.cache/whisper.cpp/ggml-large-v3-turbo.bin}"
VAD_MODEL="${WHISPER_VAD_MODEL:-$HOME/.cache/whisper.cpp/ggml-silero-v5.1.2.bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT_DIR"

for id in "$@"; do
  if [ -s "$OUT_DIR/$id.txt" ]; then echo "skip $id (already transcribed)"; continue; fi
  # The episode title goes in the prompt so Whisper spells the guest's name right.
  title="$(python3 - "$ROOT/data/episodes.csv" "$id" <<'PY'
import csv, sys
for r in csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")):
    if r["episode_id"] == sys.argv[2]:
        print(r["title"])
PY
)"
  echo "== $id"
  # whisper.cpp wants 16 kHz mono WAV; afconvert ships with macOS.
  afconvert -f WAVE -d LEI16@16000 -c 1 "$AUDIO_DIR/$id.mp3" "$TMP/$id.wav"
  start=$(date +%s)
  whisper-cli -m "$MODEL" -f "$TMP/$id.wav" -l en \
    --prompt "Delicious Revolution, a show about food, culture, and place, with Chelsea Wills and Devon Sampson. $title." \
    --vad -vm "$VAD_MODEL" -otxt -ovtt -oj -of "$OUT_DIR/$id" -np > /dev/null 2>&1
  rm -f "$TMP/$id.wav"
  # Whisper can get stuck repeating one line to the end of the file. The turbo model
  # with --vad (skip non-speech) avoided it in testing, where large-v3 looped on most
  # episodes; flag any that slip through.
  worst="$(uniq -c "$OUT_DIR/$id.txt" | awk '$1 > m { m = $1 } END { print m + 0 }')"
  if [ "${worst:-0}" -ge 5 ]; then
    mv "$OUT_DIR/$id.txt" "$OUT_DIR/$id.txt.LOOPED"
    echo "   WARNING: a line repeats $worst times in a row; kept as $id.txt.LOOPED"
  fi
  echo "   done in $(( $(date +%s) - start ))s"
done
