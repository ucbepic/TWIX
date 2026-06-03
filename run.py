"""Entry point for PDF template inference and evaluation.

Usage:
    python run.py <name>
    python run.py <name> --pages 2
    python run.py <name> --eval

    <name> is the document folder name under data/.
    Expected layout:
        data/<name>/<name>.pdf

    Outputs written to data/<name>/:
        ocr_extraction_full.csv        – full word-level OCR dump (step 1)
        template.json                  – inferred template
        pipeline/grouped.json          – records extracted by the pipeline
        pipeline/ground_truth.json     – LLM ground truth (only with --eval)
        pipeline/eval.json / eval.txt  – evaluation results (only with --eval)

    With --eval the PDF is split into train (pages 1..N) and test (remaining
    pages). The graph builds the pipeline on the train set, then runs it on the
    test set, generates ground truth via vision LLM, and scores the result.

Environment variables:
    LLM_PROVIDER    Provider name (default: openai). See src/models/ for available providers.
    OPENAI_API_KEY  Required when LLM_PROVIDER=openai.
    OPENAI_MODEL    OpenAI model name (default: gpt-4o).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import pdfplumber

from src.agents.graph import build_graph
from src.models import get_llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_ocr_full(pdf_path: str, output_path: str) -> None:
    """Extract every word from the PDF with its bounding box and save as CSV."""
    fields = ["id", "page", "x0", "top", "x1", "bottom", "text"]
    with pdfplumber.open(pdf_path) as pdf, \
         open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        word_id = 0
        for page_num, page in enumerate(pdf.pages, start=1):
            for word in page.extract_words():
                writer.writerow({
                    "id":     word_id,
                    "page":   page_num,
                    "x0":     word["x0"],
                    "top":    word["top"],
                    "x1":     word["x1"],
                    "bottom": word["bottom"],
                    "text":   word["text"],
                })
                word_id += 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Infer the structural template of a PDF document."
    )
    parser.add_argument(
        "name",
        help="Document name — must match the folder under data/ (e.g. 'invoice_2024').",
    )
    parser.add_argument(
        "--pages", type=int, default=3, metavar="N",
        help="Number of first pages to use as the training set (default: 3).",
    )
    parser.add_argument(
        "--eval", action="store_true",
        help=(
            "Split into train/test, run the pipeline on the test set, generate "
            "ground truth via vision LLM, and score the result."
        ),
    )
    parser.add_argument(
        "--eval-pages", type=int, default=None, metavar="N",
        help="Number of pages to use as the test set (default: all remaining pages after train).",
    )
    args = parser.parse_args()

    total_steps = 2

    # --- resolve paths ---
    data_dir     = os.path.join("data", args.name)
    pdf_path     = os.path.join(data_dir, f"{args.name}.pdf")
    ocr_csv_path = os.path.join(data_dir, "ocr_extraction_full.csv")

    if not os.path.isfile(pdf_path):
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # --- step 1: full OCR extraction ---
    if os.path.isfile(ocr_csv_path):
        print(f"[1/{total_steps}] OCR already exists, skipping.", file=sys.stderr)
    else:
        print(f"[1/{total_steps}] Extracting full OCR from {pdf_path} ...", file=sys.stderr)
        extract_ocr_full(pdf_path, ocr_csv_path)
        print(f"[1/{total_steps}] OCR saved to {ocr_csv_path}", file=sys.stderr)

    # --- step 2: run graph ---
    # The graph handles everything:
    #   environment_creation → template_inference → record_separation →
    #   run_record_separation → block_separation → run_block_separation →
    #   block_samples → block_extraction_scripting → collect_extraction_scripts →
    #   grouping [→ ground_truth → eval]  (last two only when eval_mode=True)
    print(f"[2/{total_steps}] Running graph ...", file=sys.stderr)
    graph = build_graph(get_llm())
    graph.invoke({
        "full_pdf_path":     pdf_path,
        "full_ocr_csv_path": ocr_csv_path,
        "doc_name":          args.name,
        "train_pages":       args.pages,
        "eval_mode":         args.eval,
        "eval_pages":        args.eval_pages,
    })
    print(f"[2/{total_steps}] Graph complete.", file=sys.stderr)

    pipeline_dir = os.path.join(data_dir, "pipeline")
    print(f"  template    → {os.path.join(data_dir, 'template.json')}", file=sys.stderr)
    print(f"  grouped     → {os.path.join(pipeline_dir, 'grouped.json')}", file=sys.stderr)
    if args.eval:
        print(f"  ground truth → {os.path.join(pipeline_dir, 'ground_truth.json')}", file=sys.stderr)

        eval_json_path = os.path.join(pipeline_dir, "eval.json")
        if os.path.isfile(eval_json_path):
            with open(eval_json_path, encoding="utf-8") as f:
                ev = json.load(f)
            print(f"  accuracy     → {ev['accuracy']:.3f}", file=sys.stderr)
            print(f"  exact_match  → {ev['exact_match']}", file=sys.stderr)
            print(f"  eval.json    → {eval_json_path}", file=sys.stderr)
            print(f"  eval.txt     → {os.path.join(pipeline_dir, 'eval.txt')}", file=sys.stderr)


if __name__ == "__main__":
    main()
