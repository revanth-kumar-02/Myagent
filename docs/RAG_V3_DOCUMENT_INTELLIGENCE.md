# KORA — RAG V3: DOCUMENT INTELLIGENCE SPECIFICATION

## Overview

Kora RAG V3 introduces **Document Intelligence**, extending the existing RAG foundation and retrieval engine with format-native parsing, relationship-aware structural chunking, granular provenance tracking, and natural provenance query routing across Code, Markdown, PDF, DOCX, XLSX, PPTX, and CSV formats.

---

## 1. Document-Aware Parsing Architecture

Each document format is processed according to its natural hierarchy and structural elements:

| Format | Parser Implementation | Structural Elements Extracted |
|---|---|---|
| **PDF** (`.pdf`) | `pypdf` extraction | Pages, page headings, paragraphs, page numbers, author, title |
| **DOCX** (`.docx`, `.doc`) | `python-docx` | Headings (with levels 1-6), body paragraphs, structured table grids |
| **XLSX / XLS** (`.xlsx`, `.xls`) | `openpyxl` / `xlrd` | Workbooks, sheets, cell ranges (`Sheet1!A1:D50`), row/column statistics |
| **PPTX / PPT** (`.pptx`, `.ppt`) | `python-pptx` | Slides, slide titles, shapes, bullet text, slide tables |
| **CSV** (`.csv`) | Python `csv` module | Column headers, total row/column counts, cell ranges (`A1:E100`) |
| **Code** (`.py`, `.ts`, `.dart`, etc.) | Custom regex AST-heuristic | Function, class, method, interface symbols, language metadata |
| **Markdown** (`.md`) | Regex hierarchy scanner | Heading breadcrumbs (`H1 > H2 > H3`), line spans |

---

## 2. Format-Native Smart Chunking

Rather than arbitrary character/word splitting, RAG V3 chunks documents along natural semantic boundaries:

- **Code Chunks**: Segmented by function, class, and component definitions.
- **Markdown Chunks**: Segmented by section headings while retaining ancestor breadcrumbs.
- **PDF Chunks**: Segmented by individual pages and section paragraphs; tagged with `page_number` and `heading`.
- **DOCX Chunks**: Segmented by section headings and tables; tagged with `heading` and `section`.
- **Spreadsheet Chunks**: Segmented by sheet and logical row batches; tagged with `sheet_name`, `cell_range` (e.g. `Revenue!A1:F25`), and `row_start`/`row_end`.
- **Presentation Chunks**: Segmented by individual slides; tagged with `slide_number` and `slide_title`.
- **CSV Chunks**: Header-aware chunking where each batch of data rows is prefixed with the table header row; tagged with `headers`, `row_start`, `row_end`, and `cell_range`.

---

## 3. Structural Metadata Model

Chunks store only applicable, clean structural metadata:

```python
{
    "file_name": "quarterly_report.xlsx",
    "file_type": "spreadsheet",
    "sheet_name": "Financials",
    "cell_range": "A1:D20",
    "row_start": 1,
    "row_end": 20,
    "token_count": 185
}
```

```python
{
    "file_name": "architecture.pptx",
    "file_type": "pptx",
    "slide_number": 3,
    "slide_title": "RAG Pipeline",
    "token_count": 142
}
```

```python
{
    "file_name": "security_spec.pdf",
    "file_type": "pdf",
    "page_number": 4,
    "heading": "Cryptographic Key Management",
    "token_count": 310
}
```

---

## 4. Natural Provenance Query Understanding

The retriever extracts structural intent from natural user queries and applies score boosts:

- **Page Queries** (*"Show information from page 3"*, *"What does page 12 say?"*):
  - Detects `target_page = N`
  - Boosts chunks where `page_number == N`.
- **Sheet Queries** (*"Which sheet contains Financials?"*, *"Look at the Q1_Metrics sheet"*):
  - Detects `target_sheet = name` or general spreadsheet preference
  - Boosts chunks matching `sheet_name`.
- **Slide Queries** (*"Find the slide about system architecture"*, *"Show slide 4"*):
  - Detects `target_slide = N` or general presentation preference
  - Boosts slide chunks.
- **Symbol Queries** (*"Where is parseUser defined?"*, *"Function calculate_score"*):
  - Detects `target_symbol = name`
  - Boosts symbol definitions in code.

---

## 5. Rich Provenance Context Construction

The `ContextBuilder` outputs structured citation headers:

```
=== Project Knowledge Context ===

[1] reports/finance.xlsx (type: spreadsheet, sheet: Revenue, range: A1:C20, score: 0.920)
Metric | Q1 | Q2
Revenue | $100k | $150k

[2] docs/deck.pptx (type: document, slide: 3, title: Core Vision, score: 0.880)
Modular autonomous agent framework overview.

[3] specs/security.pdf:page 4 (type: document, heading: Encryption, score: 0.850)
All data in transit is encrypted using TLS 1.3.

[4] data/users.csv (type: spreadsheet, headers: user_id, email, role, rows: 1-25)
user_1 | user1@example.com | admin
```
