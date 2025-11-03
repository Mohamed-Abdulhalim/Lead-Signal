#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import math
from flask import Flask, jsonify, request, render_template
from supabase import create_client, Client

APP_PORT = int(os.environ.get("PORT", "5000"))
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE", "places")

app = Flask(__name__, static_folder=None, template_folder="templates")

# --------- Supabase client ----------
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_ANON_KEY env vars for read-only UI.")

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Columns your UI expects (keep these in sync with your table)
COLUMNS = [
    "name",
    "category",
    "query_location",
    "category_line",
    "address_line",
    "phone",
    "phone_e164",
    "website",
    "website_fallback",
    "profile_url",
    "rating",
    "reviews_count",
    "opening_hours",
    "is_open_now",
    "today_time_hint",
    "hours_note",
    "gmaps_primary_category",
    "main_photo_url",
    "photo_urls",
]

# ---------- Helpers ----------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def to_str(x):
    return "" if x is None else str(x)

def list_categories():
    # distinct categories
    q = sb.table(SUPABASE_TABLE).select("category", distinct=True).not_.is_("category", "null")
    data = q.execute().data or []
    cats = sorted({to_str(r.get("category")) for r in data if r.get("category")})
    return cats or ["restaurants", "clinics", "gyms"]

def list_locations():
    # distinct locations
    q = sb.table(SUPABASE_TABLE).select("query_location", distinct=True).not_.is_("query_location", "null")
    data = q.execute().data or []
    locs = sorted({to_str(r.get("query_location")) for r in data if r.get("query_location")})
    return locs or ["Cairo, Egypt"]

def parse_photos(row):
    raw = to_str(row.get("photo_urls"))
    photos = []
    if raw:
        for part in raw.split(","):
            u = part.strip()
            if u.startswith("http"):
                photos.append(u)
    if not row.get("main_photo_url") and photos:
        row["main_photo_url"] = photos[0]
    row["photos"] = photos
    return row

# ---------- Routes ----------
@app.get("/")
def index():
    return render_template(
        "index.html",
        categories=list_categories(),
        locations=list_locations(),
    )

@app.get("/search")
def search():
    category = request.args.get("category", type=str)
    location = request.args.get("location", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    per_page = clamp(per_page, 1, 100)
    page = clamp(page, 1, 10_000)

    base = sb.table(SUPABASE_TABLE)
    # total count
    q_count = base.select("id", count="exact")
    if category:
        q_count = q_count.eq("category", category)
    if location:
        q_count = q_count.eq("query_location", location)
    res_count = q_count.execute()
    total = int(res_count.count or 0)

    pages = max(1, math.ceil(total / per_page))
    page = clamp(page, 1, pages)
    start = (page - 1) * per_page
    end = start + per_page - 1  # Supabase uses inclusive range

    q = base.select(",".join(COLUMNS))
    if category:
        q = q.eq("category", category)
    if location:
        q = q.eq("query_location", location)

    # Optional ordering: higher rating first, then more reviews
    q = q.order("rating", desc=True).order("reviews_count", desc=True).range(start, end)
    data = q.execute().data or []

    items = []
    for r in data:
        rec = {k: to_str(r.get(k, "")) for k in COLUMNS}
        parse_photos(rec)
        items.append(rec)

    return jsonify(
        {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        }
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
