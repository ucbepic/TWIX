"""Visualise block-separation results by drawing bounding boxes on PDF pages.

Usage:
    python test_separation.py <name> <pages> [--page-list p1 p2 ...]

Arguments:
    name            Document folder name under data/.
    pages           Number of pages to render (first N pages).
    --page-list     One or more 1-based page numbers to render instead of the first N.

Output:
    data/<name>/agent_space/page_<N>_blocks.png  for each rendered page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pdfplumber

# Distinct (fill_rgba, stroke_rgba) pairs cycled per block.
_COLOURS = [
    ((255,  80,  80,  60), (200,   0,   0, 200)),
    (( 80, 160, 255,  60), (  0,  80, 200, 200)),
    (( 80, 220, 120,  60), (  0, 150,  50, 200)),
    ((255, 200,  50,  60), (200, 130,   0, 200)),
    ((200,  80, 255,  60), (120,   0, 200, 200)),
    (( 80, 230, 230,  60), (  0, 160, 160, 200)),
]


def _block_bbox(words: list[dict]) -> tuple[float, float, float, float] | None:
    """Return (x0, top, x1, bottom) as the envelope of all words in a block."""
    if not words:
        return None
    x0     = min(w["x0"]     for w in words)
    top    = min(w["top"]    for w in words)
    x1     = max(w["x1"]     for w in words)
    bottom = max(w["bottom"] for w in words)
    return (x0, top, x1, bottom)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw block bounding boxes on PDF pages.")
    parser.add_argument("name", help="Document folder name under data/.")
    parser.add_argument("pages", type=int, help="Number of pages to render (first N).")
    parser.add_argument(
        "--page-list", nargs="+", type=int, metavar="P",
        help="Specific 1-based page numbers to render (overrides <pages>).",
    )
    args = parser.parse_args()

    data_dir        = os.path.join("data", args.name)
    pdf_path        = os.path.join(data_dir, f"agent_space/train/{args.name}.pdf")
    blocks_json     = os.path.join(data_dir, "pipeline", "block_separation.json")
    viz_dir         = os.path.join(data_dir, "viz", "block_separation")
    os.makedirs(viz_dir, exist_ok=True)

    for path, label in [(pdf_path, "PDF"), (blocks_json, "block_separation.json")]:
        if not os.path.isfile(path):
            print(f"Error: {label} not found at {path}", file=sys.stderr)
            sys.exit(1)

    with open(blocks_json, encoding="utf-8") as f:
        separation = json.load(f)

    # Build a page-number → blocks mapping for fast lookup.
    pages_data: dict[int, list[dict]] = {
        entry["page"]: entry["blocks"]
        for entry in separation.get("pages", [])
    }

    # Assign a stable colour to each unique template_block_id (the part before the _).
    all_template_ids: list[str] = list(dict.fromkeys(
        block["block_id"].rsplit("_", 1)[0]
        for entry in separation.get("pages", [])
        for block in entry["blocks"]
        if "block_id" in block
    ))
    colour_map: dict[str, tuple] = {
        tid: _COLOURS[i % len(_COLOURS)]
        for i, tid in enumerate(all_template_ids)
    }

    page_numbers = args.page_list if args.page_list else list(range(1, args.pages + 1))

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for page_num in page_numbers:
            if page_num < 1 or page_num > total:
                print(f"Warning: page {page_num} out of range (PDF has {total} pages), skipping.", file=sys.stderr)
                continue

            page = pdf.pages[page_num - 1]
            img  = page.to_image(resolution=150)

            blocks = pages_data.get(page_num, [])
            for block in blocks:
                bbox = _block_bbox(block.get("words", []))
                if bbox is None:
                    continue
                template_id = block.get("block_id", "_").rsplit("_", 1)[0]
                fill, stroke = colour_map.get(template_id, _COLOURS[0])
                img.draw_rect(bbox, fill=fill, stroke=stroke, stroke_width=2)

            out_path = os.path.join(viz_dir, f"page_{page_num}_blocks.png")
            img.save(out_path, format="PNG", quantize=False)
            print(f"Page {page_num}: {len(blocks)} block(s) drawn → {out_path}")


if __name__ == "__main__":
    main()
