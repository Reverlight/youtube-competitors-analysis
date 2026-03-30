#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
analyze.py — Read all CSVs in youtube_data/ and print a JSON summary report.
Claude reads this JSON to generate content suggestions.

Usage:
    ./analyze.py --niche "gaming"
"""

import argparse
import csv
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR  = SKILL_DIR / "youtube_data"


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(label: str, videos: list[dict]) -> dict:
    if not videos:
        return {"label": label, "total_videos": 0, "avg_views": 0, "top_videos": []}
    by_views = sorted(videos, key=lambda v: int(v.get("view_count", 0)), reverse=True)
    avg = sum(int(v.get("view_count", 0)) for v in videos) // len(videos)
    return {
        "label": label,
        "total_videos": len(videos),
        "avg_views": avg,
        "top_videos": [
            {
                "title":       v["title"],
                "views":       int(v.get("view_count", 0)),
                "likes":       int(v.get("like_count", 0)),
                "published":   v.get("published_at", "")[:10],
                "description": v.get("description", "")[:200],
            }
            for v in by_views[:10]
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default="", help="User's content niche, e.g. 'gaming'")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(json.dumps({
            "error": "no_data",
            "message": "No youtube_data directory found. Run fetch.py first."
        }))
        sys.exit(1)

    all_files = sorted(DATA_DIR.glob("*.csv"))
    if not all_files:
        print(json.dumps({
            "error": "no_csv",
            "message": "No CSV files found. Run fetch.py for your channel and competitors first."
        }))
        sys.exit(1)

    my_files   = [f for f in all_files if f.stem.startswith("my_channel")]
    comp_files = [f for f in all_files if not f.stem.startswith("my_channel")]

    my_videos = load_csv(my_files[-1]) if my_files else []

    report = {
        "niche":       args.niche,
        "my_channel":  summarize("my_channel", my_videos),
        "competitors": [summarize(f.stem, load_csv(f)) for f in comp_files],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()