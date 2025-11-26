# Lead Signal – Automated Google Maps Scraper & Lead Pipeline

A production-grade pipeline that turns Google Maps into clean, structured business leads.  
**Scrape → Clean → Enrich → Upsert → View in a live dashboard.**

Built for real-world use: scalable scraping, automated cleaning, deduplication, enrichment, and a live Supabase-powered UI deployed on Vercel.

---

## ✨ Highlights (Enterprise-Level Features)

### **Full Google Maps Extraction**
- Scrapes **names, phones, websites, addresses, ratings, reviews, photos, categories**, and detailed profile info.  
- Uses **Selenium + undetected-chromedriver**, rotating user-agents/languages, random delays, and periodic browser restarts to avoid bans.

### **Industrial-Grade Cleaning & Normalization**
- Standardizes **phone numbers**, **addresses**, **URLs**, and **social links**.  
- Extracts price data when available.  
- Removes duplicate businesses and duplicate photos.  
- Produces a clean, analysis-ready dataset.

### **Phone Enrichment Layer**
- Revisits profiles missing contact numbers and extracts phones from the business detail page.

### **Supabase Cloud Database (Upsert Logic)**
- Cleaned data is upserted into PostgreSQL (Supabase).  
- Unique key: **profile URL** → no duplicates ever.  
- Batch inserts for performance.

### **CI/CD Automation**
- GitHub Actions runs the full pipeline on a schedule.  
- Automatically rotates cities each run.  
- Fully hands-off operation.

### **Live Dashboard UI**
- Flask backend + Vercel hosting.  
- Filter by category and location.  
- Fast pagination, mobile-friendly UI.

### **Security Built-In**
- No credentials in code.  
- `.env.example` included.  
- Production secrets stored in GitHub Secrets.

---

## 🛠️ Tech Stack
- **Python 3.11**  
- Selenium, undetected-chromedriver  
- Supabase (PostgreSQL)  
- GitHub Actions  
- Flask (API + dashboard)  
- HTML / JS frontend (Vercel)

---

## 📂 Project Structure

```
maps-scraper/
├── maps.py                # Main scraper → results.csv
├── csv_cleaner.py         # Cleans & normalizes → Cleaned.csv
├── phone_enricher.py      # Fills missing phones → Enriched.csv
├── supabase_push.py       # Upserts into Supabase
├── app.py                 # Flask API + dashboard
├── templates/
│   └── index.html         # Dashboard UI
├── categories.txt
├── requirements.txt
└── .github/workflows/
    └── scrape.yml         # CI/CD pipeline
```

---

## ⚙️ Local Setup

### **1. Install dependencies**
```bash
pip install -r requirements.txt
```

### **2. Create `.env`**
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE=...
```

### **3. Run the pipeline**
```bash
py maps.py --categories-file categories.txt --location "Cairo, Egypt" --max-places 20 --output results.csv --headless
py csv_cleaner.py --in results.csv --out Cleaned.csv
py phone_enricher.py --in Cleaned.csv --out Enriched.csv
py supabase_push.py Enriched.csv
```

### **4. Run the dashboard**
```bash
export SUPABASE_URL=...
export SUPABASE_ANON_KEY=...
py app.py
```

Visit: **http://localhost:5000**

---

## 🕒 Automation (GitHub Actions)

The scheduled workflow handles:

- Headless scraping  
- Cleaning  
- Phone enrichment  
- Upsert to Supabase  
- Automatic city rotation  

Manual triggering:  
**GitHub → Actions → Run workflow**

---

## 💡 Use Cases
- Sales lead generation  
- Local business intelligence  
- Market research  
- Directory apps & location-based platforms  
- Automated client data collection for agencies/consultants

---

## 🔮 Roadmap
- Excel / Notion export  
- Email enrichment  
- Rating / “open now” filters  
- Multi-region scraping  
- Advanced analytics dashboard  

---

## 📜 License
MIT License.

---

## 🙋‍♂️ Author
**Mohamed Abdulhalim**  
Data scraping, automation, Supabase & Python development.  
LinkedIn: https://www.linkedin.com/in/halim99/
