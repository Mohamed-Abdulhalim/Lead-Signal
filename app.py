# app.py
from flask import Flask, jsonify, request, render_template
from supabase import create_client
import os
import math

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
LEADS_TABLE = os.environ.get("LEADS_TABLE") or os.environ.get("SUPABASE_TABLE") or "places"

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _distinct(col):
    rows = (
        sb.table(LEADS_TABLE)
          .select(col, distinct=True)
          .not_.is_(col, None)
          .order(col)
          .execute()
          .data
        or []
    )
    vals = []
    for r in rows:
        s = str(r.get(col, "")).strip()
        if s:
            vals.append(s)
    return vals


def unique_categories():
    return _distinct("category")


def unique_locations():
    return _distinct("query_location")


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

    q = sb.table(LEADS_TABLE).select("*", count="exact")
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
    rows = res.data or []
    for row in rows:
        row = {k: ("" if v is None else v) for k, v in row.items()}
        raw = (row.get("photo_urls") or "").strip()
        photos = [u.strip() for u in raw.split(",") if u.strip().startswith("http")]
        if not row.get("main_photo_url") and photos:
            row["main_photo_url"] = photos[0]
        row["photos"] = photos
        items.append(row)


    return jsonify({"items": items, "page": page, "per_page": per_page, "total": total, "pages": pages})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
