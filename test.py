"""Test grouping_node → ground_truth_node → eval_node in isolation.

Assumes:
    data/<doc_id>/<doc_id>.pdf          – full PDF
    data/<doc_id>/ocr_extraction_full.csv
    data/<doc_id>/template.json         – from a prior run
    data/<doc_id>/pipeline/             – assembled pipeline folder from a prior run

Creates (if not already present):
    data/<doc_id>/agent_space/train/<doc_id>.pdf
    data/<doc_id>/agent_space/train/ocr_extraction.csv
    data/<doc_id>/agent_space/test/<doc_id>.pdf
    data/<doc_id>/agent_space/test/ocr_extraction.csv

Runs:
    grouping_node      → data/<doc_id>/pipeline/grouped.json  (pipeline on test PDF)
    ground_truth_node  → data/<doc_id>/pipeline/ground_truth.json
    eval_node          → data/<doc_id>/pipeline/eval.json + eval.txt
"""

import csv
import json
import os

import pypdfium2 as pdfium

from src.agents.eval import eval_node
from src.agents.ground_truth import ground_truth_node
from src.agents.grouping import grouping_node
from src.models import get_llm

# ── config ────────────────────────────────────────────────────────────────────

doc_id      = "id_60"
train_pages = 3          # first N pages used for training

# ── paths ─────────────────────────────────────────────────────────────────────

data_dir    = os.path.join("data", doc_id)
full_pdf    = os.path.join(data_dir, f"{doc_id}.pdf")
full_ocr    = os.path.join(data_dir, "ocr_extraction_full.csv")
agent_space = os.path.join(data_dir, "agent_space")
train_dir   = os.path.join(agent_space, "train")
test_dir    = os.path.join(agent_space, "test")
train_pdf   = os.path.join(train_dir, f"{doc_id}.pdf")
train_ocr   = os.path.join(train_dir, "ocr_extraction.csv")
test_pdf    = os.path.join(test_dir,  f"{doc_id}.pdf")
test_ocr    = os.path.join(test_dir,  "ocr_extraction.csv")

for p in [full_pdf, full_ocr]:
    if not os.path.isfile(p):
        raise SystemExit(f"ERROR: required file not found: {p}")

pipeline_dir = os.path.join(data_dir, "pipeline")
if not os.path.isdir(pipeline_dir):
    raise SystemExit(f"ERROR: pipeline folder not found at {pipeline_dir}. Run 'python run.py {doc_id}' first.")

template_path = os.path.join(data_dir, "template.json")
if not os.path.isfile(template_path):
    raise SystemExit(f"ERROR: template.json not found at {template_path}.")

# ── build train / test splits ─────────────────────────────────────────────────

os.makedirs(train_dir, exist_ok=True)
os.makedirs(test_dir,  exist_ok=True)

doc = pdfium.PdfDocument(full_pdf)
total_pages = len(doc)
test_start  = train_pages + 1
test_end    = total_pages

if not os.path.isfile(train_pdf):
    print(f"Cropping train PDF: pages 1–{train_pages} → {train_pdf}")
    new = pdfium.PdfDocument.new()
    new.import_pages(doc, list(range(min(train_pages, total_pages))))
    new.save(train_pdf)
else:
    print(f"Train PDF exists: {train_pdf}")

if not os.path.isfile(test_pdf):
    print(f"Extracting test PDF: pages {test_start}–{test_end} → {test_pdf}")
    new = pdfium.PdfDocument.new()
    indices = [p - 1 for p in range(test_start, test_end + 1)]
    new.import_pages(doc, indices)
    new.save(test_pdf)
else:
    print(f"Test PDF exists: {test_pdf}")

if not os.path.isfile(train_ocr):
    print(f"Cropping train OCR: pages 1–{train_pages} → {train_ocr}")
    with open(full_ocr, encoding="utf-8") as fin, \
         open(train_ocr, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if int(row["page"]) <= train_pages:
                writer.writerow(row)
else:
    print(f"Train OCR exists: {train_ocr}")

if not os.path.isfile(test_ocr):
    print(f"Extracting test OCR: pages {test_start}–{test_end} → {test_ocr}")
    with open(full_ocr, encoding="utf-8") as fin, \
         open(test_ocr, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            p = int(row["page"])
            if test_start <= p <= test_end:
                row = dict(row)
                row["page"] = str(p - train_pages)
                writer.writerow(row)
else:
    print(f"Test OCR exists: {test_ocr}")

# ── load template ─────────────────────────────────────────────────────────────

with open(template_path, encoding="utf-8") as f:
    template = json.load(f)["template"]
print(f"Template: {len(template)} node(s)")

# ── build state ───────────────────────────────────────────────────────────────

state = {
    "agent_space":    agent_space,
    "pdf_path":       train_pdf,
    "ocr_csv_path":   train_ocr,
    "test_pdf_path":  test_pdf,
    "test_ocr_path":  test_ocr,
    "template":       template,
    "messages":       [],
    "cost":           [],
}

# ── run nodes ─────────────────────────────────────────────────────────────────

print("\n── grouping_node ────────────────────────────────────────────")
result = grouping_node(state)
state["cost"] = state["cost"] + result.get("cost", [])
print(f"duration: {result['cost'][0]['duration_s']}s")

print("\n── ground_truth_node ────────────────────────────────────────")
llm = get_llm()
result = ground_truth_node(state, llm)
state["cost"] = state["cost"] + result.get("cost", [])
print(f"duration: {result['cost'][0]['duration_s']}s")

print("\n── eval_node ────────────────────────────────────────────────")
result = eval_node(state)
state["cost"] = state["cost"] + result.get("cost", [])
print(f"duration: {result['cost'][0]['duration_s']}s")
