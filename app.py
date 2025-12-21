from flask import Flask, jsonify, request, render_template, Response
from supabase import create_client
import os
import time

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
LEADS_TABLE = (os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "production_maps").strip()

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


@app.get("/health")
def health():
    return "ok", 200


@app.route("/", methods=["GET", "HEAD"])
def index():
    if request.method == "HEAD":
        return "", 200
    return render_template("index.html", categories=unique_categories(), locations=[])


@app.get("/meta")
def meta():
    try:
        locs = unique_locations()
    except Exception:
        locs = []
    return jsonify({"categories": unique_categories(), "locations": locs})


@app.get("/search")
def search():
    try:
        sb = _get_sb()
    except Exception:
        return jsonify({"items": [], "page": 1, "per_page": 100, "total": 0, "error": "backend_not_ready"}), 503

    category = request.args.get("category", type=str)
    location = request.args.get("location", type=str)
    page = request.args.get("page", default=1, type=int)
    if page < 1:
        page = 1

    per_page = 100
    offset = (page - 1) * per_page

    min_rating = request.args.get("min_rating", type=float)
    has_phone = request.args.get("has_phone") == "1"
    has_website = request.args.get("has_website") == "1"
    address_contains = request.args.get("address_contains", type=str)
    sort = (request.args.get("sort", type=str) or "").strip()

    q = sb.table(LEADS_TABLE).select("*", count="exact")

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
        q = q.order("reviews_count", desc=True)
    else:
        q = q.order("rating", desc=True)

    q = q.range(offset, offset + per_page - 1)

    def _exec():
        return q.execute()

    try:
        res = _retry(_exec, tries=2, base_sleep=0.25)
    except Exception:
        return jsonify({"items": [], "page": page, "per_page": per_page, "total": 0, "error": "query_failed"}), 502

    rows = res.data or []
    total = res.count or len(rows)

    items = []
    for row in rows:
        row = {k: ("" if v is None else v) for k, v in row.items()}

        raw = (row.get("photo_urls") or "").strip()
        photos = [u.strip() for u in raw.split(",") if u.strip().startswith("http")]

        if not row.get("main_photo_url") and photos:
            row["main_photo_url"] = photos[0]

        row["photos"] = photos

        if row.get("correct_name"):
            row["name"] = row["correct_name"]

        items.append(row)

    return jsonify({"items": items, "page": page, "per_page": per_page, "total": total})


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Disallow:\n"
        "\n"
        "Sitemap: https://maps-scraper-gray.vercel.app/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    body = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <url>
    <loc>https://maps-scraper-gray.vercel.app/</loc>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    return Response(body, mimetype="application/xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)






















































# from flask import Flask, jsonify, request, render_template, Response
# from supabase import create_client
# import os

# app = Flask(__name__)

# SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
# SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
# LEADS_TABLE = os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "production_maps"

# sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# with open("categories.txt") as f:
#     HARDCODED_CATEGORIES = sorted({line.strip() for line in f if line.strip()})


# def _distinct(col: str, batch: int = 2000, max_batches: int = 250):
#     seen = set()
#     values = []
#     offset = 0

#     for _ in range(max_batches):
#         res = (
#             sb
#             .table(LEADS_TABLE)
#             .select(col)
#             .order(col)
#             .range(offset, offset + batch - 1)
#             .execute()
#         )
#         rows = res.data or []
#         if not rows:
#             break

#         for r in rows:
#             v = (r.get(col) or "").strip()
#             if not v or v in seen:
#                 continue
#             seen.add(v)
#             values.append(v)

#         if len(rows) < batch:
#             break

#         offset += batch

#     return values


# def unique_categories():
#     return HARDCODED_CATEGORIES


# def unique_locations():
#     res = (
#         sb.table("distinct_query_locations")
#         .select("query_location")
#         .order("query_location")
#         .execute()
#     )

#     rows = res.data or []
#     values = []
#     for r in rows:
#         v = (r.get("query_location") or "").strip()
#         if v:
#             values.append(v)

#     return values


# @app.route("/", methods=["GET", "HEAD"])
# def index():
#     if request.method == "HEAD":
#         return "", 200

#     return render_template(
#         "index.html",
#         categories=unique_categories(),
#         locations=unique_locations(),
#     )


# @app.get("/meta")
# def meta():
#     return jsonify(
#         {
#             "categories": unique_categories(),
#             "locations": unique_locations(),
#         }
#     )


# @app.get("/search")
# def search():
#     category = request.args.get("category", type=str)
#     location = request.args.get("location", type=str)
#     page = request.args.get("page", default=1, type=int)
#     if page < 1:
#         page = 1
#     per_page = 100
#     offset = (page - 1) * per_page

#     min_rating = request.args.get("min_rating", type=float)
#     has_phone = request.args.get("has_phone") == "1"
#     has_website = request.args.get("has_website") == "1"
#     address_contains = request.args.get("address_contains", type=str)
#     sort = (request.args.get("sort", type=str) or "").strip()

#     q = sb.table(LEADS_TABLE).select("*", count="exact")

#     if category:
#         q = q.eq("category", category)

#     if location:
#         loc = location.strip()
#         if loc:
#             q = q.ilike("query_location", f"{loc}%")

#     if min_rating is not None:
#         q = q.gte("rating", min_rating)

#     if has_phone:
#         q = (
#             q.not_.is_("phone", None)
#              .neq("phone", "")
#         )

#     if has_website:
#         q = (
#             q.not_.is_("website", None)
#              .neq("website", "")
#         )

#     if address_contains:
#         addr = address_contains.strip()
#         if addr:
#             q = q.ilike("address_line", f"%{addr}%")

#     if sort == "rating_desc":
#         q = q.order("rating", desc=True)
#     elif sort == "name_asc":
#         q = q.order("name")
#     else:
#         q = q.order("rating", desc=True)

#     q = q.range(offset, offset + per_page - 1)

#     res = q.execute()
#     rows = res.data or []
#     total = res.count or len(rows)

#     items = []
#     for row in rows:
#         row = {k: ("" if v is None else v) for k, v in row.items()}

#         raw = (row.get("photo_urls") or "").strip()
#         photos = [
#             u.strip()
#             for u in raw.split(",")
#             if u.strip().startswith("http")
#         ]

#         if not row.get("main_photo_url") and photos:
#             row["main_photo_url"] = photos[0]

#         row["photos"] = photos

#         if row.get("correct_name"):
#             row["name"] = row["correct_name"]

#         items.append(row)

#     return jsonify(
#         {
#             "items": items,
#             "page": page,
#             "per_page": per_page,
#             "total": total,
#         }
#     )


# @app.route("/robots.txt")
# def robots_txt():
#     body = (
#         "User-agent: *\n"
#         "Disallow:\n"
#         "\n"
#         "Sitemap: https://maps-scraper-gray.vercel.app/sitemap.xml\n"
#     )
#     return Response(body, mimetype="text/plain")


# @app.route("/sitemap.xml")
# def sitemap_xml():
#     body = """<?xml version="1.0" encoding="UTF-8"?>
# <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
#   <url>
#     <loc>https://maps-scraper-gray.vercel.app/</loc>
#     <priority>1.0</priority>
#   </url>
# </urlset>
# """
#     return Response(body, mimetype="application/xml")


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=False)





































# from flask import Flask, jsonify, request, render_template
# from supabase import create_client
# import os
# import math

# app = Flask(__name__)

# SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
# SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
# LEADS_TABLE = os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "places"

# sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# def _distinct(col):
#     """
#     Fetch distinct non-null values for a column from the database.
#     Uses Python set() for deduplication since Supabase Python client
#     doesn't support DISTINCT ON directly.
#     """
#     rows = (
#         sb.table(LEADS_TABLE)
#           .select(col)  # Select only the column we need
#           .not_.is_(col, None)  # Filter out NULL values
#           .order(col)  # Order by the column
#           .execute()
#           .data
#         or []
#     )
    
#     # Use a set to collect unique values
#     unique_vals = set()
#     for r in rows:
#         val = str(r.get(col, "")).strip()
#         if val:
#             unique_vals.add(val)
    
#     # Return as sorted list for consistent ordering
#     return sorted(unique_vals)

# def unique_categories():
#     """Get list of unique categories for the filter dropdown"""
#     return _distinct("category")

# def unique_locations():
#     """Get list of unique locations for the filter dropdown"""
#     return _distinct("query_location")

# @app.get("/")
# def index():
#     return render_template(
#         "index.html",
#         categories=unique_categories(),
#         locations=unique_locations(),
#     )

# @app.get("/search")
# def search():
#     category = request.args.get("category", type=str)
#     location = request.args.get("location", type=str)
#     page = request.args.get("page", default=1, type=int)
#     per_page = request.args.get("per_page", default=20, type=int)
    
#     q = sb.table(LEADS_TABLE).select("*", count="exact")
    
#     if category:
#         q = q.eq("category", category)
#     if location:
#         q = q.eq("query_location", location)
    
#     start = (page - 1) * per_page
#     end = start + per_page - 1
#     q = q.range(start, end)
    
#     res = q.execute()
#     total = res.count or 0
#     pages = max(1, math.ceil(total / per_page))
#     page = max(1, min(page, pages))
    
#     items = []
#     rows = res.data or []
#     for row in rows:
#         row = {k: ("" if v is None else v) for k, v in row.items()}
#         raw = (row.get("photo_urls") or "").strip()
#         photos = [u.strip() for u in raw.split(",") if u.strip().startswith("http")]
        
#         if not row.get("main_photo_url") and photos:
#             row["main_photo_url"] = photos[0]
        
#         row["photos"] = photos
#         items.append(row)
    
#     return jsonify({
#         "items": items,
#         "page": page,
#         "per_page": per_page,
#         "total": total,
#         "pages": pages
#     })

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=False)
