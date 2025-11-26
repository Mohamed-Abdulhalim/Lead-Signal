# config.py
# Centralized configuration for the Maps Scraper pipeline.

# -----------------------------
# Browser / Selenium Settings
# -----------------------------
PAGELOAD_TIMEOUT = 30
SCRIPT_TIMEOUT = 20
MAX_SCROLL_TRIES = 50
SCROLL_BATCH_MIN = 3
SCROLL_BATCH_MAX = 6
SCROLL_DELAY_MIN = 0.25
SCROLL_DELAY_MAX = 0.70
HEADLESS_DEFAULT = True
CHROME_VERSION_FALLBACK = 141

# -----------------------------
# Data / CSV Fields
# -----------------------------
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

# -----------------------------
# Limits and throttling
# -----------------------------
DEFAULT_MAX_PLACES = 500
BROWSER_RESTART_EVERY = 1
PHONE_ENRICH_LIMIT = None      # None = no limit
PHONE_RESTART_EVERY = 200

# -----------------------------
# Supabase Settings
# -----------------------------
SUPABASE_TABLE_NAME = "production_maps"
SUPABASE_BATCH_SIZE = 500

# -----------------------------
# Logging Settings
# -----------------------------
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"   # Default, CLI can override

# -----------------------------
# Jitter settings (random sleeps)
# -----------------------------
SCRAPER_JITTER_MIN = 0.5
SCRAPER_JITTER_MAX = 1.2

ENRICH_JITTER_MIN = 0.2
ENRICH_JITTER_MAX = 0.6
