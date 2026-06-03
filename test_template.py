import json
import os
import sys

import pdfplumber

from src.agents.template_inference import template_inference_node
from src.ground_truth_gen.ground_truth import _render_page_b64
from src.models import get_llm

doc_id  = sys.argv[1] if len(sys.argv) > 1 else "id_52"
n_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

data_dir    = os.path.join("data", doc_id)
pdf_path    = os.path.join(data_dir, f"{doc_id}.pdf")
agent_space = os.path.join(data_dir, "agent_space")
os.makedirs(agent_space, exist_ok=True)

with pdfplumber.open(pdf_path) as pdf:
    total = len(pdf.pages)
    pages_to_use = min(n_pages, total)
    print(f"Rendering {pages_to_use}/{total} page(s) from {pdf_path}...")
    pdf_pages = [_render_page_b64(pdf.pages[i]) for i in range(pages_to_use)]

state = {
    "pdf_pages":    pdf_pages,
    "agent_space":  agent_space,
    "ocr_csv_path": "",
    "pdf_path":     pdf_path,
    "messages":     [],
    "cost":         [],
}

print("Running template inference...")
result = template_inference_node(state, get_llm())

template = result["template"]
metadata = result["metadata"]
cost     = result["cost"][0] if result["cost"] else {}

print(f"\nTemplate ({len(template)} node(s)):")
print(json.dumps(template, indent=2))
print(f"\nMetadata ({len(metadata)} item(s)):")
print(json.dumps(metadata, indent=2))
print(f"\nduration: {cost.get('duration_s', '?')}s   tokens: {cost.get('tokens', '?')}")
print(f"template.json → {os.path.join(data_dir, 'template_test.json')}")
