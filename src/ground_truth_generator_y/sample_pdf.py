"""Stage 1 step 1 — sample pages from a PDF."""

from __future__ import annotations

import random
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def extract_single_page(
    pdf_path: str | Path,
    out_path: str | Path,
    page_0idx: int,
) -> None:
    """Write a single page (0-indexed) from `pdf_path` to `out_path`."""
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_0idx])
    with open(out_path, "wb") as f:
        writer.write(f)


def sample_first_pages(pdf_path: str | Path, out_path: str | Path, n_pages: int = 5) -> int:
    """Write the first n_pages of `pdf_path` to `out_path`. Return number of pages written."""
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    take = min(n_pages, total)
    writer = PdfWriter()
    for i in range(take):
        writer.add_page(reader.pages[i])
    with open(out_path, "wb") as f:
        writer.write(f)
    return take


def sample_random_pages(
    pdf_path: str | Path,
    out_path: str | Path,
    n_pages: int = 5,
    seed: int | None = None,
) -> list[int]:
    """Write n_pages randomly sampled pages to `out_path` (sorted order).

    Returns the 1-indexed original page numbers that were written.
    """
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    rng = random.Random(seed)
    indices = sorted(rng.sample(range(total), min(n_pages, total)))
    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    with open(out_path, "wb") as f:
        writer.write(f)
    return [i + 1 for i in indices]
