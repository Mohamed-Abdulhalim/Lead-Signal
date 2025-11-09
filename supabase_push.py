#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, argparse, logging, math
from typing import List, Dict, Any
from supabase import create_client


def to_bool(v: str):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true","t","1","yes","y"}:
        return True
    if s in {"false","f","0","no","n"}:
        return False
    return None


def to_int(v: str):
    if v is None or v == "":
        return None
    try:
        return int(str(v).replace(",",""))
    except Exception:
        return None


def to_float(v: str):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",",""))
    except Exception:
        return None


def clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(row)
    r["rating"] = to_float(r.get("rating"))
    r["reviews_count"] = to_int(r.get("reviews_count"))
    r["price_min_egp"] = to_int(r.get("price_min_egp"))
    r["price_max_egp"] = to_int(r.get("price_max_egp"))
    b = to_bool(r.get("price_is_plus"))
    if b is not None:
        r["price_is_plus"] = b
    if r.get("photo_urls"):
        r["photo_urls"] = r["photo_urls"].split(" ")[0].strip()
    return r


def read_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        return [dict(x) for x in rdr]


def upsert_batch(supabase, rows: List[Dict[str, Any]]):
    if not rows:
        return
    try:
        supabase.table("places").upsert(rows, on_conflict="profile_url").execute()
    except Exception as e:
        logging.warning("batch upsert failed: %s; falling back per-row", e)
        for x in rows:
            try:
                supabase.table("places").upsert(x, on_conflict="profile_url").execute()
            except Exception as ee:
                logging.warning("row failed: %s | %s", x.get("profile_url"), ee)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE", "").strip()
    if not url or not key:
        logging.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
        sys.exit(1)

    supabase = create_client(url, key)

    rows = read_csv(args.csv_path)
    logging.info("loaded %d rows from %s", len(rows), args.csv_path)

    queue: List[Dict[str, Any]] = []
    sent = 0
    for row in rows:
        u = (row.get("profile_url") or "").strip()
        if not u:
            continue
        payload = clean_row(row)
        queue.append(payload)
        if len(queue) >= args.batch:
            upsert_batch(supabase, queue)
            sent += len(queue)
            logging.info("upserted %d rows so far", sent)
            queue = []
    if queue:
        upsert_batch(supabase, queue)
        sent += len(queue)
    logging.info("done. total upserted: %d", sent)


if __name__ == "__main__":
    main()
