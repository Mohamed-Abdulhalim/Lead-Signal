from flask import Flask, jsonify, request, render_template, Response, redirect
from supabase import create_client
import os
import time
import re
import requests

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
LEADS_TABLE = (os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "production_maps").strip()
LEMON_SQUEEZY_API_KEY = os.environ.get("LEMON_SQUEEZY_API_KEY", "").strip()

PRODUCT_LIMITS = {
    "4b42f716-b443-41a5-8c5e-6cacb17b6666": 500,
    "8e857854-8226-494a-afca-072e8398da68": 2000,
    "5afbd9d6-222a-4daf-a7ec-2270b8650125": 5000,
}

FREE_LIMIT = 10

_sb = None

try:
    with open("categories.txt", encoding="utf-8") as f:
        HARDCODED_CATEGORIES = sorted({line.strip() for line in f if line.strip()})
except Exception:
    HARDCODED_CATEGORIES = []

_cache = {
    "locations": {"ts": 0.0, "value": []},
    "categories": {"ts": 0.0, "value": HARDCODED_CATEGORIES},
}

def _get_sb():
    global _sb
    if _sb is not None:
        return _sb
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    _sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _sb

def _retry(fn, tries=2, base_sleep=0.25):
    last = None
    for i in range(max(1, tries)):
        try:
            return fn()
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(base_sleep * (2 ** i))
    raise last

def unique_categories():
    return _cache["categories"]["value"]

def _fetch_locations():
    sb = _get_sb()
    res = (
        sb.table("distinct_query_locations")
        .select("query_location")
        .order("query_location")
        .execute()
    )
    rows = res.data or []
    values = []
    for r in rows:
        v = (r.get("query_location") or "").strip()
        if v:
            values.append(v)
    return values

def unique_locations(ttl_seconds=900):
    now = time.time()
    bucket = _cache["locations"]
    if bucket["value"] and (now - bucket["ts"]) < ttl_seconds:
        return bucket["value"]
    values = _retry(_fetch_locations, tries=2, base_sleep=0.3)
    bucket["value"] = values
    bucket["ts"] = now
    return values

def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

def _make_slug(category, location):
    return f"{_slugify(category)}-{_slugify(location)}"

def _parse_slug(slug):
    cats = unique_categories()
    locs = unique_locations()
    for cat in sorted(cats, key=len, reverse=True):
        cat_slug = _slugify(cat)
        if slug.startswith(cat_slug + '-'):
            loc_slug = slug[len(cat_slug) + 1:]
            for loc in locs:
                if _slugify(loc) == loc_slug:
                    return cat, loc
    return None, None

def _validate_license_key(key):
    if not key or not LEMON_SQUEEZY_API_KEY:
        return None
    try:
        res = requests.post(
            "https://api.lemonsqueezy.com/v1/licenses/validate",
            json={"license_key": key},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=5
        )
        data = res.json()
        if not data.get("valid"):
            return None
        product_id = str(data.get("meta", {}).get("product_id", ""))
        limit = PRODUCT_LIMITS.get(product_id)
        return limit
    except Exception:
        return None

@app.get("/health")
def health():
    return "ok", 200

@app.route("/", methods=["GET", "HEAD"])
def landing():
    if request.method == "HEAD":
        return "", 200
    return render_template("index.html")

@app.route("/app", methods=["GET", "HEAD"])
def tool():
    if request.method == "HEAD":
        return "", 200
    try:
        locs = unique_locations()
    except Exception:
        locs = []
    return render_template(
        "app.html",
        categories=unique_categories(),
        locations=locs
    )

@app.post("/verify-key")
def verify_key():
    data = request.get_json() or {}
    key = (data.get("license_key") or "").strip()
    if not key:
        return jsonify({"valid": False, "error": "missing_key"}), 400
    limit = _validate_license_key(key)
    if limit is None:
        return jsonify({"valid": False, "error": "invalid_key"}), 200
    return jsonify({"valid": True, "limit": limit})

@app.post("/request")
def submit_request():
    data = request.get_json()
    location = (data.get("location") or "").strip()
    category = (data.get("category") or "").strip()
    email    = (data.get("email") or "").strip()
    if not (location or category) or not email:
        return jsonify({"error": "missing_fields"}), 400
    sb = _get_sb()
    sb.table("lead_requests").insert({
        "location": location,
        "category": category,
        "email":    email
    }).execute()
    return jsonify({"ok": True})

@app.get("/meta")
def meta():
    try:
        locs = unique_locations()
    except Exception:
        locs = []
    return jsonify({"categories": unique_categories(), "locations": locs})

@app.get("/leads")
def leads_index():
    cats = unique_categories()
    locs = unique_locations()
    combos = []
    for cat in cats:
        for loc in locs:
            combos.append({
                "slug": _make_slug(cat, loc),
                "label": f"{cat.title()} in {loc}"
            })
    return render_template("leads_index.html", combos=combos)

@app.get("/leads/<slug>")
def leads_page(slug):
    try:
        category, location = _parse_slug(slug)
    except Exception:
        category, location = None, None

    if not category or not location:
        return render_template("404.html"), 404

    sb = _get_sb()

    try:
        res = (
            sb.table(LEADS_TABLE)
            .select("name,correct_name,category,phone,website,address_line,rating,profile_url")
            .eq("category", category)
            .ilike("query_location", f"{location}%")
            .order("rating", desc=True)
            .limit(10)
            .execute()
        )
        sample_results = res.data or []
    except Exception:
        sample_results = []

    try:
        count_res = (
            sb.table(LEADS_TABLE)
            .select("id", count="exact")
            .eq("category", category)
            .ilike("query_location", f"{location}%")
            .execute()
        )
        total = count_res.count or len(sample_results)
    except Exception:
        total = len(sample_results)

    phone_count   = sum(1 for r in sample_results if r.get("phone"))
    website_count = sum(1 for r in sample_results if r.get("website"))

    locs = unique_locations()
    related = []
    for loc in locs:
        if loc == location:
            continue
        related.append({"slug": _make_slug(category, loc), "label": f"{category.title()} in {loc}"})
        if len(related) >= 8:
            break

    category_title   = category.title()
    location_display = location.split(",")[0]
    page_title       = f"{category_title} in {location} — Phone Numbers, Websites & Addresses | LeadSignal"
    meta_description = (
        f"Free list of {category_title.lower()} in {location} with phone numbers, websites, "
        f"addresses and ratings. {total} businesses found. Export to CSV instantly — no signup."
    )

    return render_template(
        "leads_page.html",
        slug=slug,
        category_raw=category,
        category_title=category_title,
        location_raw=location,
        location_display=location_display,
        page_title=page_title,
        meta_description=meta_description,
        sample_results=sample_results,
        total=total,
        phone_count=phone_count,
        website_count=website_count,
        related=related,
    )

@app.get("/search")
def search():
    try:
        sb = _get_sb()
    except Exception:
        return jsonify({"items": [], "page": 1, "per_page": 10, "total": 0, "error": "backend_not_ready"}), 503

    license_key = (request.args.get("license_key") or "").strip()
    if license_key:
        row_limit = _validate_license_key(license_key)
        if row_limit is None:
            row_limit = FREE_LIMIT
    else:
        row_limit = FREE_LIMIT

    category = request.args.get("category", type=str)
    location = request.args.get("location", type=str)
    page = request.args.get("page", default=1, type=int)
    if page < 1:
        page = 1

    per_page = min(100, row_limit)
    offset = (page - 1) * per_page

    if offset >= row_limit:
        return jsonify({"items": [], "page": page, "per_page": per_page, "total": 0, "capped": True, "row_limit": row_limit})

    remaining = row_limit - offset
    fetch_count = min(per_page, remaining)

    min_rating = request.args.get("min_rating", type=float)
    has_phone = request.args.get("has_phone") == "1"
    has_website = request.args.get("has_website") == "1"
    address_contains = request.args.get("address_contains", type=str)
    sort = (request.args.get("sort", type=str) or "").strip()

    q = sb.table(LEADS_TABLE).select(
        "id,name,correct_name,category,query_location,address_line,phone,website,rating::text,opening_hours,social_links,photo_urls,profile_url",
        count="exact"
    )

    if category:
        q = q.eq("category", category)
    if location:
        loc = location.strip()
        if loc:
            q = q.ilike("query_location", f"{loc}%")
    if min_rating is not None:
        q = q.gte("rating", min_rating)
    if has_phone:
        q = q.not_.is_("phone", None).neq("phone", "")
    if has_website:
        q = q.not_.is_("website", None).neq("website", "")
    if address_contains:
        addr = address_contains.strip()
        if addr:
            q = q.ilike("address_line", f"%{addr}%")

    if sort == "rating_desc":
        q = q.order("rating", desc=True)
    elif sort == "name_asc":
        q = q.order("name")
    elif sort == "reviews_desc":
        q = q.order("rating", desc=True)
    else:
        q = q.order("rating", desc=True)

    q = q.range(offset, offset + fetch_count - 1)

    def _exec():
        return q.execute()

    try:
        res = _retry(_exec, tries=2, base_sleep=0.25)
    except Exception:
        return jsonify({"items": [], "page": page, "per_page": per_page, "total": 0, "error": "query_failed"}), 502

    rows = res.data or []
    total_in_db = res.count or len(rows)
    capped_total = min(total_in_db, row_limit)

    items = []
    for row in rows:
        row = {k: ("" if v is None else (str(v) if isinstance(v, bool) else v)) for k, v in row.items()}
        raw = (row.get("photo_urls") or "").strip()
        photos = [u.strip() for u in raw.split(",") if u.strip().startswith("http")]
        if not row.get("main_photo_url") and photos:
            row["main_photo_url"] = photos[0]
        row["photos"] = photos
        if row.get("correct_name"):
            row["name"] = row["correct_name"]
        items.append(row)

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": capped_total,
        "total_in_db": total_in_db,
        "row_limit": row_limit,
        "capped": total_in_db > row_limit
    })

@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Disallow:\n"
        "\n"
        "Sitemap: https://leadsignal-app.vercel.app/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")

@app.before_request
def redirect_old_domain():
    if request.host == "maps-scraper-gray.vercel.app":
        new_url = request.url.replace("maps-scraper-gray.vercel.app", "leadsignal-app.vercel.app")
        return redirect(new_url, code=301)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
