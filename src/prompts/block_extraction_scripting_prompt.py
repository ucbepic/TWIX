import json as _json


def PROMPT_BLOCK_EXTRACTION_SCRIPTING(template_id: str, template_node: dict | None) -> str:
    block_type = (template_node or {}).get("type", "unknown")
    template_node_json = _json.dumps(template_node, indent=2) if template_node else "null"

    return f"""You are inside the folder containing word-level OCR samples for block type "{template_id}".

The template node that describes this block type is:
{template_node_json}

The "fields" list above names every field present in this block. Use these names verbatim
as keys in the output (do not rename or invent fields).

The "complexity" object describes the structural difficulty of this block and must guide
how you write the extraction logic:
- For kv blocks:
  - "repeated": true → the block appears more than once inside a single record; your
    extract() must return "data" as a list of dicts, one per repetition. false → return
    "data" as a single dict.
- For table blocks:
  - "same_row_structure": true → every data row has the same layout (one value per
    column); a simple row-grouping by top-coordinate is sufficient. false → rows may
    differ structurally (spanning cells, blank separators, sub-labels); your logic must
    handle the variation rather than assuming uniform alignment.
  - "nested": true → cells contain structured content (sub-tables, lists, or key-value
    pairs) rather than plain text; you must parse the inner structure of each cell and
    represent it appropriately in the output. false → each cell contains a single plain
    value; extract it directly.

Each .json file in this folder is one sampled instance of this block type and has the structure:
  {{
    "page": <int>,
    "block_id": "<template_id>_<instance>",
    "type": "{block_type}",
    "words": [
      {{"x0": <float>, "top": <float>, "x1": <float>, "bottom": <float>, "text": <str>}},
      ...
    ]
  }}

Word coordinates are relative to the top-left corner of the block (top-left = 0, 0).
The corresponding .png files show the visual rendering of each sample.

Your task:
1. Read and analyse ALL the .json (and optionally .png) sample files in this directory
   to understand the spatial layout of the block.
2. Write a Python script and save it as {template_id}.py in the current directory.

The script must define exactly this function:

  def extract(block: dict) -> dict

  - `block` is a dict with keys "block_id" (str), "type" (str), and "words" (list[dict]).
    Each word dict has "x0", "top", "x1", "bottom", "text" (coordinates relative to the
    block's top-left corner).
  - The function reads block["block_id"] to populate the "block_id" field of the output.

Return format for a TABLE block ("{block_type}" == "table"):
  {{
    "type": "table",
    "block_id": "<block_id>",
    "data": [
      {{"<field_1>": "<value row 1>", "<field_2>": "<value row 1>", ...}},
      {{"<field_1>": "<value row 2>", "<field_2>": "<value row 2>", ...}},
      ...
    ]
  }}
  Each entry in "data" is one data row. Use spatial clustering to identify rows and to
  align each cell with the correct column header from the template fields list.

Return format for a KV block ("{block_type}" == "kv"):
  Single KV group:
  {{
    "type": "kv",
    "block_id": "<block_id>",
    "data": {{"<field_1>": "<value_1>", "<field_2>": "<value_2>", ...}}
  }}
  Multiple KV groups inside the same block:
  {{
    "type": "kv",
    "block_id": "<block_id>",
    "data": [
      {{"<field_1>": "<value_1>", ...}},
      {{"<field_1>": "<value_2>", ...}},
      ...
    ]
  }}
  Determine whether "data" should be a dict or a list by inspecting the samples.

Additional requirements:
- Use the template "fields" as the canonical key names in all output dicts.
- Use word positions (x0, top, x1, bottom) to group words into rows/columns and to
  match labels to values. Do not hard-code pixel thresholds; derive them from the data.
- Be generalizable: the function must work correctly on any instance of block type
  "{template_id}", not only the sampled ones.
- Use only the Python standard library. Do not import any external packages.
- In addition to `extract(block)`, define a `main(inputpath: str, out_path: str) -> None`
  function. `inputpath` is the path to the OCR CSV to run block separation on;
  `out_path` is the folder where the output file `block_separation.json` should be written.

Save the finished script as {template_id}.py in the current directory."""
