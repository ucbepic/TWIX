"""Stage 1 — sample each page individually, extract data, combine into one JSON."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from .agent import CallResult, call_claude
from .prompt import build_prompt
from .sample_pdf import extract_single_page
from ..eval.score import validate_tree


def _assign_block_ids(blocks: list[dict], template: list[dict]) -> list[dict]:
    """Inject block_id into each block using the template's bid values."""
    # Build per-type ordered list of bid[0] values from the template.
    type_bids: dict[str, list[int]] = {}
    for node in template:
        t = node.get("type", "")
        bid = node.get("bid", [0])[0]
        type_bids.setdefault(t, []).append(bid)

    type_seen: dict[str, int] = {}   # how many blocks of each type seen so far
    bid_counters: dict[int, int] = {}  # sequence counter per bid prefix

    result = []
    for block in blocks:
        t = block.get("type", "")
        bids = type_bids.get(t, [0])
        idx = type_seen.get(t, 0)
        bid = bids[idx % len(bids)]
        bid_counters[bid] = bid_counters.get(bid, 0) + 1
        type_seen[t] = idx + 1
        result.append({**block, "block_id": f"{bid}_{bid_counters[bid]:04d}"})
    return result


def _safe_doc_name(pdf_path: Path) -> str:
    return pdf_path.stem.replace("/", "_").replace(" ", "_")


def _read_json_loose(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    m = re.match(r"^```(?:json)?\s*\n([\s\S]*?)\n```\s*$", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


def _read_json_loose_from_text(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


@dataclass
class StageOneResult:
    ok: bool
    status: str               # "ok" | "schema_fail" | "error"
    doc_name: str
    output_path: str | None
    tree: dict | None
    errors: list[str] = field(default_factory=list)
    calls: list[CallResult] = field(default_factory=list)


def run_stage1(
    pdf_path: str | Path,
    results_dir: str | Path,
    template: list[dict],
    model: str = "claude-opus-4-7",
    project_root: str | Path | None = None,
    n_pages: int = 5,
    max_retries: int = 3,
    seed: int | None = None,
) -> StageOneResult:
    pdf_path = Path(pdf_path).resolve()
    results_dir = Path(results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    if project_root is None:
        project_root = Path.cwd()
    project_root = Path(project_root).resolve()

    doc_name = _safe_doc_name(pdf_path)
    sample_dir = project_root / ".tmp_pipeline" / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    # Pick which pages to process.
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    rng = random.Random(seed)
    page_0indices = sorted(rng.sample(range(total_pages), min(n_pages, total_pages)))

    all_calls: list[CallResult] = []
    all_errors: list[str] = []
    page_results: list[dict] = []

    for page_0idx in page_0indices:
        actual_page = page_0idx + 1  # 1-indexed

        # Extract this single page to its own PDF.
        single_pdf = sample_dir / f"{doc_name}__page{actual_page}.pdf"
        extract_single_page(pdf_path, single_pdf, page_0idx)

        page_output = sample_dir / f"{doc_name}__page{actual_page}_gt.json"
        if page_output.exists():
            page_output.unlink()

        last_errors: list[str] = []
        page_ok = False

        for attempt in range(1, max_retries + 1):
            prompt = build_prompt(
                doc_name=doc_name,
                sample_pdf_path=str(single_pdf),
                output_json_path=str(page_output),
                template=template,
                schema_errors_from_prior_attempt=last_errors if attempt > 1 else None,
            )
            result = call_claude(
                prompt=prompt,
                model=model,
                cwd=project_root,
                add_dirs=[str(project_root), str(sample_dir.parent), str(results_dir.parent)],
                timeout_s=600,
            )
            all_calls.append(result)

            if not result.ok:
                all_errors.append(
                    f"page {actual_page} attempt {attempt}: agent failed: {result.stderr[:200]}"
                )
                last_errors = ["the previous run errored; please retry"]
                continue

            data = _read_json_loose(page_output)
            if data is None:
                data = _read_json_loose_from_text(result.text)
                if data is not None:
                    page_output.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
            if data is None:
                all_errors.append(
                    f"page {actual_page} attempt {attempt}: no JSON found at {page_output}"
                )
                last_errors = [f"no JSON at {page_output}; use the Write tool to write it there"]
                continue

            blocks = data.get("blocks") if isinstance(data, dict) else None
            if not isinstance(blocks, list):
                all_errors.append(
                    f"page {actual_page} attempt {attempt}: output missing 'blocks' list"
                )
                last_errors = ['output must be a JSON object with a "blocks" list']
                continue

            # Assign block_ids and inject the page number in Python.
            blocks = _assign_block_ids(blocks, template)
            page_results.append({"page": actual_page, "blocks": blocks})
            page_ok = True
            break

        if not page_ok:
            all_errors.append(f"page {actual_page}: skipped after {max_retries} failed attempts")

    if not page_results:
        return StageOneResult(
            ok=False, status="error", doc_name=doc_name,
            output_path=None, tree=None, errors=all_errors, calls=all_calls,
        )

    # Combine all pages into a single document object.
    tree = {
        "doc_name": doc_name,
        "model": model,
        "sampled_pages": len(page_results),
        "pages": sorted(page_results, key=lambda p: p["page"]),
    }

    validation_errors = validate_tree(tree)
    if validation_errors:
        all_errors.append(f"combined output schema errors: {validation_errors[:5]}")
        return StageOneResult(
            ok=False, status="schema_fail", doc_name=doc_name,
            output_path=None, tree=None, errors=all_errors, calls=all_calls,
        )

    output_path = results_dir / "ground_truth.json"
    output_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    return StageOneResult(
        ok=True, status="ok", doc_name=doc_name,
        output_path=str(output_path), tree=tree, errors=all_errors, calls=all_calls,
    )
