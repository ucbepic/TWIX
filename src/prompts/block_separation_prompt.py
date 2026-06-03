def PROMPT_BLOCK_SEPARATION(ocr_csv_path, template_json):
    return f"""Create a Python script called `block_separation.py` that detects and extracts all blocks defined in the document template from every page of the OCR data.

Context:
- A sample OCR CSV file is at: {ocr_csv_path}
  Columns: id, page, x0, top, x1, bottom, text
  `id` is a globally unique integer assigned to each extracted word across the whole document.
- The document template defines the following blocks:
{template_json}

The script must define a main function with this exact signature:

  def main(inputpath: str, out_path: str) -> None

  - `inputpath`: path to the OCR CSV file to process.
  - `out_path`: path to the folder where `block_separation.json` must be written.

The main function must:
1. Read the OCR CSV from `inputpath`.
2. For each page, assign every word to the template block whose bounding box it falls inside (use the x0/top/x1/bottom coordinates from both the word and the block definition).
3. Group the matched words per block per page. For each block set:
   - `block_id`: the string value of the `node_id` field from the matching template node.
   - `uid`: a globally unique integer that increments by 1 for every block across all
     pages, starting from 0. Each block gets a different `uid` regardless of type or page.
4. Write the results to `<out_path>/block_separation.json` with structure:
   {{
     "pages": [
       {{
         "page": <int>,
         "blocks": [
           {{
             "uid": <int>,
             "block_id": "<node_id>",
             "type": <str>,
             "words": [
               {{"id": <int>, "x0": <float>, "top": <float>, "x1": <float>, "bottom": <float>, "text": <str>}},
               ...
             ]
           }},
           ...
         ]
       }},
       ...
     ]
   }}
5. Print a summary line per page to stdout.

The script must also contain:

  if __name__ == "__main__":
      import sys
      main(sys.argv[1], sys.argv[2])

Use only the Python standard library plus the csv module. Do not install any packages.
"""

