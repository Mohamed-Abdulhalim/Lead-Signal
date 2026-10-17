import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cleaner"))

import csv_cleaner as c


def test_normalize_gmaps_collapses_to_place_id():
    url = "https://www.google.com/maps/place/Some+Cafe/data=!4m7!3m6!1sChIJabc123_-XYZ!8m2"
    assert c.normalize_gmaps(url).startswith("https://www.google.com/maps/")
    pid = "https://www.google.com/maps/search/?api=1&query=x&query_place_id=ChIJzzz999"
    assert c.normalize_gmaps(pid) == "https://www.google.com/maps/place/?q=place_id:ChIJzzz999"


def test_normalize_gmaps_strips_tracking_and_coords():
    url = "https://www.google.com/maps/place/Cafe/@30.0444,31.2357,17z?entry=ttu&hl=en"
    out = c.normalize_gmaps(url)
    assert "@30.0444" not in out
    assert "entry=" not in out and "hl=" not in out


def test_normalize_website_adds_scheme_and_drops_utm():
    assert c.normalize_website("example.com") == "http://example.com"
    assert c.normalize_website("https://x.com/?utm_source=maps") == "https://x.com/"
    assert c.normalize_website("") == ""


def test_fix_rating_and_reviews():
    assert c.fix_rating("4.7 stars") == "4.7"
    assert c.fix_rating("") == ""
    assert c.fix_reviews("(1,234)") == "1234"
    assert c.fix_reviews("no reviews") == ""


def test_process_dedupes_and_cleans(tmp_path):
    src = tmp_path / "raw.csv"
    out = tmp_path / "clean.csv"
    header = "category,query_location,name,category_line,address_line,plus_code,phone,website,profile_url,rating,reviews_count,opening_hours,social_links,photo_urls,timestamp\n"
    row = "gym,\"Cairo, Egypt\",Alpha Gym,Gym,Nasr City,,01000000000,alpha.com,https://www.google.com/maps/search/?api=1&query_place_id=ChIJdup1,4.5 stars,\"(1,200)\",,,,2026-01-01\n"
    src.write_text(header + row + row, encoding="utf-8")
    c.process(str(src), str(out))
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(lines) == 2
    assert "ChIJdup1" in lines[1]
    assert "1200" in lines[1]
