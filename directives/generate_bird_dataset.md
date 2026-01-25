# Directive: Generate Bird Dataset

## Goal
Scrape 100 common bird species, translate their names, and download public domain images for a quiz app.

## Inputs
- Source URL: e.g., Wikipedia (List of common birds).
- Target Languages: Hebrew (he), Spanish (es).
- Asset Directory: `./assets/birds/`.

## Tools/Libraries
- `requests`: Fetch HTML and images.
- `BeautifulSoup` (bs4): Parse HTML.
- `googletrans`: Translate names.
- `json`: Format output.

## Steps
1. **Identify Source**: Find a reliable list of birds with scientific names and images.
2. **Execute Script**: Run `execution/scrape_birds.py`.
3. **Handle Rate Limits**: implement retries for translation and scraping.
4. **Post-processing**:
    - Broadly categorize birds.
    - Assign difficulty 1-5.
    - Extract Wikimedia Commons high-res URLs.
5. **Output**: `birds_data.json` and local image files.

## Edge Cases
- Missing images: Skip or find alternative.
- Translation failures: Retry or use English as fallback.
- Invalid URLs: Skip entry.
