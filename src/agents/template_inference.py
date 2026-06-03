from __future__ import annotations

import json
import os
import re
import time
from typing import Annotated, Any, NotRequired

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.prompts.template_inference_prompt import PROMPT_TEMPLATE_INFERENCE


# ---------------------------------------------------------------------------
# Cost reducer
# ---------------------------------------------------------------------------

def _merge_cost(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    return (a or []) + (b or [])


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ExtractionState(TypedDict):
    """Shared state passed between every node in the extraction graph."""

    # ── inputs to graph.invoke ────────────────────────────────────────────────
    full_pdf_path:     str   # path to the original full PDF
    full_ocr_csv_path: str   # path to the full OCR CSV (all pages)
    doc_name:          str   # document folder name, used to name split PDFs
    train_pages:       int   # number of pages requested for the train set
    eval_mode:         bool  # whether to create a test split

    eval_pages: NotRequired[int]  # max test pages (None = all remaining)

    # ── set by environment_creation_node ─────────────────────────────────────
    agent_space:        NotRequired[str]       # path to agent_space working directory
    pdf_path:           NotRequired[str]       # path to the train PDF
    ocr_csv_path:       NotRequired[str]       # path to the train OCR CSV
    pdf_pages:          NotRequired[list[str]] # base64 images of train pages
    actual_train_pages: NotRequired[int]       # actual number of train pages used

    # eval-only — set by environment_creation_node when eval_mode=True
    test_pdf_path: NotRequired[str]
    test_ocr_path: NotRequired[str]
    test_start:    NotRequired[int]
    test_end:      NotRequired[int]

    # ── accumulated across all nodes ─────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    cost:     Annotated[list[dict], _merge_cost]

    # ── set by template_inference_node ────────────────────────────────────────
    template: NotRequired[list[dict[str, Any]]]
    metadata: NotRequired[list[str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse the LLM response as JSON, stripping markdown fences if present."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def template_inference_node(state: ExtractionState, llm: BaseChatModel) -> dict[str, Any]:
    """Send PDF page images to a vision LLM to infer the document template.

    Reads:
        state["pdf_pages"]  – list of base64-encoded image strings (up to 3).

    Writes:
        messages            – appends the assistant response.
        template            – list of template node dicts (type, fields, bid, child, node_id).
        metadata            – list of fixed metadata phrase strings.
    """
    content: list[dict[str, Any]] = [
        {"type": "text", "text": "Here are the first pages of the PDF document:"},
    ]
    for image_b64 in state["pdf_pages"]:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
        })

    t0 = time.time()
    response = llm.invoke([
        SystemMessage(content=PROMPT_TEMPLATE_INFERENCE),
        HumanMessage(content=content),
    ])
    duration = time.time() - t0

    parsed = _parse_json_response(response.content)

    template_path = os.path.join(os.path.dirname(state["agent_space"]), "template.json")
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump({"template": parsed.get("template", []), "metadata": parsed.get("metadata", [])}, f, indent=2)

    usage = response.usage_metadata or {}
    tokens = usage.get("total_tokens") or (
        (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
    ) or None

    cost_entry: dict = {"phase": "template_inference", "duration_s": round(duration, 3)}
    if tokens:
        cost_entry["tokens"] = tokens

    return {
        "messages": [response],
        "template": parsed.get("template", []),
        "metadata": parsed.get("metadata", []),
        "cost": [cost_entry],
    }
