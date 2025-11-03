# app.py
from flask import Flask, jsonify, request, render_template
from supabase import create_client
import os
import math

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
LEADS_TABLE = os.environ.get("LEADS_TABLE", "places")

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

_cached_categories = []
_cached_locations = []


def _distinct(col):
    res = sb.table(LEADS_TABLE).select(col, distinct=True).execute()
    vals = []
    for r in res.data or []:
        v = r.get(col)
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        vals.append(s)
    vals = sorted(list(dict.fromkeys(vals)))
    return vals


def unique_categories():
    global _cached_categories
    if not _cached_categories:
        _cached_categories = _distinct("category")
    return _cached_categories


def unique_locations():
    global _cached_locations
    if not _cached_locations:
        _cached_locations = _distinct("query_location")
    return _cached_locations


@app.get("/")
def index():
    return render_template(
        "index.html",
        categories=unique_categories(),
        locations=unique_locations(),
    )


@app.get("/search")
def search():
    category = request.args.get("category", type=str)
    location = request.args.get("location", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    q = sb.table(LEADS_TABLE).select("name,category,query_location,category_line,address_line,phone,phone_e164,website,website_fallback,profile_url,rating,reviews_count,opening_hours,is_open_now,today_time_hint,hours_note,gmaps_primary_category,main_photo_url,photo_urls", count="exact")
    if category:
        q = q.eq("category", category)
    if location:
        q = q.eq("query_location", location)

    start = (page - 1) * per_page
    end = start + per_page - 1
    q = q.range(start, end)
    res = q.execute()

    total = res.count or 0
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))

    items = []
    for row in res.data or []:
        photos = []
        raw = row.get("photo_urls")
        if isinstance(raw, list):
            photos = [str(u) for u in raw if str(u).startswith("http")]
        elif isinstance(raw, str):
            parts = [p.strip() for p in raw.split(",")]
            photos = [p for p in parts if p.startswith("http")]
        rec = {
            "name": str(row.get("name", "")),
            "category": str(row.get("category", "")),
            "query_location": str(row.get("query_location", "")),
            "category_line": str(row.get("category_line", "")),
            "address_line": str(row.get("address_line", "")),
            "phone": str(row.get("phone", "")),
            "phone_e164": str(row.get("phone_e164", "")),
            "website": str(row.get("website", "")),
            "website_fallback": str(row.get("website_fallback", "")),
            "profile_url": str(row.get("profile_url", "")),
            "rating": str(row.get("rating", "")),
            "reviews_count": str(row.get("reviews_count", "")),
            "opening_hours": str(row.get("opening_hours", "")),
            "is_open_now": str(row.get("is_open_now", "")),
            "today_time_hint": str(row.get("today_time_hint", "")),
            "hours_note": str(row.get("hours_note", "")),
            "gmaps_primary_category": str(row.get("gmaps_primary_category", "")),
            "main_photo_url": str(row.get("main_photo_url", "")),
            "photo_urls": ",".join(photos),
            "photos": photos,
        }
        if not rec.get("main_photo_url") and photos:
            rec["main_photo_url"] = photos[0]
        items.append(rec)

    return jsonify({"items": items, "page": page, "per_page": per_page, "total": total, "pages": pages})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
