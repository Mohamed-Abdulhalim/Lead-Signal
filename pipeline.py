#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, sys, subprocess, logging
from pathlib import Path

from config import (
    DEFAULT_MAX_PLACES,
    PHONE_ENRICH_LIMIT,
    LOG_FORMAT,
    LOG_LEVEL,
)


def run(cmd, allow_fail=False):
    logging.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        logging.error("Command failed with code %d", result.returncode)
        if not allow_fail:
            sys.exit(result.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--location", required=True)
    ap.add_argument("--categories-file", default="categories.txt")
    ap.add_argument("--max-places", type=int, default=DEFAULT_MAX_PLACES)
    ap.add_argument("--out-prefix", default="run")
    ap.add_argument("--no-headless", action="store_true")
    ap.add_argument("--phone-limit", type=int, default=PHONE_ENRICH_LIMIT)
    ap.add_argument("--skip-scrape", action="store_true")
    ap.add_argument("--skip-clean", action="store_true")
    ap.add_argument("--skip-enrich", action="store_true")
    ap.add_argument("--skip-push", action="store_true")
    ap.add_argument("--log", default=LOG_LEVEL)
    args = ap.parse_args()

    level = getattr(logging, args.log.upper(), getattr(logging, LOG_LEVEL, logging.INFO))
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stdout,
    )

    base = Path(".")
    raw_csv = str(base / f"{args.out_prefix}_raw.csv")
    cleaned_csv = str(base / f"{args.out_prefix}_cleaned.csv")
    enriched_csv = str(base / f"{args.out_prefix}_enriched.csv")

    if not args.skip_scrape:
        cmd = [
            sys.executable,
            "scraper/maps_scraper.py",
            "--categories-file",
            args.categories_file,
            "--location",
            args.location,
            "--max-places",
            str(args.max_places),
            "--output",
            raw_csv,
        ]
        if not args.no_headless:
            cmd.append("--headless")
        run(cmd, allow_fail=False)

    if not args.skip_clean:
        cmd = [
            sys.executable,
            "cleaner/csv_cleaner.py",
            "--in",
            raw_csv,
            "--out",
            cleaned_csv,
        ]
        run(cmd, allow_fail=False)

    if not args.skip_enrich:
        cmd = [
            sys.executable,
            "scraper/phone_enricher.py",
            "--in",
            cleaned_csv,
            "--out",
            enriched_csv,
            "--limit",
            str(args.phone_limit),
        ]
        run(cmd, allow_fail=False)

    if not args.skip_push:
        cmd = [
            sys.executable,
            "db/supabase_push.py",
            enriched_csv,
        ]
        run(cmd, allow_fail=False)


if __name__ == "__main__":
    main()
