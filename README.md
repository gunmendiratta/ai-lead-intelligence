# AI-Assisted Lead Intelligence

A local Streamlit application for discovering public business leads, extracting public business contacts, and verifying whether two business records represent the same organization.

It preserves the repository's existing Booking.com and Google Maps prototype scripts. The new application is a separate, safer workflow: it uses a documented API for Google Maps data, analyzes public website pages, and uses AI only as an evidence-bound reviewer for uncertain matches.

## What you need to provide

| Goal | What you provide | Required credential |
|---|---|---|
| Process existing leads | A CSV containing at least business name and address | None |
| Find leads from Google Maps | A search phrase, for example `restaurants in Zurich` | `GOOGLE_PLACES_API_KEY` |
| Discover leads from a website | A public directory/list/category URL | None for static pages |
| Analyze JavaScript pages/popups | Same public URL | Playwright browser installation |
| AI review for uncertain matches | Candidate fields from an independent source | `OPENAI_API_KEY` |
| Verify imported leads against Google Places | CSV with business name and address | `GOOGLE_PLACES_API_KEY` |
| Verify imported leads without billing | CSV with business name and address | None; uses OpenStreetMap/Nominatim |

The included `property_booking_non_hotels.csv` is already compatible: map `property_name`, `full_address`, `city`, and `postal_code`.

## Quick start

```bash
cd /Users/varun/Desktop/scrape/ai-lead-intelligence
python3 -m pip install -r requirements.txt
uvicorn server:app --reload
```

Open `http://127.0.0.1:8000`. The JavaScript frontend is served by the local Python API. No API key is needed to generate plans or analyze ordinary public HTML pages.

The legacy Streamlit interface remains available with `streamlit run app.py`, but the primary interface is now the JavaScript frontend.

For JavaScript-heavy pages, install the browser once:

```bash
playwright install chromium
```

## Optional configuration

Copy `.env.example` to `.env` and add only the services you will use:

```env
GOOGLE_PLACES_API_KEY=your_google_places_key
OPENAI_API_KEY=your_openai_key
LEAD_REQUEST_DELAY=0.2
```

`GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID` remain available for a future Google Programmable Search provider, but are not needed for the three current interface flows. Never commit `.env`.

## Interface flows

### 0. Prompt-generated scraper

The JavaScript interface accepts a public URL and a request such as `extract hotel name, address, phone, email, and website`. The backend creates a JSON execution plan, shows its selectors and safety limits, and runs it only after approval. The plan uses maintained domain selectors for known sites and generic selectors for unknown sites. When `OPENAI_API_KEY` is configured, an optional model may propose CSS selectors from a bounded public HTML snapshot; otherwise the local parser is used. It never executes AI-generated Python or JavaScript.

### 1. Google Maps / Places

Enter a category plus location: `boutique hotels in St. Moritz`, `restaurants in Zurich`, or `dentists in Bern`.

The application calls Google Places Text Search and exports business name, formatted address, phone, website, category, and source Maps URL. It does **not** scrape the Google Maps user interface.

### 2. Paste Website URL

Paste a public directory, marketplace listing, association directory, or category page.

The discovery process is intentionally layered:

1. Validate the URL and reject local/private network destinations.
2. Identify Google Maps and search-engine URLs and route them away from unsupported UI scraping.
3. Fetch static HTML, or use optional browser mode for JavaScript-rendered content.
4. Extract `application/ld+json` / Schema.org business data first.
5. If structured data is absent, inspect repeated cards such as `article`, `listing`, `result`, or `business` containers.
6. Return candidate businesses for the user to review and download.

Browser mode waits for rendered content and can dismiss ordinary consent buttons such as “Accept” or “I agree.” It never attempts to defeat CAPTCHAs, sign-in barriers, paywalls, anti-bot defenses, or access controls.

No generic scraper can reliably understand every website format. The current engine supports public static HTML, JSON-LD, common repeated cards, and optional JavaScript rendering. Sites with custom markup, login walls, CAPTCHAs, paywalls, robots restrictions, or bot protection require an approved domain-specific template or cannot be processed. The application never bypasses those controls.

Domain templates are currently included for public listing-card markup from Booking.com, MakeMyTrip, and Goibibo. They are intentionally conservative: they extract visible card names, addresses, public phone links, and detail URLs when those elements are present. Travel sites frequently change markup or render results dynamically, so browser mode may be needed and selectors may require maintenance in [templates.py](lead_intelligence/templates.py).

### 3. Upload CSV

Map your input columns, including an independent candidate source URL when verification is needed, then optionally:

- crawl public, mapped business websites for email, phone, social links, and contact-page evidence;
- map independent candidate fields from a Places/API/export file;
- enable AI review only for `Probable Match` or `Needs Manual Review` records.

Source data is never automatically verified against itself. Candidate name/address fields without an independent candidate source URL remain `No Information Found`.

### 4. Lead Chat

Upload a CSV and enter a plain-language operation such as `remove any hotel that is already managed by a company`. The local command layer converts supported prompts into transparent filters and exports both kept and excluded rows. It currently supports category inclusion and managed-business exclusion; unsupported prompts are reported instead of silently changing data.

### 5. Lead Generator

Upload a CSV with business names and addresses. With `GOOGLE_PLACES_API_KEY`, the application searches the official Places Text Search API for each lead, chooses the highest-scoring candidate, and exports name, address, phone, website, category, source URL, and individual similarity scores. A score of 80 or higher is accepted as a practical match threshold for this workflow; hard location conflicts remain rejected or manual-review cases.

The generator can crawl each matched public official website for publicly listed email and phone details, then produces a separate contacts-only CSV. It does not scrape the Google Maps interface or Google search-result pages.

## How AI fits in

AI is useful in two constrained places:

1. **Uncertain identity review**: compare the original lead, independent candidate, deterministic scores, and short public website text. It returns a structured recommendation, confidence, reasoning, and warnings.
2. **Future extraction-template assistant**: for a new website domain, AI can propose candidate page fields/selectors from a limited HTML snapshot. A user should preview and approve the extraction before a batch crawl.

AI must not invent business information, override hard conflicts in address evidence, or independently mark a lead verified. The deterministic matcher remains the primary decision maker.

## Output fields

The exported verification CSV preserves original columns and adds:

```text
official_website, public_email, public_phone, social_links, contact_page_urls, contact_source_urls,
matched_business_name, matched_business_address,
name_similarity_score, address_similarity_score,
city_similarity_score, postal_similarity_score, overall_match_score,
final_verification_status, verification_reason,
candidate_source_url, ai_recommendation, ai_confidence_score, ai_reason, ai_warnings,
lead_quality_score, processing_status
```

## Safety and compliance

- Collect only publicly listed business contact details needed for a legitimate purpose.
- Follow the target site's terms, robots.txt, privacy law, and any applicable API rules.
- Respect crawl limits; do not target arbitrary IPs, internal services, logins, CAPTCHAs, or protected content.
- Keep API keys in `.env`, never in source code or exported CSVs.

## Project layout

```text
app.py                         Streamlit interface
lead_intelligence/
  discovery.py                 Public list-page analysis and URL routing
  places.py                    Google Places Text Search adapter
  extraction.py                Safe business-website contact crawler
  matching.py                  Explainable name/address scoring
  pipeline.py                  CSV processing and export fields
  ai_verifier.py               Optional structured AI reviewer
  cache.py                     SQLite cache
tests/test_matching.py         Matching edge-case tests
```

Run the application tests with:

```bash
python -m pytest -q tests
```

## Current limitations and next build step

The static/page-browser discovery engine is functional for structured listings and common repeated-card pages. The next practical enhancement is a **domain-template editor**: preview a page, click/select the business name, address, detail URL, and next-page elements, save that template, then run a controlled batch extraction. This gives better accuracy than a fully autonomous scraper while still demonstrating AI-assisted adaptation.
