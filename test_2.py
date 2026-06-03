import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.ground_truth_gen.ground_truth import _render_page_b64, _parse_json, _load_page_ocr
from src.ground_truth_gen.prompt import build_prompt
from src.models import get_llm

import pdfplumber
from langchain_core.messages import HumanMessage, SystemMessage

doc_id = "id_60"
pages  = 3
seed   = 42

data_dir      = os.path.join("data", doc_id)
pdf_path      = os.path.join(data_dir, f"{doc_id}.pdf")
template_path = os.path.join(data_dir, "template.json")
ocr_path      = os.path.join(data_dir, "ocr_extraction_full.csv")
out_path      = os.path.join(data_dir, "ground_truth_test.json")

with open(template_path, encoding="utf-8") as f:
    template = json.load(f)["template"]

system_prompt = build_prompt(template)
llm = get_llm()

import random
with pdfplumber.open(pdf_path) as pdf:
    total = len(pdf.pages)
    rng = random.Random(seed)
    indices = sorted(rng.sample(range(total), min(pages, total)))
    print(f"Sampling pages: {[i + 1 for i in indices]} / {total}")

    results = []
    for idx in indices:
        page_num = idx + 1
        print(f"  Processing page {page_num}...", end=" ", flush=True)

        image_b64 = _render_page_b64(pdf.pages[idx])

        content = [
            {"type": "text",
             "text": f"Extract all data blocks from page {page_num} of the document."},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]
        if os.path.isfile(ocr_path):
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
            blocks = parsed.get("blocks", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            print(f"WARN: could not parse response ({exc})")
            blocks = []

        results.append({"page": page_num, "blocks": blocks})
        print(f"{len(blocks)} block(s) found.")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Ground truth saved → {out_path}")
