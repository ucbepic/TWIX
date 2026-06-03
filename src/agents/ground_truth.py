from __future__ import annotations

import base64
import io
import json
import os
import time
from typing import Any

import pdfplumber
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.ground_truth_gen.prompt import build_prompt
from src.ground_truth_gen.ground_truth import _parse_json, _load_page_ocr


def _render_page_b64(page) -> str:
    buf = io.BytesIO()
    page.to_image(resolution=150).original.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ground_truth_node(state: dict[str, Any], llm: BaseChatModel) -> dict[str, Any]:
    """Generate ground truth for all test pages and save to pipeline/ground_truth.json.

    Reads:
        state["agent_space"]    – used to derive document_dir/pipeline/
        state["test_pdf_path"]  – test PDF (used when eval_mode=True)
        state["test_ocr_path"]  – test OCR CSV (used as LLM context)
        state["pdf_path"]       – train PDF fallback (used when eval_mode=False)
        state["ocr_csv_path"]   – train OCR fallback
        state["template"]       – inferred template (from template_inference_node)

    Writes:
        document_dir/pipeline/ground_truth.json
    """
    t0 = time.time()

    document_dir = os.path.dirname(state["agent_space"])
    pipeline_dir = os.path.join(document_dir, "pipeline")
    gt_path      = os.path.join(pipeline_dir, "ground_truth.json")
    pdf_path     = state.get("test_pdf_path") or state["pdf_path"]
    ocr_path     = state.get("test_ocr_path") or state["ocr_csv_path"]
    template     = state["template"]

    system_prompt = build_prompt(template)

    records: list[dict] = []
    record_counter = 0

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"ground_truth_node: generating ground truth for {total} page(s)...")
        for idx in range(total):
            page_num = idx + 1
            print(f"  page {page_num}/{total}...", end=" ", flush=True)

            buf = io.BytesIO()
            pdf.pages[idx].to_image(resolution=150).original.save(buf, format="PNG")
            image_b64 = base64.b64encode(buf.getvalue()).decode()

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
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ])
            try:
                parsed     = _parse_json(response.content)
                page_recs  = parsed.get("records", [])
            except (json.JSONDecodeError, AttributeError) as exc:
                print(f"WARN: {exc}")
                page_recs = []

            n_blocks = 0
            for rec in page_recs:
                blocks = rec.get("data", [])
                for block in blocks:
                    block["page"] = page_num
                records.append({"record_id": str(record_counter), "data": blocks})
                record_counter += 1
                n_blocks += len(blocks)
            print(f"{len(page_recs)} record(s), {n_blocks} block(s)")

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"ground_truth_node: ground_truth.json → {gt_path}")

    duration = time.time() - t0
    return {"cost": [{"phase": "ground_truth", "duration_s": round(duration, 3)}]}
