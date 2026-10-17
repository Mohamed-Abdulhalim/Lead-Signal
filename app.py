import math
import os
import re
import time
from xml.sax.saxutils import escape as xml_escape

from flask import Flask, Response, jsonify, redirect, render_template, request
from supabase import create_client

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
LEADS_TABLE = (os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "production_maps").strip()
SITE_URL = "https://leadsignal.halim.pro"
OLD_HOST = "maps-scraper-gray.vercel.app"

PER_PAGE = 20
MAX_PAGES = 5
SITEMAP_MIN_ROWS = 20
META_TTL = 900
COMBOS_TTL = 3600
STATS_TTL = 900

SEARCH_COLUMNS = (
    "id,name,correct_name,category,query_location,address_line,"
    "phone,website,rating,reviews_count,opening_hours,profile_url"
)
SAMPLE_COLUMNS = "name,correct_name,category,phone,website,address_line,rating,reviews_count,profile_url"
SORTS = {
    "rating_desc": ["rating.desc.nullslast", "reviews_count.desc.nullslast"],
    "reviews_desc": ["reviews_count.desc.nullslast", "rating.desc.nullslast"],
    "name_asc": ["name"],
}

_sb = None
_cache = {}


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


def _cached(key, ttl, loader, fallback):
    now = time.time()
    hit = _cache.get(key)
    if hit and (now - hit[0]) < ttl:
        return hit[1]
    try:
        value = _retry(loader)
    except Exception:
        return hit[1] if hit else fallback
    _cache[key] = (now, value)
    return value


def _rpc(name, params=None):
    return _get_sb().rpc(name, params or {}).execute().data


def _slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _make_slug(category, location):
    return f"{_slugify(category)}-{_slugify(location)}"


def _safe_url(value):
    v = (value or "").strip()
    if not v:
        return ""
    if v.lower().startswith(("http://", "https://")):
        return v
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", v, re.I):
        return "https://" + v
    return ""


def _label(category, location):
    return f"{category.title()} in {location}"


def lead_meta():
    def load():
        data = _rpc("get_lead_meta") or {}
        return {
            "categories": [c for c in data.get("categories") or [] if c],
            "locations": [l for l in data.get("locations") or [] if l],
        }

    return _cached("meta", META_TTL, load, {"categories": [], "locations": []})


def lead_stats():
    return _cached("stats", STATS_TTL, lambda: _rpc("lead_stats") or {}, {})


def combo_index():
    def load():
        rows = _rpc("get_lead_combos", {"min_n": 1}) or []
        by_slug = {}
        by_category = {}
        by_location = {}
        for category, location, n, n_phone, n_web in rows:
            combo = {
                "category": category,
                "location": location,
                "n": n,
                "n_phone": n_phone,
                "n_web": n_web,
                "slug": _make_slug(category, location),
                "label": _label(category, location),
            }
            by_slug[combo["slug"]] = combo
            by_category.setdefault(category, []).append(combo)
            by_location.setdefault(location, []).append(combo)
        return {"by_slug": by_slug, "by_category": by_category, "by_location": by_location}

    return _cached("combos", COMBOS_TTL, load, {"by_slug": {}, "by_category": {}, "by_location": {}})


def indexable_combos():
    combos = [c for c in combo_index()["by_slug"].values() if c["n"] >= SITEMAP_MIN_ROWS]
    combos.sort(key=lambda c: (c["category"], c["location"]))
    return combos


def _clean_item(row):
    item = {k: ("" if v is None else v) for k, v in row.items()}
    if item.get("correct_name"):
        item["name"] = item["correct_name"]
    item["website"] = _safe_url(item.get("website"))
    item["profile_url"] = _safe_url(item.get("profile_url"))
    return item


@app.before_request
def redirect_old_domain():
    if request.host == OLD_HOST:
        return redirect(request.url.replace(OLD_HOST, "leadsignal.halim.pro"), code=301)


@app.get("/health")
def health():
    return "ok", 200


@app.get("/stats")
def stats():
    s = lead_stats()
    resp = jsonify({
        "row_count": int(s.get("row_count") or 0),
        "phone_pct": int(s.get("phone_pct") or 0),
        "locations": int(s.get("locations") or 0),
        "categories": int(s.get("categories") or 0),
    })
    resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=900"
    return resp


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/", methods=["GET", "HEAD"])
def landing():
    if request.method == "HEAD":
        return "", 200
    return render_template("index.html")


@app.route("/app", methods=["GET", "HEAD"])
def tool():
    if request.method == "HEAD":
        return "", 200
    meta = lead_meta()
    return render_template("app.html", categories=meta["categories"], locations=meta["locations"])


@app.get("/meta")
def meta():
    resp = jsonify(lead_meta())
    resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=900"
    return resp


@app.get("/leads")
def leads_index():
    combos = [{"slug": c["slug"], "label": c["label"]} for c in indexable_combos()]
    return render_template("leads_index.html", combos=combos)


@app.get("/leads/<slug>")
def leads_page(slug):
    combo = combo_index()["by_slug"].get(slug)
    if not combo:
        return render_template("404.html"), 404

    category = combo["category"]
    location = combo["location"]

    try:
        q = (
            _get_sb()
            .table(LEADS_TABLE)
            .select(SAMPLE_COLUMNS)
            .eq("category", category)
            .eq("query_location", location)
            .order("rating.desc.nullslast")
            .limit(10)
        )
        sample_results = [_clean_item(r) for r in (_retry(q.execute).data or [])]
    except Exception:
        sample_results = []

    idx = combo_index()
    related = [
        {"slug": c["slug"], "label": c["label"]}
        for c in sorted(idx["by_category"].get(category, []), key=lambda c: -c["n"])
        if c["slug"] != slug and c["n"] >= SITEMAP_MIN_ROWS
    ][:8]
    nearby = [
        {"slug": c["slug"], "label": c["label"]}
        for c in sorted(idx["by_location"].get(location, []), key=lambda c: -c["n"])
        if c["slug"] != slug and c["n"] >= SITEMAP_MIN_ROWS
    ][:8]

    category_title = category.title()
    total = combo["n"]
    page_title = f"{category_title} in {location}: Phone Numbers, Websites & Addresses | LeadSignal"
    meta_description = (
        f"{total} {category_title.lower()} in {location} with phone numbers, websites, "
        f"addresses and ratings. Preview the list and export a sample to CSV."
    )

    return render_template(
        "leads_page.html",
        slug=slug,
        category_raw=category,
        category_title=category_title,
        location_raw=location,
        location_display=location.split(",")[0],
        page_title=page_title,
        meta_description=meta_description,
        sample_results=sample_results,
        total=total,
        phone_count=combo["n_phone"],
        website_count=combo["n_web"],
        related=related,
        nearby=nearby,
        noindex=total < SITEMAP_MIN_ROWS,
    )


def _build_search(location, category, filters, sort, count):
    q = _get_sb().table(LEADS_TABLE).select(SEARCH_COLUMNS, count=count).eq("query_location", location)
    if category:
        q = q.eq("category", category)
    if filters["min_rating"] is not None:
        q = q.gte("rating", filters["min_rating"])
    if filters["has_phone"]:
        q = q.not_.is_("phone", None).neq("phone", "")
    if filters["has_website"]:
        q = q.not_.is_("website", None).neq("website", "")
    if filters["address_contains"]:
        q = q.ilike("address_line", f"%{filters['address_contains']}%")
    for o in SORTS.get(sort, SORTS["rating_desc"]):
        q = q.order(o)
    return q


@app.get("/search")
def search():
    category = (request.args.get("category") or "").strip()
    location = (request.args.get("location") or "").strip()
    page = max(1, min(request.args.get("page", default=1, type=int) or 1, MAX_PAGES))
    sort = (request.args.get("sort") or "rating_desc").strip()

    if not location:
        return jsonify({"items": [], "page": 1, "per_page": PER_PAGE, "total": 0, "error": "location_required"}), 400

    address = re.sub(r"[%_*()]", " ", (request.args.get("address_contains") or "")).strip()[:60]
    filters = {
        "min_rating": request.args.get("min_rating", type=float),
        "has_phone": request.args.get("has_phone") == "1",
        "has_website": request.args.get("has_website") == "1",
        "address_contains": address,
    }
    plain = filters["min_rating"] is None and not filters["has_phone"] and not filters["has_website"] and not address

    offset = (page - 1) * PER_PAGE

    try:
        _get_sb()
    except Exception:
        return jsonify({"items": [], "page": page, "per_page": PER_PAGE, "total": 0, "error": "backend_not_ready"}), 503

    try:
        if plain:
            q = _build_search(location, category, filters, sort, None).range(offset, offset + PER_PAGE - 1)
            rows = _retry(q.execute).data or []
            combos = combo_index()["by_location"].get(location, [])
            total = sum(c["n"] for c in combos if not category or c["category"] == category)
            if not total:
                total = offset + len(rows)
        else:
            q = _build_search(location, category, filters, sort, "exact").range(offset, offset + PER_PAGE - 1)
            try:
                res = _retry(q.execute, tries=1)
            except Exception:
                q = _build_search(location, category, filters, sort, "planned").range(offset, offset + PER_PAGE - 1)
                res = _retry(q.execute)
            rows = res.data or []
            total = res.count or (offset + len(rows))
    except Exception:
        return jsonify({"items": [], "page": page, "per_page": PER_PAGE, "total": 0, "error": "query_failed"}), 502

    total_pages = max(1, min(math.ceil(total / PER_PAGE), MAX_PAGES))
    return jsonify({
        "items": [_clean_item(r) for r in rows],
        "page": page,
        "per_page": PER_PAGE,
        "total": total,
        "total_in_db": total,
        "total_pages": total_pages,
        "capped": total > MAX_PAGES * PER_PAGE,
        "max_rows": MAX_PAGES * PER_PAGE,
    })


@app.get("/sitemap.xml")
def sitemap():
    urls = [f"{SITE_URL}/", f"{SITE_URL}/app", f"{SITE_URL}/leads"]
    urls += [f"{SITE_URL}/leads/{c['slug']}" for c in indexable_combos()]
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    body += [f"<url><loc>{xml_escape(u)}</loc></url>" for u in urls]
    body.append("</urlset>")
    resp = Response("\n".join(body), mimetype="application/xml")
    resp.headers["Cache-Control"] = "public, max-age=3600, s-maxage=86400"
    return resp


@app.route("/robots.txt")
def robots_txt():
    body = "User-agent: *\nDisallow: /search\nDisallow: /meta\nDisallow: /stats\n\nSitemap: " + SITE_URL + "/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
