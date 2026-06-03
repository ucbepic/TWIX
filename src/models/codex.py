import json
import subprocess


def codex(prompt, dir_path, task):
    print(f"Running codex for task: {task}")
    result = subprocess.run(
        [
            "codex", "exec",
            "-C", str(dir_path),
            "-s", "workspace-write",
            "--skip-git-repo-check",
            prompt,
        ],
    )
    return result.returncode


def codex_silent(prompt, dir_path, task) -> tuple[int, int | None]:
    """Run codex with --json output, suppress stdout/stderr, return (returncode, tokens).

    Parses the JSONL event stream for token usage. Returns None for tokens if usage
    information is not found in the output.
    """
    result = subprocess.run(
        [
            "codex", "exec",
            "-C", str(dir_path),
            "-s", "workspace-write",
            "--skip-git-repo-check",
            "--json",
            prompt,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    tokens = _parse_tokens(result.stdout)
    return result.returncode, tokens


def _parse_tokens(jsonl_output: str) -> int | None:
    """Scan JSONL codex output and return the total token count, or None if not found."""
    total_tokens = 0
    found = False

    for raw_line in jsonl_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        count = _extract_tokens_from(event)
        if count:
            total_tokens = max(total_tokens, count)
            found = True

    return total_tokens if found else None


def _extract_tokens_from(obj) -> int:
    """Recursively search a parsed JSON object for token counts."""
    if not isinstance(obj, dict):
        return 0

    # Direct numeric fields
    for key in ("total_tokens", "totalTokens"):
        if isinstance(obj.get(key), int):
            return obj[key]

    # Summed input+output
    inp = obj.get("input_tokens") or obj.get("inputTokens") or 0
    out = obj.get("output_tokens") or obj.get("outputTokens") or 0
    if inp or out:
        return inp + out

    # Recurse into nested dicts/lists
    best = 0
    for v in obj.values():
        if isinstance(v, dict):
            best = max(best, _extract_tokens_from(v))
        elif isinstance(v, list):
            for item in v:
                best = max(best, _extract_tokens_from(item))
    return best
