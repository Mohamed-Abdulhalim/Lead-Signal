import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-key")

import app as app_module


COMBOS = [
    ["dentists", "Cairo, Egypt", 22, 20, 10],
    ["gym", "Cairo, Egypt", 150, 140, 90],
    ["gym", "London, United Kingdom", 300, 280, 250],
    ["florist", "London, United Kingdom", 3, 3, 1],
    ["gym", "Texas, USA", 40, 35, 30],
    ["cafes", "Zamalek, Egypt", 25, 20, 5],
]

ROWS = [
    {"id": 1, "name": "A", "correct_name": "Alpha Gym", "category": "gym", "query_location": "Cairo, Egypt",
     "address_line": "Nasr City", "phone": "+201000000000", "website": "javascript:alert(1)", "rating": 4.8,
     "reviews_count": 120, "opening_hours": "", "profile_url": "https://www.google.com/maps/place/?q=place_id:ChIJx"},
    {"id": 2, "name": "B", "correct_name": None, "category": "gym", "query_location": "Cairo, Egypt",
     "address_line": None, "phone": None, "website": "example.com", "rating": None,
     "reviews_count": None, "opening_hours": None, "profile_url": "https://www.google.com/maps/place/?q=place_id:ChIJy"},
]


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, client, table):
        self.client = client
        self.calls = [("table", table)]

    def __getattr__(self, name):
        if name == "not_":
            self.calls.append(("not_",))
            return self

        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return method

    def execute(self):
        self.client.queries.append(self.calls)
        if self.client.fail_exact and any(c[0] == "select" and c[2].get("count") == "exact" for c in self.calls):
            raise RuntimeError("statement timeout")
        return Result(ROWS, count=37)


class Rpc:
    def __init__(self, name):
        self.name = name

    def execute(self):
        if self.name == "get_lead_combos":
            return Result(COMBOS)
        if self.name == "get_lead_meta":
            return Result({"categories": ["dentists", "florist", "gym"], "locations": ["Cairo, Egypt", "London, United Kingdom"]})
        if self.name == "lead_stats":
            return Result({"row_count": 475, "phone_pct": 93, "locations": 2, "categories": 3})
        raise AssertionError(self.name)


class FakeClient:
    def __init__(self):
        self.queries = []
        self.fail_exact = False

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        return Rpc(name)


@pytest.fixture
def fake():
    client = FakeClient()
    app_module._sb = client
    app_module._cache.clear()
    yield client
    app_module._sb = None
    app_module._cache.clear()


@pytest.fixture
def http(fake):
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _orders(calls):
    return [c[1][0] for c in calls if c[0] == "order"]


def test_search_requires_location(http):
    r = http.get("/search?category=gym")
    assert r.status_code == 400
    assert r.get_json()["error"] == "location_required"


def test_search_uses_exact_location_match_and_combo_total(http, fake):
    r = http.get("/search?location=Cairo,%20Egypt&category=gym")
    body = r.get_json()
    assert r.status_code == 200
    calls = fake.queries[-1]
    assert ("eq", ("query_location", "Cairo, Egypt"), {}) in calls
    assert ("eq", ("category", "gym"), {}) in calls
    assert not any(c[0] == "ilike" for c in calls)
    assert _orders(calls)[0] == "rating.desc.nullslast"
    assert body["total"] == 150
    assert body["total_pages"] == 5
    assert body["capped"] is True


def test_search_page_is_capped(http, fake):
    http.get("/search?location=Cairo,%20Egypt&page=999")
    rng = [c for c in fake.queries[-1] if c[0] == "range"][0]
    assert rng[1] == (80, 99)


def test_search_sanitizes_urls(http):
    items = http.get("/search?location=Cairo,%20Egypt").get_json()["items"]
    assert items[0]["website"] == ""
    assert items[0]["name"] == "Alpha Gym"
    assert items[1]["website"] == "https://example.com"
    assert items[1]["rating"] == ""


def test_filtered_search_falls_back_to_planned_count(http, fake):
    fake.fail_exact = True
    r = http.get("/search?location=Cairo,%20Egypt&has_phone=1")
    assert r.status_code == 200
    assert r.get_json()["total"] == 37
    assert fake.queries[-1][1][2]["count"] == "planned"


def test_address_filter_strips_wildcards(http, fake):
    http.get("/search?location=Cairo,%20Egypt&address_contains=%25nasr*")
    ilike = [c for c in fake.queries[-1] if c[0] == "ilike"][0]
    assert ilike[1] == ("address_line", "%nasr%")


def test_reviews_sort(http, fake):
    http.get("/search?location=Cairo,%20Egypt&sort=reviews_desc")
    assert _orders(fake.queries[-1])[0] == "reviews_count.desc.nullslast"


def test_leads_page_renders_known_combo(http):
    r = http.get("/leads/gym-cairo-egypt")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Alpha Gym" in html
    assert "index,follow" in html
    assert "/leads/gym-london-united-kingdom" in html
    assert "javascript:" not in html


def test_leads_page_thin_combo_is_noindex(http):
    r = http.get("/leads/florist-london-united-kingdom")
    assert r.status_code == 200
    assert "noindex,follow" in r.get_data(as_text=True)


def test_leads_page_unknown_slug_404(http):
    assert http.get("/leads/unicorns-mars").status_code == 404


def test_sitemap_lists_only_substantial_combos(http):
    xml = http.get("/sitemap.xml").get_data(as_text=True)
    assert "/leads/gym-london-united-kingdom" in xml
    assert "/leads/dentists-cairo-egypt" in xml
    assert "/leads/florist-london-united-kingdom" not in xml


def test_stats_and_meta(http):
    assert http.get("/stats").get_json() == {"row_count": 475, "phone_pct": 93, "locations": 2, "categories": 3}
    assert "Cairo, Egypt" in http.get("/meta").get_json()["locations"]


def test_app_page_renders_dropdowns(http):
    html = http.get("/app").get_data(as_text=True)
    assert '<option value="London, United Kingdom" data-label="London" data-n="303">' in html
    assert '<option value="gym">Gym</option>' in html
    assert '<optgroup label="Egypt">' in html
    assert "leadsignal.app" not in html


def test_location_groups_come_only_from_combos(fake):
    groups = app_module.location_groups()
    countries = [g["country"] for g in groups]
    assert countries == ["Egypt", "USA", "United Kingdom"]
    egypt = {i["value"]: i for i in groups[0]["items"]}
    assert set(egypt) == {"Cairo, Egypt", "Zamalek, Egypt"}
    assert egypt["Cairo, Egypt"]["n"] == 172
    assert egypt["Zamalek, Egypt"]["label"] == "Zamalek (Cairo district)"
    assert groups[1]["items"][0]["label"] == "Texas (whole state)"


def test_categories_endpoint_lists_city_categories_with_counts(http):
    body = http.get("/categories?location=London,%20United%20Kingdom").get_json()
    assert [(i["category"], i["n"]) for i in body["items"]] == [("florist", 3), ("gym", 300)]
    assert body["total"] == 303
    assert http.get("/categories?location=Nowhere").get_json()["items"] == []
    assert http.get("/categories").status_code == 400


def test_export_returns_top_rows_in_one_query(http, fake):
    body = http.get("/search?location=Cairo,%20Egypt&page=3&export=1").get_json()
    rng = [c for c in fake.queries[-1] if c[0] == "range"][0]
    assert rng[1] == (0, 99)
    assert body["page"] == 1


def test_featured_combos_skip_missing_and_thin(fake):
    picks = app_module.featured_combos(3)
    assert len(picks) == 3
    assert len({p["location"] for p in picks}) == 3
    assert all(p["n"] >= app_module.SITEMAP_MIN_ROWS for p in picks)


def test_landing_renders_stats_server_side(http):
    html = http.get("/").get_data(as_text=True)
    assert ">475<" in html
    assert ">93%<" in html
    assert 'data-count' not in html
    assert "Alpha Gym" in html
    assert "Mohamed Abdelhalim" in html
    assert "Mohamed Abdulhalim" not in html


def test_landing_falls_back_when_backend_down(http, fake):
    def boom(*a, **k):
        raise RuntimeError("down")

    fake.rpc = boom
    html = http.get("/").get_data(as_text=True)
    assert "715,000" in html


def test_stats_survives_backend_failure(http, fake):
    def boom(*a, **k):
        raise RuntimeError("down")

    fake.rpc = boom
    assert http.get("/stats").get_json()["row_count"] == 0


def test_safe_url():
    assert app_module._safe_url("https://a.com") == "https://a.com"
    assert app_module._safe_url("a.com/x") == "https://a.com/x"
    assert app_module._safe_url("javascript:alert(1)") == ""
    assert app_module._safe_url("") == ""


def test_slugify_matches_existing_urls():
    assert app_module._make_slug("IT company", "Düsseldorf, Germany") == "it-company-düsseldorf-germany"
    assert app_module._make_slug("car rental", "Suez, Egypt") == "car-rental-suez-egypt"


@pytest.mark.parametrize("path", ["/", "/app", "/leads/gym-cairo-egypt", "/privacy"])
def test_no_portfolio_wording_and_correct_name(http, path):
    html = http.get(path).get_data(as_text=True)
    assert "portfolio" not in html.lower()
    assert "Mohamed Abdulhalim" not in html
    assert "Mohamed Abdelhalim" in html


@pytest.mark.parametrize("path", ["/", "/app", "/leads/gym-cairo-egypt"])
def test_data_date_is_shown(http, path):
    html = http.get(path).get_data(as_text=True)
    assert app_module.DATA_AS_OF in html
    assert app_module.DATA_AS_OF == "October 15, 2026"


def test_landing_faq_explains_data_age(http):
    html = http.get("/").get_data(as_text=True)
    assert "Is the data up to date?" in html
    assert "Collection stopped on October 15, 2026" in html
