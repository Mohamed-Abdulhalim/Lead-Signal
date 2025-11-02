#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, csv, re, unicodedata, os, sys, json
from datetime import datetime

CURRENCY_PATTERNS = [
    r"(?:EGP|ج(?:\.|\s*)م|LE|L\.E\.|E\s*P|جنيه)\s*\d+[\d\s,\.]*\+?",
    r"\d+[\d\s,\.]*\s*(?:EGP|ج(?:\.|\s*)م|LE|L\.E\.|E\s*P)\+?",
    r"(?:min(?:imum)?|delivery|charge|service)\s*[:=]?\s*\d+[\d\s,\.]*",
]
PRICE_RE = re.compile("|".join(CURRENCY_PATTERNS), re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:[\.,]\d+)?")
EGP_NUM_RE = re.compile(r"(?:(?:EGP|LE|L\.E\.|E\s*P|ج(?:\.|\s*)م)\s*)?(\d+[\d,\.]*)\s*(\+?)", re.IGNORECASE)
ADDR_SPLIT_RE = re.compile(r"\s*[•·]\s*|")
NBSP_REPL = {"\u00A0": " ", "\u202F": " "}

PHONE_RE = re.compile(r"(?:\+?20)?0?1[0-2,5]\d{8}|(?:\+?20)?0?2\d{7,8}|(?:\+?20)?0?\d{8,11}")
HTTP_RE = re.compile(r"^https?://", re.IGNORECASE)

SOCIAL_HOSTS = ["facebook.com","fb.com","instagram.com","x.com","twitter.com","tiktok.com","linkedin.com","youtube.com"]


def nfc(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    for k,v in NBSP_REPL.items():
        s = s.replace(k, v)
    return s.strip()


def looks_like_price(s):
    if not s:
        return False
    return bool(PRICE_RE.search(s))


def extract_price_fields(s):
    if not s:
        return "", "", "", False
    m = EGPNormalizer(s)
    return m["price_text"], m["price_min_egp"], m["price_max_egp"], m["price_is_plus"]


def EGPNormalizer(s):
    txt = " ".join(s.split())
    nums = [x.group(0) for x in NUM_RE.finditer(txt)]
    price_text = ""
    plus = False
    a = EGPNormalizeOnce(txt)
    if a:
        price_text = a["text"]
        plus = a["plus"]
        vals = a["values"]
        if len(vals) == 1:
            mn = mx = vals[0]
        else:
            mn, mx = min(vals), max(vals)
        return {"price_text": price_text, "price_min_egp": str(mn), "price_max_egp": str(mx), "price_is_plus": plus}
    if nums:
        vals = []
        for z in nums:
            try:
                vals.append(int(re.sub(r"[\.,]", "", z)))
            except:
                pass
        if vals:
            mn = min(vals)
            mx = max(vals)
            return {"price_text": txt, "price_min_egp": str(mn), "price_max_egp": str(mx), "price_is_plus": "+" in txt}
    return {"price_text": "", "price_min_egp": "", "price_max_egp": "", "price_is_plus": False}


def EGPNormalizeOnce(txt):
    vals = []
    plus = False
    for m in EGP_NUM_RE.finditer(txt):
        raw = m.group(1)
        if raw:
            try:
                vals.append(int(re.sub(r"[\.,]", "", raw)))
            except:
                pass
        if m.group(2):
            plus = True
    if not vals:
        return None
    return {"text": txt, "values": vals, "plus": plus}


def looks_like_address(s):
    if not s:
        return False
    if looks_like_price(s):
        return False
    if re.search(r"\b(?:Street|St\.|Road|Rd\.|Square|Sq\.|Mohand(?:seen)?|Nasr|Heliopolis|Giza|Cairo|Alex|Maadi|Dokki|Zamalek|New Cairo|6th of October|Sheikh Zayed|العنوان|شارع|ميدان|طريق|القاهرة|الجيزة|المعادي|الدقي|مدينة نصر|مصر الجديدة)\b", s, re.IGNORECASE):
        return True
    if re.search(r"\d", s) and re.search(r"\b[A-Za-z\u0600-\u06FF]{3,}\b", s):
        return True
    return False


def split_category_line_for_address(cat_line):
    if not cat_line:
        return "", ""
    parts = re.split(r"\s*[·•]\s*", cat_line)
    if len(parts) >= 2:
        left = parts[0].strip()
        right = parts[-1].strip()
        return left, right
    return cat_line.strip(), ""


def normalize_phone(s):
    if not s:
        return ""
    s = nfc(s)
    m = PHONE_RE.search(re.sub(r"[^\d\+]", "", s))
    if not m:
        return ""
    digits = re.sub(r"\D", "", m.group(0))
    if digits.startswith("20") and len(digits) >= 11:
        return "+" + digits
    if digits.startswith("0") and len(digits) >= 10:
        return "+20" + digits.lstrip("0")
    if digits.startswith("1") and len(digits) == 10:
        return "+20" + digits
    if digits.startswith("2") and len(digits) >= 9:
        return "+20" + digits
    return "+20" + digits


def normalize_website(u):
    if not u:
        return ""
    u = nfc(u)
    if not HTTP_RE.search(u):
        u = "http://" + u
    u = re.sub(r"[\?&](?:utm_[^=&]+|fbclid|gclid|hsa_[^=&]+)=[^&]+", "", u)
    u = re.sub(r"[\?&]+$", "", u)
    return u


def normalize_social_links(s):
    if not s:
        return ""
    links = []
    for part in re.split(r"[\s,;]+", s):
        part = part.strip()
        if not part:
            continue
        if not HTTP_RE.search(part):
            part = "http://" + part
        for h in SOCIAL_HOSTS:
            if h in part:
                links.append(part)
                break
    dedup = []
    seen = set()
    for l in links:
        k = l.lower()
        if k not in seen:
            seen.add(k)
            dedup.append(l)
    return ", ".join(dedup)


def fix_address_and_price(row):
    addr = nfc(row.get("address_line", ""))
    catline = nfc(row.get("category_line", ""))
    addr_is_price = looks_like_price(addr)
    recovered_addr = addr
    left, right = split_category_line_for_address(catline)
    if (not recovered_addr or addr_is_price) and right and looks_like_address(right):
        recovered_addr = right
    if (not recovered_addr or addr_is_price) and left and looks_like_address(left):
        recovered_addr = left
    price_source = ""
    mtxt, mn, mx, plus = "", "", "", False
    if addr_is_price:
        price_source = addr
        mtxt, mn, mx, plus = extract_price_fields(addr)
    elif looks_like_price(catline):
        price_source = catline
        mtxt, mn, mx, plus = extract_price_fields(catline)
    return recovered_addr, mtxt, mn, mx, plus


def fix_rating(x):
    x = nfc(x)
    m = re.search(r"\d+(?:\.\d+)?", x)
    return m.group(0) if m else ""


def fix_reviews(x):
    x = nfc(x).replace(",", "")
    m = re.search(r"\d+", x)
    return m.group(0) if m else ""


def dedupe_key(row):
    u = nfc(row.get("profile_url", "")).lower()
    if u:
        return ("u", u)
    n = nfc(row.get("name", "")).lower()
    a = nfc(row.get("address_line", "")).lower()
    if n and a:
        return ("na", n + "|" + a)
    return ("row", json.dumps(row, ensure_ascii=False))


def normalize_photo_identity(u):
    if not u:
        return "", ""
    u = nfc(u).strip().strip(",")
    if not u:
        return "", ""
    if not HTTP_RE.search(u):
        return "", ""
    base = re.sub(r"[\?].*$", "", u)
    base = base.split("=", 1)[0]
    low = base.lower()
    return base, low


def choose_single_unique_photo(raw, global_seen):
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    local_seen = set()
    for p in parts:
        base, key = normalize_photo_identity(p)
        if not key:
            continue
        if key in local_seen:
            continue
        local_seen.add(key)
        if key not in global_seen:
            global_seen.add(key)
            return base
    if parts:
        base, key = normalize_photo_identity(parts[0])
        return base
    return ""


def load_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        rows = [dict(row) for row in r]
        return r.fieldnames, rows


def write_rows(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def process(in_path, out_path, drop_empty_name=False):
    orig_fields, rows = load_rows(in_path)
    extra_fields = [
        "price_text","price_min_egp","price_max_egp","price_is_plus","phone_e164","address_clean_source",
    ]
    fieldset = list(orig_fields)
    for f in extra_fields:
        if f not in fieldset:
            fieldset.append(f)
    cleaned = []
    seen = set()
    global_photos_seen = set()
    for row in rows:
        for k in list(row.keys()):
            row[k] = nfc(row[k])
        row["rating"] = fix_rating(row.get("rating"))
        row["reviews_count"] = fix_reviews(row.get("reviews_count"))
        row["website"] = normalize_website(row.get("website", "")) if row.get("website") else ""
        row["social_links"] = normalize_social_links(row.get("social_links", ""))
        phone_e164 = normalize_phone(row.get("phone", ""))
        addr_rec, ptxt, pmin, pmax, pplus = fix_address_and_price(row)
        addr_src = "original"
        if addr_rec and addr_rec != row.get("address_line", ""):
            addr_src = "recovered"
        if not addr_rec:
            addr_src = "empty"
        row["address_line"] = addr_rec
        row["price_text"] = ptxt
        row["price_min_egp"] = pmin
        row["price_max_egp"] = pmax
        row["price_is_plus"] = str(bool(pplus)).upper()
        row["phone_e164"] = phone_e164
        row["address_clean_source"] = addr_src
        if "photo_urls" in row:
            row["photo_urls"] = choose_single_unique_photo(row.get("photo_urls", ""), global_photos_seen)
        k = dedupe_key(row)
        if k in seen:
            continue
        seen.add(k)
        if drop_empty_name and not row.get("name"):
            continue
        cleaned.append(row)
    write_rows(out_path, fieldset, cleaned)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--drop-empty-name", action="store_true")
    args = ap.parse_args()
    process(args.inp, args.out, drop_empty_name=args.drop_empty_name)

if __name__ == "__main__":
    main()
