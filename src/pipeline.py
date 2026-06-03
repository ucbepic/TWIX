#!/usr/bin/env python3
"""Standalone extraction pipeline.

Usage:
    python pipeline.py <pdf_path>

Steps:
  1. OCR extraction with pdfplumber
  2. Record separation (agent-generated record_separation.py)
  3. Block separation (agent-generated block_separation.py)
  4. Coordinate relativisation + per-block extraction
  5. Save block_separation.json, record_separation.json and extracted.json in out_dir
"""

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
from collections import defaultdict
import pdfplumber


# ── OCR ───────────────────────────────────────────────────────────────────────

def _extract_ocr(pdf_path: str) -> list[dict]:
    words = []
    word_id = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for word in (page.extract_words() or []):
                words.append({
                    "id":     word_id,
                    "page":   page_num,
                    "x0":     word["x0"],
                    "top":    word["top"],
                    "x1":     word["x1"],
                    "bottom": word["bottom"],
                    "text":   word["text"],
                })
                word_id += 1
    return words


def _save_ocr_csv(words: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "page", "x0", "top", "x1", "bottom", "text"]
        )
        writer.writeheader()
        writer.writerows(words)


# ── coordinate helpers ────────────────────────────────────────────────────────

def _block_bbox(words: list[dict]):
    if not words:
        return None
    return (
        min(w["x0"]     for w in words),
        min(w["top"]    for w in words),
        max(w["x1"]     for w in words),
        max(w["bottom"] for w in words),
    )


def _relativize(words: list[dict]) -> list[dict]:
    bbox = _block_bbox(words)
    if bbox is None:
        return words
    ox, oy = bbox[0], bbox[1]
    return [
        {**w,
         "x0":     w["x0"]     - ox,
         "x1":     w["x1"]     - ox,
         "top":    w["top"]    - oy,
         "bottom": w["bottom"] - oy}
        for w in words
    ]


# ── record separation ─────────────────────────────────────────────────────────

def _run_record_separation(pipeline_dir: str, ocr_csv_path: str, out_dir: str) -> dict:
    script_path = os.path.join(pipeline_dir, "record_separation.py")
    result = subprocess.run(
        [sys.executable, script_path, ocr_csv_path, out_dir],
        cwd=pipeline_dir,
    )
    if result.returncode != 0:
        print("record_separation failed", file=sys.stderr)
        sys.exit(1)
    with open(os.path.join(out_dir, "record_separation.json"), encoding="utf-8") as f:
        return json.load(f)


# ── block separation ──────────────────────────────────────────────────────────

def _run_block_separation(pipeline_dir: str, ocr_csv_path: str, out_dir: str) -> dict:
    script_path = os.path.join(pipeline_dir, "block_separation.py")
    result = subprocess.run(
        [sys.executable, script_path, ocr_csv_path, out_dir],
        cwd=pipeline_dir,
    )
    if result.returncode != 0:
        print("block_separation failed", file=sys.stderr)
        sys.exit(1)
    with open(os.path.join(out_dir, "block_separation.json"), encoding="utf-8") as f:
        return json.load(f)


# ── extraction scripts ────────────────────────────────────────────────────────

def _load_extractors(pipeline_dir: str) -> dict:
    """Import every <template_id>.py from extraction_scripts/ and return {id: extract_fn}."""
    scripts_dir = os.path.join(pipeline_dir, "extraction_scripts")
    extractors = {}
    for fname in sorted(os.listdir(scripts_dir)):
        if not fname.endswith(".py"):
            continue
        template_id = fname[:-3]
        spec = importlib.util.spec_from_file_location(
            f"extractor_{template_id}",
            os.path.join(scripts_dir, fname),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        extractors[template_id] = module.extract
    return extractors


# ── grouping ──────────────────────────────────────────────────────────────────

def _group_records(record_separation: dict, block_separation: dict, extracted: list[dict]) -> list[dict]:
    # Build spatial index: uid → (page, y_start, y_end)
    block_info = {}
    for page_entry in block_separation.get("pages", []):
        page = page_entry["page"]
        for block in page_entry.get("blocks", []):
            uid = block["uid"]
            words = block.get("words", [])
            y_start = min(w["top"]    for w in words) if words else 0
            y_end   = max(w["bottom"] for w in words) if words else 0
            block_info[uid] = (page, y_start, y_end)

    # Map each block uid to its record
    uid_to_record = {}
    for record in record_separation.get("records", []):
        record_id  = record["record_id"]
        pages      = record["pages"]
        page_start = pages[0]["page"]
        page_end   = pages[-1]["page"]
        y_start_r  = pages[0]["y_start"]
        y_end_r    = pages[-1]["y_end"]
        for uid, (page, y_start, y_end) in block_info.items():
            if page < page_start or page > page_end:
                continue
            if page == page_start and y_start < y_start_r:
                continue
            if page == page_end and y_end > y_end_r:
                continue
            uid_to_record[uid] = record_id

    # Group extracted blocks by record
    grouped: dict = defaultdict(list)
    for block in extracted:
        uid = block.get("uid")
        if uid in uid_to_record:
            grouped[uid_to_record[uid]].append(block)
        else:
            print(f"  warning: block uid={uid} not assigned to any record, skipping")

    return [{"record_id": record_id, "data": blocks} for record_id, blocks in grouped.items()]


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the extraction pipeline on a PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file to process.")
    parser.add_argument("--out-dir", default=None, metavar="DIR",
                        help="Directory for output files (default: current working directory).")
    args = parser.parse_args()

    pdf_path     = os.path.abspath(args.pdf_path)
    pipeline_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir      = os.path.abspath(args.out_dir) if args.out_dir else os.getcwd()

    # 1. OCR
    print("Extracting OCR...")
    words = _extract_ocr(pdf_path)
    ocr_csv_path = os.path.join(pipeline_dir, "ocr.csv")
    _save_ocr_csv(words, ocr_csv_path)
    print(f"  {len(words)} words extracted → ocr.csv")

    # 2. Record separation → record_separation.json written to out_dir
    print("Running record separation...")
    record_sep = _run_record_separation(pipeline_dir, ocr_csv_path, out_dir)

    # 3. Block separation → block_separation.json written to out_dir
    print("Running block separation...")
    separation = _run_block_separation(pipeline_dir, ocr_csv_path, out_dir)

    # 4. Load extractors
    extractors = _load_extractors(pipeline_dir)

    # 5. Extract each block
    print("Extracting data from blocks...")
    results = []
    for page_entry in separation.get("pages", []):
        page_num = page_entry.get("page")
        for block in page_entry.get("blocks", []):
            block_id = block.get("block_id", "")
            if not block_id:
                continue
            template_id = block_id.rsplit("_", 1)[0]
            if template_id not in extractors:
                print(f"  warning: no extractor for block {block_id}, skipping")
                continue
            relative_block = {**block, "words": _relativize(block.get("words", []))}
            try:
                extracted = extractors[template_id](relative_block)
                extracted["page"] = page_num
                extracted["uid"]  = block.get("uid")
                results.append(extracted)
            except Exception as exc:
                print(f"  warning: extraction failed for {block_id}: {exc}")

    # 6. Save extracted.json
    output_path = os.path.join(out_dir, "extracted.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  {len(results)} block(s) extracted → {output_path}")

    # 7. Group extracted blocks into records → grouped.json
    print("Grouping blocks into records...")
    grouped = _group_records(record_sep, separation, results)
    grouped_path = os.path.join(out_dir, "grouped.json")
    with open(grouped_path, "w", encoding="utf-8") as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)
    print(f"Done. {len(grouped)} record(s) → {grouped_path}")


if __name__ == "__main__":
    main()
