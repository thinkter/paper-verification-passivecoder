# ExamCooker Gemini Audit

This project scans [ExamCooker](https://examcooker.acmvit.in/home) past papers, downloads each PDF, sends page 1 to Gemini, and flags papers whose first page does not match the website metadata.

## What it does

- Scrapes the `past_papers` listing from ExamCooker
- Opens each paper detail page to get the direct PDF URL
- Downloads and caches PDFs locally in `data/cache/pdfs`
- Renders only the first page of each PDF locally
- Uses Gemini to read that page and compare it against the website metadata
- Stores the latest result set in `data/results/latest_results.json`
- Serves a dashboard that lists only the suspicious papers with direct links back to ExamCooker

## Requirements

- Python 3.10+
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` set in the environment

As of March 19, 2026, the default model in this repo is `gemini-3-pro-preview`, which is the current Gemini 3 Pro API identifier in Google's docs.

## Install

```bash
uv sync
```

## Run the scanner from the CLI

```bash
export GEMINI_API_KEY=your_api_key_here
uv run paper-audit --limit 20
```

Use `--json` if you want the final payload printed to the terminal.

## Run the frontend

```bash
export GEMINI_API_KEY=your_api_key_here
uv run uvicorn app:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The dashboard lets you start a scan and review the invalid papers with links to both the ExamCooker page and the source PDF.
