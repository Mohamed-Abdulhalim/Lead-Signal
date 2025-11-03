from flask import Flask, jsonify, request, render_template
import pandas as pd
import math
import os

app = Flask(__name__)

CSV_PATH = os.environ.get("CSV_PATH", "TheResultss_clean2.csv")

df = pd.read_csv(CSV_PATH, encoding="utf-8")
if "query_location" not in df.columns:
    df["query_location"] = "Cairo, Egypt"
if "category" not in df.columns:
    df["category"] = "clinics"


def unique_categories():
    return sorted([str(x) for x in df["category"].dropna().unique()])


def unique_locations():
    return sorted([str(x) for x in df["query_location"].dropna().unique()])


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

    q = df
    if category:
        q = q[q["category"].astype(str).str.lower() == category.lower()]
    if location:
        q = q[q["query_location"].astype(str).str.lower() == location.lower()]

    total = len(q)
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))

    start = (page - 1) * per_page
    end = start + per_page

    fields = [
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

    rows = q.iloc[start:end].fillna("").to_dict(orient="records")
    items = []
    for row in rows:
        rec = {k: str(row.get(k, "")) for k in fields}
        # Parse multiple photos from photo_urls (comma-separated)
        raw = rec.get("photo_urls", "")
        photos = []
        if raw:
            for part in raw.split(","):
                u = part.strip()
                if u and u.startswith("http"):
                    photos.append(u)
        # Fallback: synthesize main_photo_url from first photo
        if not rec.get("main_photo_url") and photos:
            rec["main_photo_url"] = photos[0]
        rec["photos"] = photos
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
    app.run(host="0.0.0.0", port=5000, debug=False)
