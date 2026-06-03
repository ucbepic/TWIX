from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from typing import Any

import pdfplumber


_SAMPLE_SIZE = 10


def _block_bbox(words: list[dict]) -> tuple[float, float, float, float] | None:
    if not words:
        return None
    return (
        min(w["x0"]     for w in words),
        min(w["top"]    for w in words),
        max(w["x1"]     for w in words),
        max(w["bottom"] for w in words),
    )


def block_samples_node(state: dict[str, Any]) -> dict[str, Any]:
    """Crop sample instances of each block type from the PDF and save as images.

    For every unique template_block_id (the prefix before the _ in block_id):
      - creates  agent_space/block_samples/<template_block_id>/
      - samples up to 10 instances across all pages
      - saves each crop as <full_block_id>.png

    Reads:
        state["agent_space"]  – directory containing block_separation.json
        state["pdf_path"]     – source PDF
    """
    t0 = time.time()
    train_dir = os.path.dirname(state["pdf_path"])
    pdf_path  = state["pdf_path"]

    blocks_json = os.path.join(train_dir, "block_separation.json")
    with open(blocks_json, encoding="utf-8") as f:
        separation = json.load(f)

    # Collect all instances: template_block_id -> list of (page_num, full_block_id, block_dict)
    instances: dict[str, list[tuple[int, str, dict]]] = defaultdict(list)
    for entry in separation.get("pages", []):
        page_num = entry["page"]
        for block in entry.get("blocks", []):
            full_id = block.get("block_id", "")
            if not full_id:
                continue
            template_id = full_id.rsplit("_", 1)[0]
            instances[template_id].append((page_num, full_id, block))

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for template_id, all_instances in instances.items():
            out_dir = os.path.join(train_dir, "block_samples", template_id)
            os.makedirs(out_dir, exist_ok=True)

            sample = (
                random.sample(all_instances, _SAMPLE_SIZE)
                if len(all_instances) > _SAMPLE_SIZE
                else all_instances
            )

            for page_num, full_id, block in sample:
                words = block.get("words", [])
                bbox = _block_bbox(words)
                if bbox is None or page_num < 1 or page_num > total_pages:
                    continue
                page = pdf.pages[page_num - 1]
                crop = page.crop(bbox)
                img  = crop.to_image(resolution=150)
                img.save(os.path.join(out_dir, f"{full_id}.png"), format="PNG", quantize=False)

                ox, oy = bbox[0], bbox[1]
                relative_words = [
                    {**w, "x0": w["x0"] - ox, "x1": w["x1"] - ox,
                          "top": w["top"] - oy, "bottom": w["bottom"] - oy}
                    for w in words
                ]
                relative_block = {**block, "words": relative_words}
                with open(os.path.join(out_dir, f"{full_id}.json"), "w", encoding="utf-8") as f:
                    json.dump({"page": page_num, **relative_block}, f, indent=2, ensure_ascii=False)

            print(f"block_samples: {template_id} → {len(sample)} sample(s) saved to {out_dir}")

    return {"cost": [{"phase": "block_samples", "duration_s": round(time.time() - t0, 3)}]}
