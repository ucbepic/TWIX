def PROMPT_RECORD_SEPARATION(ocr_csv_path: str, template_json: str) -> str:
    return f"""Create a Python script called `record_separation.py` that groups OCR words from a multi-page document into logical records based on the document template.

Context:
- A sample OCR CSV file is at: {ocr_csv_path}
  Columns: id, page, x0, top, x1, bottom, text
  `id` is a globally unique integer assigned to each extracted word across the whole document.
- The document template defines the following blocks:
{template_json}

A **record** is one complete instance of the repeating template structure.
A record is complete when all blocks defined in the template have been detected at least once.
A record is NOT limited to a single page — it may start on one page and end on a later page.
Only close (finalise) the current record when every template block has been observed since
the record started. Start a new record immediately after the previous one closes.

The script must define a main function with this exact signature:

  def main(inputpath: str, out_path: str) -> None

  - `inputpath`: path to the OCR CSV file to process.
  - `out_path`: path to the folder where `record_separation.json` must be written.

The main function must:
1. Read the OCR CSV from `inputpath` and group words by page.
2. Process pages in order. Maintain a "current record" accumulator that collects words
   page by page and tracks which template block types have been seen so far.
3. For each page, use the spatial layout of words to detect which template blocks are
   present (anchor words, bounding-box regions, or repeating label patterns).
   Useful signals:
   - Fixed label words that appear exactly once per block instance (e.g. field names
     from the template's "fields" list).
   - Vertical gaps larger than the typical inter-line gap that mark block boundaries.
   - Repeating clusters whose top-coordinate distribution is periodic within a page.
4. As soon as all template block types have been detected in the current record,
   close the record and start a new one (even mid-page if the next record begins there).
5. Assign every word in the document to exactly one record.
6. Write the results to `<out_path>/record_separation.json` with structure:
   {{
     "records": [
       {{
         "record_id": "<index>",
         "pages": [
           {{
             "page": <int>,
             "y_start": <float>,
             "y_end": <float>,
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
   Each record contains one entry per page it spans. `y_start` / `y_end` are the
   top / bottom coordinates of the record's words on that page.
7. Print a summary to stdout: one line per record showing its id and the page range it spans.

The script must also contain:

  if __name__ == "__main__":
      import sys
      main(sys.argv[1], sys.argv[2])

Use only the Python standard library plus the csv module. Do not install any packages.
"""
