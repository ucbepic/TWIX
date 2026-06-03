from __future__ import annotations

import base64
import csv
import io
import os
from typing import Any

import pdfplumber
import pypdfium2 as pdfium

from src.agents.template_inference import ExtractionState


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_page_count(pdf_path: str) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def _crop_pdf(src: str, dst: str, max_pages: int) -> None:
    doc = pdfium.PdfDocument(src)
    n = min(max_pages, len(doc))
    new_doc = pdfium.PdfDocument.new()
    new_doc.import_pages(doc, list(range(n)))
    new_doc.save(dst)


def _crop_ocr_csv(src: str, dst: str, max_pages: int) -> None:
    with open(src, encoding="utf-8") as fin, \
         open(dst, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if int(row["page"]) <= max_pages:
                writer.writerow(row)


def _extract_page_range_pdf(src: str, dst: str, start: int, end: int) -> None:
    doc = pdfium.PdfDocument(src)
    new_doc = pdfium.PdfDocument.new()
    indices = [p - 1 for p in range(start, end + 1) if 0 <= p - 1 < len(doc)]
    new_doc.import_pages(doc, indices)
    new_doc.save(dst)


def _extract_page_range_ocr(
    src: str, dst: str, start: int, end: int, remap_offset: int = 0
) -> None:
    with open(src, encoding="utf-8") as fin, \
         open(dst, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            p = int(row["page"])
            if start <= p <= end:
                row = dict(row)
                row["page"] = str(p - remap_offset)
                writer.writerow(row)


def _render_pages(pdf_path: str, n: int) -> list[str]:
    images: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:n]:
            buf = io.BytesIO()
            page.to_image(resolution=150).original.save(buf, format="PNG")
            images.append(base64.b64encode(buf.getvalue()).decode())
    return images


# ── node ──────────────────────────────────────────────────────────────────────

def environment_creation_node(state: ExtractionState) -> dict[str, Any]:
    full_pdf_path     = state["full_pdf_path"]
    full_ocr_csv_path = state["full_ocr_csv_path"]
    doc_name          = state["doc_name"]
    train_pages_req   = state["train_pages"]
    eval_mode         = state["eval_mode"]
    eval_pages_req    = state.get("eval_pages")

    total_pages = _get_page_count(full_pdf_path)
    data_dir    = os.path.dirname(full_pdf_path)
    # create the agent_space dir
    agent_space = os.path.join(data_dir, "agent_space")
    os.makedirs(agent_space, exist_ok=True)

    if eval_mode:
        actual_train_pages = min(train_pages_req, total_pages // 2)
        test_start = actual_train_pages + 1
        test_end = (
            min(test_start + eval_pages_req - 1, total_pages)
            if eval_pages_req is not None else total_pages
        )

        # create test dir and train dir
        train_dir = os.path.join(agent_space, "train")
        test_dir  = os.path.join(agent_space, "test")
        os.makedirs(train_dir, exist_ok=True)
        os.makedirs(test_dir, exist_ok=True)

        train_pdf = os.path.join(train_dir, f"{doc_name}.pdf")
        train_ocr = os.path.join(train_dir, "ocr_extraction.csv")
        test_pdf  = os.path.join(test_dir,  f"{doc_name}.pdf")
        test_ocr  = os.path.join(test_dir,  "ocr_extraction.csv")

        # create training data
        _crop_pdf(full_pdf_path, train_pdf, actual_train_pages)
        _crop_ocr_csv(full_ocr_csv_path, train_ocr, actual_train_pages)
        # create test data
        _extract_page_range_pdf(full_pdf_path, test_pdf, test_start, test_end)
        _extract_page_range_ocr(
            full_ocr_csv_path, test_ocr, test_start, test_end,
            remap_offset=actual_train_pages,
        )
        print(
            f"  Train: pages 1–{actual_train_pages} → {train_dir}\n"
            f"  Test:  pages {test_start}–{test_end} → {test_dir}"
        )

        ws_pdf = train_pdf
        ws_ocr = train_ocr

        out: dict[str, Any] = {
            "test_pdf_path": test_pdf,
            "test_ocr_path": test_ocr,
            "test_start":    test_start,
            "test_end":      test_end,
        }
    else:
        actual_train_pages = train_pages_req
        ws_pdf = os.path.join(agent_space, f"{doc_name}.pdf")
        ws_ocr = os.path.join(agent_space, "ocr_extraction.csv")
        _crop_pdf(full_pdf_path, ws_pdf, actual_train_pages)
        _crop_ocr_csv(full_ocr_csv_path, ws_ocr, actual_train_pages)
        print(f"  Cropped to {actual_train_pages} page(s) → {agent_space}")
        out = {}

    pdf_pages = _render_pages(ws_pdf, actual_train_pages)

    return {
        **out,
        "agent_space":        agent_space,
        "pdf_path":           ws_pdf,
        "ocr_csv_path":       ws_ocr,
        "pdf_pages":          pdf_pages,
        "actual_train_pages": actual_train_pages,
    }
