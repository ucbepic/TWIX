from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.models.codex import codex_silent
from src.prompts.block_extraction_scripting_prompt import PROMPT_BLOCK_EXTRACTION_SCRIPTING


# ── animated display ──────────────────────────────────────────────────────────

_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_GREEN_TICK = "\033[32m✓\033[0m"


class _Display:
    """Thread-safe multi-line spinner for parallel Codex sessions."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self._done: dict[str, bool] = {i: False for i in ids}
        self._tokens: dict[str, int | None] = {i: None for i in ids}
        self._frame = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        # Reserve one line per block
        sys.stdout.write("\n" * len(ids))
        sys.stdout.flush()

    def _redraw(self) -> None:
        n = len(self._ids)
        sys.stdout.write(f"\033[{n}A")  # move cursor up n lines
        for tid in self._ids:
            if self._done[tid]:
                tok = self._tokens[tid]
                suffix = f"  {_GREEN_TICK}  {tok:,} tokens" if tok is not None else f"  {_GREEN_TICK}"
            else:
                suffix = f"  {_FRAMES[self._frame % len(_FRAMES)]}"
            sys.stdout.write(f"\r\033[K  block_extraction_scripting | block {tid}{suffix}\n")
        sys.stdout.flush()

    def mark_done(self, tid: str, tokens: int | None) -> None:
        with self._lock:
            self._done[tid] = True
            self._tokens[tid] = tokens
            self._redraw()

    def _spin(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if not all(self._done.values()):
                    self._frame += 1
                    self._redraw()
            time.sleep(0.1)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._spin, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_template_node(agent_space: str, template_id: str) -> dict | None:
    """Return the template node whose bid list contains int(template_id), or None."""
    template_path = os.path.join(os.path.dirname(agent_space), "template.json")
    try:
        with open(template_path, encoding="utf-8") as f:
            template = json.load(f)
        bid = int(template_id)
        for node in template.get("template", []):
            if bid in node.get("bid", []):
                return node
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


# ── node ──────────────────────────────────────────────────────────────────────

def block_extraction_scripting_node(state: dict[str, Any]) -> dict[str, Any]:
    """For each block type, run a Codex instance (in parallel) inside its sample folder
    to generate a Python extraction script generalizable to all instances of that block.

    Creates agent_space/extraction_scripts/ and writes one <template_id>.py per block type.

    Reads:
        state["agent_space"]  – directory containing block_samples/ and ../template.json
    """
    agent_space = state["agent_space"]
    train_dir   = os.path.dirname(state["pdf_path"])

    block_samples_dir = os.path.join(train_dir, "block_samples")
    extraction_scripts_dir = os.path.join(train_dir, "extraction_scripts")
    os.makedirs(extraction_scripts_dir, exist_ok=True)

    # create the list of ids
    template_ids = sorted(
        d for d in os.listdir(block_samples_dir)
        if os.path.isdir(os.path.join(block_samples_dir, d))
    )

    if not template_ids:
        print("block_extraction_scripting: no block sample folders found")
        return {}

    display = _Display(template_ids)
    spinner_thread = display.start()

    t0 = time.time()

    def _run(template_id: str) -> tuple[str, int, int | None]:
        sample_dir = os.path.join(block_samples_dir, template_id)
        template_node = _load_template_node(agent_space, template_id)
        prompt = PROMPT_BLOCK_EXTRACTION_SCRIPTING(template_id, template_node)
        rc, tokens = codex_silent(prompt, sample_dir, task=f"block_extraction_scripting_{template_id}")
        return template_id, rc, tokens

    block_tokens: list[dict] = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(_run, tid): tid for tid in template_ids}
        for future in as_completed(futures):
            template_id, rc, tokens = future.result()
            if rc != 0:
                tokens = None
            display.mark_done(template_id, tokens)
            if tokens is not None:
                block_tokens.append({"id": template_id, "tokens": tokens})

    display.stop()
    spinner_thread.join(timeout=0.2)

    duration = time.time() - t0
    total_tokens = sum(b["tokens"] for b in block_tokens) if block_tokens else None

    cost_entry: dict = {
        "phase": "block_extraction_scripting",
        "duration_s": round(duration, 3),
    }
    if total_tokens is not None:
        cost_entry["tokens"] = total_tokens
        cost_entry["blocks"] = sorted(block_tokens, key=lambda b: b["id"])

    return {"cost": [cost_entry]}
