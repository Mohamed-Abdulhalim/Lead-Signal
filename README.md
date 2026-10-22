# LeadSignal

A Google Maps lead pipeline and search tool. A scraper collected business listings city by city, a cleaning and enrichment stage normalizes them, everything lands in Postgres (Supabase), and a Flask app on Vercel lets anyone browse and export the results.

Live: [leadsignal.halim.pro](https://leadsignal.halim.pro)

LeadSignal is a portfolio project. It is free to use and is not a commercial product.

## At a glance

- About 715,000 business listings across roughly 330 cities and 60 categories
- 83% of listings have a phone number
- Collection ran daily on GitHub Actions, one city per run, with no manual steps. The schedule is switched off and the dataset is frozen; the workflow can still be started by hand
- About 11,000 indexable city and category pages generated from the data

## How it works

```mermaid
flowchart LR
    A[GitHub Actions<br/>manual trigger] --> B[maps_scraper.py<br/>Selenium + undetected-chromedriver]
    B --> C[csv_cleaner.py<br/>normalize, dedupe]
    C --> D[phone_enricher.py<br/>revisit profiles, E.164 phones]
    D --> E[supabase_push.py<br/>batch upsert on profile_url]
    E --> F[(Postgres<br/>production_maps)]
    F -- statement trigger --> G[(lead_combos<br/>per city/category counts)]
    G --> H[Flask app on Vercel]
    F --> H
```

1. **Pick a city.** The workflow keeps its position in a 170+ city rotation in a `pipeline_state` table, so runs never commit to the repo.
2. **Scrape.** For every category in `categories.txt`, the scraper searches Google Maps for that city, scrolls the result list, and opens each profile for name, phone, website, address, rating, review count and hours. User agents and languages rotate and the browser restarts every few queries.
3. **Clean.** Maps URLs are collapsed to a stable `place_id` form, websites lose tracking parameters, ratings and review counts are parsed, and duplicates are removed.
4. **Enrich.** Profiles without a phone are revisited, and every phone is normalized to E.164 with `phonenumbers`, using the country of the searched city.
5. **Load.** Rows are upserted in batches with `profile_url` as the conflict key, so re-scraping a city refreshes listings instead of duplicating them.

## Database design

The main table is `production_maps`. Two decisions keep the public site fast on a small Postgres instance:

- **`lead_combos`** holds one row per category and city with total, phone and website counts. A statement-level `AFTER INSERT` trigger with a transition table keeps it current, so the app never has to count or `DISTINCT` over hundreds of thousands of rows. The location list, the landing page stats, the SEO pages and the sitemap all read from it.
- **Search indexes** match the query shape exactly: `(category, query_location, rating DESC NULLS LAST)` and `(query_location, rating DESC NULLS LAST)`. Searches use exact location matches from a dropdown instead of `ILIKE`, so a page of results is an index range scan.

Row level security is on for every table. The public role can read listings and the aggregate tables and nothing else.

`db/schema.sql` has the full schema.

## The web app

- `/app`: search by city and category, filter by rating, phone, website or address, sort, and export the visible results to CSV. Each search returns the top 100 results by rating.
- `/leads/<category>-<city>`: server-rendered pages with real counts and a sample of listings. Pages for combinations with fewer than 20 listings are marked `noindex`.
- `/sitemap.xml`: generated from `lead_combos`.

## Tech stack

Python 3.11, Selenium, undetected-chromedriver, pandas, phonenumbers, Supabase (Postgres), Flask, Vercel, GitHub Actions.

## Project layout

```
app.py                     Flask app (search API, pages, sitemap)
pipeline.py                Runs scrape, clean, enrich, push for one city
scraper/maps_scraper.py    Google Maps scraper
scraper/phone_enricher.py  Phone recovery and normalization
cleaner/csv_cleaner.py     Cleaning and deduplication
db/supabase_push.py        Batch upsert into Supabase
db/schema.sql              Database schema, functions, trigger, policies
templates/                 Landing page, search tool, SEO pages
tests/                     pytest suite for the app and the cleaner
.github/workflows/         Manual scrape, DB maintenance and CI
```

## Running locally

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run the pipeline for one city (needs Chrome, plus `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE` in the environment):

```bash
py pipeline.py --location "Cairo, Egypt" --categories-file categories.txt --max-places 20
```

Run the web app (needs `SUPABASE_URL` and `SUPABASE_ANON_KEY`):

```bash
py app.py
```

Run the tests:

```bash
py -m pytest
```

## Notes and limitations

- The data comes from public Google Maps listings. Scraping Google Maps is against Google's terms of service, which is one reason this project stays a free demo.
- Some listings belong to sole traders, whose details can count as personal data under the GDPR. Listings are removed on request.
- Review counts are only stored for listings collected or refreshed after October 2026.

## Author

Mohamed Abdulhalim, [halim.pro](https://halim.pro) · [LinkedIn](https://www.linkedin.com/in/halim99/)
