#!/usr/bin/env python3
"""Run the pipeline on a PDF, generate ground truth, and score.

Usage:
    python single_eval.py <pdf_path> <name> [--pages N] [--seed S]

    pdf_path    path to the PDF, e.g. data/id_60/agent_space/test/id_60.pdf
    name        label for this eval run — outputs go to base_folder/evals/eval_<name>/
    --pages N   sample N pages for ground truth (default: all)
    --seed S    random seed for page sampling

Expects (found by walking up from pdf_path):
    template.json
    pipeline/pipeline.py

Outputs in <base_folder>/evals/eval_<name>/:
    ocr.csv
    grouped.json
    ground_truth.json
    eval.json
    eval.txt
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys

import pdfplumber
from langchain_core.messages import HumanMessage, SystemMessage

sys.path.insert(0, os.path.dirname(__file__))

from src.eval.render import render_to_file
from src.eval.score import score as eval_score
from src.ground_truth_gen.ground_truth import _load_page_ocr, _parse_json, _render_page_b64
from src.ground_truth_gen.prompt import build_prompt
from src.models import get_llm


def _find_base_folder(start: str) -> str:
    """Walk up from start until a directory containing template.json is found."""
    current = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(current, "template.json")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise SystemExit(f"Error: could not find template.json above {start}")
        current = parent


def _extract_ocr(pdf_path: str, out_path: str) -> None:
    fields = ["id", "page", "x0", "top", "x1", "bottom", "text"]
    with pdfplumber.open(pdf_path) as pdf, \
         open(out_path, "w", newline="", encoding="utf-8", errors="replace") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        word_id = 0
        for page_num, page in enumerate(pdf.pages, start=1):
            for word in (page.extract_words() or []):
                writer.writerow({
                    "id": word_id, "page": page_num,
                    "x0": word["x0"], "top": word["top"],
                    "x1": word["x1"], "bottom": word["bottom"],
                    "text": word["text"],
                })
                word_id += 1


def _run_pipeline(pipeline_py: str, pdf_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    result = subprocess.run(
        [sys.executable, os.path.abspath(pipeline_py),
         os.path.abspath(pdf_path),
         "--out-dir", os.path.abspath(out_dir)],
        check=True,
    )


def _generate_ground_truth(
    pdf_path: str,
    template: list,
    ocr_path: str | None,
    indices: list[int],
    llm,
) -> list[dict]:
    records: list[dict] = []
    record_counter = 0
    with pdfplumber.open(pdf_path) as pdf:
        for idx in indices:
            page_num = idx + 1
            print(f"  page {page_num}...", end=" ", flush=True)
            image_b64 = _render_page_b64(pdf.pages[idx])
            content: list = [
                {"type": "text",
                 "text": f"Extract all records from page {page_num} of the document."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]
            if ocr_path and os.path.isfile(ocr_path):
                ocr_text = _load_page_ocr(ocr_path, page_num)
                content.append({
                    "type": "text",
                    "text": f"OCR words on this page (exact character sequences, reading order):\n{ocr_text}",
                })
            response = llm.invoke([
                SystemMessage(content=build_prompt(template)),
                HumanMessage(content=content),
            ])
            try:
                parsed = _parse_json(response.content)
                page_records = parsed.get("records", [])
            except (json.JSONDecodeError, AttributeError) as exc:
                print(f"WARN: {exc}")
                page_records = []

            n_blocks = 0
            for rec in page_records:
                blocks = rec.get("data", [])
                for block in blocks:
                    block["page"] = page_num
                records.append({"record_id": str(record_counter), "data": blocks})
                record_counter += 1
                n_blocks += len(blocks)
            print(f"{len(page_records)} record(s), {n_blocks} block(s)")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pipeline on a PDF, generate ground truth, and score."
    )
    parser.add_argument("pdf_path", help="Path to the PDF.")
    parser.add_argument("name", help="Eval label — outputs go to eval_<name>/ next to the PDF.")
    parser.add_argument(
        "--pages", type=int, default=None, metavar="N",
        help="Number of pages to sample for ground truth (default: all).",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for page sampling.")
    args = parser.parse_args()

    pdf_path      = os.path.abspath(args.pdf_path)
    base_folder   = _find_base_folder(os.path.dirname(pdf_path))
    eval_dir      = os.path.join(base_folder, "evals", f"eval_{args.name}")
    pipeline_py   = os.path.join(base_folder, "pipeline", "pipeline.py")
    template_path = os.path.join(base_folder, "template.json")
    ocr_path      = os.path.join(eval_dir, "ocr.csv")
    grouped_path  = os.path.join(eval_dir, "grouped.json")
    gt_path       = os.path.join(eval_dir, "ground_truth.json")

    os.makedirs(eval_dir, exist_ok=True)

    for p, label in [
        (pdf_path,      "PDF"),
        (pipeline_py,   "pipeline/pipeline.py"),
        (template_path, "template.json"),
    ]:
        if not os.path.isfile(p):
            print(f"Error: {label} not found at {p}", file=sys.stderr)
            sys.exit(1)

    with open(template_path, encoding="utf-8") as f:
        template = json.load(f).get("template", [])

    # --- OCR ---
    print("Extracting OCR...")
    _extract_ocr(pdf_path, ocr_path)
    print(f"  OCR saved → {ocr_path}")

    # --- run pipeline ---
    print("Running pipeline...")
    _run_pipeline(pipeline_py, pdf_path, eval_dir)

    with open(grouped_path, encoding="utf-8") as f:
        candidate = json.load(f)

    # --- ground truth ---
    print("Generating ground truth...")
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
    n_pages = min(args.pages, total) if args.pages is not None else total
    rng = random.Random(args.seed)
    indices = sorted(rng.sample(range(total), n_pages))
    print(f"Sampling pages: {[i + 1 for i in indices]} / {total}")

    gt_results = _generate_ground_truth(pdf_path, template, ocr_path, indices, get_llm())

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_results, f, indent=2, ensure_ascii=False)
    print(f"Ground truth saved → {gt_path}")

    # Filter candidate to pages covered by ground truth
    gt_pages = {block["page"] for rec in gt_results for block in rec.get("data", [])}
    if gt_pages:
        candidate = [
            r for r in candidate
            if any(block.get("page") in gt_pages for block in r.get("data", []))
        ]

    # --- score ---
    eval_result = eval_score(gt_results, candidate, reference="human", threshold=0.9)

    eval_json_path = os.path.join(eval_dir, "eval.json")
    eval_txt_path  = os.path.join(eval_dir, "eval.txt")
    with open(eval_json_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, indent=2, ensure_ascii=False)
    render_to_file(eval_result, eval_txt_path)

    print(f"accuracy:    {eval_result['accuracy']:.3f}")
    print(f"exact_match: {eval_result['exact_match']}")
    print(f"eval.json  → {eval_json_path}")
    print(f"eval.txt   → {eval_txt_path}")


if __name__ == "__main__":
    main()
