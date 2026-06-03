#!/usr/bin/env python3
"""Ground-truth generator for block extraction evaluation.

Samples N pages from a PDF, sends each page image to the vision LLM and asks it
to detect and extract every block directly — no OCR, no scripts, no pipeline code.
The model output is the ground truth.

Usage:
    python src/eval/ground_truth.py <pdf_path> [--pages N] [--seed S] [--out PATH]
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import random
import re
import sys

import pdfplumber
from langchain_core.messages import HumanMessage, SystemMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.models import get_llm
from src.ground_truth_gen.prompt import build_prompt


# ── helpers ───────────────────────────────────────────────────────────────────

def _render_page_b64(page) -> str:
    buf = io.BytesIO()
    page.to_image(resolution=150).original.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _parse_json(text: str) -> dict:
    """Extract and parse the first JSON object found in the model response."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _load_page_ocr(csv_path: str, page_num: int) -> str:
    """Return OCR words for one page sorted in top-to-bottom, left-to-right order."""
    words = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if int(row["page"]) == page_num:
                words.append((float(row["top"]), float(row["x0"]), row["text"]))
    words.sort()
    return " ".join(w[2] for w in words)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate ground-truth block extractions for a PDF using the vision LLM."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("--template", default=None,
                        help="Path to template.json (default: <pdf_dir>/template.json).")
    parser.add_argument("--pages", type=int, default=3, metavar="N",
                        help="Number of pages to sample (default: 3).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for page sampling (default: random).")
    parser.add_argument("--out", default="ground_truth.json",
                        help="Output file path (default: ground_truth.json).")
    parser.add_argument("--ocr", default=None,
                        help="Path to OCR CSV (columns: page,x0,top,x1,bottom,text).")
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf_path)
    if not os.path.isfile(pdf_path):
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    template_path = args.template or os.path.join(os.path.dirname(pdf_path), "template.json")
    if not os.path.isfile(template_path):
        print(f"Error: template not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    with open(template_path, encoding="utf-8") as f:
        template = json.load(f).get("template", [])

    ocr_path = args.ocr
    if ocr_path and not os.path.isfile(ocr_path):
        print(f"Error: OCR file not found: {ocr_path}", file=sys.stderr)
        sys.exit(1)

    system_prompt = build_prompt(template)
    llm = get_llm()

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        rng = random.Random(args.seed)
        indices = sorted(rng.sample(range(total), min(args.pages, total)))
        print(f"Sampling pages: {[i + 1 for i in indices]} / {total}")

        all_records = []
        record_counter = 0
        for idx in indices:
            page_num = idx + 1
            print(f"  Processing page {page_num}...", end=" ", flush=True)

            image_b64 = _render_page_b64(pdf.pages[idx])

            content = [
                {"type": "text",
                 "text": f"Extract all records from page {page_num} of the document."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]
            if ocr_path:
                ocr_text = _load_page_ocr(ocr_path, page_num)
                content.append({
                    "type": "text",
                    "text": f"OCR words on this page (exact character sequences, reading order):\n{ocr_text}",
                })

            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ])

            try:
                parsed = _parse_json(response.content)
                page_records = parsed.get("records", [])
            except (json.JSONDecodeError, AttributeError) as exc:
                print(f"WARN: could not parse response ({exc})")
                page_records = []

            n_blocks = 0
            for record in page_records:
                blocks = record.get("data", [])
                for block in blocks:
                    block["page"] = page_num
                all_records.append({
                    "record_id": str(record_counter),
                    "data": blocks,
                })
                record_counter += 1
                n_blocks += len(blocks)

            print(f"{len(page_records)} record(s), {n_blocks} block(s) found.")

        results = all_records

    out_path = os.path.abspath(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Ground truth saved → {out_path}")


if __name__ == "__main__":
    main()
