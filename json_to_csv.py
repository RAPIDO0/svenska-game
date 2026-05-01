"""Convert words.json to a CSV file in the format expected by import_words.py.

Supports two JSON shapes:
  1. A flat list:        [{"swedish": "...", "english": "..."}, ...]
  2. Chapter-keyed dict: {"1": [{"swedish": ..., "english": ...}, ...], "2": [...]}

Usage:
    python json_to_csv.py words.json [output.csv]

If no output path is given, writes to words.csv next to the input.
"""
import csv
import json
import sys
from pathlib import Path


def flatten(data) -> list[dict]:
    """Return a flat list of {swedish, english} regardless of input shape."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        out = []
        # Sort by chapter number so order is preserved
        for key in sorted(data.keys(), key=lambda k: int(k) if str(k).isdigit() else k):
            out.extend(data[key])
        return out
    raise ValueError(f"Unexpected JSON shape: {type(data).__name__}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python json_to_csv.py <input.json> [output.csv]")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_path.with_suffix(".csv")

    if not in_path.exists():
        print(f"File not found: {in_path}")
        sys.exit(1)

    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)

    pairs = flatten(data)

    written = 0
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for entry in pairs:
            sv = (entry.get("swedish") or "").strip()
            en = (entry.get("english") or "").strip()
            if not sv or not en:
                continue
            writer.writerow(["Swedish", "English", sv, en])
            written += 1

    print(f"✓ Wrote {written} rows to {out_path}")


if __name__ == "__main__":
    main()