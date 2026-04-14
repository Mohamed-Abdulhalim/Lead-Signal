import os, re, platform

PAGELOAD_TIMEOUT = 30
SCRIPT_TIMEOUT = 20
MAX_SCROLL_TRIES = 80
SCROLL_BATCH_MIN = 4
SCROLL_BATCH_MAX = 8
SCROLL_DELAY_MIN = 0.25
SCROLL_DELAY_MAX = 0.65
HEADLESS_DEFAULT = True
CHROME_VERSION_FALLBACK = None

def get_chrome_major_runtime():
    try:
        if platform.system().lower() == "linux":
            out = os.popen("google-chrome --version").read().strip()
            m = re.search(r"(\d+)\.", out)
            if m:
                return int(m.group(1))
        return None
    except Exception:
        return None

CSV_FIELDS = [
    "category",
    "query_location",
    "name",
    "category_line",
    "address_line",
    "plus_code",
    "phone",
    "website",
    "profile_url",
    "rating",
    "reviews_count",
    "opening_hours",
    "social_links",
    "photo_urls",
    "timestamp",
]

DEFAULT_MAX_PLACES = 500
BROWSER_RESTART_EVERY = 5
PHONE_ENRICH_LIMIT = 2000
PHONE_RESTART_EVERY = 100
SUPABASE_TABLE_NAME = "production_maps"
SUPABASE_BATCH_SIZE = 2000
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
SCRAPER_JITTER_MIN = 0.4
SCRAPER_JITTER_MAX = 1.0
ENRICH_JITTER_MIN = 0.2
ENRICH_JITTER_MAX = 0.5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

ACCEPT_LANG = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,ar;q=0.7",
]
