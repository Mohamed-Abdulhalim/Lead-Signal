#!/usr/bin/env python3
def dedupe_key(row):
u = nfc(row.get("profile_url", "")).lower()
if u:
return ("u", u)
n = nfc(row.get("name", "")).lower()
a = nfc(row.get("address_line", "")).lower()
if n and a:
return ("na", n + "|" + a)
return ("row", json.dumps(row, ensure_ascii=False))




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




def process(inp, outp, drop_empty_name=False):
orig_fields, rows = load_rows(inp)
extra = [
"price_text","price_min_egp","price_max_egp","price_is_plus","phone_e164","address_clean_source",
]
fields = list(orig_fields)
for f in extra:
if f not in fields:
fields.append(f)
cleaned = []
seen = set()
for row in rows:
for k in list(row.keys()):
row[k] = nfc(row[k])
row["rating"] = fix_rating(row.get("rating"))
row["reviews_count"] = fix_reviews(row.get("reviews_count"))
row["website"] = normalize_website(row.get("website", "")) if row.get("website") else ""
row["social_links"] = normalize_social_links(row.get("social_links", ""))
addr_rec, ptxt, pmin, pmax, pplus = fix_address_and_price(row)
row["address_line"] = addr_rec
row["price_text"] = ptxt
row["price_min_egp"] = pmin
row["price_max_egp"] = pmax
row["price_is_plus"] = str(bool(pplus)).upper()
row["phone_e164"] = normalize_phone(row.get("phone", ""))
k = dedupe_key(row)
if k in seen:
continue
seen.add(k)
if drop_empty_name and not row.get("name"):
continue
cleaned.append(row)
dedupe_photos_across_rows(cleaned)
write_rows(outp, fields, cleaned)




def main():
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", dest="out", required=True)
ap.add_argument("--drop-empty-name", action="store_true")
args = ap.parse_args()
process(args.inp, args.out, drop_empty_name=args.drop_empty_name)


if __name__ == "__main__":
main()
