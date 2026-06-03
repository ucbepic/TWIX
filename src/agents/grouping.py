from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any


def grouping_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run the assembled pipeline.py on the test PDF (or train if no test) to produce grouped.json.

    Reads:
        state["agent_space"]    – used to derive document_dir/pipeline/
        state["test_pdf_path"]  – test PDF (used when eval_mode=True)
        state["pdf_path"]       – train PDF fallback (used when eval_mode=False)

    Side-effect:
        Runs pipeline.py, which writes record_separation.json, block_separation.json,
        extracted.json and grouped.json into document_dir/pipeline/.
    """
    document_dir = os.path.dirname(state["agent_space"])
    pipeline_dir = os.path.join(document_dir, "pipeline")
    pipeline_py  = os.path.join(pipeline_dir, "pipeline.py")
    pdf_path     = state.get("test_pdf_path") or state["pdf_path"]

    t0 = time.time()
    result = subprocess.run(
        [sys.executable, pipeline_py, pdf_path, "--out-dir", pipeline_dir],
        capture_output=True,
        text=True,
    )
    duration = time.time() - t0

    if result.returncode != 0:
        raise RuntimeError(
            f"pipeline.py failed (exit {result.returncode}):\n{result.stderr}"
        )
    if result.stdout:
        print(result.stdout, end="")

    grouped_path = os.path.join(pipeline_dir, "grouped.json")
    print(f"grouping_node: grouped.json → {grouped_path}")

    return {"cost": [{"phase": "grouping", "duration_s": round(duration, 3)}]}
