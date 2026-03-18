# ExamCooker OCR Audit

This project scans [ExamCooker](https://examcooker.acmvit.in/home) past papers, downloads each PDF, OCRs the first few pages to find the title page, and flags papers whose OCR title does not match the website label.

## What it does

- Scrapes the `past_papers` listing from ExamCooker
- Opens each paper detail page to get the direct PDF URL
- Downloads and caches PDFs locally in `data/cache/pdfs`
- OCRs up to 4 opening pages per PDF with Tesseract
- Compares the extracted title against the website subject title and course code
- Stores the latest result set in `data/results/latest_results.json`
- Serves a dashboard that lists only the suspicious papers with direct links back to ExamCooker

## Requirements

- Python 3.10+
- Tesseract installed and available on `PATH`

This machine already has `tesseract` installed at `/opt/homebrew/bin/tesseract`.

## Install

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Run the scanner from the CLI

```bash
source .venv/bin/activate
paper-audit --limit 20
```

Use `--json` if you want the final payload printed to the terminal.

## Run the frontend

```bash
source .venv/bin/activate
uvicorn app:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The dashboard lets you start a scan and review the invalid papers with links to both the ExamCooker page and the source PDF.
