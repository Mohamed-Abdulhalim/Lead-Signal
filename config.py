PAGELOAD_TIMEOUT = 30
SCRIPT_TIMEOUT = 20
MAX_SCROLL_TRIES = 50
SCROLL_BATCH_MIN = 3
SCROLL_BATCH_MAX = 6
SCROLL_DELAY_MIN = 0.25
SCROLL_DELAY_MAX = 0.70
HEADLESS_DEFAULT = True
CHROME_VERSION_FALLBACK = 142

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

DEFAULT_MAX_PLACES = 30
BROWSER_RESTART_EVERY = 1
PHONE_ENRICH_LIMIT = 100000
PHONE_RESTART_EVERY = 200

SUPABASE_TABLE_NAME = "production_maps"
SUPABASE_BATCH_SIZE = 500

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

SCRAPER_JITTER_MIN = 0.5
SCRAPER_JITTER_MAX = 1.2

ENRICH_JITTER_MIN = 0.2
ENRICH_JITTER_MAX = 0.6

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

ACCEPT_LANG = [
    "en-US,en;q=0.9,ar;q=0.7",
    "en-GB,en;q=0.9,ar;q=0.7",
    "ar-EG,ar;q=0.9,en;q=0.6",
]
