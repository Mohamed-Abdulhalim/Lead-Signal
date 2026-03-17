#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv, sys, os, time, random, unicodedata, re, argparse, platform, logging
from typing import Dict, Any, List, Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

try:
    import phonenumbers
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

try:
    import winreg
except Exception:
    winreg = None

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import (
    USER_AGENTS,
    PAGELOAD_TIMEOUT,
    SCRIPT_TIMEOUT,
    ENRICH_JITTER_MIN,
    ENRICH_JITTER_MAX,
    PHONE_RESTART_EVERY,
    PHONE_ENRICH_LIMIT,
    LOG_FORMAT,
    LOG_LEVEL,
)

DETAIL_PHONE_XP = "//button[.//div[contains(text(),'Phone') or contains(text(),'الهاتف') or contains(text(),'اتصال')]] | //a[contains(@href,'tel:')]"

NBSP_REPL = {"\u00A0": " ", "\u202F": " "}

LOCATION_TO_COUNTRY_CODE = {
    "united kingdom": "GB", "uk": "GB",
    "united arab emirates": "AE", "uae": "AE",
    "saudi arabia": "SA",
    "egypt": "EG",
    "usa": "US", "united states": "US",
    "canada": "CA",
    "australia": "AU",
    "ireland": "IE",
    "france": "FR",
    "germany": "DE",
    "netherlands": "NL",
    "spain": "ES",
    "italy": "IT",
    "switzerland": "CH",
    "austria": "AT",
    "belgium": "BE",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "portugal": "PT",
    "greece": "GR",
    "poland": "PL",
    "czech republic": "CZ",
    "hungary": "HU",
    "romania": "RO",
    "qatar": "QA",
    "bahrain": "BH",
    "kuwait": "KW",
    "oman": "OM",
    "jordan": "JO",
    "turkey": "TR",
    "india": "IN",
    "pakistan": "PK",
    "bangladesh": "BD",
    "sri lanka": "LK",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "philippines": "PH",
    "vietnam": "VN",
    "japan": "JP",
    "south korea": "KR",
    "china": "CN",
    "hong kong": "HK",
    "taiwan": "TW",
    "brazil": "BR",
    "mexico": "MX",
    "colombia": "CO",
    "chile": "CL",
    "argentina": "AR",
    "peru": "PE",
    "south africa": "ZA",
    "kenya": "KE",
    "nigeria": "NG",
    "ghana": "GH",
    "morocco": "MA",
    "tunisia": "TN",
    "new zealand": "NZ",
    "serbia": "RS",
    "croatia": "HR",
    "bulgaria": "BG",
    "estonia": "EE",
    "latvia": "LV",
    "lithuania": "LT",
}


def nfc(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    for k, v in NBSP_REPL.items():
        s = s.replace(k, v)
    return s.strip()


def get_country_code_for_location(location: str) -> str:
    loc_lower = (location or "").lower()
    for key, cc in LOCATION_TO_COUNTRY_CODE.items():
        if key in loc_lower:
            return cc
    return "US"


def normalize_phone_international(raw: str, location: str) -> str:
    if not raw:
        return ""
    raw = nfc(raw).strip()
    if raw.startswith("tel:"):
        raw = raw[4:]
    raw = raw.strip()
    if not raw:
        return ""
    if HAS_PHONENUMBERS:
        country_code = get_country_code_for_location(location)
        try:
            parsed = phonenumbers.parse(raw, country_code)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
        try:
            parsed = phonenumbers.parse("+" + re.sub(r"\D", "", raw), None)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    if raw.startswith("+"):
        return "+" + digits
    return raw


def jitter(a=ENRICH_JITTER_MIN, b=ENRICH_JITTER_MAX):
    time.sleep(random.uniform(a, b))


def get_chrome_major_ci():
    try:
        out = ""
        for cmd in ("google-chrome --version", "chromium-browser --version", "chromium --version"):
            out = os.popen(cmd).read().strip()
            if out:
                break
        if not out:
            return None
        parts = out.split()
        if len(parts) < 3:
            return None
        return int(parts[2].split(".")[0])
    except Exception:
        return None


def new_driver(headless: bool):
    ua = random.choice(USER_AGENTS)
    logging.info("Launching phone-enricher browser: UA=%s | headless=%s", ua, headless)

    def build_opts():
        opts = uc.ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--user-agent=" + ua)
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--blink-settings=imagesEnabled=true")
        return opts

    driver = None
    for attempt in (1, 2):
        try:
            driver = uc.Chrome(options=build_opts(), use_subprocess=True)
            break
        except Exception as e:
            logging.warning("Browser launch attempt %d failed: %s", attempt, e)
            if attempt == 2:
                raise

    try:
        driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
        driver.set_script_timeout(SCRIPT_TIMEOUT)
    except Exception:
        pass
    return driver


def get_phone_from_page(driver, url: str, timeout: int = 8) -> str:
    if not url:
        return ""
    try:
        driver.get(url)
    except WebDriverException as e:
        logging.warning("Navigation failed for %s: %s", url, e)
        return ""
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, DETAIL_PHONE_XP))
        )
    except TimeoutException:
        return ""
    raw = el.get_attribute("href") or el.text or ""
    return raw.strip()


def read_csv(path: str):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        rows = [dict(x) for x in r]
        return r.fieldnames, rows


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def process(input_csv: str, output_csv: str, limit: Optional[int] = None, headless: bool = True):
    logging.info("Starting phone enrichment: in=%s out=%s limit=%s", input_csv, output_csv, limit)
    fieldnames, rows = read_csv(input_csv)
    logging.info("Loaded %d rows from input", len(rows))

    if "phone" not in fieldnames:
        fieldnames = list(fieldnames) + ["phone"]
    if "phone_e164" not in fieldnames:
        fieldnames = list(fieldnames) + ["phone_e164"]

    missing_phone_rows = [
        (idx, row) for idx, row in enumerate(rows)
        if not (row.get("phone") or "").strip()
    ]
    logging.info("Rows missing phone: %d", len(missing_phone_rows))

    if limit is not None:
        missing_phone_rows = missing_phone_rows[:limit]
        logging.info("Processing up to %d rows (limit applied)", limit)

    driver = new_driver(headless=headless)
    updated = 0

    try:
        for batch_idx, (row_idx, row) in enumerate(missing_phone_rows):
            if PHONE_RESTART_EVERY and batch_idx > 0 and batch_idx % PHONE_RESTART_EVERY == 0:
                logging.info("Restarting browser after %d enriched rows", batch_idx)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = new_driver(headless=headless)

            url = (row.get("profile_url") or "").strip()
            if not url:
                continue

            location = (row.get("query_location") or "").strip()
            raw_phone = get_phone_from_page(driver, url)
            jitter()

            if not raw_phone:
                continue

            normalized = normalize_phone_international(raw_phone, location)
            rows[row_idx]["phone"] = normalized
            rows[row_idx]["phone_e164"] = normalized
            updated += 1

            if updated % 20 == 0:
                logging.info("Progress: enriched=%d / processed=%d", updated, batch_idx + 1)
                write_csv(output_csv, fieldnames, rows)

        write_csv(output_csv, fieldnames, rows)
        logging.info("Phone enrichment done. Total rows updated: %d", updated)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--limit", type=int, default=PHONE_ENRICH_LIMIT)
    ap.add_argument("--no-headless", action="store_true")
    ap.add_argument("--log", dest="log", default=LOG_LEVEL)
    args = ap.parse_args()

    level = getattr(logging, args.log.upper(), getattr(logging, LOG_LEVEL, logging.INFO))
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler("phone_enricher.log", encoding="utf-8"),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )
    process(args.inp, args.out, limit=args.limit, headless=not args.no_headless)


if __name__ == "__main__":
    main()
