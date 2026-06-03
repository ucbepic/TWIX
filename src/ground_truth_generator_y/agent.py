"""Stage 1 step 3 — call the model via the `claude` CLI.

We invoke `claude --model <id> --print --output-format json -p <prompt>`. The
JSON result includes a usage block we use for token accounting.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CallResult:
    ok: bool
    text: str
    raw: dict
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    duration_ms: int = 0
    stderr: str = ""

    @property
    def total_input(self) -> int:
        return int(self.input_tokens) + int(self.cache_read) + int(self.cache_creation)


def call_claude(
    prompt: str,
    model: str = "claude-opus-4-7",
    cwd: str | Path | None = None,
    add_dirs: list[str] | None = None,
    timeout_s: int = 1200,
    extra_args: list[str] | None = None,
) -> CallResult:
    cmd = [
        "claude",
        "--model", model,
        "--dangerously-skip-permissions",
        "--print",
        "--output-format", "json",
    ]
    for d in add_dirs or []:
        cmd += ["--add-dir", str(d)]
    if extra_args:
        cmd += list(extra_args)
    cmd += ["-p", prompt]

    start = time.time()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=timeout_s,
    )
    duration_ms = int((time.time() - start) * 1000)

    if proc.returncode != 0:
        return CallResult(
            ok=False, text=proc.stdout, raw={}, stderr=proc.stderr, duration_ms=duration_ms
        )
    try:
        raw = json.loads(proc.stdout)
    except Exception as e:
        return CallResult(
            ok=False, text=proc.stdout, raw={}, stderr=f"json parse: {e}\n{proc.stderr}",
            duration_ms=duration_ms,
        )
    usage = raw.get("usage", {}) or {}
    return CallResult(
        ok=(not raw.get("is_error", False)),
        text=raw.get("result", ""),
        raw=raw,
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cache_read=int(usage.get("cache_read_input_tokens", 0) or 0),
        cache_creation=int(usage.get("cache_creation_input_tokens", 0) or 0),
        duration_ms=duration_ms,
        stderr=proc.stderr,
    )
