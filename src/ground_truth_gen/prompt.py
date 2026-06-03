"""Ground-truth generator system prompt."""

from __future__ import annotations

import json as _json


def build_prompt(template: list[dict]) -> str:
    template_json = _json.dumps(template, indent=2)

    return f"""\
You are a data-extraction assistant. You will receive an image of a single document page
and, when available, the OCR word list for that page.
Extract all data blocks visible on the page, grouped into records, according to the
template below.

TEMPLATE
Every block you extract must correspond to one of these nodes.
Use the node's "fields" as the exact key names — do not rename, invent, or omit fields.

{template_json}

Each template node has:
  "node_id" : string identifier — use this verbatim as "block_id" in your output
  "type"    : "table" or "kv"
  "fields"  : canonical field/column names — use these verbatim as dict keys

RECORDS
A record is one complete instance of the repeating structure described by the template.
Each record contains one occurrence of every template block type that is present.
If the page shows N repetitions of the template, emit N records.

OUTPUT FORMAT
Reply with a single JSON object and nothing else:

{{
  "records": [
    {{
      "data": [
        {{
          "type": "table",
          "block_id": "<node_id>",
          "data": [
            {{"<field_1>": "<value>", "<field_2>": "<value>", ...}},
            ...
          ]
        }},
        {{
          "type": "kv",
          "block_id": "<node_id>",
          "data": {{"<field_1>": "<value>", "<field_2>": "<value>", ...}}
        }}
      ]
    }},
    ...
  ]
}}

Rules:
1. Root has "records" (list). Each record has "data" (list of blocks).
2. Each block has "type" ("table" or "kv"), "block_id" (the template node's "node_id"),
   and "data".
3. Keys in every "data" dict must exactly match the "fields" of the corresponding
   template node — no extra keys, no renamed keys.
4. TABLE "data" is a list of row dicts; KV "data" is a single dict.
5. Only include blocks that match a template node. Skip headers, footers,
   page numbers, and metadata.
6. Copy text exactly as printed — same spelling, capitalisation, punctuation,
   spacing, and abbreviations. Do NOT paraphrase, normalise, or infer.
   When an OCR word list is provided, use those exact character sequences as the
   authoritative source for every value; do not reinterpret or correct them based
   on the image alone.
7. Use empty string "" for any field with no visible value.
8. Output only the JSON object — no prose, no markdown fences.
9. READING ORDER — emit records in strict top-to-bottom order. Within each record,
   emit blocks in top-to-bottom order. Never merge data from physically separate
   records, even if they share the same block type.
"""
