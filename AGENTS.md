# AGENTS.md

Guidance for coding agents working in this repository.

## Project purpose

TWIX is a research prototype for reconstructing structured data from PDFs that
share a visual template. It combines PDF text and geometry extraction,
LLM-assisted field and template inference, and optimization-based record/block
extraction.

The repository contains two related applications:

- the `twix` Python package, which exposes the extraction pipeline; and
- `twix-ui`, a React frontend with a Flask backend that calls the package.

The paper is available at <https://arxiv.org/abs/2501.06659>.

## Repository map

| Path | Responsibility |
| --- | --- |
| `twix/extract.py` | PDF merge, phrase extraction, page rendering, and optional vision-assisted phrase grouping |
| `twix/key.py` | Field prediction from phrase repetition, geometry, and vision-model suggestions |
| `twix/pattern.py` | Metadata detection, template inference, record/block separation, Gurobi optimization, and data extraction |
| `twix/model.py` | Dispatch to the supported OpenAI text and vision wrappers |
| `twix/models/` | OpenAI Chat Completions wrappers for GPT-4o and GPT-4o mini |
| `twix/cost.py` | Token counting and approximate model-cost accounting |
| `twix/transform.py` | End-to-end composition of the four public pipeline stages |
| `twix/user_apis.py` | Helpers for editing inferred fields and template nodes |
| `tests/*.ipynb` | Executable examples and integration checks; these can make paid API calls |
| `tests/data/` | Sample PDFs |
| `tests/out/` | Checked-in example artifacts and runtime outputs |
| `twix-ui/src/` | React application |
| `twix-ui/backend/app.py` | Flask API used by the React application |

## Pipeline and public API

The staged pipeline is:

```text
extract_phrase
  -> predict_field
  -> predict_template
  -> extract_data
```

`twix.transform(...)` invokes those stages in that order. The package exports:

```python
extract_phrase(data_files, result_folder, LLM_model_name="gpt-4o-mini",
               page_to_infer_fields=5, vision_feature=False)
predict_field(data_files, result_folder, LLM_model_name="gpt-4o-mini")
predict_template(data_files, result_folder, LLM_model_name="gpt-4o-mini")
extract_data(data_files, result_folder, template=[])
transform(pdf_paths, result_folder_path, LLM_model_name,
          vision_feature=False)
add_fields(added_fields, result_folder)
remove_fields(removed_fields, result_folder)
remove_template_node(node_ids, result_folder)
modify_template_node(node_id, type, fields, result_folder)
```

Core runtime assumptions:

- `data_files` is a list of one or more PDF paths from the same template
  family. Single-PDF and single-page inputs are supported, although repeated
  layouts give the structural inference more evidence.
- The main phrase-extraction path expects PDFs with selectable text.
  `pdfplumber` provides words and coordinates. `vision_feature=True` helps
  learn phrase-merging rules; it is not a general OCR replacement for scanned
  documents.
- Callers should pass a `result_folder` ending in the platform path separator.
  Several functions form artifact paths with string concatenation rather than
  `os.path.join`.
- Input PDFs are sorted by basename before being merged for inference.
- Supported model names are `gpt-4o-mini` and `gpt-4o`. Vision calls are
  dispatched internally as `vision-gpt-4o-mini` and `vision-gpt-4o`.
- Field prediction always uses a vision call. Template prediction can use both
  vision and text calls. Extraction reuses saved artifacts where available.
- Template nodes use `type` (`"kv"` or `"table"`), `fields`, `bid`, `child`,
  and `node_id`. Inspect checked-in `tests/out/*/template.json` files before
  changing this contract.

## Artifact contract

For an input named `document.pdf`, a normal result directory can contain:

```text
<result_folder>/
├── merged.pdf
├── merged_phrases.txt
├── merged_phrases_bounding_box_page_number.json
├── merged_raw_phrases_bounding_box_page_number.txt
├── document_phrases.txt
├── document_bounding_box_page_number.json
├── document_raw_phrases_bounding_box_page_number.txt
├── twix_key.txt
├── metadata.txt
├── metadata_rows.txt
├── template.json
├── document_extracted.json
└── _image/0.jpg
```

Despite the `.txt` suffix, `*_raw_phrases_bounding_box_page_number.txt` is CSV
with the columns `text,x0,y0,x1,y1,page`. Later stages consume these filenames
directly. Do not rename or change them in one producer without updating all
consumers, notebooks, and UI code.

## Setup and commands

Python 3.10 or newer is the documented development target. The package also
requires external components that `pip` cannot fully configure:

- Poppler for `pdf2image` page rendering;
- Gurobi and a working license for optimization in template/data extraction;
- an OpenAI API key for field and template inference; and
- optionally, the Tesseract executable when using the helper image-OCR path.

Typical setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
export OPENAI_API_KEY="..."
```

Useful checks that do not call external models:

```bash
python -m compileall -q twix twix-ui/backend/app.py
python -c "import twix; print(twix.__all__)"

cd twix-ui
npm test -- --watchAll=false
npm run build
```

The Python examples are Jupyter notebooks, not an offline unit-test suite. Do
not run all notebook cells during routine verification: pipeline cells use the
OpenAI API and may incur cost. When changing behavior, add a focused offline
test where practical and use small fixtures or mocks for model calls.

## UI development

The frontend expects the Flask API at `http://127.0.0.1:3001`; Create React App
runs at `http://localhost:3000`. Start them in separate terminals:

```bash
python twix-ui/backend/app.py
```

```bash
cd twix-ui
npm install
npm start
```

The backend writes uploads and result files under the repository. Treat those
as runtime data even where historical examples are checked in.

## Safe change workflow

Before editing:

1. Run `git status --short --branch`. Preserve unrelated local work.
2. Read the implementation, all callers, the corresponding notebook example,
   and any UI endpoint that consumes the artifact being changed.
3. Avoid live OpenAI calls unless the task explicitly requests an integration
   run. Never print or commit API keys.
4. Do not bulk-delete or reformat `tests/out/`, `twix-ui/results/`, sample PDFs,
   images, notebooks, or other checked-in artifacts.

When changing a contract:

- Public API changes must update `twix/__init__.py`, this file, `readme.md`, and
  relevant notebooks and UI calls.
- Artifact-name or schema changes must update `extract.py`, `key.py`,
  `pattern.py`, `user_apis.py`, Flask endpoints, React consumers, and examples.
- Model changes must update `twix/model.py`, wrappers in `twix/models/`, cost
  accounting, setup metadata, and documentation.
- UI API changes must keep the backend port and `twix-ui/src/services/api.js`
  base URL synchronized.
- Dependency changes must update both `setup.py` and the relevant frontend
  package files.

## Known sharp edges

- Cost accounting uses module-level mutable totals. Repeated calls in one
  process can retain earlier stage cost, and `transform` currently returns the
  last stage's `cost` value rather than its computed `total_cost`.
- `modify_template_node` should be treated cautiously: its non-target branch
  currently appends the whole template rather than the individual node.
- Many output paths rely on a trailing slash in `result_folder`.
- Scanned/image-only PDFs are reported as having no selectable text; the vision
  option does not provide full-document OCR.
- Gurobi is required by `twix.pattern` at import/runtime and may require a
  separately provisioned license.
- Model pricing in `twix/cost.py` is a static estimate and can become stale.
- The root has no broad ignore policy and includes historical generated files.
  Check the diff carefully before committing.
