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
from src.prompts.ground_truth_generator_prompt import GROUND_TRUTH_GENERATOR_PROMPT


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

    system_prompt = GROUND_TRUTH_GENERATOR_PROMPT(template)
    llm = get_llm()

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        rng = random.Random(args.seed)
        indices = sorted(rng.sample(range(total), min(args.pages, total)))
        print(f"Sampling pages: {[i + 1 for i in indices]} / {total}")

        results = []
        for idx in indices:
            page_num = idx + 1
            print(f"  Processing page {page_num}...", end=" ", flush=True)

            image_b64 = _render_page_b64(pdf.pages[idx])

            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=[
                    {"type": "text",
                     "text": f"Extract all data blocks from page {page_num} of the document."},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ]),
            ])

            try:
                parsed = _parse_json(response.content)
                blocks = parsed.get("blocks", [])
            except (json.JSONDecodeError, AttributeError) as exc:
                print(f"WARN: could not parse response ({exc})")
                blocks = []

            results.append({"page": page_num, "blocks": blocks})
            print(f"{len(blocks)} block(s) found.")

    out_path = os.path.abspath(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Ground truth saved → {out_path}")


if __name__ == "__main__":
    main()
