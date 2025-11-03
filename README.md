# Lead Finder – Google Maps Scraper (Automated)

**Collect business leads from Google Maps.**  
Categories → CSV → Cleaned → Upserted into Supabase → Displayed in a web dashboard.

This repository contains an automated scraping pipeline that:

- Scrapes business listings from Google Maps using **Selenium + undetected_chromedriver**
- Cleans and normalizes data (phone formatting, address recovery, price extraction, duplicate photo detection)
- Pushes cleaned data to **Supabase** (upsert — no duplicates)
- Runs automatically on **GitHub Actions** (scheduled scraping)

> Built to solve a real problem: *finding clean contact data without manual search.*

---

## ✨ Features

| Feature | Details |
|--------|---------|
| ✅ Google Maps data extraction | Name, phone, website, address, rating, photos, categories |
| ✅ CSV cleaning pipeline | Fixes addresses, removes duplicates, normalizes phone numbers |
| ✅ Unique image extraction | Removes repeated Google Maps photo URLs across rows |
| ✅ Automated CI/CD pipeline | Scraper → Cleaner → Supabase push |
| ✅ Idempotent upsert | Avoids duplicated database entries |
| ✅ Secrets safe | No credentials committed into git |

---

## 🛠️ Tech Stack

- **Python 3.11**
- `undetected-chromedriver`, `selenium`
- Supabase (PostgreSQL)
- GitHub Actions (CI/CD automation)

---

## 📦 Repository Structure

maps-scraper/
│
├── maps.py # The scraper
├── csv_cleaner.py # Cleans / normalizes scraped CSV
├── supabase_push.py # Upserts final CSV into Supabase
├── categories.txt # List of categories to scrape
├── .github/workflows/
│ └── scrape.yml # Scheduled GitHub Action
├── requirements.txt
└── .env.example # Environment variables (local only)
---

## ⚙️ Environment Variables

Create `.env`:

SUPABASE_URL=<your-project-url>
SUPABASE_SERVICE_ROLE=<service-role-key>
> Do NOT commit real keys — use **GitHub Secrets** for automation.

---

## 🚀 Run locally

```bash
py maps.py --categories-file categories.txt --location "Cairo, Egypt" --max-places 20 --output results.csv --headless

py csv_cleaner.py --in results.csv --out Cleaned.csv


py supabase_push.py Cleaned.csv
```
🕒 GitHub Actions (Auto-Scraping)

The repo includes a workflow that:

- Runs the scraper headlessly

- Cleans the results

- Pushes to Supabase

To trigger manually:
GitHub repo → Actions → Run workflow

🔥 Roadmap

✅ Dashboard UI (in progress)

⏳ Export to Excel / Notion

⏳ Paid version with filters & email enrichment

📜 License

This project is licensed under MIT License.

🙋‍♂️ Author

Mohamed Abdulhalim

Data scraping, automation, Supabase & Python development.

LinkedIn: https://[www.linkedin.com/in/mohamed-abdulhalim](https://www.linkedin.com/in/halim99/)
