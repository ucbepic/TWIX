"""Visualise record-separation results by drawing bounding boxes on PDF pages.

Usage:
    python viz_record_separation.py <pdf> <json> [--base DIR] [--folder-name NAME]

Arguments:
    pdf             Path to the PDF file.
    json            Path to the record_separation JSON file.
    --base          Base document folder for output (default: parent directory of the PDF).
    --folder-name   Output subfolder name under <base>/viz/ (default: record_separation).

Output:
    <base>/viz/<folder-name>/page_<N>_records.png  for each page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pdfplumber

_COLOURS = [
    ((255,  80,  80,  60), (200,   0,   0, 200)),
    (( 80, 160, 255,  60), (  0,  80, 200, 200)),
    (( 80, 220, 120,  60), (  0, 150,  50, 200)),
    ((255, 200,  50,  60), (200, 130,   0, 200)),
    ((200,  80, 255,  60), (120,   0, 200, 200)),
    (( 80, 230, 230,  60), (  0, 160, 160, 200)),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw record bounding boxes on PDF pages.")
    parser.add_argument("pdf", help="Path to the PDF file.")
    parser.add_argument("json", help="Path to the record_separation JSON file.")
    parser.add_argument(
        "--base", default=None, metavar="DIR",
        help="Base document folder for output (default: parent directory of the PDF).",
    )
    parser.add_argument(
        "--folder-name", default="record_separation", metavar="NAME",
        help="Output subfolder under <base>/viz/ (default: record_separation).",
    )
    args = parser.parse_args()

    pdf_path     = args.pdf
    records_json = args.json
    base_dir     = os.path.abspath(args.base) if args.base else os.path.dirname(os.path.abspath(pdf_path))
    viz_dir      = os.path.join(base_dir, "viz", args.folder_name)
    os.makedirs(viz_dir, exist_ok=True)

    for path, label in [(pdf_path, "PDF"), (records_json, "JSON")]:
        if not os.path.isfile(path):
            print(f"Error: {label} not found at {path}", file=sys.stderr)
            sys.exit(1)

    with open(records_json, encoding="utf-8") as f:
        separation = json.load(f)

    records = separation.get("records", [])

    colour_map: dict[str, tuple] = {
        r["record_id"]: _COLOURS[i % len(_COLOURS)]
        for i, r in enumerate(records)
    }

    pages_data: dict[int, list[tuple]] = {}
    for record in records:
        rid = record["record_id"]
        for page_entry in record.get("pages", []):
            page_num = page_entry["page"]
            y_start  = page_entry.get("y_start")
            y_end    = page_entry.get("y_end")
            words    = page_entry.get("words", [])
            if y_start is None or y_end is None:
                if not words:
                    continue
                y_start = min(w["top"]    for w in words)
                y_end   = max(w["bottom"] for w in words)
            pages_data.setdefault(page_num, []).append((rid, y_start, y_end))

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(1, len(pdf.pages) + 1):
            page = pdf.pages[page_num - 1]
            img  = page.to_image(resolution=150)

            entries = pages_data.get(page_num, [])
            for rid, y_start, y_end in entries:
                bbox = (page.bbox[0], y_start, page.bbox[2], y_end)
                fill, stroke = colour_map.get(rid, _COLOURS[0])
                img.draw_rect(bbox, fill=fill, stroke=stroke, stroke_width=2)

            out_path = os.path.join(viz_dir, f"page_{page_num}_records.png")
            img.save(out_path, format="PNG", quantize=False)
            print(f"Page {page_num}: {len(entries)} record segment(s) drawn → {out_path}")


if __name__ == "__main__":
    main()
