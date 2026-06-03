import json as _json


def GROUND_TRUTH_GENERATOR_PROMPT(template: list[dict]) -> str:
    template_json = _json.dumps(template, indent=2)

    return f"""\
You are a document data-extraction engine producing ground-truth annotations.
You will receive a single page image from a PDF document.

The document follows this template, which defines every block type that can appear on a page:
{template_json}

Each template node has:
- "node_id"  : numeric identifier
- "bid"      : list of block indices (the numeric prefix used in block_id)
- "type"     : "table" or "kv"
- "fields"   : the canonical field/column names for that block

Your task:
1. Scan the page top-to-bottom, left-to-right and identify every physical block
   occurrence that corresponds to a template node.
2. Each distinct physical occurrence of a block — even if the same template type
   appears multiple times on the page — must be its own separate entry in the
   "blocks" array, in the exact order it appears on the page.
3. Extract the data for that occurrence using the template "fields" as the canonical
   key names.
4. Assign a block_id using the format "<bid>_<sequence>" where <bid> is the first
   value in the node's "bid" list and <sequence> is a zero-padded 4-digit counter
   starting at 0001, incremented per block type as you encounter them in reading
   order (e.g. first occurrence of bid 0 → "0_0001", second → "0_0002", ...).

CRITICAL — ordering and separation:
- The order of entries in "blocks" must mirror the real top-to-bottom reading order
  of the document. Do NOT group all instances of the same block type together.
- If block type A appears, then block type B, then block type A again, the output
  must be: [A_0001, B_0001, A_0002] — not [A_0001, A_0002, B_0001].
- Each physical block is always a separate entry, regardless of whether two
  consecutive blocks share the same template type.

Return ONLY a valid JSON object — no markdown, no explanation — with this structure:

{{
  "blocks": [
    {{
      "type": "table",
      "block_id": "<bid>_<sequence>",
      "data": [
        {{"<field_1>": "<value>", "<field_2>": "<value>", ...}},
        ...
      ]
    }},
    {{
      "type": "kv",
      "block_id": "<bid>_<sequence>",
      "data": {{"<field_1>": "<value>", "<field_2>": "<value>", ...}}
    }}
  ]
}}

Rules:
- Use ONLY the field names listed in the template "fields" for each block — do not
  invent or rename keys.
- For a TABLE block: each entry in "data" is one data row; the keys are the column
  headers from the template fields.
- For a KV block: "data" is always a plain dict representing that single physical
  occurrence. Never merge multiple physical KV blocks into a list — they are
  separate entries in "blocks" with their own block_ids.
- Copy the text character-by-character exactly as printed in the document — same
  spelling, capitalisation, punctuation, spacing, and abbreviations. Do NOT
  paraphrase, normalise, correct, infer, or add any word that is not explicitly
  visible in the image.
- If a field has no visible value for that occurrence, use an empty string "".
- Do not include page headers, footers, page numbers, or decorative elements.
"""
