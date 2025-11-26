#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, argparse, logging
from typing import List, Dict, Any
from supabase import create_client
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import LOG_FORMAT, LOG_LEVEL

TABLE_NAME = os.environ.get("LEADS_TABLE", "production_maps")


def to_bool(v: str):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "t", "1", "yes", "y"}:
        return True
    if s in {"false", "f", "0", "no", "n"}:
        return False
    return None


def to_float(v: str):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def read_csv(path: str) -> List[Dict[str, Any]]:
    logging.info("Reading CSV from %s", path)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        rows = [dict(x) for x in rdr]
    logging.info("Loaded %d rows from CSV", len(rows))
    return rows


def clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    r: Dict[str, Any] = {}
    r["name"] = (row.get("name") or "").strip()
    r["correct_name"] = (row.get("correct_name") or "").strip()
    r["profile_url"] = (row.get("profile_url") or "").strip()
    r["photo_urls"] = (row.get("photo_urls") or "").strip()
    r["category"] = (row.get("category") or "").strip()
    r["query_location"] = (row.get("query_location") or "").strip()
    r["address_line"] = (row.get("address_line") or "").strip()
    r["phone"] = (row.get("phone") or "").strip()
    r["website"] = (row.get("website") or "").strip()
    r["opening_hours"] = (row.get("opening_hours") or "").strip()
    r["social_links"] = (row.get("social_links") or "").strip()
    r["rating"] = to_float(row.get("rating"))
    return r


def upsert_batch(supabase, rows: List[Dict[str, Any]]):
    if not rows:
        return
    logging.info("Upserting batch of %d rows into %s", len(rows), TABLE_NAME)
    try:
        supabase.table(TABLE_NAME).upsert(rows, on_conflict="profile_url").execute()
    except Exception as e:
        logging.warning("Batch upsert failed: %s; falling back to per-row", e)
        for x in rows:
            try:
                supabase.table(TABLE_NAME).upsert(x, on_conflict="profile_url").execute()
            except Exception as ee:
                logging.warning("Row failed for profile_url=%s | %s", x.get("profile_url"), ee)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--log", type=str, default=LOG_LEVEL)
    args = ap.parse_args()

    level = getattr(logging, args.log.upper(), getattr(logging, LOG_LEVEL, logging.INFO))
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler("supabase_push.log", encoding="utf-8"),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )

    logging.info("Starting Supabase push")
    logging.info("CSV: %s | batch: %d | table: %s", args.csv_path, args.batch, TABLE_NAME)

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE", "").strip()
    if not url or not key:
        logging.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
        sys.exit(1)

    logging.info("Creating Supabase client")
    supabase = create_client(url, key)

    rows = read_csv(args.csv_path)

    queue: List[Dict[str, Any]] = []
    sent = 0
    skipped_empty_url = 0
    for row in rows:
        u = (row.get("profile_url") or "").strip()
        if not u:
            skipped_empty_url += 1
            continue
        payload = clean_row(row)
        if not payload.get("profile_url"):
            skipped_empty_url += 1
            continue
        queue.append(payload)
        if len(queue) >= args.batch:
            upsert_batch(supabase, queue)
            sent += len(queue)
            logging.info("Upserted %d rows so far into %s", sent, TABLE_NAME)
            queue = []
    if queue:
        upsert_batch(supabase, queue)
        sent += len(queue)
        logging.info("Final batch upserted, total rows now %d", sent)

    logging.info(
        "Supabase push done. Table=%s | total_upserted=%d | skipped_missing_url=%d",
        TABLE_NAME,
        sent,
        skipped_empty_url,
    )


if __name__ == "__main__":
    main()
