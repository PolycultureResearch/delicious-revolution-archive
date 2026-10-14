#!/usr/bin/env python3
"""Check edited and formatted transcripts against the Whisper output.

For each episode with a formatted transcript, split the Whisper text into ten slices and
report the share of each slice's longer words that survive near the same place in the
formatted file. A low slice means content was dropped or summarized there (the first and
last slices run lower because show boilerplate is removed on purpose).

Usage:  scripts/check_transcripts.py [episode_id ...]     (default: every formatted episode)
"""
import glob
import os
import re
import sys

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "transcripts")


def words(path):
    with open(path, encoding="utf-8") as f:
        return re.findall(r"[a-z']+", f.read().lower())


def main():
    ids = sys.argv[1:] or sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(T, "formatted", "*.md")))
    bad = 0
    for i in ids:
        raw = words(os.path.join(T, "whisper", i + ".txt"))
        out = words(os.path.join(T, "formatted", i + ".md"))
        shares = []
        for k in range(10):
            src = {w for w in raw[len(raw) * k // 10:len(raw) * (k + 1) // 10] if len(w) > 6}
            lo = max(0, len(out) * k // 10 - 500)
            near = set(out[lo:len(out) * (k + 1) // 10 + 500])
            shares.append(round(100 * len(src & near) / len(src)) if src else 100)
        ratio = round(100 * len(out) / max(1, len(raw)))
        flag = "" if min(shares[1:9]) >= 90 and ratio >= 75 else "  <-- CHECK"
        bad += bool(flag)
        print(f"{i[:48]:48} {len(raw):6} -> {len(out):6} ({ratio}%)  {shares}{flag}")
    print(f"{len(ids)} checked, {bad} flagged")


if __name__ == "__main__":
    main()
